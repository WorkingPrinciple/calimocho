/*
 * Minimal AGS 5.4 interface for the explicitly selected non-AMD adapter.
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

enum ags_result { AGS_SUCCESS, AGS_FAILURE, AGS_INVALID_ARGS };

struct ags_gpu_info
{
    int version_major, version_minor, version_patch, wack_compliant;
    const char *driver_version, *software_version;
    int device_count;
    void *devices;
};

struct ags_dx12_create_params
{
    IDXGIAdapter *adapter;
    IID iid;
    D3D_FEATURE_LEVEL feature_level;
};

struct ags_dx12_returned_params
{
    ID3D12Device *device;
    unsigned int extensions_supported;
};
