/* Prints the Windows version a prefix reports (REQ-155 A/B evidence).
 * Build: x86_64-w64-mingw32-gcc -O2 -Wall -Wextra -Werror -o winver_probe.exe winver_probe.c */
#include <windows.h>
#include <stdio.h>

typedef LONG (WINAPI *rtl_get_version)(OSVERSIONINFOEXW *);

int main(void)
{
    OSVERSIONINFOEXW info;
    rtl_get_version get = (rtl_get_version)(void *)GetProcAddress(GetModuleHandleW(L"ntdll.dll"),
                                                                  "RtlGetVersion");
    ZeroMemory(&info, sizeof(info));
    info.dwOSVersionInfoSize = sizeof(info);
    if (!get || get(&info))
    {
        printf("RtlGetVersion failed\n");
        return 1;
    }
    printf("RtlGetVersion %lu.%lu.%lu platform %lu product %u\n", info.dwMajorVersion,
           info.dwMinorVersion, info.dwBuildNumber, info.dwPlatformId, info.wProductType);
    return 0;
}
