/*
 * Explicit AGS5.4 and minidump installed-module probe. No windows or game launch.
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#define COBJMACROS
#include <windows.h>
#include <initguid.h>
#include <d3d12.h>
#include <stdio.h>
#include <string.h>
#include "../patches/wine/files/amd_ags_x64/ags54.h"

int main(int argc, char **argv)
{
    HMODULE ags = NULL, api = NULL, dbghelp = NULL;
    void *context = NULL;
    struct ags_gpu_info info;
    struct ags_dx12_create_params params = {0};
    struct ags_dx12_returned_params returned = {0};
    unsigned int references = 0xffffffff;
    int result = 1;
    enum ags_result (WINAPI *init)(void **, const void *, struct ags_gpu_info *);
    enum ags_result (WINAPI *deinit)(void *) = NULL;
    enum ags_result (WINAPI *create)(void *, const struct ags_dx12_create_params *,
                                    const void *, struct ags_dx12_returned_params *);
    enum ags_result (WINAPI *destroy)(void *, ID3D12Device *, unsigned int *);

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 2 || strcmp(argv[1], "--device"))
    {
        fputs("Usage: ags54-probe --device (headless D3D12 device creation)\n", stderr);
        return 2;
    }
    ags = LoadLibraryW(L"amd_ags_x64.dll");
    api = LoadLibraryW(L"api-ms-win-core-debug-minidump-l1-1-0.dll");
    dbghelp = LoadLibraryW(L"dbghelp.dll");
    if (!ags || !api || !dbghelp)
    {
        fprintf(stderr, "Module load failed error=%lu ags=%p api=%p dbghelp=%p\n",
                GetLastError(), ags, api, dbghelp);
        goto cleanup;
    }
    if (!GetProcAddress(api, "MiniDumpWriteDump") ||
        GetProcAddress(api, "MiniDumpWriteDump") != GetProcAddress(dbghelp, "MiniDumpWriteDump") ||
        !GetProcAddress(api, "MiniDumpReadDumpStream") ||
        GetProcAddress(api, "MiniDumpReadDumpStream") != GetProcAddress(dbghelp, "MiniDumpReadDumpStream"))
    {
        fputs("Minidump forwarder mismatch\n", stderr);
        goto cleanup;
    }
    puts("minidump: exact dbghelp forwarding PASS");
    init = (void *)GetProcAddress(ags, "agsInit");
    deinit = (void *)GetProcAddress(ags, "agsDeInit");
    create = (void *)GetProcAddress(ags, "agsDriverExtensionsDX12_CreateDevice");
    destroy = (void *)GetProcAddress(ags, "agsDriverExtensionsDX12_DestroyDevice");
    if (!init || !deinit || !create || !destroy)
    {
        fputs("Missing AGS5.4 export\n", stderr);
        goto cleanup;
    }
    memset(&info, 0xa5, sizeof(info));
    if (init(&context, NULL, &info) != AGS_SUCCESS || !context ||
        info.version_major != 5 || info.version_minor != 4 || info.version_patch != 1 ||
        !info.driver_version || strcmp(info.driver_version, "") ||
        !info.software_version || strcmp(info.software_version, "") ||
        info.device_count || info.devices)
    {
        fputs("AGS non-AMD initialization contract failed\n", stderr);
        goto cleanup;
    }
    puts("ags54: version5.4.1, empty nonnull strings, zero devices PASS");
    params.iid = IID_ID3D12Device;
    params.feature_level = D3D_FEATURE_LEVEL_11_0;
    if (create(context, &params, NULL, &returned) != AGS_SUCCESS ||
        !returned.device || returned.extensions_supported)
    {
        fputs("AGS standard D3D12 device creation failed\n", stderr);
        goto cleanup;
    }
    puts("ags54: standard D3D12 device, zero extensions PASS");
    if (destroy(context, returned.device, &references) != AGS_SUCCESS)
    {
        fputs("AGS device destruction failed\n", stderr);
        returned.device = NULL;
        goto cleanup;
    }
    returned.device = NULL;
    printf("ags54: device released, remaining references=%u PASS\n", references);
    if (deinit(context) != AGS_SUCCESS)
    {
        fputs("AGS context destruction failed\n", stderr);
        context = NULL;
        goto cleanup;
    }
    context = NULL;
    result = 0;
cleanup:
    if (returned.device) ID3D12Device_Release(returned.device);
    if (context && deinit) deinit(context);
    if (dbghelp) FreeLibrary(dbghelp);
    if (api) FreeLibrary(api);
    if (ags) FreeLibrary(ags);
    return result;
}
