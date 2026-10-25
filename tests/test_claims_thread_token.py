import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.test_package_context import added_file
from tools.build_uwp_overlay import REPO
from tools.diagnose_package_activation import CallDiagnostics
from tools.port_claims_thread_token import DIGEST


class ClaimsThreadTokenTests(unittest.TestCase):
    def test_exact_r8_pin_and_actual_wrapper_context_status_and_canaries(self):
        pin = json.loads((REPO / "versions.json").read_text())["whiny_claims_thread_token"]
        artifact = (REPO / pin["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(artifact).hexdigest(), DIGEST)
        self.assertEqual(pin["sha256"], DIGEST)
        harness = r"""
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
    int i;
    status = STATUS_NOT_FOUND;
    assert(RtlQueryPackageClaims(token,0,0,0,0,0,&out.claim,&attr.value) == STATUS_NOT_FOUND);
    assert(out.claim.Flags == 7 && out.claim.Origin == 8 && !attr.value);
    assert(strstr(captured,"handle=thread-effective-token presence=60 unpackaged=1 gamingapp=0 result=c0000225"));
    assert(out.before == 11 && out.after == 22 && attr.before == 33 && attr.after == 44);
    assert(RtlQueryPackageClaims(token,0,0,0,0,0,0,0) == STATUS_NOT_FOUND);
    status = 0;
    memcpy(identity.family_name,L"Microsoft.GamingApp_8wekyb3d8bbwe",
           sizeof(L"Microsoft.GamingApp_8wekyb3d8bbwe"));
    identity.verified_gamingapp = 1;
    attr.value = UINT64_MAX;
    assert(RtlQueryPackageClaims(token,0,0,0,0,0,&out.claim,&attr.value) == STATUS_NOT_IMPLEMENTED);
    assert(out.claim.Flags == 7 && out.claim.Origin == 8 && attr.value == UINT64_MAX);
    assert(strstr(captured,"handle=thread-effective-token presence=60 unpackaged=0 gamingapp=1 result=c0000002"));
    assert(!RtlQueryPackageClaims((void *)(intptr_t)-4,0,0,0,0,0,&out.claim,&attr.value));
    assert(out.claim.Flags == 5 && out.claim.Origin == 3 && attr.value == 3);
    identity.verified_gamingapp = 0;
    assert(RtlQueryPackageClaims(token,0,0,0,0,0,&out.claim,&attr.value) == STATUS_NOT_IMPLEMENTED);
    assert(strstr(captured,"unpackaged=0 gamingapp=0"));
    for(i=0;i<124;i++) RtlQueryPackageClaims(token,0,0,0,0,0,0,0);
    assert(!strcmp(captured,"claims-context limited=1\n"));
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
            (path / "test.c").write_text(harness)
            subprocess.run(["/usr/bin/clang", "-D_WIN64", "-std=c11", "-fshort-wchar", "-Wall", "-Wextra",
                            "-Werror", "-I" + directory, str(path / "test.c"), "-o", str(path / "test")],
                           check=True, capture_output=True)
            subprocess.run([str(path / "test")], check=True)

    def test_collector_admits_only_fixed_grammar_in_run_and_reports_losses(self):
        calls = CallDiagnostics()
        message = "claims-context handle=thread-effective-token presence=60 unpackaged=0 gamingapp=1 result=c0000002"
        calls.observe(256,260,"pkgstatus","diagnostic_claims_context",message)
        self.assertEqual(len(calls.claims_context),0)
        calls.running.add(256)
        for _ in range(130):
            calls.observe(256,260,"pkgstatus","diagnostic_claims_context",message)
        self.assertEqual(len(calls.claims_context),128)
        row = calls.claims_context[-1]
        self.assertEqual(row["optional_pointer_presence"],96)
        self.assertTrue(row["packaged_gamingapp_signed"])
        self.assertFalse(row["unpackaged"])
        self.assertEqual(calls.claims_context_count,130)
        calls.observe(256,260,"pkgstatus","diagnostic_claims_context",message+" address=private")
        self.assertEqual(calls.claims_context_count,130)
        calls.observe(256,260,"pkgstatus","diagnostic_claims_context","claims-context limited=1")
        self.assertIn(256,calls.claims_context_limited)
