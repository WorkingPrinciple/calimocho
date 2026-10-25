/*
 * Explicit AGS 5.4 non-AMD adapter. Never reports an AMD driver or extensions.
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#define COBJMACROS
#include <stdarg.h>
#include <string.h>
#include "windef.h"
#include "winbase.h"
#include "d3d12.h"
#include "wine/debug.h"
#include "ags54.h"

WINE_DEFAULT_DEBUG_CHANNEL(amd_ags);

static int context_token;

enum ags_result WINAPI agsInit(void **context, const void *config, struct ags_gpu_info *info)
{
    (void)config;
    if (!context) return AGS_INVALID_ARGS;
    *context = NULL;
    if (!info) return AGS_INVALID_ARGS;
    memset(info, 0, sizeof(*info));
    info->version_major = 5;
    info->version_minor = 4;
    info->version_patch = 1;
    info->driver_version = "";
    info->software_version = "";
    *context = &context_token;
    return AGS_SUCCESS;
}

enum ags_result WINAPI agsDeInit(void *context)
{
    return context == &context_token ? AGS_SUCCESS : AGS_INVALID_ARGS;
}

enum ags_result WINAPI agsDriverExtensionsDX12_CreateDevice(void *context,
        const struct ags_dx12_create_params *params, const void *extensions,
        struct ags_dx12_returned_params *returned)
{
    ID3D12Device *device = NULL;
    HRESULT result;

    (void)extensions;
    if (!returned) return AGS_INVALID_ARGS;
    memset(returned, 0, sizeof(*returned));
    if (context != &context_token || !params) return AGS_INVALID_ARGS;
    result = D3D12CreateDevice((IUnknown *)params->adapter, params->feature_level, &params->iid,
                               (void **)&device);
    if (!SUCCEEDED(result))
    {
        WARN("Standard D3D12 device creation failed, HRESULT %#lx\n", result);
        return AGS_FAILURE;
    }
    returned->device = device;
    return AGS_SUCCESS;
}

enum ags_result WINAPI agsDriverExtensionsDX12_DestroyDevice(void *context,
        ID3D12Device *device, unsigned int *references)
{
    ULONG remaining;

    if (context != &context_token || !device) return AGS_INVALID_ARGS;
    remaining = ID3D12Device_Release(device);
    if (references) *references = remaining;
    return AGS_SUCCESS;
}
