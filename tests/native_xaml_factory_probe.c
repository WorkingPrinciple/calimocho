/* Exact native factory discriminator, no registry mutation. SPDX-License-Identifier: LGPL-2.1-or-later */
#define COBJMACROS
#define WIDL_using_Windows_ApplicationModel_Core
#include <stdio.h>
#include "initguid.h"
#include "windows.h"
#include "roapi.h"
#include "winstring.h"
#include "windows.applicationmodel.core.h"

int main(void)
{
    HMODULE module;
    HRESULT hr, initialized;
    HSTRING name = NULL;
    IActivationFactory *factory = NULL;
    IInspectable *instance = NULL;
    IFrameworkViewSource *source = NULL;
    HRESULT (WINAPI *get_factory)(HSTRING, IActivationFactory **);
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
