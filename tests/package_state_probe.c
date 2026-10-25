/* Target-only bounded debugger and window observation. SPDX-License-Identifier: LGPL-2.1-or-later */
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include "ntstatus.h"
#define WIN32_NO_STATUS
#include "windows.h"
#include "winternl.h"
#include "tlhelp32.h"
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wpacked-not-aligned"
#include "dbghelp.h"
#pragma GCC diagnostic pop
#include "wine/package.h"

#define MAX_THREADS 64
#define MAX_MODULES 512
#define MAX_FRAMES 16

static DWORD target, windows_seen, modules_seen;
static MODULEENTRY32W modules[MAX_MODULES];

static void thread_count(void)
{
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    THREADENTRY32 entry = {0};
    DWORD count = 0;
    entry.dwSize = sizeof(entry);
    if (snapshot == INVALID_HANDLE_VALUE)
    { printf("state threads-error=%lu\n", GetLastError()); return; }
    if (!Thread32First(snapshot, &entry))
        printf("state threads-error=%lu\n", GetLastError());
    else do
    {
        if (entry.th32OwnerProcessID == target) ++count;
    } while (Thread32Next(snapshot, &entry));
    printf("state threads-before-attach=%lu\n", count);
    CloseHandle(snapshot);
}

static BOOL CALLBACK observe_window(HWND hwnd, LPARAM ignored)
{
    WCHAR name[128];
    RECT rect;
    DWORD pid;
    GetWindowThreadProcessId(hwnd, &pid);
    if (pid != target) return TRUE;
    if (++windows_seen > 32) return FALSE;
    if (!GetClassNameW(hwnd, name, ARRAY_SIZE(name)) || !GetWindowRect(hwnd, &rect))
    {
        printf("state window-error=%lu\n", GetLastError());
        return TRUE;
    }
    printf("state hwnd=%llx class=%s visible=%u width=%ld height=%ld\n",
           (unsigned long long)(ULONG_PTR)hwnd,
           !lstrcmpW(name, L"CalimochoCoreWindow") ? "CalimochoCoreWindow" : "other-redacted",
           IsWindowVisible(hwnd), rect.right - rect.left, rect.bottom - rect.top);
    return TRUE;
}

static void frame(DWORD tid, unsigned int index, DWORD64 pc)
{
    unsigned int i, j;
    char name[128];
    for (i = 0; i < modules_seen; ++i)
    {
        DWORD64 base = (ULONG_PTR)modules[i].modBaseAddr;
        if (pc < base || pc - base >= modules[i].modBaseSize) continue;
        for (j = 0; modules[i].szModule[j] && j < sizeof(name) - 1; ++j)
        {
            WCHAR c = modules[i].szModule[j];
            if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
                  || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-')) break;
            name[j] = c;
        }
        if (modules[i].szModule[j]) break;
        name[j] = 0;
        if (index == MAX_FRAMES)
            printf("state tid=%lu start module=%s offset=%llx\n", tid, name, pc - base);
        else printf("state tid=%lu frame=%u module=%s offset=%llx\n", tid, index, name, pc - base);
        return;
    }
    if (index == MAX_FRAMES) printf("state tid=%lu start module=unknown-redacted offset=0\n", tid);
    else printf("state tid=%lu frame=%u module=unknown-redacted offset=0\n", tid, index);
}

static void stacks(HANDLE process)
{
    HANDLE snapshot, thread;
    MODULEENTRY32W module = {0};
    THREADENTRY32 entry = {0};
    DWORD count = 0, captured = 0;
    BOOL symbols;
    DWORD module_errors = 0;
    module.dwSize = sizeof(module);
    entry.dwSize = sizeof(entry);
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, target);
    if (snapshot == INVALID_HANDLE_VALUE)
        printf("state modules-error=%lu\n", GetLastError());
    else
    {
        if (!Module32FirstW(snapshot, &module))
            printf("state modules-error=%lu\n", GetLastError());
        else do
        {
            if (modules_seen == MAX_MODULES) { printf("state modules-truncated=1\n"); break; }
            modules[modules_seen++] = module;
        } while (Module32NextW(snapshot, &module));
        CloseHandle(snapshot);
    }
    /* Empty local search path and no symbol server: unwind only local module bytes. */
    SymSetOptions(SYMOPT_DEFERRED_LOADS | SYMOPT_FAIL_CRITICAL_ERRORS | SYMOPT_NO_PROMPTS
                  | SYMOPT_IGNORE_CVREC);
    symbols = SymInitialize(process, "", FALSE);
    if (symbols)
    {
        unsigned int i;
        for (i = 0; i < modules_seen; ++i)
            if (!SymLoadModuleExW(process, NULL, modules[i].szExePath, NULL,
                                 (ULONG_PTR)modules[i].modBaseAddr, modules[i].modBaseSize, NULL, 0))
                ++module_errors;
        printf("state module-load-errors=%lu\n", module_errors);
    }
    else printf("state symbols-error=%lu\n", GetLastError());
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snapshot == INVALID_HANDLE_VALUE)
        printf("state threads-error=%lu\n", GetLastError());
    else
    {
        if (!Thread32First(snapshot, &entry))
            printf("state threads-error=%lu\n", GetLastError());
        else do
        {
            CONTEXT context = {0};
            STACKFRAME64 stack = {0};
            DWORD64 previous;
            unsigned int i;
            if (entry.th32OwnerProcessID != target) continue;
            ++count;
            if (captured++ >= MAX_THREADS) continue;
            thread = OpenThread(THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE, entry.th32ThreadID);
            if (!thread) { printf("state tid=%lu context-error=%lu\n", entry.th32ThreadID, GetLastError()); continue; }
            {
                DWORD exit_code;
                void *start_address = NULL;
                NTSTATUS query = NtQueryInformationThread(thread, ThreadQuerySetWin32StartAddress,
                                                          &start_address, sizeof(start_address), NULL);
                if (!query) frame(entry.th32ThreadID, MAX_FRAMES, (ULONG_PTR)start_address);
                else printf("state tid=%lu start-error=%lu\n", entry.th32ThreadID, (ULONG)query);
                if (GetExitCodeThread(thread, &exit_code))
                    printf("state tid=%lu alive=%u wait=unknown\n", entry.th32ThreadID, exit_code == STILL_ACTIVE);
                else printf("state tid=%lu live-error=%lu\n", entry.th32ThreadID, GetLastError());
            }
            context.ContextFlags = CONTEXT_FULL;
            if (!GetThreadContext(thread, &context))
            {
                printf("state tid=%lu context-error=%lu\n", entry.th32ThreadID, GetLastError());
                CloseHandle(thread);
                continue;
            }
            stack.AddrPC.Offset = context.Rip;
            stack.AddrFrame.Offset = context.Rbp;
            stack.AddrStack.Offset = context.Rsp;
            stack.AddrPC.Mode = stack.AddrFrame.Mode = stack.AddrStack.Mode = AddrModeFlat;
            frame(entry.th32ThreadID, 0, stack.AddrPC.Offset);
            for (i = 1; symbols && i < MAX_FRAMES; ++i)
            {
                previous = stack.AddrPC.Offset;
                SetLastError(0);
                if (!StackWalk64(IMAGE_FILE_MACHINE_AMD64, process, thread, &stack, &context,
                                 NULL, SymFunctionTableAccess64, SymGetModuleBase64, NULL))
                {
                    printf("state tid=%lu unwind-end=%lu\n", entry.th32ThreadID, GetLastError());
                    break;
                }
                if (!stack.AddrPC.Offset || stack.AddrPC.Offset == previous) break;
                frame(entry.th32ThreadID, i, stack.AddrPC.Offset);
            }
            printf("state tid=%lu frames=%u\n", entry.th32ThreadID, i);
            CloseHandle(thread);
        } while (Thread32Next(snapshot, &entry));
        CloseHandle(snapshot);
    }
    printf("state threads=%lu captured=%lu\n", count, min(count, MAX_THREADS));
    if (count > MAX_THREADS) printf("state threads-truncated=1\n");
    if (symbols) SymCleanup(process);
}

int wmain(int argc, WCHAR **argv)
{
    WCHAR *end, image[32768];
    DWORD length = ARRAY_SIZE(image), code, status, continuation;
    DWORD events = 0, continued = 0;
    HANDLE process, token = NULL;
    struct wine_package_identity identity;
    DEBUG_EVENT event;
    ULONGLONG start;
    BOOL attached = FALSE, pending = FALSE, captured = FALSE, exited = FALSE;
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4) return 2;
    target = wcstoul(argv[1], &end, 10);
    if (!target || *end) return 2;
    process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | SYNCHRONIZE, FALSE, target);
    if (!process) { printf("state open-error=%lu\n", GetLastError()); return 3; }
    if (!QueryFullProcessImageNameW(process, 0, image, &length) || lstrcmpiW(image, argv[2])
        || !OpenProcessToken(process, TOKEN_QUERY, &token))
    { printf("state identity-mismatch=1\n"); CloseHandle(process); return 4; }
    status = wine_query_package_identity(token, &identity);
    CloseHandle(token);
    if (status || !identity.verified_gamingapp || lstrcmpW(identity.app_id, argv[3]))
    { printf("state identity-mismatch=1\n"); CloseHandle(process); return 4; }
    if (!GetExitCodeProcess(process, &code) || code != STILL_ACTIVE)
    { printf("state target-not-active=1\n"); CloseHandle(process); return 5; }
    printf("state pid=%lu verified=1\n", target);
    thread_count();
    if (!EnumWindows(observe_window, 0) && windows_seen <= 32)
        printf("state enum-error=%lu\n", GetLastError());
    printf("state windows=%lu\n", min(windows_seen, 32));
    if (windows_seen > 32) printf("state windows-truncated=1\n");
    /* Detach on helper exit, including an external bounded helper termination. */
    status = DbgUiConnectToDbg();
    if (status)
    { printf("state debug-connect-error=%lu\n", status); CloseHandle(process); return 6; }
    if (!DebugSetProcessKillOnExit(FALSE))
    { printf("state debug-policy-error=%lu\n", GetLastError()); CloseHandle(process); return 6; }
    printf("state kill-on-exit=0\n");
    if (!DebugActiveProcess(target))
    { printf("state attach-error=%lu\n", GetLastError()); CloseHandle(process); return 6; }
    attached = TRUE;
    printf("state attached=1\n");
    start = GetTickCount64();
    while (GetTickCount64() - start < 5000)
    {
        if (!WaitForDebugEvent(&event, 100)) continue;
        ++events;
        pending = TRUE;
        continuation = DBG_CONTINUE;
        if (event.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT)
        {
            if (event.u.CreateProcessInfo.hFile) CloseHandle(event.u.CreateProcessInfo.hFile);
            if (event.u.CreateProcessInfo.hThread) CloseHandle(event.u.CreateProcessInfo.hThread);
            if (event.u.CreateProcessInfo.hProcess) CloseHandle(event.u.CreateProcessInfo.hProcess);
        }
        else if (event.dwDebugEventCode == CREATE_THREAD_DEBUG_EVENT && event.u.CreateThread.hThread)
            CloseHandle(event.u.CreateThread.hThread);
        else if (event.dwDebugEventCode == LOAD_DLL_DEBUG_EVENT && event.u.LoadDll.hFile)
            CloseHandle(event.u.LoadDll.hFile);
        else if (event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT) exited = TRUE;
        else if (event.dwDebugEventCode == EXCEPTION_DEBUG_EVENT)
        {
            if (event.u.Exception.ExceptionRecord.ExceptionCode == (DWORD)EXCEPTION_BREAKPOINT)
            { stacks(process); captured = TRUE; }
            else continuation = DBG_EXCEPTION_NOT_HANDLED;
        }
        if (!ContinueDebugEvent(event.dwProcessId, event.dwThreadId, continuation))
        { printf("state continue-error=%lu\n", GetLastError()); break; }
        ++continued;
        pending = FALSE;
        if (captured || exited) break;
    }
    if (pending)
    {
        if (!ContinueDebugEvent(event.dwProcessId, event.dwThreadId, DBG_EXCEPTION_NOT_HANDLED))
            printf("state continue-error=%lu\n", GetLastError());
        else ++continued;
    }
    printf("state debug-events=%lu continued=%lu\n", events, continued);
    if (attached && !DebugActiveProcessStop(target))
    { printf("state detach-error=%lu\n", GetLastError()); CloseHandle(process); return 7; }
    printf("state detached=1 stacks=%u target-exited=%u\n", captured, exited);
    CloseHandle(process);
    return captured ? 0 : 8;
}
