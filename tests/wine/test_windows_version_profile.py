"""Compile Wine's real Windows version tables without starting Wine (REQ-155).

Usage: python3 tests/wine/test_windows_version_profile.py <patched wine-11.20 source>

The win11-24h2 profile (patch 0019) must exist in both places Wine keeps
Windows versions: ntdll's version table (what RtlGetVersion returns when the
profile is chosen by name) and winecfg's table (what `winecfg /v` writes to
HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion, which ntdll then reads).
Without the patch both tests fail.
"""

import argparse
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = None


def block(source, start, end):
    begin = source.index(start)
    return source[begin:source.index(end, begin) + len(end)]


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


PRELUDE = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
typedef wchar_t WCHAR;
typedef unsigned int DWORD, ULONG;
typedef unsigned short WORD, USHORT;
typedef unsigned char UCHAR;
typedef int BOOL;
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define MAKEWORD(lo, hi) ((WORD)(((lo) & 0xff) | (((hi) & 0xff) << 8)))
#define VER_PLATFORM_WIN32s 0
#define VER_PLATFORM_WIN32_WINDOWS 1
#define VER_PLATFORM_WIN32_NT 2
#define VER_SUITE_SINGLEUSERTS 0x100
#define VER_NT_WORKSTATION 1
#define VER_NT_SERVER 3
#include <stdarg.h>
/* Wine's wide printf treats %s as a wide string, like msvcrt; the host needs %ls. */
static int wine_swprintf(WCHAR *buffer, size_t size, const WCHAR *format, ...)
{
    WCHAR fixed[128];
    size_t j = 0;
    va_list args;
    int ret;
    for (size_t i = 0; format[i] && j < ARRAY_SIZE(fixed) - 2; i++)
    {
        fixed[j++] = format[i];
        if (format[i] == L'%' && format[i + 1] == L's') fixed[j++] = L'l';
    }
    fixed[j] = 0;
    va_start(args, format);
    ret = vswprintf(buffer, size, fixed, args);
    va_end(args);
    return ret;
}
#define swprintf wine_swprintf
"""


class WindowsVersionProfile(unittest.TestCase):
    def compile_run(self, body):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "fixture.c"
            executable = Path(temporary) / "fixture"
            source.write_text(PRELUDE + body)
            subprocess.run(["cc", "-std=c11", "-Wall", "-Werror", "-Wno-unused-function",
                            "-Wno-unused-variable", str(source), "-o", str(executable)], check=True)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ntdll_version_table(self):
        # REQ-155: RtlGetVersion/GetVersionEx report 10.0.26100 for "win11-24h2".
        ntdll = (ROOT / "dlls/ntdll/version.c").read_text()
        self.compile_run("\n".join([
            "typedef struct { ULONG dwOSVersionInfoSize, dwMajorVersion, dwMinorVersion, "
            "dwBuildNumber, dwPlatformId; WCHAR szCSDVersion[128]; USHORT wServicePackMajor, "
            "wServicePackMinor, wSuiteMask; UCHAR wProductType, wReserved; } RTL_OSVERSIONINFOEXW;",
            block(ntdll, "typedef enum", "} WINDOWS_VERSION;"),
            block(ntdll, "static const RTL_OSVERSIONINFOEXW VersionData", "\n};"),
            block(ntdll, "static const struct { WCHAR name[12]; WINDOWS_VERSION ver; } version_names",
                  "\n};"),
            r"""
int main(void)
{
    for (unsigned i = 0; i < ARRAY_SIZE(version_names); i++)
    {
        if (wcscmp(version_names[i].name, L"win11-24h2")) continue;
        const RTL_OSVERSIONINFOEXW *v = &VersionData[version_names[i].ver];
        assert(v->dwMajorVersion == 10 && v->dwMinorVersion == 0);
        assert(v->dwBuildNumber == 26100);
        assert(v->dwPlatformId == VER_PLATFORM_WIN32_NT);
        assert(v->wProductType == VER_NT_WORKSTATION);
        /* the existing profiles are unchanged */
        for (unsigned j = 0; j < ARRAY_SIZE(version_names); j++)
        {
            if (!wcscmp(version_names[j].name, L"win10"))
                assert(VersionData[version_names[j].ver].dwBuildNumber == 19045);
            if (!wcscmp(version_names[j].name, L"win11"))
                assert(VersionData[version_names[j].ver].dwBuildNumber == 22000);
        }
        return 0;
    }
    printf("no win11-24h2 entry in ntdll's version table\n");
    return 1;
}
"""]))

    def test_winecfg_registry_values(self):
        # REQ-155: `winecfg /v win11-24h2` writes CurrentBuild, CurrentBuildNumber, UBR,
        # DisplayVersion=24H2 and ProductName, and switching back removes DisplayVersion.
        winecfg = (ROOT / "programs/winecfg/appdefaults.c").read_text()
        writer = re.sub(r"\bapply\(\);", "", function(winecfg, "static void set_winver("))
        self.compile_run("\n".join([
            block(winecfg, "struct win_version\n{", "\n};"),
            block(winecfg, "static const struct win_version win_versions[]", "\n};"),
            block(winecfg, "static const WCHAR szKey9x[]", ";"),
            block(winecfg, "static const WCHAR szKeyNT[]", ";"),
            block(winecfg, "static const WCHAR szKeyProdNT[]", ";"),
            r"""
typedef void *HKEY;
#define HKEY_LOCAL_MACHINE ((HKEY)1)
static HKEY config_key = (HKEY)2;
static const WCHAR *keypath(const WCHAR *p) { return p; }
static struct { WCHAR name[64]; WCHAR value[64]; DWORD dword; int kind; } values[64];
static unsigned count;
static int touched_program_files;
static void record(const WCHAR *key, const WCHAR *name, const WCHAR *value, DWORD dword, int kind)
{
    if (name && wcsstr(name, L"FilesDir")) touched_program_files = 1;
    if (name && wcsstr(name, L"W6432")) touched_program_files = 1;
    if (wcscmp(key, szKeyNT)) return;
    for (unsigned i = 0; i < count; i++)
        if (!wcscmp(values[i].name, name)) { count--; values[i] = values[count]; break; }
    if (!kind) return;
    wcscpy(values[count].name, name);
    if (value) wcscpy(values[count].value, value);
    values[count].dword = dword;
    values[count++].kind = kind;
}
static void set_reg_key(HKEY root, const WCHAR *key, const WCHAR *name, const WCHAR *value)
{ (void)root; record(key, name, value, 0, value ? 1 : 0); }
static void set_reg_key_dword(HKEY root, const WCHAR *key, const WCHAR *name, DWORD value)
{ (void)root; record(key, name, NULL, value, 2); }
static const WCHAR *string(const WCHAR *name)
{
    for (unsigned i = 0; i < count; i++)
        if (values[i].kind == 1 && !wcscmp(values[i].name, name)) return values[i].value;
    return NULL;
}
static int dword(const WCHAR *name, DWORD *out)
{
    for (unsigned i = 0; i < count; i++)
        if (values[i].kind == 2 && !wcscmp(values[i].name, name)) { *out = values[i].dword; return 1; }
    return 0;
}
static const struct win_version *find(const WCHAR *name)
{
    for (unsigned i = 0; i < ARRAY_SIZE(win_versions); i++)
        if (!wcscmp(win_versions[i].szVersion, name)) return &win_versions[i];
    return NULL;
}
""",
            writer,
            r"""
int main(void)
{
    const struct win_version *profile = find(L"win11-24h2");
    DWORD value;
    if (!profile) { printf("no win11-24h2 entry in winecfg's version table\n"); return 1; }
    set_winver(profile);
    assert(string(L"CurrentBuild") && !wcscmp(string(L"CurrentBuild"), L"26100"));
    assert(string(L"CurrentBuildNumber") && !wcscmp(string(L"CurrentBuildNumber"), L"26100"));
    assert(string(L"DisplayVersion") && !wcscmp(string(L"DisplayVersion"), L"24H2"));
    assert(string(L"ReleaseId") && !wcscmp(string(L"ReleaseId"), L"2009"));
    assert(string(L"ProductName") && !wcscmp(string(L"ProductName"), L"Windows 10 Pro"));
    assert(dword(L"UBR", &value) && value == 4652);
    assert(dword(L"CurrentMajorVersionNumber", &value) && value == 10);
    assert(dword(L"CurrentMinorVersionNumber", &value) && value == 0);
    /* The profile never writes ProgramFilesDir, CommonFilesDir or the W6432 values;
       wine.inf owns them as REG_SZ (REQ-155 review, COR-352 evidence). */
    assert(!touched_program_files);
    set_winver(find(L"win10"));
    assert(!wcscmp(string(L"CurrentBuildNumber"), L"19045"));
    assert(!string(L"DisplayVersion") && !string(L"ReleaseId"));
    assert(!wcscmp(string(L"ProductName"), L"Microsoft Windows 10"));
    return 0;
}
"""]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    ROOT = args.source.resolve()
    unittest.main(argv=[__file__])
