/*
 * Calimocho NVAPI stub (REQ-120, ADR-0083)
 *
 * Copyright 2026 the Calimocho authors
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * A minimal nvapi64.dll for titles that run with the opt-in NVIDIA GPU
 * identity (D3DM_VENDOR_ID=0x10de) on D3DMetal. Such a title finds no
 * nvapi64.dll, so it cannot read the driver version and Forza Horizon 6
 * shows FH302 ("unable to detect graphics driver version").
 * dxvk-nvapi cannot be used: it needs DXVK's IDXGIVkInteropAdapter,
 * which Apple's dxgi.dll does not have.
 *
 * It answers only identity queries, with the same values patch 0012
 * publishes in the registry and D3DKMT. Everything else returns
 * NVAPI_NO_IMPLEMENTATION, so callers that probe optional features
 * (Reflex, DLSS, Aftermath) move on. It is never installed by default:
 * a title profile copies it into the prefix as system32\nvapi64.dll.
 *
 * Function IDs and structure layouts follow NVIDIA's public NVAPI SDK
 * headers (https://github.com/NVIDIA/nvapi, MIT).
 */

#include <windows.h>

#include "nvapi_version.h"

typedef int NvAPI_Status;
typedef unsigned int NvU32;
typedef char NvAPI_ShortString[64];
typedef void *NvPhysicalGpuHandle;

#define NVAPI_OK 0
#define NVAPI_NO_IMPLEMENTATION (-3)
#define NVAPI_API_NOT_INITIALIZED (-4)
#define NVAPI_INVALID_ARGUMENT (-5)
#define NVAPI_NVIDIA_DEVICE_NOT_FOUND (-6)
#define NVAPI_INVALID_HANDLE (-8)
#define NVAPI_INCOMPATIBLE_STRUCT_VERSION (-9)

#define NVAPI_MAX_PHYSICAL_GPUS 64
#define NV_GPU_TYPE_DGPU 2
#define NV_GPU_ARCHITECTURE_AD100 0x190
#define NV_GPU_ARCH_IMPLEMENTATION_AD104 0x4
#define NV_GPU_CHIP_REV_A1 0x1

/* Fallback when the display Class key has no DriverVersion: 32.0.16.1656 (patch 0012). */
#define DEFAULT_DRIVER_VERSION 61656u

typedef struct
{
    NvU32 version;
    NvU32 architecture;
    NvU32 implementation;
    NvU32 revision;
} NV_GPU_ARCH_INFO;

typedef struct
{
    NvU32 version;
    NvU32 drvVersion;
    NvU32 bldChangeListNum;
    NvAPI_ShortString szBuildBranchString;
    NvAPI_ShortString szAdapterString;
} NV_DISPLAY_DRIVER_VERSION;

#define MAKE_NVAPI_VERSION(type, ver) ((NvU32)(sizeof(type) | ((ver) << 16)))

static char gpu_marker;
static NvPhysicalGpuHandle const gpu_handle = &gpu_marker;
static LONG initialized;
static NvU32 driver_version = DEFAULT_DRIVER_VERSION;
static NvU32 vendor_id, device_id, subsystem_id, revision_id;
static char adapter_name[64] = "NVIDIA GeForce RTX 4070";

static CRITICAL_SECTION log_lock;
static NvU32 logged_ids[512];
static unsigned int logged_count;

static void copy_string(char *dst, const char *src, size_t size)
{
    size_t i = 0;
    if (!dst || !size) return;
    while (i + 1 < size && src[i]) { dst[i] = src[i]; i++; }
    dst[i] = 0;
}

static void append_number(char *buffer, size_t size, size_t *pos, unsigned long value, int hex)
{
    char digits[16];
    int count = 0;
    unsigned int base = hex ? 16 : 10;
    do { digits[count++] = "0123456789abcdef"[value % base]; value /= base; } while (value && count < 16);
    if (hex) while (count < 8) digits[count++] = '0';
    while (count && *pos + 1 < size) buffer[(*pos)++] = digits[--count];
    buffer[*pos] = 0;
}

static void append_text(char *buffer, size_t size, size_t *pos, const char *text)
{
    while (*text && *pos + 1 < size) buffer[(*pos)++] = *text++;
    buffer[*pos] = 0;
}

/* Opt-in trace for the REQ-120 evidence run: CALIMOCHO_NVAPI_LOG=<Windows path>, or an
 * existing C:\calimocho-nvapi.log file when a launcher pins the environment. */
static void trace(const char *what, NvU32 id, NvAPI_Status status)
{
    char path[MAX_PATH], line[160];
    size_t pos = 0;
    HANDLE file;
    DWORD written;

    if (!GetEnvironmentVariableA( "CALIMOCHO_NVAPI_LOG", path, sizeof(path) ))
    {
        copy_string( path, "C:\\calimocho-nvapi.log", sizeof(path) );
        if (GetFileAttributesA( path ) == INVALID_FILE_ATTRIBUTES) return;
    }
    line[0] = 0;
    append_text( line, sizeof(line), &pos, what );
    append_text( line, sizeof(line), &pos, " 0x" );
    append_number( line, sizeof(line), &pos, id, 1 );
    append_text( line, sizeof(line), &pos, " status " );
    if (status < 0) append_text( line, sizeof(line), &pos, "-" );
    append_number( line, sizeof(line), &pos, (unsigned long)(status < 0 ? -status : status), 0 );
    append_text( line, sizeof(line), &pos, "\r\n" );
    file = CreateFileA( path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_ALWAYS, 0, NULL );
    if (file == INVALID_HANDLE_VALUE) return;
    WriteFile( file, line, (DWORD)pos, &written, NULL );
    CloseHandle( file );
}

static void trace_query_once(NvU32 id, BOOL served)
{
    unsigned int i;
    EnterCriticalSection( &log_lock );
    for (i = 0; i < logged_count; i++) if (logged_ids[i] == id) break;
    if (i == logged_count && logged_count < sizeof(logged_ids) / sizeof(logged_ids[0]))
    {
        logged_ids[logged_count++] = id;
        trace( served ? "query served" : "query noimpl", id, served ? NVAPI_OK : NVAPI_NO_IMPLEMENTATION );
    }
    LeaveCriticalSection( &log_lock );
}

static NvU32 parse_hex_env(const char *name)
{
    char value[32];
    NvU32 result = 0;
    const char *p = value;
    if (!GetEnvironmentVariableA( name, value, sizeof(value) )) return 0;
    if (p[0] == '0' && (p[1] == 'x' || p[1] == 'X')) p += 2;
    for (; *p; p++)
    {
        if (*p >= '0' && *p <= '9') result = result * 16 + (NvU32)(*p - '0');
        else if (*p >= 'a' && *p <= 'f') result = result * 16 + (NvU32)(*p - 'a' + 10);
        else if (*p >= 'A' && *p <= 'F') result = result * 16 + (NvU32)(*p - 'A' + 10);
        else return 0;
    }
    return result;
}

static void read_driver_version(void)
{
    char value[64];
    DWORD size = sizeof(value) - 1, type = 0;
    HKEY key;
    NvU32 parsed;

    if (RegOpenKeyExA( HKEY_LOCAL_MACHINE,
                       "System\\CurrentControlSet\\Control\\Class\\{4D36E968-E325-11CE-BFC1-08002BE10318}\\0000",
                       0, KEY_QUERY_VALUE, &key ))
        return;
    if (!RegQueryValueExA( key, "DriverVersion", NULL, &type, (BYTE *)value, &size ) && type == REG_SZ)
    {
        value[size < sizeof(value) ? size : sizeof(value) - 1] = 0;
        if ((parsed = calimocho_nvapi_version_from_string( value ))) driver_version = parsed;
    }
    RegCloseKey( key );
}

static void branch_string(char out[64])
{
    size_t pos = 0;
    out[0] = 0;
    append_text( out, 64, &pos, "r" );
    append_number( out, 64, &pos, driver_version / 100, 0 );
    append_text( out, 64, &pos, "_00" );
}

static NvAPI_Status __cdecl nv_Initialize(void)
{
    char name[64];
    NvAPI_Status status = NVAPI_OK;

    vendor_id = parse_hex_env( "D3DM_VENDOR_ID" );
    device_id = parse_hex_env( "D3DM_DEVICE_ID" );
    subsystem_id = parse_hex_env( "D3DM_DEVICE_SUBSYS" );
    revision_id = parse_hex_env( "D3DM_DEVICE_REVISION" );
    if (GetEnvironmentVariableA( "D3DM_DEVICE_DESCRIPTION", name, sizeof(name) ) && name[0])
        copy_string( adapter_name, name, sizeof(adapter_name) );
    /* Only the opt-in NVIDIA identity gets an NVIDIA driver; anything else sees no device. */
    if (vendor_id != 0x10de || !device_id) status = NVAPI_NVIDIA_DEVICE_NOT_FOUND;
    else
    {
        read_driver_version();
        InterlockedExchange( &initialized, 1 );
    }
    trace( "call Initialize", 0x0150e828, status );
    return status;
}

static NvAPI_Status __cdecl nv_Unload(void)
{
    InterlockedExchange( &initialized, 0 );
    return NVAPI_OK;
}

static NvAPI_Status __cdecl nv_GetErrorMessage(NvAPI_Status status, NvAPI_ShortString message)
{
    if (!message) return NVAPI_INVALID_ARGUMENT;
    switch (status)
    {
    case NVAPI_OK: copy_string( message, "NVAPI_OK", 64 ); break;
    case NVAPI_NO_IMPLEMENTATION: copy_string( message, "NVAPI_NO_IMPLEMENTATION", 64 ); break;
    case NVAPI_NVIDIA_DEVICE_NOT_FOUND: copy_string( message, "NVAPI_NVIDIA_DEVICE_NOT_FOUND", 64 ); break;
    default: copy_string( message, "NVAPI_ERROR", 64 ); break;
    }
    return NVAPI_OK;
}

static NvAPI_Status __cdecl nv_GetInterfaceVersionString(NvAPI_ShortString text)
{
    if (!text) return NVAPI_INVALID_ARGUMENT;
    copy_string( text, "Calimocho NVAPI stub", 64 );
    return NVAPI_OK;
}

static NvAPI_Status __cdecl nv_SYS_GetDriverAndBranchVersion(NvU32 *version, NvAPI_ShortString branch)
{
    NvAPI_Status status = NVAPI_OK;
    if (!initialized) status = NVAPI_API_NOT_INITIALIZED;
    else if (!version || !branch) status = NVAPI_INVALID_ARGUMENT;
    else
    {
        *version = driver_version;
        branch_string( branch );
    }
    trace( "call SYS_GetDriverAndBranchVersion", driver_version, status );
    return status;
}

static NvAPI_Status __cdecl nv_GetDisplayDriverVersion(void *display, NV_DISPLAY_DRIVER_VERSION *info)
{
    NvAPI_Status status = NVAPI_OK;
    (void)display;
    if (!initialized) status = NVAPI_API_NOT_INITIALIZED;
    else if (!info) status = NVAPI_INVALID_ARGUMENT;
    else if (info->version != MAKE_NVAPI_VERSION(NV_DISPLAY_DRIVER_VERSION, 1)) status = NVAPI_INCOMPATIBLE_STRUCT_VERSION;
    else
    {
        info->drvVersion = driver_version;
        info->bldChangeListNum = 0;
        branch_string( info->szBuildBranchString );
        copy_string( info->szAdapterString, adapter_name, 64 );
    }
    trace( "call GetDisplayDriverVersion", driver_version, status );
    return status;
}

static NvAPI_Status __cdecl nv_EnumPhysicalGPUs(NvPhysicalGpuHandle handles[NVAPI_MAX_PHYSICAL_GPUS], NvU32 *count)
{
    NvAPI_Status status = NVAPI_OK;
    if (!initialized) status = NVAPI_API_NOT_INITIALIZED;
    else if (!handles || !count) status = NVAPI_INVALID_ARGUMENT;
    else
    {
        handles[0] = gpu_handle;
        *count = 1;
    }
    trace( "call EnumPhysicalGPUs", 0xe5ac921f, status );
    return status;
}

static NvAPI_Status check_gpu(NvPhysicalGpuHandle handle)
{
    if (!initialized) return NVAPI_API_NOT_INITIALIZED;
    return handle == gpu_handle ? NVAPI_OK : NVAPI_INVALID_HANDLE;
}

static NvAPI_Status __cdecl nv_GPU_GetFullName(NvPhysicalGpuHandle handle, NvAPI_ShortString name)
{
    NvAPI_Status status = check_gpu( handle );
    if (!status && !name) status = NVAPI_INVALID_ARGUMENT;
    if (!status) copy_string( name, adapter_name, 64 );
    trace( "call GPU_GetFullName", 0xceee8e9f, status );
    return status;
}

static NvAPI_Status __cdecl nv_GPU_GetPCIIdentifiers(NvPhysicalGpuHandle handle, NvU32 *device, NvU32 *subsystem,
                                                     NvU32 *revision, NvU32 *ext_device)
{
    NvAPI_Status status = check_gpu( handle );
    if (!status && (!device || !subsystem || !revision || !ext_device)) status = NVAPI_INVALID_ARGUMENT;
    if (!status)
    {
        *device = (device_id << 16) | vendor_id;
        *subsystem = subsystem_id;
        *revision = revision_id;
        *ext_device = device_id;
    }
    trace( "call GPU_GetPCIIdentifiers", 0x2ddfb66e, status );
    return status;
}

static NvAPI_Status __cdecl nv_GPU_GetArchInfo(NvPhysicalGpuHandle handle, NV_GPU_ARCH_INFO *info)
{
    NvAPI_Status status = check_gpu( handle );
    if (!status && !info) status = NVAPI_INVALID_ARGUMENT;
    if (!status && info->version != MAKE_NVAPI_VERSION(NV_GPU_ARCH_INFO, 1)
                && info->version != MAKE_NVAPI_VERSION(NV_GPU_ARCH_INFO, 2))
        status = NVAPI_INCOMPATIBLE_STRUCT_VERSION;
    if (!status)
    {
        /* The opt-in identity is an RTX 4070 (AD104); FH6 requires Turing or newer. */
        info->architecture = NV_GPU_ARCHITECTURE_AD100;
        info->implementation = NV_GPU_ARCH_IMPLEMENTATION_AD104;
        info->revision = NV_GPU_CHIP_REV_A1;
    }
    trace( "call GPU_GetArchInfo", 0xd8265d24, status );
    return status;
}

static NvAPI_Status __cdecl nv_GPU_GetGPUType(NvPhysicalGpuHandle handle, NvU32 *type)
{
    NvAPI_Status status = check_gpu( handle );
    if (!status && !type) status = NVAPI_INVALID_ARGUMENT;
    if (!status) *type = NV_GPU_TYPE_DGPU;
    trace( "call GPU_GetGPUType", 0xc33baeb1, status );
    return status;
}

static NvAPI_Status __cdecl nv_GetLogicalGPUFromPhysicalGPU(NvPhysicalGpuHandle handle, void **logical)
{
    NvAPI_Status status = check_gpu( handle );
    if (!status && !logical) status = NVAPI_INVALID_ARGUMENT;
    /* One GPU, so the logical handle is the physical one. */
    if (!status) *logical = gpu_handle;
    trace( "call GetLogicalGPUFromPhysicalGPU", 0xadd604d1, status );
    return status;
}

/* No driver settings database (DRS) exists here; say so instead of handing out a session. */
static NvAPI_Status __cdecl nv_DRS_CreateSession(void **session)
{
    if (session) *session = NULL;
    trace( "call DRS_CreateSession", 0x0694d52e, NVAPI_NO_IMPLEMENTATION );
    return NVAPI_NO_IMPLEMENTATION;
}

static NvAPI_Status __cdecl nv_NoImplementation(void)
{
    return NVAPI_NO_IMPLEMENTATION;
}

__declspec(dllexport) void * __cdecl nvapi_QueryInterface(NvU32 id)
{
    void *function = NULL;
    switch (id)
    {
    case 0x0150e828: function = (void *)nv_Initialize; break;
    case 0xd22bdd7e: function = (void *)nv_Unload; break;
    case 0x6c2d048c: function = (void *)nv_GetErrorMessage; break;
    case 0x01053fa5: function = (void *)nv_GetInterfaceVersionString; break;
    case 0x2926aaad: function = (void *)nv_SYS_GetDriverAndBranchVersion; break;
    case 0xf951a4d1: function = (void *)nv_GetDisplayDriverVersion; break;
    case 0xe5ac921f: function = (void *)nv_EnumPhysicalGPUs; break;
    case 0xceee8e9f: function = (void *)nv_GPU_GetFullName; break;
    case 0x2ddfb66e: function = (void *)nv_GPU_GetPCIIdentifiers; break;
    case 0xd8265d24: function = (void *)nv_GPU_GetArchInfo; break;
    case 0xc33baeb1: function = (void *)nv_GPU_GetGPUType; break;
    case 0xadd604d1: function = (void *)nv_GetLogicalGPUFromPhysicalGPU; break;
    case 0x0694d52e: function = (void *)nv_DRS_CreateSession; break;
    }
    trace_query_once( id, function != NULL );
    return function ? function : (void *)nv_NoImplementation;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls( instance );
        InitializeCriticalSection( &log_lock );
    }
    return TRUE;
}
