/* Owned windowless package-protocol fixture. SPDX-License-Identifier: LGPL-2.1-or-later */
#define COBJMACROS
#define WIDL_using_Windows_Foundation
#define WIDL_using_Windows_System
#include <stdio.h>
#include <string.h>
#include "windef.h"
#include "winbase.h"
#include "winternl.h"
#include "winstring.h"
#include "roapi.h"
#include "initguid.h"
#include "launcher.h"
#include "wine/package.h"
#undef Size
_Static_assert(offsetof(ILauncherStaticsVtbl, LaunchUriAsync) == 8 * sizeof(void *),
               "SDK file overloads precede LaunchUriAsync");
_Static_assert(offsetof(ILauncherStaticsVtbl, LaunchUriWithOptionsAsync) == 9 * sizeof(void *),
               "SDK options overload is the final LauncherStatics slot");

static unsigned int failures;
#define check(test) do { if (!(test)) { printf("launcher-failure line=%u\n", __LINE__); ++failures; } } while (0)

static HRESULT operation_result(IAsyncOperation_boolean *operation, BOOLEAN *result)
{
    IAsyncInfo *info = NULL;
    AsyncStatus status = Started;
    HRESULT hr;
    unsigned int attempt;
    hr = IAsyncOperation_boolean_QueryInterface(operation, &IID_IAsyncInfo, (void **)&info);
    if (FAILED(hr)) return hr;
    for (attempt = 0; attempt < 100 && status == Started; ++attempt)
    {
        IAsyncInfo_get_Status(info, &status);
        if (status == Started) Sleep(10);
    }
    if (status == Started) hr = HRESULT_FROM_WIN32(WAIT_TIMEOUT);
    else hr = IAsyncOperation_boolean_GetResults(operation, result);
    IAsyncInfo_Release(info);
    return hr;
}

static HRESULT launch(ILauncherStatics *launcher, IUriRuntimeClassFactory *uris,
                      const WCHAR *value, BOOLEAN *result)
{
    HSTRING text;
    IUriRuntimeClass *uri = NULL;
    IAsyncOperation_boolean *operation = NULL;
    HRESULT hr = WindowsCreateString(value, lstrlenW(value), &text);
    if (FAILED(hr)) return hr;
    hr = IUriRuntimeClassFactory_CreateUri(uris, text, &uri);
    WindowsDeleteString(text);
    if (FAILED(hr)) return hr;
    hr = ILauncherStatics_LaunchUriAsync(launcher, uri, &operation);
    IUriRuntimeClass_Release(uri);
    if (SUCCEEDED(hr))
    {
        hr = operation_result(operation, result);
        IAsyncOperation_boolean_Release(operation);
    }
    return hr;
}

int main(int argc, char **argv)
{
    HSTRING name;
    ILauncherStatics *launcher = NULL;
    IUriRuntimeClassFactory *uris = NULL;
    BOOLEAN result;
    WCHAR marker[1024];
    HANDLE file;
    DWORD count;
    char bytes[32] = {0};
    unsigned int attempt;
    if (argc > 1)
    {
        struct wine_package_identity identity;
        if (wine_query_package_identity((HANDLE)(LONG_PTR)-4, &identity)
            || !identity.verified_gamingapp || lstrcmpW(identity.app_id, L"Target")
            || strcmp(argv[1], "fixture-full:test")) return 2;
        if (!GetEnvironmentVariableW(L"CALIMOCHO_LAUNCHER_MARKER", marker, ARRAY_SIZE(marker))) return 3;
        file = CreateFileW(marker, GENERIC_WRITE, 0, NULL, CREATE_NEW, 0, NULL);
        if (file == INVALID_HANDLE_VALUE) return 4;
        if (!WriteFile(file, "target-admitted", 15, &count, NULL) || count != 15) return 5;
        CloseHandle(file);
        return 0;
    }
    check(SUCCEEDED(RoInitialize(RO_INIT_MULTITHREADED)));
    WindowsCreateString(L"Windows.System.Launcher", 23, &name);
    check(RoGetActivationFactory(name, &IID_ILauncherStatics, (void **)&launcher) == S_OK);
    WindowsDeleteString(name);
    WindowsCreateString(L"Windows.Foundation.Uri", 22, &name);
    check(RoGetActivationFactory(name, &IID_IUriRuntimeClassFactory, (void **)&uris) == S_OK);
    WindowsDeleteString(name);
    if (!launcher || !uris) return 1;
    result = TRUE;
    check(launch(launcher, uris, L"fixture-unknown:test", &result) == S_OK && !result);
    result = TRUE;
    check(launch(launcher, uris, L"fixture-uwp:test", &result) == E_NOTIMPL && !result);
    result = FALSE;
    check(launch(launcher, uris, L"fixture-full:test", &result) == S_OK && result);
    check(GetEnvironmentVariableW(L"CALIMOCHO_LAUNCHER_MARKER", marker, ARRAY_SIZE(marker)) > 0);
    for (attempt = 0; attempt < 100; ++attempt)
    {
        file = CreateFileW(marker, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
        if (file != INVALID_HANDLE_VALUE) break;
        Sleep(10);
    }
    check(file != INVALID_HANDLE_VALUE);
    if (file != INVALID_HANDLE_VALUE)
    {
        check(ReadFile(file, bytes, sizeof(bytes), &count, NULL) && count == 15);
        check(!memcmp(bytes, "target-admitted", 15));
        CloseHandle(file);
    }
    ILauncherStatics_Release(launcher);
    IUriRuntimeClassFactory_Release(uris);
    RoUninitialize();
    printf("launcher-fixture failures=%u\n", failures);
    return failures ? 1 : 0;
}
