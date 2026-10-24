/*
 * Copyright 2026 Calimocho contributors
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winhttp.h>
#include <stdio.h>
#include <string.h>

static volatile LONG secure_failure_flags;

static void CALLBACK status_callback(HINTERNET handle, DWORD_PTR context,
                                     DWORD status, void *info, DWORD length)
{
    (void)handle;
    (void)context;
    if (status == WINHTTP_CALLBACK_STATUS_SECURE_FAILURE && length == sizeof(DWORD))
        InterlockedOr(&secure_failure_flags, *(DWORD *)info);
}

int main(int argc, char **argv)
{
    HINTERNET session = NULL, connection = NULL, request = NULL;
    DWORD status = 0, size = sizeof(status);
    const char *stage = "WinHttpOpen";
    int result = 1;
    int expired = argc == 2 && !strcmp(argv[1], "--expired-certificate");
    const WCHAR *host = expired ? L"expired.badssl.com" : L"www.microsoft.com";

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc > 2 || (argc == 2 && !expired))
    {
        printf("ERROR usage: winhttp-https-probe.exe [--expired-certificate]\n");
        return 2;
    }
    printf("HTTPS GET https://%s/ certificate_validation=enabled expected=%s\n",
           expired ? "expired.badssl.com" : "www.microsoft.com",
           expired ? "expired_certificate_rejection" : "status_200");
    session = WinHttpOpen(L"CalimochoTlsProbe/1.0", WINHTTP_ACCESS_TYPE_NO_PROXY,
                         WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!session) goto failure;
    stage = "WinHttpSetStatusCallback";
    if (WinHttpSetStatusCallback(session, status_callback,
                                WINHTTP_CALLBACK_FLAG_SECURE_FAILURE, 0)
        == WINHTTP_INVALID_STATUS_CALLBACK) goto failure;
    stage = "WinHttpSetTimeouts";
    if (!WinHttpSetTimeouts(session, 10000, 10000, 20000, 20000)) goto failure;
    stage = "WinHttpConnect";
    connection = WinHttpConnect(session, host, INTERNET_DEFAULT_HTTPS_PORT, 0);
    if (!connection) goto failure;
    stage = "WinHttpOpenRequest";
    request = WinHttpOpenRequest(connection, L"GET", L"/", NULL, WINHTTP_NO_REFERER,
                                WINHTTP_DEFAULT_ACCEPT_TYPES, WINHTTP_FLAG_SECURE);
    if (!request) goto failure;
    stage = "WinHttpSendRequest";
    if (!WinHttpSendRequest(request, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
                            WINHTTP_NO_REQUEST_DATA, 0, 0, 0)) goto failure;
    stage = "WinHttpReceiveResponse";
    if (!WinHttpReceiveResponse(request, NULL)) goto failure;
    stage = "WinHttpQueryHeaders";
    if (!WinHttpQueryHeaders(request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                             WINHTTP_HEADER_NAME_BY_INDEX, &status, &size,
                             WINHTTP_NO_HEADER_INDEX)) goto failure;
    printf("HTTPS status=%lu certificate_validation=enabled\n", (unsigned long)status);
    result = !expired && status == 200 ? 0 : 1;
    goto cleanup;
failure:
    {
        DWORD error = GetLastError();
        printf("HTTPS ERROR stage=%s win32=%lu secure_failure_flags=0x%08lx\n",
               stage, (unsigned long)error, (unsigned long)secure_failure_flags);
        if (expired && error == ERROR_WINHTTP_SECURE_FAILURE &&
            (secure_failure_flags & WINHTTP_CALLBACK_STATUS_FLAG_CERT_DATE_INVALID))
        {
            printf("HTTPS expired_certificate_rejected=1\n");
            result = 0;
        }
    }
cleanup:
    if (request) WinHttpCloseHandle(request);
    if (connection) WinHttpCloseHandle(connection);
    if (session) WinHttpCloseHandle(session);
    printf("HTTPS result=%d\n", result);
    return result;
}
