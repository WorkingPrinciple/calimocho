/*
 * Verified package-local Launcher, never a host URI launcher.
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#include "initguid.h"
#include "private.h"
#include "wine/package_graph.h"
#include "wine/debug.h"
WINE_DEFAULT_DEBUG_CHANNEL(pkglaunch);

struct protocol_route
{
    WCHAR scheme[64];
    struct wine_package_registration registration;
    WCHAR entrypoint[256];
};
struct protocol_table
{
    DWORD magic, version, count;
    struct protocol_route routes[64];
};
struct launcher
{
    IActivationFactory factory;
    ILauncherStatics statics;
    LONG refs;
};
static struct launcher launcher;

static HRESULT query(REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (!iid) return E_INVALIDARG;
    if (IsEqualGUID(iid, &IID_IUnknown) || IsEqualGUID(iid, &IID_IInspectable)
        || IsEqualGUID(iid, &IID_IAgileObject) || IsEqualGUID(iid, &IID_IActivationFactory))
        *out = &launcher.factory;
    else if (IsEqualGUID(iid, &IID_ILauncherStatics)) *out = &launcher.statics;
    else
    {
        TRACE("missing-iid=%s result=80004002\n", debugstr_guid(iid));
        return E_NOINTERFACE;
    }
    InterlockedIncrement(&launcher.refs);
    return S_OK;
}

#define COMMON(prefix, type) \
static HRESULT WINAPI prefix##_query(type *iface, REFIID iid, void **out) { return query(iid, out); } \
static ULONG WINAPI prefix##_addref(type *iface) { return InterlockedIncrement(&launcher.refs); } \
static ULONG WINAPI prefix##_release(type *iface) { return InterlockedDecrement(&launcher.refs); } \
static HRESULT WINAPI prefix##_iids(type *iface, ULONG *count, IID **iids) \
{ \
    if (!count || !iids) return E_POINTER; \
    *count = 0; *iids = CoTaskMemAlloc(sizeof(IID)); \
    if (!*iids) return E_OUTOFMEMORY; \
    **iids = IID_ILauncherStatics; *count = 1; return S_OK; \
} \
static HRESULT WINAPI prefix##_name(type *iface, HSTRING *name) \
{ return name ? WindowsCreateString(L"Windows.System.Launcher", 23, name) : E_POINTER; } \
static HRESULT WINAPI prefix##_trust(type *iface, TrustLevel *trust) \
{ if (!trust) return E_POINTER; *trust = BaseTrust; return S_OK; }
COMMON(factory, IActivationFactory)
COMMON(statics, ILauncherStatics)

static HRESULT WINAPI factory_activate(IActivationFactory *iface, IInspectable **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    return E_ILLEGAL_METHOD_CALL;
}

static HRESULT load_routes(struct protocol_table **out)
{
    struct wine_package_graph *graph = NULL;
    struct wine_package_identity current;
    struct protocol_table *table;
    WCHAR path[1024];
    HANDLE file;
    DWORD length, read, i, j;
    HRESULT hr;
    NTSTATUS status;
    *out = NULL;
    status = wine_load_package_graph(&graph);
    if (status) return HRESULT_FROM_NT(status);
    RtlFreeHeap(GetProcessHeap(), 0, graph);
    status = wine_query_package_identity((HANDLE)(LONG_PTR)-4, &current);
    if (status) return HRESULT_FROM_NT(status);
    length = GetEnvironmentVariableW(L"CALIMOCHO_PACKAGE_PROTOCOLS", path, ARRAY_SIZE(path));
    if (!length) return HRESULT_FROM_WIN32(ERROR_NOT_FOUND);
    if (length >= ARRAY_SIZE(path)) return E_INVALIDARG;
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (file == INVALID_HANDLE_VALUE) return HRESULT_FROM_WIN32(GetLastError());
    table = calloc(1, sizeof(*table) + 1);
    if (!table) { CloseHandle(file); return E_OUTOFMEMORY; }
    hr = S_OK;
    if (!ReadFile(file, table, sizeof(*table) + 1, &read, NULL))
        hr = HRESULT_FROM_WIN32(GetLastError());
    CloseHandle(file);
    if (FAILED(hr)) goto failed;
    if (read < 12 || table->magic != 0x50505743 || table->version != 1
        || table->count > ARRAY_SIZE(table->routes)
        || read != 12 + table->count * sizeof(table->routes[0]))
    { hr = E_INVALIDARG; goto failed; }
    for (i = 0; i < table->count; ++i)
    {
        const struct protocol_route *route = &table->routes[i];
        const struct wine_package_identity *identity = &route->registration.identity;
        if (!route->scheme[0] || !wine_graph_terminated(route->scheme, 64)
            || !wine_graph_terminated(route->entrypoint, 256)
            || !wine_graph_terminated(route->registration.image, 1024)
            || !wine_graph_terminated(identity->full_name, 256)
            || !wine_graph_terminated(identity->family_name, 256)
            || !identity->app_id[0] || !wine_graph_terminated(identity->app_id, 256)
            || identity->version != WINE_PACKAGE_VERSION || identity->size != sizeof(*identity)
            || identity->verified_gamingapp
            || wcscmp(identity->full_name, current.full_name)
            || wcscmp(identity->family_name, current.family_name))
        { hr = E_ACCESSDENIED; goto failed; }
        for (j = 0; route->scheme[j]; ++j)
            if (!((route->scheme[j] >= 'a' && route->scheme[j] <= 'z')
                  || (j && ((route->scheme[j] >= '0' && route->scheme[j] <= '9')
                            || wcschr(L"+.-", route->scheme[j])))))
            { hr = E_INVALIDARG; goto failed; }
        for (j = 0; j < i; ++j)
            if (!wcscmp(route->scheme, table->routes[j].scheme))
            { hr = E_INVALIDARG; goto failed; }
    }
    *out = table;
    return S_OK;
failed:
    free(table);
    return hr;
}

static HRESULT activate_route(const struct protocol_route *route, const WCHAR *uri, BOOLEAN *started)
{
    const WCHAR *image = route->registration.image;
    struct wine_package_identity requested = route->registration.identity, bound;
    struct { SIZE_T TotalLength; PS_ATTRIBUTE Attributes[2]; } attributes = {0};
    PS_CREATE_INFO create = {0};
    PRTL_USER_PROCESS_PARAMETERS parameters = NULL;
    UNICODE_STRING nt_image, command;
    WCHAR *command_line;
    HANDLE process = NULL, thread = NULL, token = NULL;
    NTSTATUS status;
    HRESULT hr;
    size_t length;
    *started = FALSE;
    if (wcscmp(route->entrypoint, L"Windows.FullTrustApplication"))
    {
        TRACE("route scheme=%s app=%s pid=0 result=80004001 missing=uwp-protocol-activation\n",
              debugstr_w(route->scheme), debugstr_w(requested.app_id));
        return E_NOTIMPL;
    }
    if (wcsncmp(image, L"\\??\\Z:\\", 7)) return E_ACCESSDENIED;
    /* Quotes/control characters cannot enter the single protocol argument. */
    for (length = 0; uri[length]; ++length)
        if (uri[length] < 0x20 || uri[length] == '"' || length > 16000) return E_INVALIDARG;
    if (!(command_line = malloc((wcslen(image) + length + 8) * sizeof(WCHAR)))) return E_OUTOFMEMORY;
    swprintf(command_line, wcslen(image) + length + 8, L"\"%s\" \"%s\"", image + 4, uri);
    RtlInitUnicodeString(&nt_image, image);
    RtlInitUnicodeString(&command, command_line);
    status = RtlCreateProcessParametersEx(&parameters, &nt_image, NULL, NULL, &command,
                                         NULL, NULL, NULL, NULL, NULL, PROCESS_PARAMS_FLAG_NORMALIZED);
    free(command_line);
    if (status) return HRESULT_FROM_NT(status);
    parameters->hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    parameters->hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    parameters->hStdError = GetStdHandle(STD_ERROR_HANDLE);
    attributes.TotalLength = sizeof(attributes);
    attributes.Attributes[0].Attribute = PS_ATTRIBUTE_IMAGE_NAME;
    attributes.Attributes[0].Size = nt_image.Length;
    attributes.Attributes[0].ValuePtr = nt_image.Buffer;
    attributes.Attributes[1].Attribute = PS_ATTRIBUTE_WINE_PACKAGE;
    attributes.Attributes[1].Size = sizeof(requested);
    attributes.Attributes[1].ValuePtr = &requested;
    create.Size = sizeof(create);
    status = NtCreateUserProcess(&process, &thread, PROCESS_ALL_ACCESS, THREAD_ALL_ACCESS,
                                 NULL, NULL, PROCESS_CREATE_FLAGS_INHERIT_HANDLES,
                                 THREAD_CREATE_FLAGS_CREATE_SUSPENDED, parameters,
                                 &create, (PS_ATTRIBUTE_LIST *)&attributes);
    RtlDestroyProcessParameters(parameters);
    if (status) return HRESULT_FROM_NT(status);
    if (!OpenProcessToken(process, TOKEN_QUERY, &token)) hr = HRESULT_FROM_WIN32(GetLastError());
    else
    {
        status = wine_query_package_identity(token, &bound);
        CloseHandle(token);
        bound.verified_gamingapp = status ? 0 : bound.verified_gamingapp;
        hr = status ? HRESULT_FROM_NT(status) :
             (!bound.verified_gamingapp || wcscmp(bound.app_id, requested.app_id)
              || wcscmp(bound.full_name, requested.full_name) ? E_ACCESSDENIED : S_OK);
    }
    if (SUCCEEDED(hr))
    {
        status = NtResumeThread(thread, NULL);
        hr = status ? HRESULT_FROM_NT(status) : S_OK;
    }
    if (FAILED(hr))
    {
        TerminateProcess(process, 1);
        WaitForSingleObject(process, 5000);
    }
    *started = SUCCEEDED(hr);
    TRACE("route scheme=%s app=%s pid=%lu result=%08lx missing=none\n",
          debugstr_w(route->scheme), debugstr_w(requested.app_id), GetProcessId(process), hr);
    CloseHandle(thread);
    CloseHandle(process);
    return hr;
}

static HRESULT launch_callback(IUnknown *invoker, IUnknown *param, PROPVARIANT *result, BOOL asynchronous)
{
    IUriRuntimeClass *uri;
    struct protocol_table *table = NULL;
    HSTRING scheme = NULL, raw = NULL;
    const WCHAR *text;
    DWORD i;
    HRESULT hr;
    result->vt = VT_BOOL;
    result->boolVal = VARIANT_FALSE;
    if (FAILED(hr = IUnknown_QueryInterface(param, &IID_IUriRuntimeClass, (void **)&uri))) return hr;
    hr = IUriRuntimeClass_get_SchemeName(uri, &scheme);
    if (SUCCEEDED(hr)) hr = load_routes(&table);
    if (SUCCEEDED(hr))
    {
        text = WindowsGetStringRawBuffer(scheme, NULL);
        for (i = 0; i < table->count; ++i)
            if (!wcsicmp(text, table->routes[i].scheme)) break;
        if (i < table->count)
        {
            BOOLEAN started = FALSE;
            hr = IUriRuntimeClass_get_AbsoluteUri(uri, &raw);
            if (SUCCEEDED(hr)) hr = activate_route(&table->routes[i],
                                                   WindowsGetStringRawBuffer(raw, NULL), &started);
            result->boolVal = started ? VARIANT_TRUE : VARIANT_FALSE;
        }
        /* Unknown schemes have no external fallback and complete false. */
    }
    free(table);
    WindowsDeleteString(raw);
    WindowsDeleteString(scheme);
    IUriRuntimeClass_Release(uri);
    return hr;
}

static HRESULT WINAPI launch_uri(ILauncherStatics *iface, IUriRuntimeClass *uri, IAsyncOperation_boolean **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (!uri) return E_INVALIDARG;
    return async_operation_boolean_create((IUnknown *)iface, (IUnknown *)uri, launch_callback, out);
}
static HRESULT WINAPI launch_uri_options(ILauncherStatics *iface, IUriRuntimeClass *uri,
                                         IInspectable *options, IAsyncOperation_boolean **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (options)
    {
        TRACE("unsupported method=LaunchUriWithOptionsAsync result=80004001\n");
        return E_NOTIMPL;
    }
    return launch_uri(iface, uri, out);
}
static HRESULT WINAPI launch_file(ILauncherStatics *iface, IInspectable *file, IAsyncOperation_boolean **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    TRACE("unsupported method=LaunchFileAsync result=80004001\n");
    return E_NOTIMPL;
}
static HRESULT WINAPI launch_file_options(ILauncherStatics *iface, IInspectable *file,
                                          IInspectable *options, IAsyncOperation_boolean **out)
{
    return launch_file(iface, file, out);
}
static const IActivationFactoryVtbl factory_vtable = {
    factory_query, factory_addref, factory_release, factory_iids, factory_name, factory_trust, factory_activate,
};
static const ILauncherStaticsVtbl statics_vtable = {
    statics_query, statics_addref, statics_release, statics_iids, statics_name, statics_trust,
    launch_file, launch_file_options, launch_uri, launch_uri_options,
};
static struct launcher launcher = {{&factory_vtable}, {&statics_vtable}, 1};

HRESULT WINAPI DllGetActivationFactory(HSTRING name, IActivationFactory **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (wcscmp(WindowsGetStringRawBuffer(name, NULL), L"Windows.System.Launcher"))
        return CLASS_E_CLASSNOTAVAILABLE;
    return query(&IID_IActivationFactory, (void **)out);
}
HRESULT WINAPI DllCanUnloadNow(void)
{
    /* Reused async machinery may still hold queued work or completion handlers. */
    return S_FALSE;
}
