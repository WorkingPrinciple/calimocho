/* Owned scheduled-window fixture. SPDX-License-Identifier: LGPL-2.1-or-later */
#define COBJMACROS
#define WIDL_using_Windows_Foundation
#define WIDL_using_Windows_ApplicationModel_Core
#define WIDL_using_Windows_ApplicationModel_Activation
#define WIDL_using_Windows_UI_Core
#include <stdio.h>
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
int main(void)
{
    ICoreApplication *core = NULL;
    HSTRING name;
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
