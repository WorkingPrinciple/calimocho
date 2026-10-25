import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests.test_package_context import added_file
from tools.build_uwp_overlay import REPO
from tools.port_claims_site_b import CONTEXT_FILES, port


class ClaimsSiteBTests(unittest.TestCase):
    def test_exact_unchanged_producer_artifact_is_pinned(self):
        pin = json.loads((REPO / "versions.json").read_text())["whiny_claims_site_b"]
        self.assertEqual(pin["sha256"], "2924dd6c183b944d3a177fd2f2bf96571dde92b175b123eee64a938faf4b14d6")
        self.assertEqual(hashlib.sha256((REPO / pin["path"]).read_bytes()).hexdigest(), pin["sha256"])
        self.assertEqual(pin["packaged_reference_sha256"],
                         "986c9562dcf4ac31432d401e56cd022f8a0362346cf569bb6ca6c28f532f3212")

    def test_port_preserves_context_and_rejects_changed_or_frozen_source(self):
        baseline = REPO / "build/winehq-11.20/package-uwp-status-01/source"
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            source = Path(directory) / "source"
            for relative in (*CONTEXT_FILES, "dlls/ntdll/package_claims_generated.h"):
                destination = source / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, destination)
            record = port(source)
            for relative, digest in CONTEXT_FILES.items():
                self.assertEqual(record["files"][relative], digest)
            artifact = (REPO / "patches/wine/files/package_claims_site_b_generated.h").read_bytes()
            for suffix in ("c", "h"):
                self.assertEqual((source / ("dlls/ntdll/package_claims_generated." + suffix)).read_bytes(), artifact)
            self.assertEqual(port(source), record)
            wrapper = source / "dlls/ntdll/package_claims_context.c"
            wrapper.write_text("changed context\n")
            with self.assertRaisesRegex(ValueError, "context or build seam changed"):
                port(source)
            (source.parent / "CELL021-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)

    def test_actual_context_and_generated_site_b_preserve_signed_scope_and_output_width(self):
        program = r"""
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <wchar.h>
typedef wchar_t WCHAR;
typedef void *HANDLE;
typedef intptr_t LONG_PTR;
typedef int32_t NTSTATUS;
#define NTSYSAPI
#define WINAPI
#define STATUS_SUCCESS 0
#define STATUS_NOT_FOUND ((NTSTATUS)0xc0000225)
#define ERR(...) ((void)0)
#include "wine/package.h"
static NTSTATUS status;
static struct wine_package_identity identity;
NTSTATUS wine_query_package_identity(HANDLE token, struct wine_package_identity *out)
{
    assert(token == (HANDLE)(LONG_PTR)-4);
    if (!status) *out = identity;
    return status;
}
#include "wine/whiny_context.h"
#define WHINY_NO_DLLEXPORT
#include "generated.h"
int main(void)
{
    struct { uint64_t before; PackageClaim claim; uint64_t after; } output = {11, {0,0}, 22};
    struct { uint64_t before, attributes, after; } attr = {33, UINT64_MAX, 44};
    void *self = (void *)(intptr_t)-4;
    uint64_t size = 0x88776655;
    status = 0;
    memcpy(identity.family_name, L"Microsoft.GamingApp_8wekyb3d8bbwe",
           sizeof(L"Microsoft.GamingApp_8wekyb3d8bbwe"));
    identity.verified_gamingapp = 1;
#ifdef EXPECT_OLD
    assert(RtlQueryPackageClaims(self,0,0,0,0,0,&output.claim,&attr.attributes) == (int32_t)0xc0000002);
    assert(!output.claim.Flags && !output.claim.Origin && attr.attributes == UINT64_MAX);
    return 0;
#endif
    assert(!RtlQueryPackageClaims(self,0,0,0,0,0,&output.claim,&attr.attributes));
    assert(output.claim.Flags == 5 && output.claim.Origin == 3 && attr.attributes == 3);
    assert(output.before == 11 && output.after == 22 && attr.before == 33 && attr.after == 44);
    assert(!RtlQueryPackageClaims(self,0,0,0,0,0,&output.claim,0));
    output.claim.Flags = output.claim.Origin = 0xaabbccdd; attr.attributes = UINT64_MAX;
    assert(RtlQueryPackageClaims(self,0,&size,0,0,0,&output.claim,&attr.attributes) == (int32_t)0xc0000002);
    assert(size == 0x88776655 && attr.attributes == UINT64_MAX && output.claim.Flags == 0xaabbccdd);
    assert(RtlQueryPackageClaims((void *)(intptr_t)-1,0,0,0,0,0,&output.claim,&attr.attributes) == (int32_t)0xc0000002);
    assert(RtlQueryPackageClaims(self,0,0,0,0,0,0,&attr.attributes) == (int32_t)0xc0000002);
    identity.verified_gamingapp = 0;
    assert(RtlQueryPackageClaims(self,0,0,0,0,0,&output.claim,&attr.attributes) == (int32_t)0xc0000002);
    assert(output.claim.Flags == 0xaabbccdd && attr.attributes == UINT64_MAX);
    identity.verified_gamingapp = 1; identity.family_name[0] = 'X';
    assert(RtlQueryPackageClaims(self,0,0,0,0,0,&output.claim,&attr.attributes) == (int32_t)0xc0000002);
    status = STATUS_NOT_FOUND;
    assert(RtlQueryPackageClaims(self,0,0,0,0,0,&output.claim,&attr.attributes) == STATUS_NOT_FOUND);
    assert(output.claim.Flags == 0xaabbccdd && !attr.attributes);
    status = (NTSTATUS)0xc0000022; attr.attributes = UINT64_MAX;
    assert(RtlQueryPackageClaims(self,0,0,0,0,0,&output.claim,&attr.attributes) == (int32_t)0xc0000002);
    assert(output.claim.Flags == 0xaabbccdd && attr.attributes == UINT64_MAX);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "wine").mkdir()
            for name in ("package.h", "whiny_context.h"):
                (path / "wine" / name).write_text(added_file("include/wine/" + name))
            (path / "generated.h").write_bytes((REPO / "patches/wine/files/package_claims_site_b_generated.h").read_bytes())
            (path / "test.c").write_text(program)
            command = ["/usr/bin/clang", "-std=c11", "-fshort-wchar", "-Wall", "-Wextra",
                       "-Werror", "-I" + directory, str(path / "test.c"), "-o", str(path / "test")]
            for historical in (True, False):
                if historical:
                    (path / "generated.h").write_text(added_file("dlls/ntdll/package_claims_generated.h"))
                else:
                    (path / "generated.h").write_bytes((REPO / "patches/wine/files/package_claims_site_b_generated.h").read_bytes())
                subprocess.run(command + (["-DEXPECT_OLD"] if historical else []), check=True, capture_output=True)
                subprocess.run([str(path / "test")], check=True)
