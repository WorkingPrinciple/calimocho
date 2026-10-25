/*
 * Local package activation fixture. No Store or account operations.
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include "ntstatus.h"
#define WIN32_NO_STATUS
#include "windows.h"
#include "winternl.h"
#include "appmodel.h"
#include "roapi.h"
#include "winstring.h"
#include "wine/package.h"

LONG WINAPI GetCurrentPackageFullName(UINT32 *, WCHAR *);
LONG WINAPI GetCurrentPackageFamilyName(UINT32 *, WCHAR *);
LONG WINAPI GetCurrentApplicationUserModelId(UINT32 *, WCHAR *);
LONG WINAPI GetCurrentPackageId(UINT32 *, BYTE *);
LONG WINAPI GetCurrentPackageInfo(UINT32, UINT32 *, BYTE *, UINT32 *);
LONG WINAPI GetCurrentPackagePath(UINT32 *, WCHAR *);
LONG WINAPI GetPackagePathByFullName(const WCHAR *, UINT32 *, WCHAR *);

static unsigned int failures;
#define check(test) do { if (!(test)) { \
    fprintf(stderr, "FAIL line %u: %s\n", __LINE__, #test); ++failures; } } while (0)

static void verify_graph(BOOL registered)
{
    WCHAR setting[1024], path[1024];
    UINT32 size = 0, count = 0, length = 0;
    BYTE *buffer;
    PACKAGE_INFO *packages;
    HMODULE dll;
    unsigned int (WINAPI *marker)(void);
    HSTRING classid;
    void *factory = NULL;
    static const GUID activation_factory = {0x00000035,0x0000,0x0000,{0xc0,0x00,0x00,0x00,0x00,0x00,0x00,0x46}};
    if (!GetEnvironmentVariableW(L"CALIMOCHO_PACKAGE_GRAPH", setting, ARRAY_SIZE(setting))) return;
    if (!registered)
    {
        check(GetCurrentPackageInfo(0, &size, NULL, &count) == APPMODEL_ERROR_NO_PACKAGE);
        return;
    }
    check(GetCurrentPackageInfo(0, &size, NULL, &count) == ERROR_INSUFFICIENT_BUFFER);
    check(count == 2 && size > 2 * sizeof(PACKAGE_INFO));
    buffer = malloc(size);
    if (!buffer) { check(FALSE); return; }
    check(GetCurrentPackageInfo(0, &size, buffer, &count) == ERROR_SUCCESS);
    packages = (PACKAGE_INFO *)buffer;
    check(count == 2 && !packages[0].flags && packages[1].flags == PACKAGE_PROPERTY_FRAMEWORK);
    check(GetCurrentPackagePath(&length, NULL) == ERROR_INSUFFICIENT_BUFFER);
    check(length < ARRAY_SIZE(path));
    check(GetCurrentPackagePath(&length, path) == ERROR_SUCCESS);
    check(!wcscmp(path, packages[0].path));
    length = ARRAY_SIZE(path);
    check(GetPackagePathByFullName(packages[1].packageFullName, &length, path) == ERROR_SUCCESS);
    check(!wcscmp(path, packages[1].path));
    size = 0;
    check(GetCurrentPackageInfo(PACKAGE_FILTER_DIRECT, &size, NULL, &count) == ERROR_INSUFFICIENT_BUFFER);
    check(count == 1);
    size = 0;
    check(GetCurrentPackageInfo(0x80000000, &size, NULL, &count) == ERROR_NOT_SUPPORTED);
    dll = LoadLibraryW(L"calimocho_graph_fixture.dll");
    check(dll != NULL);
    if (dll)
    {
        marker = (void *)GetProcAddress(dll, "graph_marker");
        check(marker && marker() == 0x1234abcd);
        FreeLibrary(dll);
    }
    check(WindowsCreateString(L"Calimocho.Fixture.Absent", 24, &classid) == S_OK);
    check(FAILED(RoGetActivationFactory(classid, &activation_factory, &factory)));
    WindowsDeleteString(classid);
    free(buffer);
}

static int verify_identity(BOOL packaged, BOOL registered)
{
    struct wine_package_identity identity, copy;
    HANDLE token = NULL, duplicate = NULL;
    WCHAR buffer[512];
    UINT32 length;
    LONG result;
    NTSTATUS status;
    ULONG returned = 0;
    struct { ULONG flags, origin; } claim = {0xdeadbeef, 0xdeadbeef};
    NTSTATUS (WINAPI *query_claims)(HANDLE, void *, void *, void *, void *, void *, void *, void *);
    BYTE package_id[2048];
    verify_graph(registered);

    memset(&identity, 0xa5, sizeof(identity));
    status = wine_query_package_identity((HANDLE)(LONG_PTR)-4, &identity);
    check(status == (packaged ? STATUS_SUCCESS : STATUS_NOT_FOUND));
    if (packaged) check(identity.verified_gamingapp == (unsigned int)registered);
    check(OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY | TOKEN_DUPLICATE, &token));
    if (!token) return 1;
    check(DuplicateTokenEx(token, TOKEN_QUERY, NULL, SecurityIdentification, TokenPrimary, &duplicate));
    CloseHandle(token);
    if (!duplicate) return 1;
    status = wine_query_package_identity(duplicate, &copy);
    check(status == (packaged ? STATUS_SUCCESS : STATUS_NOT_FOUND));
    if (packaged) check(!memcmp(&identity, &copy, sizeof(identity)));
    check(NtQueryInformationToken(duplicate, TokenWinePackageIdentity, &copy, 1, &returned)
          == (packaged ? STATUS_BUFFER_TOO_SMALL : STATUS_NOT_FOUND));
    if (packaged) check(returned == sizeof(copy));
    CloseHandle(duplicate);
    check(wine_query_package_identity(duplicate, &copy) == STATUS_INVALID_HANDLE);
    check(wine_query_package_identity(GetCurrentProcess(), &copy) == STATUS_OBJECT_TYPE_MISMATCH);
    check(GetCurrentPackageFullName(NULL, NULL) == ERROR_INVALID_PARAMETER);
    length = 1;
    check(GetCurrentPackageFullName(&length, NULL) == ERROR_INVALID_PARAMETER);
    length = 0;
    result = GetCurrentPackageFullName(&length, NULL);
    if (!packaged)
    {
        check(result == APPMODEL_ERROR_NO_PACKAGE);
        check(length == 0);
    }
    else
    {
        check(result == ERROR_INSUFFICIENT_BUFFER);
        check(length == lstrlenW(identity.full_name) + 1u);
        memset(buffer, 0xa5, sizeof(buffer));
        --length;
        check(GetCurrentPackageFullName(&length, buffer) == ERROR_INSUFFICIENT_BUFFER);
        check(buffer[0] == 0xa5a5);
        check(GetCurrentPackageFullName(&length, buffer) == ERROR_SUCCESS);
        check(!lstrcmpW(buffer, identity.full_name));
        check(buffer[length] == 0xa5a5);
        length = 0;
        check(GetCurrentPackageFamilyName(&length, NULL) == ERROR_INSUFFICIENT_BUFFER);
        check(GetCurrentPackageFamilyName(&length, buffer) == ERROR_SUCCESS);
        check(!lstrcmpW(buffer, identity.family_name));
        length = 0;
        check(GetCurrentApplicationUserModelId(&length, NULL) == ERROR_INSUFFICIENT_BUFFER);
        check(GetCurrentApplicationUserModelId(&length, buffer) == ERROR_SUCCESS);
        check(wcsstr(buffer, L"!") != NULL);
        length = 0;
        check(GetCurrentPackageId(&length, NULL) == ERROR_INSUFFICIENT_BUFFER);
        check(length <= sizeof(package_id));
        check(GetCurrentPackageId(&length, package_id) == ERROR_SUCCESS);
        check(((PACKAGE_ID *)package_id)->version.Major == 1);

        query_claims = (void *)GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "RtlQueryPackageClaims");
        check(query_claims != NULL);
        if (query_claims)
        {
            check(query_claims((HANDLE)(LONG_PTR)-4, NULL, NULL, NULL, NULL, NULL,
                               &claim, NULL) == STATUS_NOT_IMPLEMENTED);
            check(claim.flags == 0xdeadbeef && claim.origin == 0xdeadbeef);
        }
        {
            WCHAR executable[MAX_PATH], cmdline[MAX_PATH + 32];
            STARTUPINFOW startup = {.cb = sizeof(startup)};
            PROCESS_INFORMATION process;
            DWORD code = 0;
            check(GetModuleFileNameW(NULL, executable, MAX_PATH) > 0);
            lstrcpyW(cmdline, L"\"");
            lstrcatW(cmdline, executable);
            lstrcatW(cmdline, L"\" --verify-plain-child");
            if (CreateProcessW(executable, cmdline, NULL, NULL, FALSE, 0, NULL, NULL,
                               &startup, &process))
            {
                if (WaitForSingleObject(process.hProcess, 5000) != WAIT_OBJECT_0)
                {
                    check(FALSE);
                    TerminateProcess(process.hProcess, 2);
                    WaitForSingleObject(process.hProcess, 1000);
                }
                check(GetExitCodeProcess(process.hProcess, &code) && code == 19);
                CloseHandle(process.hThread);
                CloseHandle(process.hProcess);
            }
            else check(FALSE);
        }
    }
    printf("package fixture packaged=%u failures=%u\n", packaged, failures);
    return failures ? 1 : 0;
}

static void diagnostic_text(const char *key, const WCHAR *value)
{
    char buffer[65536];
    if (!value) value = L"";
    if (!WideCharToMultiByte(CP_UTF8, 0, value, -1, buffer, sizeof(buffer), NULL, NULL))
        strcpy(buffer, "<UTF-8 conversion failed>");
    printf("calimocho-activation %s %s\n", key, buffer);
    fflush(stdout);
}

static void diagnostic_time(const char *key)
{
    SYSTEMTIME time;
    GetSystemTime(&time);
    printf("calimocho-activation %s %04u-%02u-%02uT%02u:%02u:%02u.%03uZ\n", key,
           time.wYear, time.wMonth, time.wDay, time.wHour, time.wMinute,
           time.wSecond, time.wMilliseconds);
    fflush(stdout);
}

static int activate(const WCHAR *blob_path, const WCHAR *executable, BOOL fixture, BOOL registered,
                    BOOL diagnostic)
{
    struct wine_package_identity package;
    struct { SIZE_T TotalLength; PS_ATTRIBUTE Attributes[2]; } attributes;
    PRTL_USER_PROCESS_PARAMETERS params = NULL;
    PS_CREATE_INFO create_info;
    UNICODE_STRING image, command;
    HANDLE file, process = NULL, thread = NULL, output = NULL, token = NULL;
    WCHAR *environment = NULL;
    DWORD read, extra;
    BYTE byte;
    WCHAR cmdline[32768];
    NTSTATUS status;
    ULONGLONG started = GetTickCount64();
    DWORD wait_result = WAIT_FAILED;

    file = CreateFileW(blob_path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (file == INVALID_HANDLE_VALUE) return 2;
    if (!ReadFile(file, &package, sizeof(package), &read, NULL) || read != sizeof(package)
        || !ReadFile(file, &byte, 1, &extra, NULL) || extra)
    {
        CloseHandle(file);
        return 2;
    }
    CloseHandle(file);
    if (package.version != WINE_PACKAGE_VERSION || package.size != sizeof(package)) return 2;
    if (lstrlenW(executable) > 16000) return 2;
    lstrcpyW(cmdline, L"\"");
    lstrcatW(cmdline, executable);
    lstrcatW(cmdline, fixture ? (registered ? L"\" --verify-host-registered" :
                                L"\" --verify-packaged") : L"\"");
    if ((status = RtlDosPathNameToNtPathName_U_WithStatus(executable, &image, NULL, NULL))) return 2;
    RtlInitUnicodeString(&command, cmdline);
    if (diagnostic)
    {
        UNICODE_STRING name, value;
        status = RtlCreateEnvironment(TRUE, &environment);
        RtlInitUnicodeString(&name, L"WINEDEBUG");
        RtlInitUnicodeString(&value,
            L"err+all,trace+process,trace+loaddll,trace+sync,trace+combase,fixme+combase,trace+pkgactivate,trace+pkglaunch,trace+pkgcore,trace+pkgwindow,+pid,+tid");
        if (!status) status = RtlSetEnvironmentVariable(&environment, &name, &value);
        if (status)
        {
            fprintf(stderr, "child diagnostic environment failed NTSTATUS=%08lx\n", status);
            if (environment) RtlDestroyEnvironment(environment);
            RtlFreeUnicodeString(&image);
            return 2;
        }
        {
            WCHAR parent_debug[128] = {0};
            GetEnvironmentVariableW(L"WINEDEBUG", parent_debug, 128);
            diagnostic_text("parent_winedebug", parent_debug);
            diagnostic_text("child_winedebug", value.Buffer);
        }
    }
    status = RtlCreateProcessParametersEx(&params, &image, NULL, NULL, &command, environment,
                                         NULL, NULL, NULL, NULL, PROCESS_PARAMS_FLAG_NORMALIZED);
    if (status)
    {
        if (environment) RtlDestroyEnvironment(environment);
        RtlFreeUnicodeString(&image);
        return 2;
    }
    if (diagnostic)
    {
        /* Child output goes to the host collector's redacted stderr stream.
         * The helper alone writes authoritative metadata to stdout. */
        if (!DuplicateHandle(GetCurrentProcess(), GetStdHandle(STD_ERROR_HANDLE),
                             GetCurrentProcess(), &output, 0, TRUE, DUPLICATE_SAME_ACCESS))
        {
            fprintf(stderr, "child diagnostic handle failed error=%lu\n", GetLastError());
            RtlDestroyProcessParameters(params);
            RtlDestroyEnvironment(environment);
            RtlFreeUnicodeString(&image);
            return 2;
        }
        params->hStdOutput = params->hStdError = output;
        params->hStdInput = NULL;
        params->ConsoleHandle = NtCurrentTeb()->Peb->ProcessParameters->ConsoleHandle;
        params->dwFlags |= STARTF_USESTDHANDLES;
        diagnostic_text("image", image.Buffer);
        diagnostic_text("command", command.Buffer);
        diagnostic_text("cwd", params->CurrentDirectory.DosPath.Buffer);
        diagnostic_time("create_utc");
    }
    memset(&attributes, 0, sizeof(attributes));
    attributes.TotalLength = sizeof(attributes);
    attributes.Attributes[0].Attribute = PS_ATTRIBUTE_IMAGE_NAME;
    attributes.Attributes[0].Size = image.Length;
    attributes.Attributes[0].ValuePtr = image.Buffer;
    attributes.Attributes[1].Attribute = PS_ATTRIBUTE_WINE_PACKAGE;
    attributes.Attributes[1].Size = sizeof(package);
    attributes.Attributes[1].ValuePtr = &package;
    memset(&create_info, 0, sizeof(create_info));
    create_info.Size = sizeof(create_info);
    status = NtCreateUserProcess(&process, &thread, PROCESS_ALL_ACCESS, THREAD_ALL_ACCESS,
                                 NULL, NULL, diagnostic ? PROCESS_CREATE_FLAGS_INHERIT_HANDLES : 0,
                                 THREAD_CREATE_FLAGS_CREATE_SUSPENDED,
                                 params, &create_info, (PS_ATTRIBUTE_LIST *)&attributes);
    if (output) CloseHandle(output);
    RtlDestroyProcessParameters(params);
    if (environment) RtlDestroyEnvironment(environment);
    RtlFreeUnicodeString(&image);
    if (diagnostic) printf("calimocho-activation create_status %08lx\n", status);
    if (status)
    {
        fprintf(stderr, "explicit package activation failed NTSTATUS=%08lx\n", status);
        return 2;
    }
    if (diagnostic)
    {
        struct wine_package_identity bound;
        printf("calimocho-activation child_pid %lu\n", GetProcessId(process));
        if (!OpenProcessToken(process, TOKEN_QUERY, &token))
            status = STATUS_ACCESS_DENIED;
        else
        {
            status = wine_query_package_identity(token, &bound);
            CloseHandle(token);
        }
        printf("calimocho-activation token_status %08lx\n", status);
        if (!status)
        {
            diagnostic_text("full_name", bound.full_name);
            diagnostic_text("family_name", bound.family_name);
            diagnostic_text("app_id", bound.app_id);
            printf("calimocho-activation verified_gamingapp %u\n", bound.verified_gamingapp);
        }
        if (status)
        {
            TerminateProcess(process, 2);
            WaitForSingleObject(process, 5000);
            CloseHandle(thread);
            CloseHandle(process);
            return 2;
        }
    }
    status = NtResumeThread(thread, NULL);
    if (diagnostic)
    {
        printf("calimocho-activation resume_status %08lx\n", status);
        fflush(stdout);
    }
    CloseHandle(thread);
    if (!status) wait_result = WaitForSingleObject(process, fixture ? 10000 : 45000);
    if (diagnostic) printf("calimocho-activation wait_result %lu\n", wait_result);
    if (status || wait_result != WAIT_OBJECT_0)
    {
        if (diagnostic)
        {
            printf("calimocho-activation still_running %u\n", wait_result == WAIT_TIMEOUT);
            diagnostic_time("termination_requested_utc");
        }
        TerminateProcess(process, 2);
        WaitForSingleObject(process, 5000);
        if (!status) status = STATUS_TIMEOUT;
    }
    if (!GetExitCodeProcess(process, &extra))
    {
        fprintf(stderr, "child exit query failed error=%lu\n", GetLastError());
        extra = 2;
        status = STATUS_UNSUCCESSFUL;
    }
    if (diagnostic)
    {
        FILETIME creation, exit, kernel, user;
        SYSTEMTIME time;
        if (WaitForSingleObject(process, 0) == WAIT_OBJECT_0 &&
            GetProcessTimes(process, &creation, &exit, &kernel, &user) &&
            FileTimeToSystemTime(&exit, &time))
            printf("calimocho-activation exit_utc %04u-%02u-%02uT%02u:%02u:%02u.%03uZ\n",
                   time.wYear, time.wMonth, time.wDay, time.wHour, time.wMinute,
                   time.wSecond, time.wMilliseconds);
        diagnostic_time("exit_observed_utc");
        printf("calimocho-activation exit_code %lu\n", extra);
        printf("calimocho-activation elapsed_ms %llu\n", GetTickCount64() - started);
        fflush(stdout);
    }
    CloseHandle(process);
    if (status) return 2;
    if (fixture)
    {
        fprintf(stdout, "registered child exit=%lu (expected 17)\n", extra);
        return extra == 17 ? 0 : 1;
    }
    return extra;
}

int wmain(int argc, WCHAR **argv)
{
    if (argc == 2 && !lstrcmpW(argv[1], L"--verify-packaged")) return verify_identity(TRUE, FALSE) ? 1 : 17;
    if (argc == 2 && !lstrcmpW(argv[1], L"--verify-host-registered")) return verify_identity(TRUE, TRUE) ? 1 : 17;
    if (argc == 2 && !lstrcmpW(argv[1], L"--verify-plain-child")) return verify_identity(FALSE, FALSE) ? 1 : 19;
    if (argc == 2 && !lstrcmpW(argv[1], L"--verify-plain")) return verify_identity(FALSE, FALSE);
    if (argc == 4 && !lstrcmpW(argv[1], L"--activate")) return activate(argv[2], argv[3], FALSE, FALSE, FALSE);
    if (argc == 4 && !lstrcmpW(argv[1], L"--activate-fixture")) return activate(argv[2], argv[3], TRUE, FALSE, FALSE);
    if (argc == 4 && !lstrcmpW(argv[1], L"--activate-registered-fixture")) return activate(argv[2], argv[3], TRUE, TRUE, FALSE);
    if (argc == 4 && !lstrcmpW(argv[1], L"--activate-diagnostic")) return activate(argv[2], argv[3], FALSE, FALSE, TRUE);
    if (argc == 4 && !lstrcmpW(argv[1], L"--activate-diagnostic-fixture")) return activate(argv[2], argv[3], TRUE, FALSE, TRUE);
    if (argc == 4 && !lstrcmpW(argv[1], L"--activate-diagnostic-registered-fixture")) return activate(argv[2], argv[3], TRUE, TRUE, TRUE);
    fputs("Usage: package-activation-probe --verify-plain | --activate IDENTITY.bin EXE\n", stderr);
    return 2;
}
