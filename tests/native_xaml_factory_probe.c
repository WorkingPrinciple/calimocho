/* Exact native factory discriminator, no registry mutation. SPDX-License-Identifier: LGPL-2.1-or-later */
#define COBJMACROS
#define WIDL_using_Windows_ApplicationModel_Core
#include <stdio.h>
#include "initguid.h"
#include "windows.h"
#include "roapi.h"
#include "winstring.h"
#include "windows.applicationmodel.core.h"

static int bulk(const WCHAR *path)
{
    FILE *input = _wfopen(path, L"rb");
    WCHAR text[513];
    char line[513];
    HMODULE module;
    HRESULT initialized, hr;
    unsigned int index = 0, supported = 0;
    HRESULT (WINAPI *get_factory)(HSTRING, IActivationFactory **);
    if (!input) return 10;
    initialized = RoInitialize(RO_INIT_SINGLETHREADED);
    if (FAILED(initialized)) { fclose(input); return 11; }
    module = LoadLibraryExW(L"C:\\windows\\system32\\Windows.UI.Xaml.dll", NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!module) { fclose(input); RoUninitialize(); return 12; }
    get_factory = (void *)GetProcAddress(module, "DllGetActivationFactory");
    if (!get_factory) { fclose(input); FreeLibrary(module); RoUninitialize(); return 13; }
    while (fgets(line, sizeof(line), input))
    {
        IActivationFactory *factory = NULL, *queried = NULL;
        HSTRING name = NULL;
        size_t length = strlen(line), i;
        HRESULT qi = E_NOINTERFACE;
        if (length && line[length - 1] == '\n') line[--length] = 0;
        if (!length || length > 511 || index >= 1024) break;
        for (i = 0; i < length; ++i)
            if (!((line[i] >= 'A' && line[i] <= 'Z') || (line[i] >= 'a' && line[i] <= 'z')
                  || (line[i] >= '0' && line[i] <= '9') || line[i] == '.' || line[i] == '_')) break;
        if (i != length || strncmp(line, "Windows.UI.Xaml.", 16)) break;
        for (i = 0; i <= length; ++i) text[i] = (unsigned char)line[i];
        hr = WindowsCreateString(text, length, &name);
        if (SUCCEEDED(hr)) hr = get_factory(name, &factory);
        if (SUCCEEDED(hr) && factory)
            qi = IActivationFactory_QueryInterface(factory, &IID_IActivationFactory, (void **)&queried);
        printf("xaml-factory index=%u factory=%08lx present=%u qi=%08lx\n",
               index++, hr, factory != NULL, qi);
        if (SUCCEEDED(hr) && factory && SUCCEEDED(qi) && queried) ++supported;
        if (queried) IActivationFactory_Release(queried);
        if (factory) IActivationFactory_Release(factory);
        WindowsDeleteString(name);
        fflush(stdout);
    }
    hr = feof(input) && !ferror(input) ? S_OK : E_INVALIDARG;
    printf("xaml-factory count=%u supported=%u result=%08lx\n", index, supported, hr);
    fclose(input);
    FreeLibrary(module);
    RoUninitialize();
    return FAILED(hr) ? 14 : 0;
}

int wmain(int argc, WCHAR **argv)
{
    HMODULE module;
    HRESULT hr, initialized;
    HSTRING name = NULL;
    IActivationFactory *factory = NULL;
    IInspectable *instance = NULL;
    IFrameworkViewSource *source = NULL;
    HRESULT (WINAPI *get_factory)(HSTRING, IActivationFactory **);
    if (argc == 3 && !lstrcmpW(argv[1], L"--classes")) return bulk(argv[2]);
    if (argc != 1) return 15;
    initialized = RoInitialize(RO_INIT_SINGLETHREADED);
    printf("xaml-factory initialize=%08lx\n", initialized);
    if (FAILED(initialized)) return 1;
    module = LoadLibraryExW(L"C:\\windows\\system32\\Windows.UI.Xaml.dll", NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!module)
    {
        printf("xaml-factory load-error=%lu\n", GetLastError());
        RoUninitialize();
        return 2;
    }
    get_factory = (void *)GetProcAddress(module, "DllGetActivationFactory");
    if (!get_factory)
    {
        printf("xaml-factory export-error=%lu\n", GetLastError());
        FreeLibrary(module);
        RoUninitialize();
        return 3;
    }
    hr = WindowsCreateString(L"Windows.UI.Xaml.FrameworkViewSource", 35, &name);
    if (SUCCEEDED(hr)) hr = get_factory(name, &factory);
    printf("xaml-factory exact-factory=%08lx present=%u\n", hr, factory != NULL);
    WindowsDeleteString(name);
    if (SUCCEEDED(hr) && factory)
    {
        hr = IActivationFactory_ActivateInstance(factory, &instance);
        printf("xaml-factory activate=%08lx present=%u\n", hr, instance != NULL);
        if (SUCCEEDED(hr) && instance)
        {
            hr = IInspectable_QueryInterface(instance, &IID_IFrameworkViewSource, (void **)&source);
            printf("xaml-factory view-source=%08lx present=%u\n", hr, source != NULL);
        }
    }
    if (source) IFrameworkViewSource_Release(source);
    if (instance) IInspectable_Release(instance);
    if (factory) IActivationFactory_Release(factory);
    FreeLibrary(module);
    RoUninitialize();
    return SUCCEEDED(hr) && source ? 0 : 4;
}
