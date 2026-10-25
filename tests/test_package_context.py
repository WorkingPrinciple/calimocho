"""Compile the actual patched context predicate and unchanged generated table."""

import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def added_file(name):
    lines = (ROOT / "patches/wine/0006-explicit-local-package-identity.patch").read_text().splitlines()
    start = lines.index("+++ b/" + name) + 1
    result = []
    for line in lines[start:]:
        if line.startswith("--- "):
            break
        if line.startswith("+"):
            result.append(line[1:])
    return "\n".join(result) + "\n"


class PackageContextTests(unittest.TestCase):
    def test_generated_header_is_exact_r5_artifact(self):
        self.assertEqual(hashlib.sha256(added_file(
            "dlls/ntdll/package_claims_generated.h").encode()).hexdigest(),
            "2194a9ac3f418b9af78fcfefae307faaf1260fa6b6932a85df0b8bfbffc8bb72")

    def test_context_comes_from_query_and_signed_host_metadata(self):
        compiler = shutil.which("cc")
        self.assertIsNotNone(compiler)
        harness = r"""
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
static NTSTATUS result;
static struct wine_package_identity metadata;
NTSTATUS wine_query_package_identity(HANDLE token, struct wine_package_identity *out)
{
    assert(token == (HANDLE)(LONG_PTR)-4);
    if (!result) *out = metadata;
    return result;
}
#include "wine/whiny_context.h"
#define WHINY_NO_DLLEXPORT
#include "generated.h"
int main(void)
{
    PackageClaim claim;
    uint64_t attributes;
    result = STATUS_NOT_FOUND;
    attributes = UINT64_MAX;
    assert(whiny_context_active("unpackaged"));
    assert(!whiny_context_active("packaged-gamingapp-signed"));
    assert(RtlQueryPackageClaims((HANDLE)(LONG_PTR)-4, 0,0,0,0,0,0,&attributes) == STATUS_NOT_FOUND);
    assert(!attributes);
    result = (NTSTATUS)0xc0000022;
    assert(!whiny_context_active("unpackaged"));
    assert(!whiny_context_active("packaged"));
    assert(!whiny_context_active("packaged-gamingapp-signed"));
    result = 0;
    memcpy(metadata.family_name, L"Microsoft.GamingApp_8wekyb3d8bbwe",
           sizeof(L"Microsoft.GamingApp_8wekyb3d8bbwe"));
    assert(whiny_context_active("packaged"));
    assert(!whiny_context_active("unpackaged"));
    assert(!whiny_context_active("packaged-gamingapp-signed"));
    claim.Flags = claim.Origin = 0xdeadbeef;
    assert(RtlQueryPackageClaims((HANDLE)(LONG_PTR)-4, 0,0,0,0,0,&claim,0) == (NTSTATUS)0xc0000002);
    assert(claim.Flags == 0xdeadbeef && claim.Origin == 0xdeadbeef);
    metadata.verified_gamingapp = 1;
    assert(whiny_context_active("packaged-gamingapp-signed"));
    assert(!RtlQueryPackageClaims((HANDLE)(LONG_PTR)-4, 0,0,0,0,0,&claim,0));
    assert(claim.Flags == 5 && claim.Origin == 3);
    metadata.family_name[0] = 'X';
    assert(!whiny_context_active("packaged-gamingapp-signed"));
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "wine").mkdir()
            for name in ("package.h", "whiny_context.h"):
                (path / "wine" / name).write_text(added_file("include/wine/" + name))
            (path / "generated.h").write_text(added_file("dlls/ntdll/package_claims_generated.h"))
            (path / "test.c").write_text(harness)
            subprocess.run([compiler, "-std=c11", "-fshort-wchar", "-Wall", "-Wextra", "-Werror",
                            "-I" + directory, str(path / "test.c"), "-o", str(path / "test")],
                           check=True, capture_output=True, timeout=30)
            subprocess.run([str(path / "test")], check=True, timeout=10)


if __name__ == "__main__":
    unittest.main()
