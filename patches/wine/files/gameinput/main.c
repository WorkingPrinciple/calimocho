/*
 * Truthful no-device GameInput diagnostic implementation.
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#include <stdarg.h>
#include <stdlib.h>
#define COBJMACROS
#include "windef.h"
#include "winbase.h"
#include "initguid.h"
#include "gameinput.h"
#include "wine/debug.h"

WINE_DEFAULT_DEBUG_CHANNEL(ginput);

struct callback
{
    struct callback *next;
    GameInputCallbackToken token;
};

struct gameinput
{
    v0_IGameInput v0_iface;
    v1_IGameInput v1_iface;
    v2_IGameInput v2_iface;
    LONG refs;
    CRITICAL_SECTION lock;
    struct callback *callbacks;
    LARGE_INTEGER frequency;
};

struct dispatcher
{
    IGameInputDispatcher iface;
    LONG refs;
    HANDLE event;
};

static LONG objects;
static DECLSPEC_ALIGN(8) LONG64 next_token;

static HRESULT query_interface(struct gameinput *input, REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (!iid) return E_INVALIDARG;
    if (IsEqualGUID(iid, &IID_IUnknown) || IsEqualGUID(iid, &IID_v0_IGameInput))
        *out = &input->v0_iface;
    else if (IsEqualGUID(iid, &IID_v1_IGameInput)) *out = &input->v1_iface;
    else if (IsEqualGUID(iid, &IID_v2_IGameInput)) *out = &input->v2_iface;
    else return E_NOINTERFACE;
    InterlockedIncrement(&input->refs);
    return S_OK;
}

static ULONG release(struct gameinput *input)
{
    ULONG refs = InterlockedDecrement(&input->refs);
    if (!refs)
    {
        struct callback *entry = input->callbacks;
        while (entry)
        {
            struct callback *next = entry->next;
            free(entry);
            entry = next;
        }
        DeleteCriticalSection(&input->lock);
        free(input);
        InterlockedDecrement(&objects);
    }
    return refs;
}

static uint64_t timestamp(struct gameinput *input)
{
    LARGE_INTEGER counter;
    if (!QueryPerformanceCounter(&counter))
    {
        ERR("QueryPerformanceCounter failed, error %lu\n", GetLastError());
        return 0;
    }
    return counter.QuadPart / input->frequency.QuadPart * 1000000 +
           counter.QuadPart % input->frequency.QuadPart * 1000000 / input->frequency.QuadPart;
}

static HRESULT register_callback(struct gameinput *input, BOOL has_device, BOOL has_callback,
                                 GameInputCallbackToken *token)
{
    struct callback *entry;
    if (!token) return E_POINTER;
    *token = GAMEINPUT_INVALID_CALLBACK_TOKEN_VALUE;
    if (!has_callback) return E_INVALIDARG;
    if (has_device) return GAMEINPUT_E_DEVICE_NOT_FOUND;
    if (!(entry = malloc(sizeof(*entry)))) return E_OUTOFMEMORY;
    do entry->token = InterlockedIncrement64(&next_token);
    while (!entry->token || entry->token == GAMEINPUT_CURRENT_CALLBACK_TOKEN_VALUE);
    EnterCriticalSection(&input->lock);
    entry->next = input->callbacks;
    input->callbacks = entry;
    *token = entry->token;
    LeaveCriticalSection(&input->lock);
    return S_OK;
}

static bool unregister_callback(struct gameinput *input, GameInputCallbackToken token)
{
    struct callback **cursor, *found = NULL;
    EnterCriticalSection(&input->lock);
    for (cursor = &input->callbacks; *cursor; cursor = &(*cursor)->next)
    {
        if ((*cursor)->token != token) continue;
        found = *cursor;
        *cursor = found->next;
        break;
    }
    LeaveCriticalSection(&input->lock);
    if (!found) return false;
    free(found);
    return true;
}

static HRESULT WINAPI dispatcher_query(IGameInputDispatcher *iface, REFIID iid, void **out)
{
    struct dispatcher *dispatcher = CONTAINING_RECORD(iface, struct dispatcher, iface);
    if (!out) return E_POINTER;
    *out = NULL;
    if (!iid) return E_INVALIDARG;
    if (!IsEqualGUID(iid, &IID_IUnknown) && !IsEqualGUID(iid, &IID_IGameInputDispatcher))
        return E_NOINTERFACE;
    *out = iface;
    InterlockedIncrement(&dispatcher->refs);
    return S_OK;
}

static ULONG WINAPI dispatcher_addref(IGameInputDispatcher *iface)
{
    return InterlockedIncrement(&CONTAINING_RECORD(iface, struct dispatcher, iface)->refs);
}

static ULONG WINAPI dispatcher_release(IGameInputDispatcher *iface)
{
    struct dispatcher *dispatcher = CONTAINING_RECORD(iface, struct dispatcher, iface);
    ULONG refs = InterlockedDecrement(&dispatcher->refs);
    if (!refs)
    {
        CloseHandle(dispatcher->event);
        free(dispatcher);
        InterlockedDecrement(&objects);
    }
    return refs;
}

static bool WINAPI dispatcher_dispatch(IGameInputDispatcher *iface, uint64_t quota)
{
    return false;
}

static HRESULT WINAPI dispatcher_wait(IGameInputDispatcher *iface, HANDLE *out)
{
    struct dispatcher *dispatcher = CONTAINING_RECORD(iface, struct dispatcher, iface);
    if (!out) return E_POINTER;
    *out = NULL;
    if (!DuplicateHandle(GetCurrentProcess(), dispatcher->event, GetCurrentProcess(),
                         out, SYNCHRONIZE, FALSE, 0))
        return HRESULT_FROM_WIN32(GetLastError());
    return S_OK;
}

static const IGameInputDispatcherVtbl dispatcher_vtable = {
    dispatcher_query, dispatcher_addref, dispatcher_release, dispatcher_dispatch, dispatcher_wait,
};

static HRESULT create_dispatcher(IGameInputDispatcher **out)
{
    struct dispatcher *dispatcher;
    DWORD error;
    if (!out) return E_POINTER;
    *out = NULL;
    if (!(dispatcher = calloc(1, sizeof(*dispatcher)))) return E_OUTOFMEMORY;
    if (!(dispatcher->event = CreateEventW(NULL, TRUE, FALSE, NULL)))
    {
        error = GetLastError();
        free(dispatcher);
        return HRESULT_FROM_WIN32(error);
    }
    dispatcher->iface.lpVtbl = &dispatcher_vtable;
    dispatcher->refs = 1;
    InterlockedIncrement(&objects);
    *out = &dispatcher->iface;
    return S_OK;
}

#define DEFINE_COMMON(ver) \
static struct gameinput *impl_##ver(ver##_IGameInput *iface) \
{ return CONTAINING_RECORD(iface, struct gameinput, ver##_iface); } \
static HRESULT WINAPI ver##_query(ver##_IGameInput *iface, REFIID iid, void **out) \
{ return query_interface(impl_##ver(iface), iid, out); } \
static ULONG WINAPI ver##_addref(ver##_IGameInput *iface) \
{ return InterlockedIncrement(&impl_##ver(iface)->refs); } \
static ULONG WINAPI ver##_release(ver##_IGameInput *iface) \
{ return release(impl_##ver(iface)); } \
static uint64_t WINAPI ver##_timestamp(ver##_IGameInput *iface) \
{ return timestamp(impl_##ver(iface)); } \
static HRESULT WINAPI ver##_current(ver##_IGameInput *iface, GameInputKind kind, ver##_IGameInputDevice *device, ver##_IGameInputReading **out) \
{ if (!out) return E_POINTER; *out = NULL; return GAMEINPUT_E_READING_NOT_FOUND; } \
static HRESULT WINAPI ver##_next(ver##_IGameInput *iface, ver##_IGameInputReading *reference, GameInputKind kind, ver##_IGameInputDevice *device, ver##_IGameInputReading **out) \
{ if (!out) return E_POINTER; *out = NULL; return GAMEINPUT_E_READING_NOT_FOUND; } \
static HRESULT WINAPI ver##_previous(ver##_IGameInput *iface, ver##_IGameInputReading *reference, GameInputKind kind, ver##_IGameInputDevice *device, ver##_IGameInputReading **out) \
{ if (!out) return E_POINTER; *out = NULL; return GAMEINPUT_E_READING_NOT_FOUND; } \
static HRESULT WINAPI ver##_device_callback(ver##_IGameInput *iface, ver##_IGameInputDevice *device, GameInputKind kind, GameInputDeviceStatus filter, GameInputEnumerationKind enumeration, void *context, ver##_GameInputDeviceCallback callback, GameInputCallbackToken *token) \
{ \
    if (enumeration < GameInputNoEnumeration || enumeration > GameInputBlockingEnumeration) \
    { if (token) *token = 0; return E_INVALIDARG; } \
    return register_callback(impl_##ver(iface), device != NULL, callback != NULL, token); \
} \
static HRESULT WINAPI ver##_system_callback(ver##_IGameInput *iface, ver##_IGameInputDevice *device, GameInputSystemButtons filter, void *context, ver##_GameInputSystemButtonCallback callback, GameInputCallbackToken *token) \
{ return register_callback(impl_##ver(iface), device != NULL, callback != NULL, token); } \
static HRESULT WINAPI ver##_keyboard_callback(ver##_IGameInput *iface, ver##_IGameInputDevice *device, void *context, ver##_GameInputKeyboardLayoutCallback callback, GameInputCallbackToken *token) \
{ return register_callback(impl_##ver(iface), device != NULL, callback != NULL, token); } \
static void WINAPI ver##_stop(ver##_IGameInput *iface, GameInputCallbackToken token) \
{ /* No devices means no in-flight or future callback invocation. */ } \
static HRESULT WINAPI ver##_dispatcher(ver##_IGameInput *iface, IGameInputDispatcher **out) \
{ return create_dispatcher(out); } \
static HRESULT WINAPI ver##_find_id(ver##_IGameInput *iface, const APP_LOCAL_DEVICE_ID *id, ver##_IGameInputDevice **out) \
{ if (!out) return E_POINTER; *out = NULL; return id ? (HRESULT)GAMEINPUT_E_DEVICE_NOT_FOUND : E_INVALIDARG; } \
static HRESULT WINAPI ver##_find_string(ver##_IGameInput *iface, const WCHAR *id, ver##_IGameInputDevice **out) \
{ if (!out) return E_POINTER; *out = NULL; return id ? (HRESULT)GAMEINPUT_E_DEVICE_NOT_FOUND : E_INVALIDARG; } \
static void WINAPI ver##_focus(ver##_IGameInput *iface, GameInputFocusPolicy policy) \
{ TRACE("No devices; focus policy %#x does not capture input\n", policy); }

DEFINE_COMMON(v0)
DEFINE_COMMON(v1)
DEFINE_COMMON(v2)

static HRESULT WINAPI v0_temporal(v0_IGameInput *iface, uint64_t time, v0_IGameInputDevice *device,
                                  v0_IGameInputReading **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    return GAMEINPUT_E_READING_NOT_FOUND;
}

static HRESULT WINAPI v0_reading_callback(v0_IGameInput *iface, v0_IGameInputDevice *device, GameInputKind kind,
                                         float threshold, void *context, v0_GameInputReadingCallback callback,
                                         GameInputCallbackToken *token)
{
    return register_callback(impl_v0(iface), device != NULL, callback != NULL, token);
}

static bool WINAPI v0_unregister(v0_IGameInput *iface, GameInputCallbackToken token, uint64_t timeout)
{
    return unregister_callback(impl_v0(iface), token);
}

static HRESULT WINAPI v0_aggregate(v0_IGameInput *iface, GameInputKind kind, v0_IGameInputDevice **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    return GAMEINPUT_E_DEVICE_NOT_FOUND;
}

static HRESULT WINAPI v0_find_object(v0_IGameInput *iface, IUnknown *object, v0_IGameInputDevice **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    return object ? (HRESULT)GAMEINPUT_E_DEVICE_NOT_FOUND : E_INVALIDARG;
}

static HRESULT WINAPI v0_find_handle(v0_IGameInput *iface, HANDLE handle, v0_IGameInputDevice **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    return handle ? (HRESULT)GAMEINPUT_E_DEVICE_NOT_FOUND : E_INVALIDARG;
}

static HRESULT WINAPI v0_enable_oem(v0_IGameInput *iface, uint16_t vid, uint16_t pid, uint8_t index, uint8_t collection)
{
    WARN("OEM device support is unavailable in this no-device implementation\n");
    return E_NOTIMPL;
}

#define DEFINE_NEW_CALLBACKS(ver) \
static HRESULT WINAPI ver##_reading_callback(ver##_IGameInput *iface, ver##_IGameInputDevice *device, GameInputKind kind, void *context, ver##_GameInputReadingCallback callback, GameInputCallbackToken *token) \
{ return register_callback(impl_##ver(iface), device != NULL, callback != NULL, token); } \
static bool WINAPI ver##_unregister(ver##_IGameInput *iface, GameInputCallbackToken token) \
{ return unregister_callback(impl_##ver(iface), token); }
DEFINE_NEW_CALLBACKS(v1)
DEFINE_NEW_CALLBACKS(v2)

static const v0_IGameInputVtbl v0_vtable = {
    v0_query, v0_addref, v0_release, v0_timestamp, v0_current, v0_next, v0_previous, v0_temporal,
    v0_reading_callback, v0_device_callback, v0_system_callback, v0_keyboard_callback, v0_stop,
    v0_unregister, v0_dispatcher, v0_aggregate, v0_find_id, v0_find_object, v0_find_handle,
    v0_find_string, v0_enable_oem, v0_focus,
};

#define NEW_VTABLE(ver) { \
    ver##_query, ver##_addref, ver##_release, ver##_timestamp, ver##_current, ver##_next, ver##_previous, \
    ver##_reading_callback, ver##_device_callback, ver##_system_callback, ver##_keyboard_callback, \
    ver##_stop, ver##_unregister, ver##_dispatcher, ver##_find_id, ver##_find_string, ver##_focus, \
}
static const v1_IGameInputVtbl v1_vtable = NEW_VTABLE(v1);
static const v2_IGameInputVtbl v2_vtable = NEW_VTABLE(v2);

HRESULT WINAPI GameInputInitialize(REFIID iid, void **out)
{
    struct gameinput *input;
    HRESULT hr;
    if (!out) return E_POINTER;
    *out = NULL;
    if (!iid) return E_INVALIDARG;
    if (!IsEqualGUID(iid, &IID_IUnknown) && !IsEqualGUID(iid, &IID_v0_IGameInput)
        && !IsEqualGUID(iid, &IID_v1_IGameInput) && !IsEqualGUID(iid, &IID_v2_IGameInput))
        return E_NOINTERFACE;
    if (!(input = calloc(1, sizeof(*input)))) return E_OUTOFMEMORY;
    if (!QueryPerformanceFrequency(&input->frequency) || input->frequency.QuadPart <= 0)
    {
        ERR("QueryPerformanceFrequency unavailable\n");
        free(input);
        return E_FAIL;
    }
    input->v0_iface.lpVtbl = &v0_vtable;
    input->v1_iface.lpVtbl = &v1_vtable;
    input->v2_iface.lpVtbl = &v2_vtable;
    input->refs = 1;
    InitializeCriticalSection(&input->lock);
    InterlockedIncrement(&objects);
    hr = query_interface(input, iid, out);
    release(input);
    WARN("No physical devices exposed by this diagnostic GameInput implementation\n");
    return hr;
}

HRESULT WINAPI GameInputCreate(v0_IGameInput **out)
{
    return GameInputInitialize(&IID_v0_IGameInput, (void **)out);
}

HRESULT WINAPI DllCanUnloadNow(void)
{
    return InterlockedCompareExchange(&objects, 0, 0) ? S_FALSE : S_OK;
}

HRESULT WINAPI DllGetClassObject(REFCLSID clsid, REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    WARN("No GameInput COM class is registered; use GameInputInitialize/Create\n");
    return CLASS_E_CLASSNOTAVAILABLE;
}
