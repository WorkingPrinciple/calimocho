/* Observe only the exact admitted protocol target. SPDX-License-Identifier: LGPL-2.1-or-later */
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include "ntstatus.h"
#define WIN32_NO_STATUS
#include "windows.h"
#include "winternl.h"
#include "wine/package.h"

int wmain(int argc, WCHAR **argv)
{
    WCHAR *end, image[32768];
    unsigned long pid, seconds;
    DWORD length = ARRAY_SIZE(image), result, code;
    HANDLE process, token = NULL;
    struct wine_package_identity identity;
    if (argc != 5) return 2;
    pid = wcstoul(argv[1], &end, 10);
    if (!pid || *end) return 2;
    seconds = wcstoul(argv[4], &end, 10);
    if (!seconds || seconds > 180 || *end) return 2;
    process = OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!process)
    {
        printf("calimocho-target pid=%lu state=open-failed error=%lu\n", pid, GetLastError());
        return 3;
    }
    if (!QueryFullProcessImageNameW(process, 0, image, &length) || lstrcmpiW(image, argv[2])
        || !OpenProcessToken(process, TOKEN_QUERY, &token))
    {
        printf("calimocho-target pid=%lu state=identity-mismatch\n", pid);
        CloseHandle(process);
        return 4;
    }
    result = wine_query_package_identity(token, &identity);
    CloseHandle(token);
    if (result || !identity.verified_gamingapp || lstrcmpW(identity.app_id, argv[3]))
    {
        printf("calimocho-target pid=%lu state=identity-mismatch\n", pid);
        CloseHandle(process);
        return 4;
    }
    result = WaitForSingleObject(process, seconds * 1000);
    if (result == WAIT_OBJECT_0 && GetExitCodeProcess(process, &code))
    {
        printf("calimocho-target pid=%lu state=exited code=%lu\n", pid, code);
        CloseHandle(process);
        return 0;
    }
    printf("calimocho-target pid=%lu state=%s\n", pid,
           result == WAIT_TIMEOUT ? "bound-reached" : "wait-failed");
    CloseHandle(process);
    return 5;
}
