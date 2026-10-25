/*
 * HWND-backed local CoreWindow and UI-thread dispatcher.
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#include <stdlib.h>
#include <stdint.h>
#include "private.h"
#include "winuser.h"
#include "wine/debug.h"

WINE_DEFAULT_DEBUG_CHANNEL(pkgwindow);
#define DISPATCH_MESSAGE (WM_APP + 75)

struct dispatched_action
{
    IAsyncAction IAsyncAction_iface;
    IAsyncInfo IAsyncInfo_iface;
    LONG refs;
    UINT32 id;
    SRWLOCK lock;
    AsyncStatus status;
    HRESULT error;
    BOOL closed, completion_set;
    IAsyncActionCompletedHandler *completion;
    IDispatchedHandler *callback;
    CoreDispatcherPriority priority;
};
static HRESULT WINAPI action_query(IAsyncAction *iface, REFIID iid, void **out)
{
    struct dispatched_action *action = CONTAINING_RECORD(iface, struct dispatched_action, IAsyncAction_iface);
    if (!out) return E_POINTER;
    *out = NULL;
    if (IsEqualGUID(iid, &IID_IUnknown) || IsEqualGUID(iid, &IID_IInspectable)
        || IsEqualGUID(iid, &IID_IAgileObject) || IsEqualGUID(iid, &IID_IAsyncAction))
        *out = iface;
    else if (IsEqualGUID(iid, &IID_IAsyncInfo)) *out = &action->IAsyncInfo_iface;
    else { TRACE("missing-iid=%s result=80004002\n", debugstr_guid(iid)); return E_NOINTERFACE; }
    InterlockedIncrement(&action->refs);
    return S_OK;
}
static ULONG WINAPI action_addref(IAsyncAction *iface)
{
    return InterlockedIncrement(&CONTAINING_RECORD(iface, struct dispatched_action, IAsyncAction_iface)->refs);
}
static ULONG WINAPI action_release(IAsyncAction *iface)
{
    struct dispatched_action *action = CONTAINING_RECORD(iface, struct dispatched_action, IAsyncAction_iface);
    ULONG refs = InterlockedDecrement(&action->refs);
    if (!refs)
    {
        if (action->completion) IAsyncActionCompletedHandler_Release(action->completion);
        IDispatchedHandler_Release(action->callback);
        free(action);
    }
    return refs;
}
static HRESULT WINAPI action_iids(IAsyncAction *iface, ULONG *count, IID **out)
{
    if (!count || !out) return E_POINTER;
    *count = 0;
    *out = CoTaskMemAlloc(2 * sizeof(IID));
    if (!*out) return E_OUTOFMEMORY;
    (*out)[0] = IID_IAsyncAction;
    (*out)[1] = IID_IAsyncInfo;
    *count = 2;
    return S_OK;
}
static HRESULT WINAPI action_name(IAsyncAction *iface, HSTRING *out)
{ return out ? WindowsCreateString(L"Windows.Foundation.IAsyncAction", 31, out) : E_POINTER; }
static HRESULT WINAPI action_trust(IAsyncAction *iface, TrustLevel *out)
{ if (!out) return E_POINTER; *out = BaseTrust; return S_OK; }
static HRESULT WINAPI action_completed(IAsyncAction *iface, IAsyncActionCompletedHandler *handler)
{
    struct dispatched_action *action = CONTAINING_RECORD(iface, struct dispatched_action, IAsyncAction_iface);
    AsyncStatus status;
    HRESULT hr = S_OK;
    AcquireSRWLockExclusive(&action->lock);
    status = action->status;
    if (action->closed) hr = RO_E_CLOSED;
    else if (action->completion_set) hr = E_ILLEGAL_DELEGATE_ASSIGNMENT;
    else
    {
        action->completion_set = TRUE;
        action->completion = handler;
        if (handler) IAsyncActionCompletedHandler_AddRef(handler);
    }
    ReleaseSRWLockExclusive(&action->lock);
    if (SUCCEEDED(hr) && handler && status != Started)
        hr = IAsyncActionCompletedHandler_Invoke(handler, iface, status);
    return hr;
}
static HRESULT WINAPI action_get_completed(IAsyncAction *iface, IAsyncActionCompletedHandler **out)
{
    struct dispatched_action *action = CONTAINING_RECORD(iface, struct dispatched_action, IAsyncAction_iface);
    HRESULT hr = S_OK;
    if (!out) return E_POINTER;
    *out = NULL;
    AcquireSRWLockShared(&action->lock);
    if (action->closed) hr = RO_E_CLOSED;
    else if ((*out = action->completion)) IAsyncActionCompletedHandler_AddRef(*out);
    ReleaseSRWLockShared(&action->lock);
    return hr;
}
static HRESULT WINAPI action_results(IAsyncAction *iface)
{
    struct dispatched_action *action = CONTAINING_RECORD(iface, struct dispatched_action, IAsyncAction_iface);
    HRESULT hr;
    AcquireSRWLockShared(&action->lock);
    hr = action->closed ? RO_E_CLOSED : action->status == Started ? E_ILLEGAL_METHOD_CALL :
         action->status == Canceled ? HRESULT_FROM_WIN32(ERROR_CANCELLED) : action->error;
    ReleaseSRWLockShared(&action->lock);
    return hr;
}
static const IAsyncActionVtbl action_vtable = {
    action_query, action_addref, action_release, action_iids, action_name, action_trust,
    action_completed, action_get_completed, action_results,
};
DEFINE_IINSPECTABLE(info, IAsyncInfo, struct dispatched_action, IAsyncAction_iface)
static HRESULT WINAPI info_id(IAsyncInfo *iface, UINT32 *out)
{
    struct dispatched_action *action = impl_from_IAsyncInfo(iface);
    HRESULT hr = S_OK;
    if (!out) return E_POINTER;
    AcquireSRWLockShared(&action->lock);
    if (action->closed) hr = RO_E_CLOSED;
    else *out = action->id;
    ReleaseSRWLockShared(&action->lock);
    return hr;
}
static HRESULT WINAPI info_status(IAsyncInfo *iface, AsyncStatus *out)
{
    struct dispatched_action *action = impl_from_IAsyncInfo(iface);
    HRESULT hr = S_OK;
    if (!out) return E_POINTER;
    AcquireSRWLockShared(&action->lock);
    if (action->closed) hr = RO_E_CLOSED;
    else *out = action->status;
    ReleaseSRWLockShared(&action->lock);
    return hr;
}
static HRESULT WINAPI info_error(IAsyncInfo *iface, HRESULT *out)
{
    struct dispatched_action *action = impl_from_IAsyncInfo(iface);
    HRESULT hr = S_OK;
    if (!out) return E_POINTER;
    AcquireSRWLockShared(&action->lock);
    if (action->closed) hr = RO_E_CLOSED;
    else *out = action->error;
    ReleaseSRWLockShared(&action->lock);
    return hr;
}
static void action_finish(struct dispatched_action *action, HRESULT result, BOOL cancel)
{
    IAsyncActionCompletedHandler *completion = NULL;
    AsyncStatus status;
    AcquireSRWLockExclusive(&action->lock);
    if (action->status == Started)
    {
        action->error = cancel ? HRESULT_FROM_WIN32(ERROR_CANCELLED) : result;
        action->status = cancel ? Canceled : FAILED(result) ? Error : Completed;
        completion = action->completion;
        if (completion) IAsyncActionCompletedHandler_AddRef(completion);
    }
    status = action->status;
    ReleaseSRWLockExclusive(&action->lock);
    if (completion)
    {
        HRESULT hr = IAsyncActionCompletedHandler_Invoke(completion, &action->IAsyncAction_iface, status);
        if (FAILED(hr)) TRACE("completion result=%08lx\n", hr);
        IAsyncActionCompletedHandler_Release(completion);
    }
}
static HRESULT WINAPI info_cancel(IAsyncInfo *iface)
{
    struct dispatched_action *action = impl_from_IAsyncInfo(iface);
    BOOL closed;
    AcquireSRWLockShared(&action->lock);
    closed = action->closed;
    ReleaseSRWLockShared(&action->lock);
    if (closed) return RO_E_CLOSED;
    action_finish(action, S_OK, TRUE);
    return S_OK;
}
static HRESULT WINAPI info_close(IAsyncInfo *iface)
{
    struct dispatched_action *action = impl_from_IAsyncInfo(iface);
    HRESULT hr = S_OK;
    AcquireSRWLockExclusive(&action->lock);
    if (action->status == Started) hr = E_ILLEGAL_METHOD_CALL;
    else action->closed = TRUE;
    ReleaseSRWLockExclusive(&action->lock);
    return hr;
}
static const IAsyncInfoVtbl info_vtable = {
    info_QueryInterface, info_AddRef, info_Release, info_GetIids, info_GetRuntimeClassName, info_GetTrustLevel,
    info_id, info_status, info_error, info_cancel, info_close,
};

typedef __FITypedEventHandler_2_Windows__CUI__CCore__CCoreWindow_Windows__CUI__CCore__CWindowActivatedEventArgs window_activated_handler;
typedef __FITypedEventHandler_2_Windows__CUI__CCore__CCoreWindow_Windows__CUI__CCore__CWindowSizeChangedEventArgs window_size_handler;
struct host_window
{
    ICoreWindow ICoreWindow_iface;
    ICoreDispatcher ICoreDispatcher_iface;
    LONG refs;
    HWND hwnd;
    DWORD thread;
    BOOL quit;
    SRWLOCK lock;
    INT64 token;
    struct { INT64 token; IUnknown *handler; unsigned int kind; } events[32];
    struct dispatched_action *queue[64];
    unsigned int queued;
};
static INIT_ONCE tls_once = INIT_ONCE_STATIC_INIT;
static DWORD window_tls = TLS_OUT_OF_INDEXES;
static BOOL CALLBACK initialize_tls(INIT_ONCE *once, void *param, void **context)
{ return (window_tls = TlsAlloc()) != TLS_OUT_OF_INDEXES; }
static HRESULT missing(const char *method)
{ TRACE("missing-method=%s result=80004001\n", method); return E_NOTIMPL; }
static HRESULT WINAPI window_query(ICoreWindow *iface, REFIID iid, void **out)
{
    struct host_window *window = CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface);
    if (!out) return E_POINTER;
    *out = NULL;
    if (IsEqualGUID(iid, &IID_IUnknown) || IsEqualGUID(iid, &IID_IInspectable)
        || IsEqualGUID(iid, &IID_ICoreWindow)) *out = iface;
    else if (IsEqualGUID(iid, &IID_ICoreDispatcher)) *out = &window->ICoreDispatcher_iface;
    else { TRACE("missing-iid=%s result=80004002\n", debugstr_guid(iid)); return E_NOINTERFACE; }
    InterlockedIncrement(&window->refs);
    return S_OK;
}
static ULONG WINAPI window_addref(ICoreWindow *iface)
{ return InterlockedIncrement(&CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface)->refs); }
static ULONG WINAPI window_release(ICoreWindow *iface)
{
    struct host_window *window = CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface);
    ULONG refs = InterlockedDecrement(&window->refs);
    if (!refs) free(window);
    return refs;
}
static HRESULT WINAPI window_iids(ICoreWindow *iface, ULONG *count, IID **out)
{
    if (!count || !out) return E_POINTER;
    *count = 0;
    *out = CoTaskMemAlloc(2 * sizeof(IID));
    if (!*out) return E_OUTOFMEMORY;
    (*out)[0] = IID_ICoreWindow; (*out)[1] = IID_ICoreDispatcher; *count = 2;
    return S_OK;
}
static HRESULT WINAPI window_name(ICoreWindow *iface, HSTRING *out)
{ return out ? WindowsCreateString(L"Windows.UI.Core.CoreWindow", 26, out) : E_POINTER; }
static HRESULT WINAPI window_trust(ICoreWindow *iface, TrustLevel *out)
{ if (!out) return E_POINTER; *out = BaseTrust; return S_OK; }
static HRESULT WINAPI window_automation(ICoreWindow *iface, IInspectable **out)
{ if (!out) return E_POINTER; *out = NULL; return missing("AutomationHostProvider"); }
static HRESULT WINAPI window_bounds(ICoreWindow *iface, Rect *out)
{
    struct host_window *window = CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface);
    RECT rect;
    POINT origin = {0};
    UINT dpi;
    float scale;
    if (!out) return E_POINTER;
    if (!GetClientRect(window->hwnd, &rect) || !ClientToScreen(window->hwnd, &origin))
        return HRESULT_FROM_WIN32(GetLastError());
    dpi = GetDpiForWindow(window->hwnd);
    if (!dpi) return HRESULT_FROM_WIN32(GetLastError());
    scale = 96.0f / dpi;
    out->X = origin.x * scale; out->Y = origin.y * scale;
    out->Width = rect.right * scale; out->Height = rect.bottom * scale;
    return S_OK;
}
static HRESULT WINAPI window_properties(ICoreWindow *iface,
    __x_ABI_CWindows_CFoundation_CCollections_CIPropertySet **out)
{ if (!out) return E_POINTER; *out = NULL; return missing("CustomProperties"); }
static HRESULT WINAPI window_dispatcher(ICoreWindow *iface, ICoreDispatcher **out)
{
    struct host_window *window = CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface);
    if (!out) return E_POINTER;
    *out = &window->ICoreDispatcher_iface; ICoreWindow_AddRef(iface); return S_OK;
}
static HRESULT WINAPI window_flow(ICoreWindow *iface, CoreWindowFlowDirection *out)
{ if (!out) return E_POINTER; *out = CoreWindowFlowDirection_LeftToRight; return S_OK; }
static HRESULT WINAPI window_put_flow(ICoreWindow *iface, CoreWindowFlowDirection value)
{ return missing("FlowDirection"); }
static HRESULT WINAPI window_input(ICoreWindow *iface, boolean *out)
{
    struct host_window *window = CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface);
    if (!out) return E_POINTER;
    *out = IsWindowEnabled(window->hwnd); return S_OK;
}
static HRESULT WINAPI window_put_input(ICoreWindow *iface, boolean value)
{
    struct host_window *window = CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface);
    if (window->thread != GetCurrentThreadId()) return RPC_E_WRONG_THREAD;
    if (!IsWindow(window->hwnd)) return RO_E_CLOSED;
    EnableWindow(window->hwnd, value); return S_OK;
}
static HRESULT WINAPI window_cursor(ICoreWindow *iface, ICoreCursor **out)
{ if (!out) return E_POINTER; *out = NULL; return missing("PointerCursor"); }
static HRESULT WINAPI window_put_cursor(ICoreWindow *iface, ICoreCursor *value)
{ return missing("PutPointerCursor"); }
static HRESULT WINAPI window_pointer(ICoreWindow *iface, Point *out)
{
    POINT point;
    if (!out) return E_POINTER;
    if (!GetCursorPos(&point)) return HRESULT_FROM_WIN32(GetLastError());
    out->X = point.x; out->Y = point.y; return S_OK;
}
static HRESULT WINAPI window_visible(ICoreWindow *iface, boolean *out)
{
    struct host_window *window = CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface);
    if (!out) return E_POINTER;
    *out = IsWindowVisible(window->hwnd); return S_OK;
}
static HRESULT WINAPI window_activate(ICoreWindow *iface)
{
    struct host_window *window = CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface);
    if (window->thread != GetCurrentThreadId()) return RPC_E_WRONG_THREAD;
    if (!IsWindow(window->hwnd)) return RO_E_CLOSED;
    ShowWindow(window->hwnd, SW_SHOW);
    if (!IsWindow(window->hwnd)) return RO_E_CLOSED;
    SetActiveWindow(window->hwnd);
    TRACE("window category=package-view class=CalimochoCoreWindow visible=1\n");
    return S_OK;
}
static HRESULT WINAPI window_close(ICoreWindow *iface)
{
    struct host_window *window = CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface);
    if (window->thread != GetCurrentThreadId()) return RPC_E_WRONG_THREAD;
    if (!window->hwnd) return S_OK;
    return DestroyWindow(window->hwnd) ? S_OK : HRESULT_FROM_WIN32(GetLastError());
}
static HRESULT WINAPI window_async_key(ICoreWindow *iface, __x_ABI_CWindows_CSystem_CVirtualKey key, CoreVirtualKeyStates *out)
{ if (!out) return E_POINTER; return missing("GetAsyncKeyState"); }
static HRESULT WINAPI window_key(ICoreWindow *iface, __x_ABI_CWindows_CSystem_CVirtualKey key, CoreVirtualKeyStates *out)
{ if (!out) return E_POINTER; return missing("GetKeyState"); }
static HRESULT WINAPI window_release_capture(ICoreWindow *iface) { return missing("ReleasePointerCapture"); }
static HRESULT WINAPI window_capture(ICoreWindow *iface) { return missing("SetPointerCapture"); }

static HRESULT event_add(struct host_window *window, unsigned int kind, IUnknown *handler, EventRegistrationToken *token)
{
    unsigned int i;
    if (!handler || !token) return E_POINTER;
    token->value = 0;
    if (window->thread != GetCurrentThreadId()) return RPC_E_WRONG_THREAD;
    for (i = 0; i < ARRAY_SIZE(window->events); ++i) if (!window->events[i].handler) break;
    if (i == ARRAY_SIZE(window->events) || window->token == INT64_MAX) return E_OUTOFMEMORY;
    window->events[i].handler = handler; IUnknown_AddRef(handler);
    window->events[i].kind = kind; token->value = window->events[i].token = ++window->token;
    return S_OK;
}
static HRESULT event_remove(struct host_window *window, unsigned int kind, EventRegistrationToken token)
{
    unsigned int i;
    if (window->thread != GetCurrentThreadId()) return RPC_E_WRONG_THREAD;
    for (i = 0; i < ARRAY_SIZE(window->events); ++i)
        if (window->events[i].handler && window->events[i].kind == kind && window->events[i].token == token.value)
        {
            IUnknown *handler = window->events[i].handler;
            window->events[i].handler = NULL; IUnknown_Release(handler); return S_OK;
        }
    return E_INVALIDARG;
}
#define EVENT(name, type, kind) \
static HRESULT WINAPI window_add_##name(ICoreWindow *iface, \
__FITypedEventHandler_2_Windows__CUI__CCore__CCoreWindow_Windows__CUI__CCore__C##type *handler, EventRegistrationToken *token) \
{ return event_add(CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface), kind, (IUnknown *)handler, token); } \
static HRESULT WINAPI window_remove_##name(ICoreWindow *iface, EventRegistrationToken token) \
{ return event_remove(CONTAINING_RECORD(iface, struct host_window, ICoreWindow_iface), kind, token); }
#define UNSUPPORTED_EVENT(name, type) \
static HRESULT WINAPI window_add_##name(ICoreWindow *iface, \
__FITypedEventHandler_2_Windows__CUI__CCore__CCoreWindow_Windows__CUI__CCore__C##type *handler, EventRegistrationToken *token) \
{ if (token) token->value = 0; return missing(#name); } \
static HRESULT WINAPI window_remove_##name(ICoreWindow *iface, EventRegistrationToken token) { return missing("Remove" #name); }
EVENT(Activated, WindowActivatedEventArgs, 1)
EVENT(SizeChanged, WindowSizeChangedEventArgs, 2)
UNSUPPORTED_EVENT(AutomationProviderRequested, AutomationProviderRequestedEventArgs)
UNSUPPORTED_EVENT(CharacterReceived, CharacterReceivedEventArgs)
UNSUPPORTED_EVENT(Closed, CoreWindowEventArgs)
UNSUPPORTED_EVENT(InputEnabled, InputEnabledEventArgs)
UNSUPPORTED_EVENT(KeyDown, KeyEventArgs)
UNSUPPORTED_EVENT(KeyUp, KeyEventArgs)
UNSUPPORTED_EVENT(PointerCaptureLost, PointerEventArgs)
UNSUPPORTED_EVENT(PointerEntered, PointerEventArgs)
UNSUPPORTED_EVENT(PointerExited, PointerEventArgs)
UNSUPPORTED_EVENT(PointerMoved, PointerEventArgs)
UNSUPPORTED_EVENT(PointerPressed, PointerEventArgs)
UNSUPPORTED_EVENT(PointerReleased, PointerEventArgs)
UNSUPPORTED_EVENT(TouchHitTesting, TouchHitTestingEventArgs)
UNSUPPORTED_EVENT(PointerWheelChanged, PointerEventArgs)
UNSUPPORTED_EVENT(VisibilityChanged, VisibilityChangedEventArgs)
#define EVENT_SLOTS(name) window_add_##name, window_remove_##name
static const ICoreWindowVtbl window_vtable = {
    window_query, window_addref, window_release, window_iids, window_name, window_trust,
    window_automation, window_bounds, window_properties, window_dispatcher,
    window_flow, window_put_flow, window_input, window_put_input,
    window_cursor, window_put_cursor, window_pointer, window_visible, window_activate, window_close,
    window_async_key, window_key, window_release_capture, window_capture,
    EVENT_SLOTS(Activated), EVENT_SLOTS(AutomationProviderRequested), EVENT_SLOTS(CharacterReceived),
    EVENT_SLOTS(Closed), EVENT_SLOTS(InputEnabled), EVENT_SLOTS(KeyDown), EVENT_SLOTS(KeyUp),
    EVENT_SLOTS(PointerCaptureLost), EVENT_SLOTS(PointerEntered), EVENT_SLOTS(PointerExited),
    EVENT_SLOTS(PointerMoved), EVENT_SLOTS(PointerPressed), EVENT_SLOTS(PointerReleased),
    EVENT_SLOTS(TouchHitTesting), EVENT_SLOTS(PointerWheelChanged), EVENT_SLOTS(SizeChanged),
    EVENT_SLOTS(VisibilityChanged),
};
DEFINE_IINSPECTABLE(dispatcher, ICoreDispatcher, struct host_window, ICoreWindow_iface)
static HRESULT WINAPI dispatcher_access(ICoreDispatcher *iface, boolean *out)
{
    if (!out) return E_POINTER;
    *out = impl_from_ICoreDispatcher(iface)->thread == GetCurrentThreadId(); return S_OK;
}
static HRESULT WINAPI dispatcher_process(ICoreDispatcher *iface, CoreProcessEventsOption option)
{
    struct host_window *window = impl_from_ICoreDispatcher(iface);
    MSG message;
    BOOL wait;
    if (window->thread != GetCurrentThreadId()) return RPC_E_WRONG_THREAD;
    if (option < CoreProcessEventsOption_ProcessOneAndAllPending || option > CoreProcessEventsOption_ProcessUntilQuit)
        return E_INVALIDARG;
    wait = option != CoreProcessEventsOption_ProcessAllIfPresent;
    do
    {
        BOOL found = PeekMessageW(&message, NULL, 0, 0, PM_REMOVE);
        if (!found && wait && !window->quit)
        {
            int result = GetMessageW(&message, NULL, 0, 0);
            if (result < 0) return HRESULT_FROM_WIN32(GetLastError());
            if (!result) { window->quit = TRUE; break; }
            found = TRUE;
        }
        if (!found || window->quit) break;
        if (message.message == WM_QUIT) { window->quit = TRUE; break; }
        TranslateMessage(&message); DispatchMessageW(&message);
        if (option == CoreProcessEventsOption_ProcessOneIfPresent) break;
        wait = option == CoreProcessEventsOption_ProcessUntilQuit;
    } while (!window->quit);
    return S_OK;
}
static HRESULT WINAPI dispatcher_async(ICoreDispatcher *iface, CoreDispatcherPriority priority,
                                       IDispatchedHandler *callback, IAsyncAction **out)
{
    struct host_window *window = impl_from_ICoreDispatcher(iface);
    struct dispatched_action *action;
    static LONG64 next_id;
    LONG64 id;
    HRESULT hr = S_OK;
    if (!out) return E_POINTER;
    *out = NULL;
    if (!callback || priority < CoreDispatcherPriority_Idle || priority > CoreDispatcherPriority_High) return E_INVALIDARG;
    id = InterlockedIncrement64(&next_id);
    if (id <= 0 || id > UINT32_MAX) return E_OUTOFMEMORY;
    if (!(action = calloc(1, sizeof(*action)))) return E_OUTOFMEMORY;
    action->IAsyncAction_iface.lpVtbl = &action_vtable;
    action->IAsyncInfo_iface.lpVtbl = &info_vtable;
    action->refs = 1; action->callback = callback; action->priority = priority; action->status = Started;
    action->id = id;
    IDispatchedHandler_AddRef(callback);
    AcquireSRWLockExclusive(&window->lock);
    if (!window->hwnd || window->quit) hr = RO_E_CLOSED;
    else if (window->queued == ARRAY_SIZE(window->queue)) hr = E_OUTOFMEMORY;
    else if (!PostMessageW(window->hwnd, DISPATCH_MESSAGE, 0, 0)) hr = HRESULT_FROM_WIN32(GetLastError());
    else
    {
        window->queue[window->queued++] = action;
        IAsyncAction_AddRef(&action->IAsyncAction_iface);
    }
    ReleaseSRWLockExclusive(&window->lock);
    if (FAILED(hr)) IAsyncAction_Release(&action->IAsyncAction_iface);
    else *out = &action->IAsyncAction_iface;
    return hr;
}
static HRESULT WINAPI dispatcher_idle(ICoreDispatcher *iface, IIdleDispatchedHandler *callback, IAsyncAction **out)
{ if (!out) return E_POINTER; *out = NULL; return missing("RunIdleAsync"); }
static const ICoreDispatcherVtbl dispatcher_vtable = {
    dispatcher_QueryInterface, dispatcher_AddRef, dispatcher_Release,
    dispatcher_GetIids, dispatcher_GetRuntimeClassName, dispatcher_GetTrustLevel,
    dispatcher_access, dispatcher_process, dispatcher_async, dispatcher_idle,
};

struct window_event
{
    ICoreWindowEventArgs ICoreWindowEventArgs_iface;
    IWindowActivatedEventArgs IWindowActivatedEventArgs_iface;
    IWindowSizeChangedEventArgs IWindowSizeChangedEventArgs_iface;
    LONG refs;
    unsigned int kind;
    boolean handled;
    CoreWindowActivationState activation;
    Size size;
};
static HRESULT WINAPI event_query(ICoreWindowEventArgs *iface, REFIID iid, void **out)
{
    struct window_event *event = CONTAINING_RECORD(iface, struct window_event, ICoreWindowEventArgs_iface);
    if (!out) return E_POINTER;
    *out = NULL;
    if (IsEqualGUID(iid, &IID_IUnknown) || IsEqualGUID(iid, &IID_IInspectable)
        || IsEqualGUID(iid, &IID_ICoreWindowEventArgs)) *out = iface;
    else if (event->kind == 1 && IsEqualGUID(iid, &IID_IWindowActivatedEventArgs))
        *out = &event->IWindowActivatedEventArgs_iface;
    else if (event->kind == 2 && IsEqualGUID(iid, &IID_IWindowSizeChangedEventArgs))
        *out = &event->IWindowSizeChangedEventArgs_iface;
    else { TRACE("missing-iid=%s result=80004002\n", debugstr_guid(iid)); return E_NOINTERFACE; }
    InterlockedIncrement(&event->refs);
    return S_OK;
}
static ULONG WINAPI event_addref(ICoreWindowEventArgs *iface)
{ return InterlockedIncrement(&CONTAINING_RECORD(iface, struct window_event, ICoreWindowEventArgs_iface)->refs); }
static ULONG WINAPI event_release(ICoreWindowEventArgs *iface)
{
    struct window_event *event = CONTAINING_RECORD(iface, struct window_event, ICoreWindowEventArgs_iface);
    ULONG refs = InterlockedDecrement(&event->refs);
    if (!refs) free(event);
    return refs;
}
static HRESULT WINAPI event_iids(ICoreWindowEventArgs *iface, ULONG *count, IID **out)
{
    struct window_event *event = CONTAINING_RECORD(iface, struct window_event, ICoreWindowEventArgs_iface);
    if (!count || !out) return E_POINTER;
    *count = 0;
    *out = CoTaskMemAlloc(2 * sizeof(IID));
    if (!*out) return E_OUTOFMEMORY;
    (*out)[0] = IID_ICoreWindowEventArgs;
    (*out)[1] = event->kind == 1 ? IID_IWindowActivatedEventArgs : IID_IWindowSizeChangedEventArgs;
    *count = 2; return S_OK;
}
static HRESULT WINAPI event_name(ICoreWindowEventArgs *iface, HSTRING *out)
{
    struct window_event *event = CONTAINING_RECORD(iface, struct window_event, ICoreWindowEventArgs_iface);
    const WCHAR *name = event->kind == 1 ? L"Windows.UI.Core.WindowActivatedEventArgs" :
                                          L"Windows.UI.Core.WindowSizeChangedEventArgs";
    return out ? WindowsCreateString(name, lstrlenW(name), out) : E_POINTER;
}
static HRESULT WINAPI event_trust(ICoreWindowEventArgs *iface, TrustLevel *out)
{ if (!out) return E_POINTER; *out = BaseTrust; return S_OK; }
static HRESULT WINAPI event_handled(ICoreWindowEventArgs *iface, boolean *out)
{
    if (!out) return E_POINTER;
    *out = CONTAINING_RECORD(iface, struct window_event, ICoreWindowEventArgs_iface)->handled; return S_OK;
}
static HRESULT WINAPI event_put_handled(ICoreWindowEventArgs *iface, boolean value)
{
    CONTAINING_RECORD(iface, struct window_event, ICoreWindowEventArgs_iface)->handled = value; return S_OK;
}
static const ICoreWindowEventArgsVtbl event_vtable = {
    event_query, event_addref, event_release, event_iids, event_name, event_trust, event_handled, event_put_handled,
};
DEFINE_IINSPECTABLE(activated_event, IWindowActivatedEventArgs, struct window_event, ICoreWindowEventArgs_iface)
DEFINE_IINSPECTABLE(size_event, IWindowSizeChangedEventArgs, struct window_event, ICoreWindowEventArgs_iface)
static HRESULT WINAPI activated_event_state(IWindowActivatedEventArgs *iface, CoreWindowActivationState *out)
{ if (!out) return E_POINTER; *out = impl_from_IWindowActivatedEventArgs(iface)->activation; return S_OK; }
static HRESULT WINAPI size_event_size(IWindowSizeChangedEventArgs *iface, Size *out)
{ if (!out) return E_POINTER; *out = impl_from_IWindowSizeChangedEventArgs(iface)->size; return S_OK; }
static const IWindowActivatedEventArgsVtbl activated_event_vtable = {
    activated_event_QueryInterface, activated_event_AddRef, activated_event_Release,
    activated_event_GetIids, activated_event_GetRuntimeClassName, activated_event_GetTrustLevel, activated_event_state,
};
static const IWindowSizeChangedEventArgsVtbl size_event_vtable = {
    size_event_QueryInterface, size_event_AddRef, size_event_Release,
    size_event_GetIids, size_event_GetRuntimeClassName, size_event_GetTrustLevel, size_event_size,
};
static void emit_window_event(struct host_window *window, unsigned int kind, WPARAM value)
{
    IUnknown *handlers[32];
    struct window_event *event;
    unsigned int i, count = 0;
    RECT rect;
    if (!(event = calloc(1, sizeof(*event))))
    { ERR("event allocation result=8007000e\n"); return; }
    event->ICoreWindowEventArgs_iface.lpVtbl = &event_vtable;
    event->IWindowActivatedEventArgs_iface.lpVtbl = &activated_event_vtable;
    event->IWindowSizeChangedEventArgs_iface.lpVtbl = &size_event_vtable;
    event->refs = 1; event->kind = kind;
    event->activation = LOWORD(value) == WA_INACTIVE ? CoreWindowActivationState_Deactivated :
                        LOWORD(value) == WA_CLICKACTIVE ? CoreWindowActivationState_PointerActivated :
                                                        CoreWindowActivationState_CodeActivated;
    if (!GetClientRect(window->hwnd, &rect))
    {
        ERR("event bounds error=%lu\n", GetLastError());
        ICoreWindowEventArgs_Release(&event->ICoreWindowEventArgs_iface);
        return;
    }
    {
        UINT dpi = GetDpiForWindow(window->hwnd);
        if (!dpi)
        {
            ERR("event dpi error=%lu\n", GetLastError());
            ICoreWindowEventArgs_Release(&event->ICoreWindowEventArgs_iface);
            return;
        }
        event->size.Width = rect.right * 96.0f / dpi;
        event->size.Height = rect.bottom * 96.0f / dpi;
    }
    for (i = 0; i < ARRAY_SIZE(window->events); ++i)
        if (window->events[i].handler && window->events[i].kind == kind)
        {
            handlers[count] = window->events[i].handler;
            IUnknown_AddRef(handlers[count]);
            ++count;
        }
    for (i = 0; i < count; ++i)
    {
        HRESULT hr;
        if (kind == 1)
        {
            window_activated_handler *handler = (window_activated_handler *)handlers[i];
            hr = handler->lpVtbl->Invoke(handler, &window->ICoreWindow_iface, &event->IWindowActivatedEventArgs_iface);
        }
        else
        {
            window_size_handler *handler = (window_size_handler *)handlers[i];
            hr = handler->lpVtbl->Invoke(handler, &window->ICoreWindow_iface, &event->IWindowSizeChangedEventArgs_iface);
        }
        if (FAILED(hr)) TRACE("event kind=%u result=%08lx\n", kind, hr);
        IUnknown_Release(handlers[i]);
    }
    ICoreWindowEventArgs_Release(&event->ICoreWindowEventArgs_iface);
}
static void drain_action(struct host_window *window)
{
    struct dispatched_action *action = NULL;
    unsigned int i, selected = 0;
    AsyncStatus status;
    AcquireSRWLockExclusive(&window->lock);
    if (window->queued)
    {
        for (i = 1; i < window->queued; ++i)
            if (window->queue[i]->priority > window->queue[selected]->priority) selected = i;
        action = window->queue[selected];
        memmove(window->queue + selected, window->queue + selected + 1,
                (--window->queued - selected) * sizeof(window->queue[0]));
    }
    ReleaseSRWLockExclusive(&window->lock);
    if (!action) return;
    if (SUCCEEDED(info_status(&action->IAsyncInfo_iface, &status)) && status == Started)
        action_finish(action, IDispatchedHandler_Invoke(action->callback), FALSE);
    IAsyncAction_Release(&action->IAsyncAction_iface);
}
static LRESULT CALLBACK host_proc(HWND hwnd, UINT message, WPARAM wparam, LPARAM lparam)
{
    struct host_window *window = (struct host_window *)GetWindowLongPtrW(hwnd, GWLP_USERDATA);
    LRESULT result;
    if (message == WM_NCCREATE)
    {
        window = ((CREATESTRUCTW *)lparam)->lpCreateParams;
        window->hwnd = hwnd;
        SetWindowLongPtrW(hwnd, GWLP_USERDATA, (LONG_PTR)window);
        ICoreWindow_AddRef(&window->ICoreWindow_iface);
    }
    if (!window) return DefWindowProcW(hwnd, message, wparam, lparam);
    ICoreWindow_AddRef(&window->ICoreWindow_iface);
    if (message == DISPATCH_MESSAGE)
    {
        drain_action(window);
        ICoreWindow_Release(&window->ICoreWindow_iface);
        return 0;
    }
    if (message == WM_ACTIVATE) emit_window_event(window, 1, wparam);
    if (message == WM_SIZE) emit_window_event(window, 2, wparam);
    if (message == WM_CLOSE)
    {
        DestroyWindow(hwnd);
        ICoreWindow_Release(&window->ICoreWindow_iface);
        return 0;
    }
    if (message == WM_NCDESTROY)
    {
        struct dispatched_action *queue[64];
        unsigned int i, count;
        AcquireSRWLockExclusive(&window->lock);
        window->hwnd = NULL; window->quit = TRUE;
        count = window->queued; window->queued = 0;
        memcpy(queue, window->queue, count * sizeof(queue[0]));
        ReleaseSRWLockExclusive(&window->lock);
        TlsSetValue(window_tls, NULL);
        SetWindowLongPtrW(hwnd, GWLP_USERDATA, 0);
        for (i = 0; i < count; ++i)
        {
            action_finish(queue[i], S_OK, TRUE);
            IAsyncAction_Release(&queue[i]->IAsyncAction_iface);
        }
        for (i = 0; i < ARRAY_SIZE(window->events); ++i)
            if (window->events[i].handler)
            {
                IUnknown *handler = window->events[i].handler;
                window->events[i].handler = NULL;
                IUnknown_Release(handler);
            }
        TRACE("window category=package-view class=CalimochoCoreWindow destroyed=1\n");
        ICoreWindow_Release(&window->ICoreWindow_iface);
    }
    result = DefWindowProcW(hwnd, message, wparam, lparam);
    ICoreWindow_Release(&window->ICoreWindow_iface);
    return result;
}
HRESULT WINAPI __wine_create_core_window(ICoreWindow **out)
{
    static const WCHAR class_name[] = L"CalimochoCoreWindow";
    WNDCLASSW cls = {0};
    struct host_window *window;
    if (!out) return E_POINTER;
    *out = NULL;
    if (!InitOnceExecuteOnce(&tls_once, initialize_tls, NULL, NULL)) return HRESULT_FROM_WIN32(GetLastError());
    if (TlsGetValue(window_tls)) return E_ILLEGAL_METHOD_CALL;
    if (!(window = calloc(1, sizeof(*window)))) return E_OUTOFMEMORY;
    window->ICoreWindow_iface.lpVtbl = &window_vtable;
    window->ICoreDispatcher_iface.lpVtbl = &dispatcher_vtable;
    window->refs = 1; window->thread = GetCurrentThreadId();
    cls.lpfnWndProc = host_proc; cls.lpszClassName = class_name;
    cls.hCursor = LoadCursorW(NULL, (const WCHAR *)IDC_ARROW);
    if (!RegisterClassW(&cls) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
    { HRESULT hr = HRESULT_FROM_WIN32(GetLastError()); free(window); return hr; }
    if (!CreateWindowExW(0, class_name, L"Calimocho package view", WS_OVERLAPPEDWINDOW,
                         CW_USEDEFAULT, CW_USEDEFAULT, 1024, 768, NULL, NULL, NULL, window))
    { HRESULT hr = HRESULT_FROM_WIN32(GetLastError()); ICoreWindow_Release(&window->ICoreWindow_iface); return hr; }
    if (!TlsSetValue(window_tls, window))
    {
        HRESULT hr = HRESULT_FROM_WIN32(GetLastError());
        DestroyWindow(window->hwnd); ICoreWindow_Release(&window->ICoreWindow_iface); return hr;
    }
    *out = &window->ICoreWindow_iface;
    TRACE("window category=package-view class=CalimochoCoreWindow created=1 visible=0\n");
    return S_OK;
}
HRESULT WINAPI wine_get_core_window(ICoreWindow **out)
{
    struct host_window *window;
    if (!out) return E_POINTER;
    *out = NULL;
    if (!InitOnceExecuteOnce(&tls_once, initialize_tls, NULL, NULL)) return HRESULT_FROM_WIN32(GetLastError());
    window = TlsGetValue(window_tls);
    if (window)
    { *out = &window->ICoreWindow_iface; ICoreWindow_AddRef(*out); }
    return S_OK;
}
