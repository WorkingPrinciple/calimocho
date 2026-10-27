/*
 * monodump.exe: load monodump.dll into a running process (REQ-132 diagnostic)
 *
 * Copyright 2026 the Calimocho authors
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * Usage: monodump.exe <pid|image-name.exe> [dll-path]
 * The DLL writes its report to C:\monodump.txt (or %MONODUMP_OUT% in the
 * target's environment). Waits up to 60 s for LoadLibrary to return.
 */

#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

static DWORD find_pid(const WCHAR *name)
{
    PROCESSENTRY32W pe;
    HANDLE snap = CreateToolhelp32Snapshot( TH32CS_SNAPPROCESS, 0 );
    DWORD pid = 0;
    pe.dwSize = sizeof(pe);
    if (snap == INVALID_HANDLE_VALUE) return 0;
    if (Process32FirstW( snap, &pe ))
    {
        do
        {
            if (!_wcsicmp( pe.szExeFile, name )) { pid = pe.th32ProcessID; break; }
        } while (Process32NextW( snap, &pe ));
    }
    CloseHandle( snap );
    return pid;
}

int wmain(int argc, WCHAR **argv)
{
    WCHAR dll[MAX_PATH];
    DWORD pid, code = 0;
    HANDLE process, thread;
    void *remote;
    SIZE_T size;

    if (argc < 2)
    {
        fwprintf( stderr, L"usage: monodump <pid|name.exe> [dll]\n" );
        return 2;
    }
    pid = wcstoul( argv[1], NULL, 0 );
    if (!pid) pid = find_pid( argv[1] );
    if (!pid)
    {
        fwprintf( stderr, L"process %ls not found\n", argv[1] );
        return 3;
    }
    if (argc > 2) lstrcpynW( dll, argv[2], MAX_PATH );
    else
    {
        GetModuleFileNameW( NULL, dll, MAX_PATH );
        lstrcpyW( wcsrchr( dll, L'\\' ) + 1, L"monodump.dll" );
    }
    size = (lstrlenW( dll ) + 1) * sizeof(WCHAR);
    process = OpenProcess( PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION,
                           FALSE, pid );
    if (!process)
    {
        fwprintf( stderr, L"OpenProcess %lu failed %lu\n", pid, GetLastError() );
        return 4;
    }
    remote = VirtualAllocEx( process, NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE );
    if (!remote || !WriteProcessMemory( process, remote, dll, size, NULL ))
    {
        fwprintf( stderr, L"remote write failed %lu\n", GetLastError() );
        return 5;
    }
    thread = CreateRemoteThread( process, NULL, 0,
                                 (LPTHREAD_START_ROUTINE)(void *)GetProcAddress( GetModuleHandleW( L"kernel32.dll" ),
                                                                                "LoadLibraryW" ),
                                 remote, 0, NULL );
    if (!thread)
    {
        fwprintf( stderr, L"CreateRemoteThread failed %lu\n", GetLastError() );
        return 6;
    }
    WaitForSingleObject( thread, 60000 );
    GetExitCodeThread( thread, &code );
    wprintf( L"pid %lu: LoadLibraryW(%ls) returned %#lx\n", pid, dll, code );
    CloseHandle( thread );
    CloseHandle( process );
    return code ? 0 : 7;
}
