/*
 * Calimocho DXGI front-end: report the user-mode driver version (REQ-120, ADR-0084)
 *
 * Copyright 2026 the Calimocho authors
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * Apple's D3DMetal dxgi.dll answers IDXGIAdapter::CheckInterfaceSupport with
 * S_OK and the version 65535.65535.65535.65535, which Forza Horizon 6 reports
 * as FH302 ("unable to detect graphics driver version"). This front-end loads
 * Apple's dxgi.dll unchanged and forwards every export to it. Each factory and
 * adapter it hands out gets its own copy of the object's vtable; in that copy
 * CheckInterfaceSupport (and the factory calls that return adapters) point
 * here. Apple's files and code pages are never written. Only the answer to
 * CheckInterfaceSupport changes: the UMD version becomes the display Class key
 * DriverVersion that patch 0012 writes (32.0.16.1656 for the NVIDIA identity).
 *
 * A title profile installs it as system32\dxgi.dll with the override dxgi=n,b. Its export name
 * is dxgi_calimocho.dll: Wine 11 matches modules by export name, so Apple's dxgi.dll could
 * not be loaded next to a module that also calls itself dxgi.dll.
 * It does nothing unless D3DM_VENDOR_ID is set (the opt-in GPU identity).
 */

#define COBJMACROS
#include <windows.h>
#include <stddef.h>
#include <initguid.h>
#include <dxgi1_6.h>

#include "umd_version.h"

typedef HRESULT (WINAPI *create_factory_fn)(REFIID, void **);
typedef HRESULT (WINAPI *create_factory2_fn)(UINT, REFIID, void **);

static HMODULE real_dxgi;
static INIT_ONCE init_once = INIT_ONCE_STATIC_INIT;
static BOOL override_active;
static LARGE_INTEGER umd_version;
static CRITICAL_SECTION table_lock;

#define SLOT(vtbl, name) (offsetof(vtbl, name) / sizeof(void *))
#define MAX_TABLES 16

struct table { void **original; void **copy; };
static struct table tables[MAX_TABLES];
static unsigned int table_count;

static void trace(const char *text)
{
    static const char path[] = "C:\\calimocho-dxgi.log";
    HANDLE file;
    DWORD written;
    if (GetFileAttributesA( path ) == INVALID_FILE_ATTRIBUTES) return;
    file = CreateFileA( path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_ALWAYS, 0, NULL );
    if (file == INVALID_HANDLE_VALUE) return;
    WriteFile( file, text, lstrlenA( text ), &written, NULL );
    WriteFile( file, "\r\n", 2, &written, NULL );
    CloseHandle( file );
}

/* Apple's dxgi.dll: CALIMOCHO_DXGI_REAL, or the sibling of HB_D3D12_REAL (the FH6 profile sets
 * it to the engine's lib\\wine\\x86_64-windows\\d3d12.dll). Wine does not pass WINELOADER into the
 * Windows environment, so the engine root can't be found from it. */
static BOOL real_dxgi_path(WCHAR *out, DWORD size)
{
    static const WCHAR name[] = L"dxgi.dll";
    DWORD length, i, cut = 0;

    if (GetEnvironmentVariableW( L"CALIMOCHO_DXGI_REAL", out, size )) return TRUE;
    length = GetEnvironmentVariableW( L"HB_D3D12_REAL", out, size );
    if (!length || length >= size) return FALSE;
    for (i = length; i > 0; i--) if (out[i - 1] == '\\') { cut = i; break; }
    if (!cut || cut + ARRAYSIZE(name) > size) return FALSE;
    for (i = 0; i < ARRAYSIZE(name); i++) out[cut + i] = name[i];
    return TRUE;
}

static void read_umd_version(void)
{
    char value[64], vendor[16];
    DWORD size = sizeof(value) - 1, type = 0;
    unsigned int parts[4];
    HKEY key;

    if (!GetEnvironmentVariableA( "D3DM_VENDOR_ID", vendor, sizeof(vendor) ) || !vendor[0]) return;
    if (RegOpenKeyExA( HKEY_LOCAL_MACHINE,
                       "System\\CurrentControlSet\\Control\\Class\\{4D36E968-E325-11CE-BFC1-08002BE10318}\\0000",
                       0, KEY_QUERY_VALUE, &key ))
        return;
    if (!RegQueryValueExA( key, "DriverVersion", NULL, &type, (BYTE *)value, &size ) && type == REG_SZ)
    {
        value[size < sizeof(value) ? size : sizeof(value) - 1] = 0;
        if (calimocho_parse_driver_version( value, parts ))
        {
            umd_version.HighPart = (LONG)((parts[0] << 16) | parts[1]);
            umd_version.LowPart = (parts[2] << 16) | parts[3];
            override_active = TRUE;
        }
    }
    RegCloseKey( key );
}

static BOOL CALLBACK initialize(INIT_ONCE *once, void *param, void **context)
{
    WCHAR path[MAX_PATH];
    (void)once; (void)param; (void)context;
    InitializeCriticalSection( &table_lock );
    if (real_dxgi_path( path, MAX_PATH )) real_dxgi = LoadLibraryExW( path, NULL, LOAD_WITH_ALTERED_SEARCH_PATH );
    read_umd_version();
    if (!real_dxgi)
    {
        char text[48] = "init: real dxgi NOT loaded, error ";
        DWORD error = GetLastError(), pos = lstrlenA( text ), digits = 1, i;
        for (i = error; i >= 10; i /= 10) digits++;
        for (i = 0; i < digits; i++, error /= 10) text[pos + digits - 1 - i] = (char)('0' + error % 10);
        text[pos + digits] = 0;
        trace( text );
    }
    else trace( override_active ? "init: real dxgi loaded, UMD override on" : "init: real dxgi loaded, override off" );
    return TRUE;
}

static void *real_export(const char *name)
{
    InitOnceExecuteOnce( &init_once, initialize, NULL, NULL );
    return real_dxgi ? (void *)GetProcAddress( real_dxgi, name ) : NULL;
}

/* Give one object a private copy of its vtable with some slots replaced. The copy keeps
 * the entry before slot 0 (RTTI) and is shared by every object with the same original. */
static void retarget(void *object, unsigned int count, const unsigned int *slots, void *const *functions,
                     unsigned int replaced)
{
    void ***vptr = object, **original = *vptr, **copy = NULL;
    unsigned int i;

    EnterCriticalSection( &table_lock );
    for (i = 0; i < table_count; i++)
    {
        if (tables[i].copy + 1 == original) { LeaveCriticalSection( &table_lock ); return; }
        if (tables[i].original == original) copy = tables[i].copy;
    }
    if (!copy && table_count < MAX_TABLES)
    {
        copy = HeapAlloc( GetProcessHeap(), 0, (count + 1) * sizeof(void *) );
        if (copy)
        {
            copy[0] = original[-1];
            for (i = 0; i < count; i++) copy[1 + i] = original[i];
            for (i = 0; i < replaced; i++) copy[1 + slots[i]] = functions[i];
            tables[table_count].original = original;
            tables[table_count].copy = copy;
            table_count++;
        }
    }
    if (copy) InterlockedExchangePointer( (void **)vptr, copy + 1 );
    LeaveCriticalSection( &table_lock );
}

static void **original_table(void *object)
{
    void **current = *(void ***)object;
    unsigned int i;
    for (i = 0; i < table_count; i++) if (tables[i].copy + 1 == current) return tables[i].original;
    return current;
}

static unsigned int interface_slots(IUnknown *object, const IID *const *iids, const unsigned int *sizes, unsigned int n)
{
    unsigned int i;
    for (i = 0; i < n; i++)
    {
        IUnknown *other;
        if (SUCCEEDED(IUnknown_QueryInterface( object, iids[i], (void **)&other )))
        {
            IUnknown_Release( other );
            return sizes[i];
        }
    }
    return sizes[n - 1];
}

/* ---------------------------------------------------------------- adapters */

typedef HRESULT (STDMETHODCALLTYPE *check_fn)(IDXGIAdapter *, REFGUID, LARGE_INTEGER *);

static HRESULT STDMETHODCALLTYPE adapter_CheckInterfaceSupport(IDXGIAdapter *iface, REFGUID guid, LARGE_INTEGER *version)
{
    check_fn real = (check_fn)original_table( iface )[SLOT(IDXGIAdapterVtbl, CheckInterfaceSupport)];
    HRESULT hr = real( iface, guid, version );
    if (SUCCEEDED(hr) && version && override_active)
    {
        *version = umd_version;
        trace( "CheckInterfaceSupport: UMD version replaced" );
    }
    return hr;
}

static void hook_adapter(void *adapter)
{
    static const IID *const iids[] = {&IID_IDXGIAdapter4, &IID_IDXGIAdapter3, &IID_IDXGIAdapter2,
                                      &IID_IDXGIAdapter1, &IID_IDXGIAdapter};
    static const unsigned int sizes[] = {
        sizeof(IDXGIAdapter4Vtbl) / sizeof(void *), sizeof(IDXGIAdapter3Vtbl) / sizeof(void *),
        sizeof(IDXGIAdapter2Vtbl) / sizeof(void *), sizeof(IDXGIAdapter1Vtbl) / sizeof(void *),
        sizeof(IDXGIAdapterVtbl) / sizeof(void *)};
    static const unsigned int slots[] = {SLOT(IDXGIAdapterVtbl, CheckInterfaceSupport)};
    static void *const functions[] = {(void *)adapter_CheckInterfaceSupport};

    if (!adapter || !override_active) return;
    retarget( adapter, interface_slots( adapter, iids, sizes, ARRAYSIZE(iids) ), slots, functions, 1 );
}

/* --------------------------------------------------------------- factories */

typedef HRESULT (STDMETHODCALLTYPE *enum_fn)(IDXGIFactory *, UINT, void **);
typedef HRESULT (STDMETHODCALLTYPE *enum_luid_fn)(IDXGIFactory4 *, LUID, REFIID, void **);
typedef HRESULT (STDMETHODCALLTYPE *enum_pref_fn)(IDXGIFactory6 *, UINT, DXGI_GPU_PREFERENCE, REFIID, void **);

static HRESULT STDMETHODCALLTYPE factory_EnumAdapters(IDXGIFactory *iface, UINT index, void **adapter)
{
    enum_fn real = (enum_fn)original_table( iface )[SLOT(IDXGIFactoryVtbl, EnumAdapters)];
    HRESULT hr = real( iface, index, adapter );
    if (SUCCEEDED(hr) && adapter) hook_adapter( *adapter );
    return hr;
}

static HRESULT STDMETHODCALLTYPE factory_EnumAdapters1(IDXGIFactory *iface, UINT index, void **adapter)
{
    enum_fn real = (enum_fn)original_table( iface )[SLOT(IDXGIFactory1Vtbl, EnumAdapters1)];
    HRESULT hr = real( iface, index, adapter );
    if (SUCCEEDED(hr) && adapter) hook_adapter( *adapter );
    return hr;
}

static HRESULT STDMETHODCALLTYPE factory_EnumAdapterByLuid(IDXGIFactory4 *iface, LUID luid, REFIID iid, void **adapter)
{
    enum_luid_fn real = (enum_luid_fn)original_table( iface )[SLOT(IDXGIFactory4Vtbl, EnumAdapterByLuid)];
    HRESULT hr = real( iface, luid, iid, adapter );
    if (SUCCEEDED(hr) && adapter) hook_adapter( *adapter );
    return hr;
}

static HRESULT STDMETHODCALLTYPE factory_EnumAdapterByGpuPreference(IDXGIFactory6 *iface, UINT index,
                                                                   DXGI_GPU_PREFERENCE preference, REFIID iid, void **adapter)
{
    enum_pref_fn real = (enum_pref_fn)original_table( iface )[SLOT(IDXGIFactory6Vtbl, EnumAdapterByGpuPreference)];
    HRESULT hr = real( iface, index, preference, iid, adapter );
    if (SUCCEEDED(hr) && adapter) hook_adapter( *adapter );
    return hr;
}

static void hook_factory(void *factory)
{
    static const IID *const iids[] = {&IID_IDXGIFactory7, &IID_IDXGIFactory6, &IID_IDXGIFactory5, &IID_IDXGIFactory4,
                                      &IID_IDXGIFactory3, &IID_IDXGIFactory2, &IID_IDXGIFactory1, &IID_IDXGIFactory};
    static const unsigned int sizes[] = {
        sizeof(IDXGIFactory7Vtbl) / sizeof(void *), sizeof(IDXGIFactory6Vtbl) / sizeof(void *),
        sizeof(IDXGIFactory5Vtbl) / sizeof(void *), sizeof(IDXGIFactory4Vtbl) / sizeof(void *),
        sizeof(IDXGIFactory3Vtbl) / sizeof(void *), sizeof(IDXGIFactory2Vtbl) / sizeof(void *),
        sizeof(IDXGIFactory1Vtbl) / sizeof(void *), sizeof(IDXGIFactoryVtbl) / sizeof(void *)};
    unsigned int count, replaced = 0;
    unsigned int slots[4];
    void *functions[4];

    if (!factory || !override_active) return;
    count = interface_slots( factory, iids, sizes, ARRAYSIZE(iids) );
    slots[replaced] = SLOT(IDXGIFactoryVtbl, EnumAdapters); functions[replaced++] = (void *)factory_EnumAdapters;
    if (count > SLOT(IDXGIFactory1Vtbl, EnumAdapters1))
    { slots[replaced] = SLOT(IDXGIFactory1Vtbl, EnumAdapters1); functions[replaced++] = (void *)factory_EnumAdapters1; }
    if (count > SLOT(IDXGIFactory4Vtbl, EnumAdapterByLuid))
    { slots[replaced] = SLOT(IDXGIFactory4Vtbl, EnumAdapterByLuid); functions[replaced++] = (void *)factory_EnumAdapterByLuid; }
    if (count > SLOT(IDXGIFactory6Vtbl, EnumAdapterByGpuPreference))
    { slots[replaced] = SLOT(IDXGIFactory6Vtbl, EnumAdapterByGpuPreference); functions[replaced++] = (void *)factory_EnumAdapterByGpuPreference; }
    retarget( factory, count, slots, functions, replaced );
}

/* ----------------------------------------------------------------- exports */

HRESULT WINAPI CreateDXGIFactory(REFIID iid, void **factory)
{
    create_factory_fn real = (create_factory_fn)real_export( "CreateDXGIFactory" );
    HRESULT hr = real ? real( iid, factory ) : E_FAIL;
    if (SUCCEEDED(hr) && factory) hook_factory( *factory );
    return hr;
}

HRESULT WINAPI CreateDXGIFactory1(REFIID iid, void **factory)
{
    create_factory_fn real = (create_factory_fn)real_export( "CreateDXGIFactory1" );
    HRESULT hr = real ? real( iid, factory ) : E_FAIL;
    if (SUCCEEDED(hr) && factory) hook_factory( *factory );
    return hr;
}

HRESULT WINAPI CreateDXGIFactory2(UINT flags, REFIID iid, void **factory)
{
    create_factory2_fn real = (create_factory2_fn)real_export( "CreateDXGIFactory2" );
    HRESULT hr = real ? real( flags, iid, factory ) : E_FAIL;
    if (SUCCEEDED(hr) && factory) hook_factory( *factory );
    return hr;
}

/* The remaining exports pass straight through; their arguments are not touched. */
#define FORWARD(name, params, args) \
    HRESULT WINAPI name params \
    { \
        typedef HRESULT (WINAPI *fn) params; \
        fn real = (fn)real_export( #name ); \
        return real ? real args : E_NOTIMPL; \
    }

FORWARD(DXGID3D10CreateDevice, (HMODULE a, IDXGIFactory *b, IDXGIAdapter *c, UINT d, void *e, void **f), (a, b, c, d, e, f))
FORWARD(DXGID3D10RegisterLayers, (const void *a, UINT b), (a, b))
FORWARD(DXGIGetDebugInterface1, (UINT a, REFIID b, void **c), (a, b, c))
FORWARD(DXGIDeclareAdapterRemovalSupport, (void), ())

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) DisableThreadLibraryCalls( instance );
    return TRUE;
}
