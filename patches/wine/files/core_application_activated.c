/*
 * Process-bound CoreApplication activation.
 * Copyright 2025 Zhiyi Zhang for CodeWeavers
 * Copyright 2026 Calimocho contributors
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * Lesser General Public License for more details.
 */
#include <stdint.h>
#define WIDL_using_Windows_ApplicationModel_Activation
#define WIDL_using_Windows_UI_Core
#include "private.h"
#include "winternl.h"
#include "ntstatus.h"
#include "roapi.h"
#include "wine/package.h"
#include "initguid.h"
#include "package_activation.h"
#include "windows.ui.core.h"
#undef Size

WINE_DEFAULT_DEBUG_CHANNEL(pkgcore);

struct activation_args
{
    IActivatedEventArgs IActivatedEventArgs_iface;
    IProtocolActivatedEventArgs IProtocolActivatedEventArgs_iface;
    ILaunchActivatedEventArgs ILaunchActivatedEventArgs_iface;
    LONG refs;
    ActivationKind kind;
    IUriRuntimeClass *uri;
};

static HRESULT WINAPI args_query(IActivatedEventArgs *iface, REFIID iid, void **out)
{
    struct activation_args *args = CONTAINING_RECORD(iface, struct activation_args, IActivatedEventArgs_iface);
    if (!out) return E_POINTER;
    *out = NULL;
    if (IsEqualGUID(iid, &IID_IUnknown) || IsEqualGUID(iid, &IID_IInspectable)
        || IsEqualGUID(iid, &IID_IActivatedEventArgs))
        *out = iface;
    else if (args->kind == ActivationKind_Protocol && IsEqualGUID(iid, &IID_IProtocolActivatedEventArgs))
        *out = &args->IProtocolActivatedEventArgs_iface;
    else if (args->kind == ActivationKind_Launch && IsEqualGUID(iid, &IID_ILaunchActivatedEventArgs))
        *out = &args->ILaunchActivatedEventArgs_iface;
    else
    {
        TRACE("missing-iid=%s result=80004002\n", debugstr_guid(iid));
        return E_NOINTERFACE;
    }
    InterlockedIncrement(&args->refs);
    return S_OK;
}

static ULONG WINAPI args_addref(IActivatedEventArgs *iface)
{
    return InterlockedIncrement(&CONTAINING_RECORD(iface, struct activation_args, IActivatedEventArgs_iface)->refs);
}
static ULONG WINAPI args_release(IActivatedEventArgs *iface)
{
    struct activation_args *args = CONTAINING_RECORD(iface, struct activation_args, IActivatedEventArgs_iface);
    ULONG refs = InterlockedDecrement(&args->refs);
    if (!refs)
    {
        if (args->uri) IUriRuntimeClass_Release(args->uri);
        free(args);
    }
    return refs;
}
static HRESULT WINAPI args_iids(IActivatedEventArgs *iface, ULONG *count, IID **out)
{
    struct activation_args *args = CONTAINING_RECORD(iface, struct activation_args, IActivatedEventArgs_iface);
    if (!count || !out) return E_POINTER;
    *count = 0;
    *out = CoTaskMemAlloc(2 * sizeof(IID));
    if (!*out) return E_OUTOFMEMORY;
    (*out)[0] = IID_IActivatedEventArgs;
    (*out)[1] = args->kind == ActivationKind_Protocol ? IID_IProtocolActivatedEventArgs : IID_ILaunchActivatedEventArgs;
    *count = 2;
    return S_OK;
}
static HRESULT WINAPI args_name(IActivatedEventArgs *iface, HSTRING *out)
{
    struct activation_args *args = CONTAINING_RECORD(iface, struct activation_args, IActivatedEventArgs_iface);
    const WCHAR *name = args->kind == ActivationKind_Protocol ?
        L"Windows.ApplicationModel.Activation.ProtocolActivatedEventArgs" :
        L"Windows.ApplicationModel.Activation.LaunchActivatedEventArgs";
    return out ? WindowsCreateString(name, lstrlenW(name), out) : E_POINTER;
}
static HRESULT WINAPI args_trust(IActivatedEventArgs *iface, TrustLevel *out)
{
    if (!out) return E_POINTER;
    *out = BaseTrust;
    return S_OK;
}
static HRESULT WINAPI args_kind(IActivatedEventArgs *iface, ActivationKind *out)
{
    if (!out) return E_POINTER;
    *out = CONTAINING_RECORD(iface, struct activation_args, IActivatedEventArgs_iface)->kind;
    return S_OK;
}
static HRESULT WINAPI args_previous(IActivatedEventArgs *iface, ApplicationExecutionState *out)
{
    if (!out) return E_POINTER;
    *out = ApplicationExecutionState_NotRunning;
    return S_OK;
}
static HRESULT WINAPI args_splash(IActivatedEventArgs *iface, ISplashScreen **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    TRACE("missing-method=SplashScreen result=80004001\n");
    return E_NOTIMPL;
}
static const IActivatedEventArgsVtbl args_vtable = {
    args_query, args_addref, args_release, args_iids, args_name, args_trust,
    args_kind, args_previous, args_splash,
};
DEFINE_IINSPECTABLE(protocol, IProtocolActivatedEventArgs, struct activation_args, IActivatedEventArgs_iface)
DEFINE_IINSPECTABLE(launch, ILaunchActivatedEventArgs, struct activation_args, IActivatedEventArgs_iface)

static HRESULT WINAPI protocol_uri(IProtocolActivatedEventArgs *iface, IUriRuntimeClass **out)
{
    struct activation_args *args = impl_from_IProtocolActivatedEventArgs(iface);
    if (!out) return E_POINTER;
    *out = args->uri;
    IUriRuntimeClass_AddRef(*out);
    return S_OK;
}
static HRESULT WINAPI launch_empty(ILaunchActivatedEventArgs *iface, HSTRING *out)
{
    if (!out) return E_POINTER;
    return WindowsCreateString(L"", 0, out);
}
static const IProtocolActivatedEventArgsVtbl protocol_vtable = {
    protocol_QueryInterface, protocol_AddRef, protocol_Release,
    protocol_GetIids, protocol_GetRuntimeClassName, protocol_GetTrustLevel, protocol_uri,
};
static const ILaunchActivatedEventArgsVtbl launch_vtable = {
    launch_QueryInterface, launch_AddRef, launch_Release,
    launch_GetIids, launch_GetRuntimeClassName, launch_GetTrustLevel, launch_empty, launch_empty,
};

static HRESULT create_args(struct wine_activation_record *record, IActivatedEventArgs **out)
{
    struct activation_args *args;
    IUriRuntimeClassFactory *factory = NULL;
    HSTRING name = NULL, text = NULL;
    NTSTATUS status;
    HRESULT hr = S_OK;
    ULONG size;
    *out = NULL;
    memset(record, 0, sizeof(*record));
    status = NtQueryInformationProcess(GetCurrentProcess(), ProcessWineActivation, record, sizeof(*record), &size);
    if (status && status != STATUS_NOT_FOUND) return HRESULT_FROM_NT(status);
    if (!status && (size != sizeof(*record) || record->version != 1 || record->size != sizeof(*record)
                   || record->kind != WINE_ACTIVATION_PROTOCOL || !record->uri[0]
                   || record->uri[WINE_ACTIVATION_URI_CHARS - 1] || record->entrypoint[255]))
        return E_INVALIDARG;
    if (!(args = calloc(1, sizeof(*args)))) return E_OUTOFMEMORY;
    args->IActivatedEventArgs_iface.lpVtbl = &args_vtable;
    args->IProtocolActivatedEventArgs_iface.lpVtbl = &protocol_vtable;
    args->ILaunchActivatedEventArgs_iface.lpVtbl = &launch_vtable;
    args->refs = 1;
    args->kind = status == STATUS_NOT_FOUND ? ActivationKind_Launch : ActivationKind_Protocol;
    if (args->kind == ActivationKind_Protocol)
    {
        hr = WindowsCreateString(L"Windows.Foundation.Uri", 22, &name);
        if (SUCCEEDED(hr)) hr = RoGetActivationFactory(name, &IID_IUriRuntimeClassFactory, (void **)&factory);
        if (SUCCEEDED(hr)) hr = WindowsCreateString(record->uri, lstrlenW(record->uri), &text);
        if (SUCCEEDED(hr)) hr = IUriRuntimeClassFactory_CreateUri(factory, text, &args->uri);
        if (factory) IUriRuntimeClassFactory_Release(factory);
        WindowsDeleteString(name);
        WindowsDeleteString(text);
    }
    if (FAILED(hr)) IActivatedEventArgs_Release(&args->IActivatedEventArgs_iface);
    else *out = &args->IActivatedEventArgs_iface;
    return hr;
}

typedef __FITypedEventHandler_2_Windows__CApplicationModel__CCore__CCoreApplicationView_Windows__CApplicationModel__CActivation__CIActivatedEventArgs activated_handler;
struct core
{
    IActivationFactory IActivationFactory_iface;
    ICoreApplication ICoreApplication_iface;
    ICoreApplicationView ICoreApplicationView_iface;
    IStaticLifetime IStaticLifetime_iface;
    LONG refs, running;
    DWORD thread;
    INT64 next_token;
    struct { INT64 token; activated_handler *handler; } handlers[32];
};
static struct core core;
static SRWLOCK handler_lock = SRWLOCK_INIT;

static HRESULT WINAPI core_query(IActivationFactory *iface, REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (IsEqualGUID(iid, &IID_IUnknown) || IsEqualGUID(iid, &IID_IInspectable)
        || IsEqualGUID(iid, &IID_IActivationFactory) || IsEqualGUID(iid, &IID_IAgileObject))
        *out = iface;
    else if (IsEqualGUID(iid, &IID_ICoreApplication)) *out = &core.ICoreApplication_iface;
    else if (IsEqualGUID(iid, &IID_IStaticLifetime)) *out = &core.IStaticLifetime_iface;
    else
    {
        TRACE("missing-iid=%s result=80004002\n", debugstr_guid(iid));
        return E_NOINTERFACE;
    }
    InterlockedIncrement(&core.refs);
    return S_OK;
}
static ULONG WINAPI core_addref(IActivationFactory *iface) { return InterlockedIncrement(&core.refs); }
static ULONG WINAPI core_release(IActivationFactory *iface) { return InterlockedDecrement(&core.refs); }
static HRESULT WINAPI core_iids(IActivationFactory *iface, ULONG *count, IID **out)
{
    if (!count || !out) return E_POINTER;
    *count = 0;
    *out = CoTaskMemAlloc(2 * sizeof(IID));
    if (!*out) return E_OUTOFMEMORY;
    (*out)[0] = IID_ICoreApplication;
    (*out)[1] = IID_IStaticLifetime;
    *count = 2;
    return S_OK;
}
static HRESULT WINAPI core_name(IActivationFactory *iface, HSTRING *out)
{
    return out ? WindowsCreateString(L"Windows.ApplicationModel.Core.CoreApplication", 45, out) : E_POINTER;
}
static HRESULT WINAPI core_trust(IActivationFactory *iface, TrustLevel *out)
{
    if (!out) return E_POINTER;
    *out = BaseTrust;
    return S_OK;
}
static HRESULT WINAPI core_activate(IActivationFactory *iface, IInspectable **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    return E_ILLEGAL_METHOD_CALL;
}
static const IActivationFactoryVtbl core_vtable = {
    core_query, core_addref, core_release, core_iids, core_name, core_trust, core_activate,
};
DEFINE_IINSPECTABLE(application, ICoreApplication, struct core, IActivationFactory_iface)
DEFINE_IINSPECTABLE(lifetime, IStaticLifetime, struct core, IActivationFactory_iface)

/* Microsoft's cppwinrt static collection is ABI-compatible with the string/object map. */
static const GUID static_collection_iid =
    {0x1b0d3570,0x0877,0x5ec2,{0x8a,0x2c,0x3b,0x95,0x39,0x50,0x6a,0xca}};
static IMap_HSTRING_IInspectable *lifetime_map;
static INIT_ONCE lifetime_once = INIT_ONCE_STATIC_INIT;
static HRESULT lifetime_error = E_UNEXPECTED;
static IMap_HSTRING_IInspectable lifetime_collection;

static BOOL CALLBACK lifetime_initialize(INIT_ONCE *once, void *parameter, void **context)
{
    IInspectable *instance = NULL;
    HSTRING name = NULL;
    lifetime_error = WindowsCreateString(L"Windows.Foundation.Collections.PropertySet", 42, &name);
    if (SUCCEEDED(lifetime_error)) lifetime_error = RoActivateInstance(name, &instance);
    if (SUCCEEDED(lifetime_error))
        lifetime_error = IInspectable_QueryInterface(instance, &IID_IMap_HSTRING_IInspectable, (void **)&lifetime_map);
    if (instance) IInspectable_Release(instance);
    WindowsDeleteString(name);
    return TRUE; /* Retain the actual initialization HRESULT, never silently retry. */
}
static HRESULT WINAPI collection_query(IMap_HSTRING_IInspectable *iface, REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (IsEqualGUID(iid, &IID_IUnknown) || IsEqualGUID(iid, &IID_IInspectable)
        || IsEqualGUID(iid, &IID_IAgileObject) || IsEqualGUID(iid, &IID_IMap_HSTRING_IInspectable)
        || IsEqualGUID(iid, &static_collection_iid))
    {
        *out = iface;
        IMap_HSTRING_IInspectable_AddRef(lifetime_map);
        return S_OK;
    }
    TRACE("missing-iid=%s result=80004002\n", debugstr_guid(iid));
    return E_NOINTERFACE;
}
static ULONG WINAPI collection_addref(IMap_HSTRING_IInspectable *iface)
{ return IMap_HSTRING_IInspectable_AddRef(lifetime_map); }
static ULONG WINAPI collection_release(IMap_HSTRING_IInspectable *iface)
{ return IMap_HSTRING_IInspectable_Release(lifetime_map); }
static HRESULT WINAPI collection_iids(IMap_HSTRING_IInspectable *iface, ULONG *count, IID **out)
{
    if (!count || !out) return E_POINTER;
    *count = 0;
    *out = CoTaskMemAlloc(2 * sizeof(IID));
    if (!*out) return E_OUTOFMEMORY;
    (*out)[0] = IID_IMap_HSTRING_IInspectable;
    (*out)[1] = static_collection_iid;
    *count = 2;
    return S_OK;
}
static HRESULT WINAPI collection_name(IMap_HSTRING_IInspectable *iface, HSTRING *out)
{ return out ? WindowsCreateString(L"Windows.Foundation.Collections.PropertySet", 42, out) : E_POINTER; }
static HRESULT WINAPI collection_trust(IMap_HSTRING_IInspectable *iface, TrustLevel *out)
{ if (!out) return E_POINTER; *out = BaseTrust; return S_OK; }
static HRESULT WINAPI collection_lookup(IMap_HSTRING_IInspectable *iface, HSTRING key, IInspectable **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    return IMap_HSTRING_IInspectable_Lookup(lifetime_map, key, out);
}
static HRESULT WINAPI collection_size(IMap_HSTRING_IInspectable *iface, UINT32 *out)
{ if (!out) return E_POINTER; return IMap_HSTRING_IInspectable_get_Size(lifetime_map, out); }
static HRESULT WINAPI collection_has(IMap_HSTRING_IInspectable *iface, HSTRING key, boolean *out)
{ if (!out) return E_POINTER; return IMap_HSTRING_IInspectable_HasKey(lifetime_map, key, out); }
static HRESULT WINAPI collection_view(IMap_HSTRING_IInspectable *iface, IMapView_HSTRING_IInspectable **out)
{ if (!out) return E_POINTER; *out = NULL; return IMap_HSTRING_IInspectable_GetView(lifetime_map, out); }
static HRESULT WINAPI collection_insert(IMap_HSTRING_IInspectable *iface, HSTRING key,
                                       IInspectable *value, boolean *replaced)
{
    if (!replaced) return E_POINTER;
    return IMap_HSTRING_IInspectable_Insert(lifetime_map, key, value, replaced);
}
static HRESULT WINAPI collection_remove(IMap_HSTRING_IInspectable *iface, HSTRING key)
{ return IMap_HSTRING_IInspectable_Remove(lifetime_map, key); }
static HRESULT WINAPI collection_clear(IMap_HSTRING_IInspectable *iface)
{ return IMap_HSTRING_IInspectable_Clear(lifetime_map); }
static const IMap_HSTRING_IInspectableVtbl collection_vtable = {
    collection_query, collection_addref, collection_release, collection_iids, collection_name, collection_trust,
    collection_lookup, collection_size, collection_has, collection_view, collection_insert, collection_remove, collection_clear,
};
static IMap_HSTRING_IInspectable lifetime_collection = {&collection_vtable};
static HRESULT WINAPI lifetime_reserved(IStaticLifetime *iface)
{
    TRACE("missing-method=StaticLifetime.Reserved result=80004001\n");
    return E_NOTIMPL;
}
static HRESULT WINAPI lifetime_collection_get(IStaticLifetime *iface, IInspectable **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (!InitOnceExecuteOnce(&lifetime_once, lifetime_initialize, NULL, NULL))
        return HRESULT_FROM_WIN32(GetLastError());
    if (FAILED(lifetime_error))
    {
        TRACE("static-lifetime collection-result=%08lx\n", lifetime_error);
        return lifetime_error;
    }
    *out = (IInspectable *)&lifetime_collection;
    IInspectable_AddRef(*out);
    TRACE("static-lifetime collection-result=00000000\n");
    return S_OK;
}
static const IStaticLifetimeVtbl lifetime_vtable = {
    lifetime_QueryInterface, lifetime_AddRef, lifetime_Release,
    lifetime_GetIids, lifetime_GetRuntimeClassName, lifetime_GetTrustLevel,
    lifetime_reserved, lifetime_collection_get,
};

static HRESULT WINAPI application_id(ICoreApplication *iface, HSTRING *out)
{
    struct wine_package_identity identity;
    NTSTATUS status;
    if (!out) return E_POINTER;
    *out = NULL;
    status = wine_query_package_identity((HANDLE)(LONG_PTR)-4, &identity);
    if (status) return HRESULT_FROM_NT(status);
    return WindowsCreateString(identity.app_id, lstrlenW(identity.app_id), out);
}
static HRESULT unsupported(const char *method)
{
    TRACE("missing-method=%s result=80004001\n", method);
    return E_NOTIMPL;
}
static HRESULT WINAPI application_suspending(ICoreApplication *iface,
    __FIEventHandler_1_Windows__CApplicationModel__CSuspendingEventArgs *handler, EventRegistrationToken *token)
{ return unsupported("Suspending"); }
static HRESULT WINAPI application_remove_suspending(ICoreApplication *iface, EventRegistrationToken token)
{ return unsupported("RemoveSuspending"); }
static HRESULT WINAPI application_resuming(ICoreApplication *iface,
    __FIEventHandler_1_IInspectable *handler, EventRegistrationToken *token)
{ return unsupported("Resuming"); }
static HRESULT WINAPI application_remove_resuming(ICoreApplication *iface, EventRegistrationToken token)
{ return unsupported("RemoveResuming"); }
static HRESULT WINAPI application_properties(ICoreApplication *iface, IPropertySet **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    return unsupported("Properties");
}
static HRESULT WINAPI application_view(ICoreApplication *iface, ICoreApplicationView **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (core.thread != GetCurrentThreadId()) return RPC_E_WRONG_THREAD;
    *out = &core.ICoreApplicationView_iface;
    ICoreApplicationView_AddRef(*out);
    return S_OK;
}
static HRESULT WINAPI view_query(ICoreApplicationView *iface, REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (IsEqualGUID(iid, &IID_IUnknown) || IsEqualGUID(iid, &IID_IInspectable)
        || IsEqualGUID(iid, &IID_ICoreApplicationView))
    {
        *out = iface;
        InterlockedIncrement(&core.refs);
        return S_OK;
    }
    TRACE("missing-iid=%s result=80004002\n", debugstr_guid(iid));
    return E_NOINTERFACE;
}
static ULONG WINAPI view_addref(ICoreApplicationView *iface) { return InterlockedIncrement(&core.refs); }
static ULONG WINAPI view_release(ICoreApplicationView *iface) { return InterlockedDecrement(&core.refs); }
static HRESULT WINAPI view_iids(ICoreApplicationView *iface, ULONG *count, IID **out)
{
    HRESULT hr = core_iids(&core.IActivationFactory_iface, count, out);
    if (SUCCEEDED(hr)) { **out = IID_ICoreApplicationView; *count = 1; }
    return hr;
}
static HRESULT WINAPI view_name(ICoreApplicationView *iface, HSTRING *out)
{
    const WCHAR *name = L"Windows.ApplicationModel.Core.CoreApplicationView";
    return out ? WindowsCreateString(name, lstrlenW(name), out) : E_POINTER;
}
static HRESULT WINAPI view_trust(ICoreApplicationView *iface, TrustLevel *out)
{ return core_trust(&core.IActivationFactory_iface, out); }

static HRESULT WINAPI view_window(ICoreApplicationView *iface, ICoreWindow **out)
{
    ICoreWindowStatic *factory = NULL;
    HSTRING name = NULL;
    HRESULT hr;
    if (!out) return E_POINTER;
    *out = NULL;
    hr = WindowsCreateString(L"Windows.UI.Core.CoreWindow", 26, &name);
    if (SUCCEEDED(hr)) hr = RoGetActivationFactory(name, &IID_ICoreWindowStatic, (void **)&factory);
    if (SUCCEEDED(hr)) hr = ICoreWindowStatic_GetForCurrentThread(factory, out);
    if (factory) ICoreWindowStatic_Release(factory);
    WindowsDeleteString(name);
    /* The pinned windows.ui currently returns S_OK with no window. */
    if (SUCCEEDED(hr) && !*out) return unsupported("CoreWindow.GetForCurrentThread");
    return hr;
}
static HRESULT WINAPI view_activated(ICoreApplicationView *iface, activated_handler *handler,
                                    EventRegistrationToken *token)
{
    unsigned int i;
    if (!handler || !token) return E_POINTER;
    token->value = 0;
    if (core.thread != GetCurrentThreadId()) return RPC_E_WRONG_THREAD;
    AcquireSRWLockExclusive(&handler_lock);
    for (i = 0; i < ARRAY_SIZE(core.handlers); ++i)
        if (!core.handlers[i].handler) break;
    if (i == ARRAY_SIZE(core.handlers) || core.next_token == INT64_MAX)
    {
        ReleaseSRWLockExclusive(&handler_lock);
        return E_OUTOFMEMORY;
    }
    IUnknown_AddRef((IUnknown *)handler);
    core.handlers[i].handler = handler;
    token->value = core.handlers[i].token = ++core.next_token;
    ReleaseSRWLockExclusive(&handler_lock);
    return S_OK;
}
static HRESULT WINAPI view_remove_activated(ICoreApplicationView *iface, EventRegistrationToken token)
{
    activated_handler *handler = NULL;
    unsigned int i;
    if (core.thread != GetCurrentThreadId()) return RPC_E_WRONG_THREAD;
    AcquireSRWLockExclusive(&handler_lock);
    for (i = 0; i < ARRAY_SIZE(core.handlers); ++i)
        if (core.handlers[i].handler && core.handlers[i].token == token.value)
        {
            handler = core.handlers[i].handler;
            core.handlers[i].handler = NULL;
            break;
        }
    ReleaseSRWLockExclusive(&handler_lock);
    if (!handler) return E_INVALIDARG;
    IUnknown_Release((IUnknown *)handler);
    return S_OK;
}
static HRESULT WINAPI view_main(ICoreApplicationView *iface, boolean *out)
{ if (!out) return E_POINTER; *out = TRUE; return S_OK; }
static HRESULT WINAPI view_hosted(ICoreApplicationView *iface, boolean *out)
{ if (!out) return E_POINTER; *out = FALSE; return S_OK; }
static const ICoreApplicationViewVtbl view_vtable = {
    view_query, view_addref, view_release, view_iids, view_name, view_trust,
    view_window, view_activated, view_remove_activated, view_main, view_hosted,
};
static HRESULT fire_activated(IActivatedEventArgs *args)
{
    activated_handler *handlers[32];
    unsigned int i, count = 0;
    HRESULT hr = S_OK;
    AcquireSRWLockShared(&handler_lock);
    for (i = 0; i < ARRAY_SIZE(core.handlers); ++i)
        if (core.handlers[i].handler)
        {
            handlers[count] = core.handlers[i].handler;
            IUnknown_AddRef((IUnknown *)handlers[count]);
            ++count;
        }
    ReleaseSRWLockShared(&handler_lock);
    for (i = 0; i < count; ++i)
    {
        HRESULT invoked = handlers[i]->lpVtbl->Invoke(handlers[i], &core.ICoreApplicationView_iface, args);
        if (FAILED(invoked) && SUCCEEDED(hr)) hr = invoked;
        IUnknown_Release((IUnknown *)handlers[i]);
    }
    TRACE("activated kind=%u handlers=%u result=%08lx\n",
          CONTAINING_RECORD(args, struct activation_args, IActivatedEventArgs_iface)->kind, count, hr);
    return hr;
}

struct pending_activation
{
    IDispatchedHandler IDispatchedHandler_iface;
    LONG refs;
    IActivatedEventArgs *args;
};
static HRESULT WINAPI pending_query(IDispatchedHandler *iface, REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (!IsEqualGUID(iid, &IID_IUnknown) && !IsEqualGUID(iid, &IID_IDispatchedHandler)) return E_NOINTERFACE;
    *out = iface; IDispatchedHandler_AddRef(iface); return S_OK;
}
static ULONG WINAPI pending_addref(IDispatchedHandler *iface)
{ return InterlockedIncrement(&CONTAINING_RECORD(iface, struct pending_activation, IDispatchedHandler_iface)->refs); }
static ULONG WINAPI pending_release(IDispatchedHandler *iface)
{
    struct pending_activation *pending = CONTAINING_RECORD(iface, struct pending_activation, IDispatchedHandler_iface);
    ULONG refs = InterlockedDecrement(&pending->refs);
    if (!refs) { IActivatedEventArgs_Release(pending->args); free(pending); }
    return refs;
}
static HRESULT WINAPI pending_invoke(IDispatchedHandler *iface)
{ return fire_activated(CONTAINING_RECORD(iface, struct pending_activation, IDispatchedHandler_iface)->args); }
static const IDispatchedHandlerVtbl pending_vtable = {
    pending_query, pending_addref, pending_release, pending_invoke,
};
static HRESULT queue_activation(ICoreWindow *window, IActivatedEventArgs *args, IAsyncAction **out)
{
    ICoreDispatcher *dispatcher = NULL;
    struct pending_activation *pending;
    HRESULT hr;
    if (!(pending = calloc(1, sizeof(*pending)))) return E_OUTOFMEMORY;
    pending->IDispatchedHandler_iface.lpVtbl = &pending_vtable;
    pending->refs = 1; pending->args = args; IActivatedEventArgs_AddRef(args);
    hr = ICoreWindow_get_Dispatcher(window, &dispatcher);
    if (SUCCEEDED(hr)) hr = ICoreDispatcher_RunAsync(dispatcher, CoreDispatcherPriority_Normal,
                                                    &pending->IDispatchedHandler_iface, out);
    if (dispatcher) ICoreDispatcher_Release(dispatcher);
    IDispatchedHandler_Release(&pending->IDispatchedHandler_iface);
    return hr;
}
static HRESULT WINAPI application_run(ICoreApplication *iface, IFrameworkViewSource *source)
{
    struct wine_activation_record record;
    IFrameworkView *view = NULL;
    IActivatedEventArgs *args = NULL;
    ICoreWindow *window = NULL;
    IAsyncAction *activation_action = NULL;
    static HMODULE ui;
    HRESULT (WINAPI *create_window)(ICoreWindow **);
    HSTRING entrypoint = NULL;
    HRESULT hr, uninitialized;
    BOOL initialized = FALSE;
    unsigned int i;
    if (!source) return E_INVALIDARG;
    if (InterlockedCompareExchange(&core.running, 1, 0)) return E_ILLEGAL_METHOD_CALL;
    core.thread = GetCurrentThreadId();
    hr = create_args(&record, &args);
    if (SUCCEEDED(hr)) hr = IFrameworkViewSource_CreateView(source, &view);
    if (SUCCEEDED(hr) && !view) hr = E_UNEXPECTED;
    if (SUCCEEDED(hr))
    {
        hr = IFrameworkView_Initialize(view, &core.ICoreApplicationView_iface);
        initialized = SUCCEEDED(hr);
    }
    if (SUCCEEDED(hr))
    {
        if (!ui) ui = LoadLibraryW(L"windows.ui.dll");
        if (!ui) hr = HRESULT_FROM_WIN32(GetLastError());
        else if (!(create_window = (void *)GetProcAddress(ui, "__wine_create_core_window")))
            hr = unsupported("CreateCoreWindow");
        else hr = create_window(&window);
    }
    if (SUCCEEDED(hr)) hr = IFrameworkView_SetWindow(view, window);
    if (SUCCEEDED(hr)) hr = WindowsCreateString(record.entrypoint, lstrlenW(record.entrypoint), &entrypoint);
    if (SUCCEEDED(hr)) hr = IFrameworkView_Load(view, entrypoint);
    if (SUCCEEDED(hr)) hr = queue_activation(window, args, &activation_action);
    if (SUCCEEDED(hr)) hr = IFrameworkView_Run(view);
    if (SUCCEEDED(hr)) hr = IAsyncAction_GetResults(activation_action);
    if (initialized)
    {
        uninitialized = IFrameworkView_Uninitialize(view);
        if (SUCCEEDED(hr)) hr = uninitialized;
    }
    for (i = 0; i < ARRAY_SIZE(core.handlers); ++i)
    {
        EventRegistrationToken token;
        AcquireSRWLockShared(&handler_lock);
        token.value = core.handlers[i].token;
        ReleaseSRWLockShared(&handler_lock);
        view_remove_activated(&core.ICoreApplicationView_iface, token);
    }
    if (window)
    {
        ICoreWindow_Close(window);
        ICoreWindow_Release(window);
    }
    if (activation_action) IAsyncAction_Release(activation_action);
    if (args) IActivatedEventArgs_Release(args);
    if (view) IFrameworkView_Release(view);
    WindowsDeleteString(entrypoint);
    core.thread = 0;
    InterlockedExchange(&core.running, 0);
    TRACE("run result=%08lx\n", hr);
    return hr;
}
static HRESULT WINAPI application_factories(ICoreApplication *iface, IGetActivationFactory *factory)
{ return unsupported("RunWithActivationFactories"); }
static const ICoreApplicationVtbl application_vtable = {
    application_QueryInterface, application_AddRef, application_Release,
    application_GetIids, application_GetRuntimeClassName, application_GetTrustLevel,
    application_id, application_suspending, application_remove_suspending,
    application_resuming, application_remove_resuming, application_properties,
    application_view, application_run, application_factories,
};
static struct core core = {
    {&core_vtable}, {&application_vtable}, {&view_vtable}, {&lifetime_vtable}, 1,
};
IActivationFactory *core_application_factory = &core.IActivationFactory_iface;
