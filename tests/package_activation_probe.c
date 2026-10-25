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
#include "wine/package.h"

LONG WINAPI GetCurrentPackageFullName(UINT32 *, WCHAR *);
LONG WINAPI GetCurrentPackageFamilyName(UINT32 *, WCHAR *);
LONG WINAPI GetCurrentApplicationUserModelId(UINT32 *, WCHAR *);
LONG WINAPI GetCurrentPackageId(UINT32 *, BYTE *);

static unsigned int failures;
#define check(test) do { if (!(test)) { \
    fprintf(stderr, "FAIL line %u: %s\n", __LINE__, #test); ++failures; } } while (0)

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

    memset(&identity, 0xa5, sizeof(identity));
    status = wine_query_package_identity((HANDLE)(LONG_PTR)-4, &identity);
    check(status == (packaged ? STATUS_SUCCESS : STATUS_NOT_FOUND));
    if (packaged) check(identity.verified_gamingapp == registered);
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
        check(length == lstrlenW(identity.full_name) + 1);
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
            STARTUPINFOW startup = {sizeof(startup)};
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

static int activate(const WCHAR *blob_path, const WCHAR *executable, BOOL fixture, BOOL registered)
{
    struct wine_package_identity package;
    struct { SIZE_T TotalLength; PS_ATTRIBUTE Attributes[2]; } attributes;
    PRTL_USER_PROCESS_PARAMETERS params = NULL;
    PS_CREATE_INFO create_info;
    UNICODE_STRING image, command;
    HANDLE file, process = NULL, thread = NULL;
    DWORD read, extra;
    BYTE byte;
    WCHAR cmdline[32768];
    NTSTATUS status;

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
    status = RtlCreateProcessParametersEx(&params, &image, NULL, NULL, &command, NULL,
                                         NULL, NULL, NULL, NULL, PROCESS_PARAMS_FLAG_NORMALIZED);
    if (status)
    {
        RtlFreeUnicodeString(&image);
        return 2;
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
                                 NULL, NULL, 0, THREAD_CREATE_FLAGS_CREATE_SUSPENDED,
                                 params, &create_info, (PS_ATTRIBUTE_LIST *)&attributes);
    RtlDestroyProcessParameters(params);
    RtlFreeUnicodeString(&image);
    if (status)
    {
        fprintf(stderr, "explicit package activation failed NTSTATUS=%08lx\n", status);
        return 2;
    }
    status = NtResumeThread(thread, NULL);
    CloseHandle(thread);
    if (!status && WaitForSingleObject(process, fixture ? 10000 : 45000) != WAIT_OBJECT_0)
    {
        TerminateProcess(process, 2);
        WaitForSingleObject(process, 5000);
        status = STATUS_TIMEOUT;
    }
    if (status || !GetExitCodeProcess(process, &extra)) extra = 2;
    CloseHandle(process);
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
    if (argc == 4 && !lstrcmpW(argv[1], L"--activate")) return activate(argv[2], argv[3], FALSE, FALSE);
    if (argc == 4 && !lstrcmpW(argv[1], L"--activate-fixture")) return activate(argv[2], argv[3], TRUE, FALSE);
    if (argc == 4 && !lstrcmpW(argv[1], L"--activate-registered-fixture")) return activate(argv[2], argv[3], TRUE, TRUE);
    fputs("Usage: package-activation-probe --verify-plain | --activate IDENTITY.bin EXE\n", stderr);
    return 2;
}
