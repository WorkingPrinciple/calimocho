/* Owned scheduled-window fixture. SPDX-License-Identifier: LGPL-2.1-or-later */
#define COBJMACROS
#define WIDL_using_Windows_Foundation
#define WIDL_using_Windows_Foundation_Collections
#define WIDL_using_Windows_ApplicationModel_Core
#define WIDL_using_Windows_ApplicationModel_Activation
#define WIDL_using_Windows_UI_Core
#include <stdio.h>
#include <stddef.h>
#include "initguid.h"
#include "windef.h"
#include "winbase.h"
#include "winternl.h"
#include "ntstatus.h"
#include "winstring.h"
#include "roapi.h"
#include "windows.applicationmodel.core.h"
#include "package_activation.h"
#include "windows.ui.core.h"
#include "wine/package.h"
#undef Size
C_ASSERT(offsetof(IStaticLifetimeVtbl, Reserved) == 6 * sizeof(void *));
C_ASSERT(offsetof(IStaticLifetimeVtbl, GetCollection) == 7 * sizeof(void *));
C_ASSERT(offsetof(IMap_HSTRING_IInspectableVtbl, Lookup) == 6 * sizeof(void *));
C_ASSERT(offsetof(IMap_HSTRING_IInspectableVtbl, Insert) == 10 * sizeof(void *));
C_ASSERT(offsetof(IMap_HSTRING_IInspectableVtbl, Remove) == 11 * sizeof(void *));

static unsigned int failures, activated, dispatched;
static ICoreWindow *window;
static ICoreDispatcher *dispatcher;
static IAsyncAction *action;
static EventRegistrationToken token;
static ICoreApplicationView *application_view;
#define check(value) do { if (!(value)) { printf("uwp-fixture failure-line=%u\n", __LINE__); ++failures; } } while (0)

typedef __FITypedEventHandler_2_Windows__CApplicationModel__CCore__CCoreApplicationView_Windows__CApplicationModel__CActivation__CIActivatedEventArgs handler_type;
static HRESULT WINAPI activated_query(handler_type *iface, REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (!IsEqualGUID(iid, &IID_IUnknown) && !IsEqualGUID(iid, &IID___FITypedEventHandler_2_Windows__CApplicationModel__CCore__CCoreApplicationView_Windows__CApplicationModel__CActivation__CIActivatedEventArgs))
        return E_NOINTERFACE;
    *out = iface; return S_OK;
}
static ULONG WINAPI activated_ref(handler_type *iface) { return 2; }
static HRESULT WINAPI activated_invoke(handler_type *iface, ICoreApplicationView *view, IActivatedEventArgs *args)
{
    ActivationKind kind;
    ApplicationExecutionState previous;
    IProtocolActivatedEventArgs *protocol = NULL;
    ILaunchActivatedEventArgs *launch = NULL;
    struct wine_activation_record record;
    ULONG size;
    NTSTATUS status = NtQueryInformationProcess(GetCurrentProcess(), ProcessWineActivation, &record, sizeof(record), &size);
    check(IActivatedEventArgs_get_Kind(args, &kind) == S_OK);
    check(IActivatedEventArgs_get_PreviousExecutionState(args, &previous) == S_OK);
    check(previous == ApplicationExecutionState_NotRunning);
    if (!status)
    {
        IUriRuntimeClass *uri = NULL;
        HSTRING text = NULL;
        check(kind == ActivationKind_Protocol);
        check(IActivatedEventArgs_QueryInterface(args, &IID_IProtocolActivatedEventArgs, (void **)&protocol) == S_OK);
        if (protocol)
        {
            check(IProtocolActivatedEventArgs_get_Uri(protocol, &uri) == S_OK);
            if (uri)
            {
                check(IUriRuntimeClass_get_AbsoluteUri(uri, &text) == S_OK);
                check(!lstrcmpW(WindowsGetStringRawBuffer(text, NULL), record.uri));
                WindowsDeleteString(text); IUriRuntimeClass_Release(uri);
            }
            IProtocolActivatedEventArgs_Release(protocol);
        }
    }
    else
    {
        check(status == STATUS_NOT_FOUND);
        check(kind == ActivationKind_Launch);
        check(IActivatedEventArgs_QueryInterface(args, &IID_ILaunchActivatedEventArgs, (void **)&launch) == S_OK);
        if (launch) ILaunchActivatedEventArgs_Release(launch);
    }
    ++activated;
    return S_OK;
}
static const __FITypedEventHandler_2_Windows__CApplicationModel__CCore__CCoreApplicationView_Windows__CApplicationModel__CActivation__CIActivatedEventArgsVtbl activated_vtable = {
    activated_query, activated_ref, activated_ref, activated_invoke,
};
static handler_type activated_handler = {&activated_vtable};
static HRESULT WINAPI dispatch_query(IDispatchedHandler *iface, REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (!IsEqualGUID(iid, &IID_IUnknown) && !IsEqualGUID(iid, &IID_IDispatchedHandler)) return E_NOINTERFACE;
    *out = iface; return S_OK;
}
static ULONG WINAPI dispatch_ref(IDispatchedHandler *iface) { return 2; }
static HRESULT WINAPI dispatch_invoke(IDispatchedHandler *iface)
{
    boolean access = FALSE;
    check(ICoreDispatcher_get_HasThreadAccess(dispatcher, &access) == S_OK && access);
    ++dispatched; return S_OK;
}
static const IDispatchedHandlerVtbl dispatch_vtable = {dispatch_query, dispatch_ref, dispatch_ref, dispatch_invoke};
static IDispatchedHandler dispatch_handler = {&dispatch_vtable};

static HRESULT WINAPI view_query(IFrameworkView *iface, REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (!IsEqualGUID(iid, &IID_IUnknown) && !IsEqualGUID(iid, &IID_IInspectable) && !IsEqualGUID(iid, &IID_IFrameworkView))
        return E_NOINTERFACE;
    *out = iface; return S_OK;
}
static ULONG WINAPI view_ref(IFrameworkView *iface) { return 2; }
static HRESULT WINAPI view_iids(IFrameworkView *iface, ULONG *count, IID **out) { return E_NOTIMPL; }
static HRESULT WINAPI view_name(IFrameworkView *iface, HSTRING *out) { return E_NOTIMPL; }
static HRESULT WINAPI view_trust(IFrameworkView *iface, TrustLevel *out) { return E_NOTIMPL; }
static HRESULT WINAPI view_initialize(IFrameworkView *iface, ICoreApplicationView *view)
{
    application_view = view;
    return ICoreApplicationView_add_Activated(view, &activated_handler, &token);
}
static HRESULT WINAPI view_window(IFrameworkView *iface, ICoreWindow *value)
{
    Rect bounds;
    ICoreWindowStatic *factory = NULL;
    ICoreWindow *current = NULL;
    HSTRING name;
    window = value; ICoreWindow_AddRef(window);
    check(ICoreWindow_get_Bounds(window, &bounds) == S_OK && bounds.Width > 0 && bounds.Height > 0);
    WindowsCreateString(L"Windows.UI.Core.CoreWindow", 26, &name);
    check(RoGetActivationFactory(name, &IID_ICoreWindowStatic, (void **)&factory) == S_OK);
    WindowsDeleteString(name);
    if (factory)
    {
        check(ICoreWindowStatic_GetForCurrentThread(factory, &current) == S_OK && current == window);
        if (current) ICoreWindow_Release(current);
        ICoreWindowStatic_Release(factory);
    }
    check(ICoreWindow_get_Dispatcher(window, &dispatcher) == S_OK);
    if (!dispatcher) return E_FAIL;
    return ICoreDispatcher_RunAsync(dispatcher, CoreDispatcherPriority_Normal, &dispatch_handler, &action);
}
static HRESULT WINAPI view_load(IFrameworkView *iface, HSTRING entrypoint) { return S_OK; }
static HRESULT WINAPI view_run(IFrameworkView *iface)
{
    boolean visible = FALSE;
    HRESULT hr = ICoreWindow_Activate(window);
    if (FAILED(hr)) return hr;
    check(ICoreWindow_get_Visible(window, &visible) == S_OK && visible);
    hr = ICoreDispatcher_ProcessEvents(dispatcher, CoreProcessEventsOption_ProcessAllIfPresent);
    if (SUCCEEDED(hr))
    {
        IAsyncInfo *info = NULL;
        UINT32 id = 0;
        AsyncStatus status;
        check(IAsyncAction_GetResults(action) == S_OK);
        check(IAsyncAction_QueryInterface(action, &IID_IAsyncInfo, (void **)&info) == S_OK);
        if (info)
        {
            check(IAsyncInfo_get_Id(info, &id) == S_OK && id > 0);
            check(IAsyncInfo_get_Status(info, &status) == S_OK && status == Completed);
            check(IAsyncInfo_Close(info) == S_OK);
            check(IAsyncInfo_get_Status(info, &status) == RO_E_CLOSED);
            check(IAsyncInfo_Cancel(info) == RO_E_CLOSED);
            IAsyncInfo_Release(info);
        }
    }
    check(dispatched == 1 && activated == 1);
    return hr;
}
static HRESULT WINAPI view_uninitialize(IFrameworkView *iface)
{
    check(ICoreApplicationView_remove_Activated(application_view, token) == S_OK);
    if (action) IAsyncAction_Release(action);
    if (dispatcher) ICoreDispatcher_Release(dispatcher);
    if (window) ICoreWindow_Release(window);
    return S_OK;
}
static const IFrameworkViewVtbl view_vtable = {
    view_query, view_ref, view_ref, view_iids, view_name, view_trust,
    view_initialize, view_window, view_load, view_run, view_uninitialize,
};
static IFrameworkView fixture_view = {&view_vtable};
static HRESULT WINAPI source_query(IFrameworkViewSource *iface, REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (!IsEqualGUID(iid, &IID_IUnknown) && !IsEqualGUID(iid, &IID_IInspectable) && !IsEqualGUID(iid, &IID_IFrameworkViewSource))
        return E_NOINTERFACE;
    *out = iface; return S_OK;
}
static ULONG WINAPI source_ref(IFrameworkViewSource *iface) { return 2; }
static HRESULT WINAPI source_iids(IFrameworkViewSource *iface, ULONG *count, IID **out) { return E_NOTIMPL; }
static HRESULT WINAPI source_name(IFrameworkViewSource *iface, HSTRING *out) { return E_NOTIMPL; }
static HRESULT WINAPI source_trust(IFrameworkViewSource *iface, TrustLevel *out) { return E_NOTIMPL; }
static HRESULT WINAPI source_create(IFrameworkViewSource *iface, IFrameworkView **out)
{ if (!out) return E_POINTER; *out = &fixture_view; return S_OK; }
static const IFrameworkViewSourceVtbl source_vtable = {
    source_query, source_ref, source_ref, source_iids, source_name, source_trust, source_create,
};
static IFrameworkViewSource fixture_source = {&source_vtable};
static int static_lifetime_probe(void)
{
    static const GUID collection_iid =
        {0x1b0d3570,0x0877,0x5ec2,{0x8a,0x2c,0x3b,0x95,0x39,0x50,0x6a,0xca}};
    IStaticLifetime *lifetime = NULL;
    IInspectable *collection = NULL, *second = NULL, *value = NULL;
    IMap_HSTRING_IInspectable *map = NULL, *custom = NULL;
    IMapView_HSTRING_IInspectable *view = NULL;
    IUnknown *identity1 = NULL, *identity2 = NULL;
    HSTRING name = NULL, key = NULL;
    boolean replaced = TRUE, exists = TRUE;
    UINT32 count = 99;
    HRESULT hr;
    check(SUCCEEDED(RoInitialize(RO_INIT_MULTITHREADED)));
    WindowsCreateString(L"Windows.ApplicationModel.Core.CoreApplication", 45, &name);
    hr = RoGetActivationFactory(name, &IID_IStaticLifetime, (void **)&lifetime);
    check(hr == S_OK && lifetime);
    WindowsDeleteString(name);
    if (!lifetime) goto done;
    check(IStaticLifetime_Reserved(lifetime) == E_NOTIMPL);
    check(IStaticLifetime_GetCollection(lifetime, NULL) == E_POINTER);
    check(IStaticLifetime_GetCollection(lifetime, &collection) == S_OK && collection);
    check(IStaticLifetime_GetCollection(lifetime, &second) == S_OK && second);
    if (!collection || !second) goto done;
    check(IInspectable_QueryInterface(collection, &IID_IMap_HSTRING_IInspectable, (void **)&map) == S_OK);
    check(IInspectable_QueryInterface(second, &collection_iid, (void **)&custom) == S_OK);
    if (!map || !custom) goto done;
    check(IMap_HSTRING_IInspectable_QueryInterface(map, &IID_IUnknown, (void **)&identity1) == S_OK);
    check(IMap_HSTRING_IInspectable_QueryInterface(custom, &IID_IUnknown, (void **)&identity2) == S_OK);
    check(identity1 == identity2);
    WindowsCreateString(L"Calimocho.StaticLifetime.Fixture", 32, &key);
    check(IMap_HSTRING_IInspectable_Clear(map) == S_OK);
    check(IMap_HSTRING_IInspectable_Lookup(custom, key, &value) == E_BOUNDS && !value);
    check(IMap_HSTRING_IInspectable_Insert(custom, key, (IInspectable *)lifetime, &replaced) == S_OK && !replaced);
    check(IMap_HSTRING_IInspectable_HasKey(map, key, &exists) == S_OK && exists);
    check(IMap_HSTRING_IInspectable_get_Size(map, &count) == S_OK && count == 1);
    check(IMap_HSTRING_IInspectable_GetView(map, &view) == S_OK && view);
    if (view)
    {
        check(IMapView_HSTRING_IInspectable_get_Size(view, &count) == S_OK && count == 1);
        check(IMapView_HSTRING_IInspectable_Lookup(view, key, &value) == S_OK && value == (IInspectable *)lifetime);
        if (value) { IInspectable_Release(value); value = NULL; }
        IMapView_HSTRING_IInspectable_Release(view);
        view = NULL;
    }
    check(IMap_HSTRING_IInspectable_Lookup(map, key, &value) == S_OK && value == (IInspectable *)lifetime);
    if (value) { IInspectable_Release(value); value = NULL; }
    check(IMap_HSTRING_IInspectable_Insert(map, key, second, &replaced) == S_OK && replaced);
    check(IMap_HSTRING_IInspectable_Remove(custom, key) == S_OK);
    check(IMap_HSTRING_IInspectable_Remove(custom, key) == E_BOUNDS);
    check(IMap_HSTRING_IInspectable_Insert(map, key, (IInspectable *)lifetime, &replaced) == S_OK);
    check(IMap_HSTRING_IInspectable_Clear(custom) == S_OK);
    check(IMap_HSTRING_IInspectable_get_Size(map, &count) == S_OK && !count);
done:
    WindowsDeleteString(key);
    if (identity1) IUnknown_Release(identity1);
    if (identity2) IUnknown_Release(identity2);
    if (custom) IMap_HSTRING_IInspectable_Release(custom);
    if (map) IMap_HSTRING_IInspectable_Release(map);
    if (second) IInspectable_Release(second);
    if (collection) IInspectable_Release(collection);
    if (lifetime) IStaticLifetime_Release(lifetime);
    RoUninitialize();
    printf("static-lifetime-fixture failures=%u\n", failures);
    return failures ? 1 : 0;
}

int main(int argc, char **argv)
{
    ICoreApplication *core = NULL;
    HSTRING name;
    if (argc == 2 && !strcmp(argv[1], "--static-lifetime")) return static_lifetime_probe();
    check(RoInitialize(RO_INIT_SINGLETHREADED) == S_OK);
    WindowsCreateString(L"Windows.ApplicationModel.Core.CoreApplication", 45, &name);
    check(RoGetActivationFactory(name, &IID_ICoreApplication, (void **)&core) == S_OK);
    WindowsDeleteString(name);
    if (core)
    {
        check(ICoreApplication_Run(core, &fixture_source) == S_OK);
        ICoreApplication_Release(core);
    }
    RoUninitialize();
    printf("uwp-fixture activated=%u dispatched=%u failures=%u\n", activated, dispatched, failures);
    return failures ? 1 : 0;
}
