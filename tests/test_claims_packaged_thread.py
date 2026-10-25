import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.test_package_context import added_file
from tools.build_uwp_overlay import REPO
from tools.port_claims_thread_token import PACKAGED_DIGEST


class ClaimsPackagedThreadTests(unittest.TestCase):
    def test_unchanged_r9_actual_wrapper_context_outputs_and_unknown_failures(self):
        pin = json.loads((REPO / "versions.json").read_text())["whiny_claims_packaged_thread"]
        artifact = (REPO / pin["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(artifact).hexdigest(), PACKAGED_DIGEST)
        self.assertEqual(pin["sha256"], PACKAGED_DIGEST)
        self.assertEqual(pin["packaged_reference_sha256"],
                         "0a5fee773716fc80d0661f08bb2a27602d38d13ba713eed07d7889306389d07b")
        program = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include <stdarg.h>
typedef wchar_t WCHAR;
typedef void *HANDLE;
typedef intptr_t LONG_PTR;
typedef int32_t NTSTATUS;
typedef int LONG;
typedef unsigned int UINT;
typedef int BOOL;
#define NTSYSAPI
#define WINAPI
#define STATUS_SUCCESS 0
#define STATUS_NOT_FOUND ((NTSTATUS)0xc0000225)
#define STATUS_NOT_IMPLEMENTED ((NTSTATUS)0xc0000002)
#define ERR(...) ((void)0)
#define WINE_DEFAULT_DEBUG_CHANNEL(x)
#define WINE_DECLARE_DEBUG_CHANNEL(x)
#define TRACE_ON(x) 1
#define TRACE_(x) capture
static char captured[512];
static void capture(const char *format, ...)
{
    va_list args; va_start(args,format);
    vsnprintf(captured,sizeof(captured),format,args); va_end(args);
}
static LONG InterlockedIncrement(LONG *value) { return ++*value; }
BOOL __wine_pkg_diagnostic_active(void) { return 1; }
#include "wine/package.h"
static NTSTATUS status;
static struct wine_package_identity identity;
NTSTATUS wine_query_package_identity(HANDLE token, struct wine_package_identity *out)
{
    assert(token == (HANDLE)(LONG_PTR)-4);
    if (!status) *out = identity;
    return status;
}
#include "wrapper.c"
int main(void)
{
    struct { uint64_t before; PackageClaim claim; uint64_t after; } out = {11,{7,8},22};
    struct { uint64_t before, value, after; } attr = {33,UINT64_MAX,44};
    void *token = (void *)(intptr_t)-6;
    uint64_t size = 99;
    memcpy(identity.family_name,L"Microsoft.GamingApp_8wekyb3d8bbwe",
           sizeof(L"Microsoft.GamingApp_8wekyb3d8bbwe"));
    identity.verified_gamingapp = 1;
    assert(!RtlQueryPackageClaims(token,0,0,0,0,0,&out.claim,&attr.value));
    assert(out.claim.Flags == 5 && out.claim.Origin == 3 && attr.value == 3);
    assert(out.before == 11 && out.after == 22 && attr.before == 33 && attr.after == 44);
    assert(strstr(captured,"handle=thread-effective-token presence=60 unpackaged=0 gamingapp=1 result=00000000"));
    out.claim.Flags = 7; out.claim.Origin = 8;
    assert(!RtlQueryPackageClaims(token,0,0,0,0,0,&out.claim,0));
    assert(out.claim.Flags == 5 && out.claim.Origin == 3);
    assert(!RtlQueryPackageClaims(token,0,0,0,0,0,0,0));
    out.claim.Flags = 7; out.claim.Origin = 8; attr.value = UINT64_MAX;
    assert(RtlQueryPackageClaims(token,0,&size,0,0,0,&out.claim,&attr.value) == STATUS_NOT_IMPLEMENTED);
    assert(out.claim.Flags == 7 && out.claim.Origin == 8 && attr.value == UINT64_MAX && size == 99);
    assert(RtlQueryPackageClaims(token,0,0,0,0,0,0,&attr.value) == STATUS_NOT_IMPLEMENTED);
    assert(RtlQueryPackageClaims((void *)(intptr_t)-1,0,0,0,0,0,&out.claim,&attr.value) == STATUS_NOT_IMPLEMENTED);
    identity.verified_gamingapp = 0;
    assert(RtlQueryPackageClaims(token,0,0,0,0,0,&out.claim,&attr.value) == STATUS_NOT_IMPLEMENTED);
    identity.verified_gamingapp = 1; identity.family_name[0] = 'X';
    assert(RtlQueryPackageClaims(token,0,0,0,0,0,&out.claim,&attr.value) == STATUS_NOT_IMPLEMENTED);
    status = STATUS_NOT_FOUND;
    assert(RtlQueryPackageClaims(token,0,0,0,0,0,&out.claim,&attr.value) == STATUS_NOT_FOUND);
    assert(out.claim.Flags == 7 && out.claim.Origin == 8 && !attr.value);
    assert(strstr(captured,"unpackaged=1 gamingapp=0 result=c0000225"));
    status = (NTSTATUS)0xc0000022; attr.value = UINT64_MAX;
    assert(RtlQueryPackageClaims(token,0,0,0,0,0,&out.claim,&attr.value) == STATUS_NOT_IMPLEMENTED);
    assert(out.claim.Flags == 7 && out.claim.Origin == 8 && attr.value == UINT64_MAX);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "wine").mkdir()
            for name in ("ntstatus.h", "windef.h", "winternl.h", "wine/debug.h"):
                (path / name).write_text("")
            for name in ("package.h", "whiny_context.h"):
                (path / "wine" / name).write_text(added_file("include/wine/" + name))
            (path / "package_claims_generated.h").write_bytes(artifact)
            (path / "wrapper.c").write_bytes((REPO / "patches/wine/files/package_claims_context_diagnostics.c").read_bytes())
            (path / "test.c").write_text(program)
            subprocess.run(["/usr/bin/clang", "-D_WIN64", "-std=c11", "-fshort-wchar", "-Wall", "-Wextra",
                            "-Werror", "-I" + directory, str(path / "test.c"), "-o", str(path / "test")],
                           check=True, capture_output=True)
            subprocess.run([str(path / "test")], check=True)
