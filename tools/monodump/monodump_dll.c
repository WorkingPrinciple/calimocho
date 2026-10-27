/*
 * monodump: managed stack snapshot of a Unity Mono game under Calimocho (REQ-132)
 *
 * Copyright 2026 the Calimocho authors
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * Diagnostic only, never shipped in an engine. monodump.dll runs once inside
 * the game (loaded by monodump.exe). It suspends each other thread just long
 * enough to copy its registers and the top of its stack (no allocation while
 * a thread is suspended), resumes it, and only then resolves the copied
 * addresses with the game's own Mono exports (mono_jit_info_table_find,
 * mono_method_full_name). Stack slots that resolve to JIT code are listed as
 * candidate managed frames; this is a heuristic, not an exact unwind. The
 * game is not modified.
 */

#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>

#define STACK_COPY 0x10000
#define MAX_THREADS 256

typedef void *(*mono_get_root_domain_fn)(void);
typedef void *(*mono_thread_attach_fn)(void *);
typedef void (*mono_thread_detach_fn)(void *);
typedef void *(*mono_jit_info_table_find_fn)(void *, void *);
typedef void *(*mono_jit_info_get_method_fn)(void *);
typedef void *(*mono_jit_info_get_code_start_fn)(void *);
typedef char *(*mono_method_full_name_fn)(void *, int);

struct snapshot
{
    DWORD tid;
    BOOL ok;
    DWORD64 rip, rsp;
    SIZE_T copied;
    BYTE stack[STACK_COPY];
};

struct mono_api
{
    mono_get_root_domain_fn root;
    mono_thread_attach_fn attach;
    mono_thread_detach_fn detach;
    mono_jit_info_table_find_fn find;
    mono_jit_info_get_method_fn method;
    mono_jit_info_get_code_start_fn start;
    mono_method_full_name_fn name;
};

static struct snapshot snaps[MAX_THREADS];
static WCHAR output_path[MAX_PATH];

static void resolve(FILE *out, const struct mono_api *api, void *domain, DWORD64 address, const char *label)
{
    void *ji = api->find( domain, (void *)address );
    void *m;
    char *full;
    if (!ji) return;
    m = api->method( ji );
    full = m ? api->name( m, 1 ) : NULL;
    fprintf( out, "  %s %016llx = %s +0x%llx\n", label, (unsigned long long)address,
             full ? full : "(unknown method)", (unsigned long long)(address - (DWORD64)api->start( ji )) );
}

static void *get(HMODULE module, const char *name)
{
    return (void *)GetProcAddress( module, name );
}

static DWORD WINAPI worker(void *arg)
{
    HMODULE mono = GetModuleHandleW( L"mono-2.0-bdwgc.dll" );
    DWORD self = GetCurrentThreadId(), pid = GetCurrentProcessId();
    struct mono_api api;
    HANDLE snap;
    THREADENTRY32 te;
    unsigned int count = 0, i;
    FILE *out;
    void *domain, *thread;
    (void)arg;

    out = _wfopen( output_path, L"w" );
    if (!out) return 1;
    fprintf( out, "monodump pid %lu\n", pid );
    if (!mono)
    {
        fprintf( out, "mono-2.0-bdwgc.dll not loaded\n" );
        fclose( out );
        return 1;
    }
    api.root = (mono_get_root_domain_fn)get( mono, "mono_get_root_domain" );
    api.attach = (mono_thread_attach_fn)get( mono, "mono_thread_attach" );
    api.detach = (mono_thread_detach_fn)get( mono, "mono_thread_detach" );
    api.find = (mono_jit_info_table_find_fn)get( mono, "mono_jit_info_table_find" );
    api.method = (mono_jit_info_get_method_fn)get( mono, "mono_jit_info_get_method" );
    api.start = (mono_jit_info_get_code_start_fn)get( mono, "mono_jit_info_get_code_start" );
    api.name = (mono_method_full_name_fn)get( mono, "mono_method_full_name" );
    if (!api.root || !api.attach || !api.detach || !api.find || !api.method || !api.start || !api.name)
    {
        fprintf( out, "missing Mono exports\n" );
        fclose( out );
        return 1;
    }

    /* Phase 1: copy registers and stack while each thread is briefly suspended. */
    te.dwSize = sizeof(te);
    snap = CreateToolhelp32Snapshot( TH32CS_SNAPTHREAD, 0 );
    if (snap != INVALID_HANDLE_VALUE && Thread32First( snap, &te ))
    {
        do
        {
            HANDLE h;
            CONTEXT ctx;
            if (te.th32OwnerProcessID != pid || te.th32ThreadID == self || count >= MAX_THREADS) continue;
            h = OpenThread( THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, te.th32ThreadID );
            if (!h) continue;
            snaps[count].tid = te.th32ThreadID;
            if (SuspendThread( h ) != (DWORD)-1)
            {
                ctx.ContextFlags = CONTEXT_CONTROL | CONTEXT_INTEGER;
                if (GetThreadContext( h, &ctx ))
                {
                    snaps[count].ok = TRUE;
                    snaps[count].rip = ctx.Rip;
                    snaps[count].rsp = ctx.Rsp;
                    ReadProcessMemory( GetCurrentProcess(), (void *)ctx.Rsp, snaps[count].stack, STACK_COPY,
                                       &snaps[count].copied );
                }
                ResumeThread( h );
            }
            CloseHandle( h );
            count++;
        } while (Thread32Next( snap, &te ));
    }
    if (snap != INVALID_HANDLE_VALUE) CloseHandle( snap );

    /* Phase 2: resolve with every thread running again. */
    domain = api.root();
    thread = api.attach( domain );
    for (i = 0; i < count; i++)
    {
        SIZE_T j;
        fprintf( out, "thread %04lx rip %016llx rsp %016llx copied %llu\n", snaps[i].tid,
                 (unsigned long long)snaps[i].rip, (unsigned long long)snaps[i].rsp,
                 (unsigned long long)snaps[i].copied );
        if (!snaps[i].ok) continue;
        resolve( out, &api, domain, snaps[i].rip, "rip    " );
        for (j = 0; j + 8 <= snaps[i].copied; j += 8)
        {
            DWORD64 value = *(DWORD64 *)(snaps[i].stack + j);
            char label[24];
            if (value < 0x10000) continue;
            snprintf( label, sizeof(label), "sp+%04llx", (unsigned long long)j );
            resolve( out, &api, domain, value, label );
        }
        fflush( out );
    }
    api.detach( thread );
    fprintf( out, "done\n" );
    fclose( out );
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH)
    {
        HANDLE t;
        DisableThreadLibraryCalls( instance );
        if (!GetEnvironmentVariableW( L"MONODUMP_OUT", output_path, MAX_PATH ))
            lstrcpyW( output_path, L"C:\\monodump.txt" );
        t = CreateThread( NULL, 0, worker, NULL, 0, NULL );
        if (t) CloseHandle( t );
    }
    return TRUE;
}
