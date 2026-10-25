"""Functional source-only checks; never loads Wine or a process token."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/wine/0005-query-package-claims-errors.patch"


class PackageClaimsTests(unittest.TestCase):
    def test_export_has_eight_abi_arguments(self):
        self.assertIn(
            "+@ stdcall RtlQueryPackageClaims(long ptr ptr ptr ptr ptr ptr ptr)",
            PATCH.read_text(),
        )

    def test_actual_candidate_function_error_and_output_contract(self):
        added = "\n".join(line[1:] for line in PATCH.read_text().splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
        function = added[added.index("NTSTATUS WINAPI"): ]
        compiler = shutil.which("cc")
        self.assertIsNotNone(compiler, "An installed C compiler is required")
        harness = r"""
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef void *HANDLE;
typedef uint16_t WCHAR;
typedef size_t SIZE_T;
typedef struct { unsigned char bytes[16]; } GUID;
typedef uint64_t ULONG64;
typedef uint32_t ULONG;
typedef int32_t NTSTATUS;
typedef int TOKEN_TYPE;
#define WINAPI
#define TRACE(...) ((void)snprintf(NULL, 0, __VA_ARGS__))
#define FIXME(...) ((void)0)
#define TokenType 8
#define TokenSecurityAttributes 39
#define STATUS_NOT_IMPLEMENTED ((NTSTATUS)0xc0000002)
static NTSTATUS validation, query;
static int calls;
static HANDLE expected_token;
static ULONG64 *observed_attributes;
static NTSTATUS NtQueryInformationToken(HANDLE token, int info, void *buffer,
                                        ULONG size, ULONG *length)
{
    assert(token == expected_token);
    assert(!observed_attributes || *observed_attributes == 0);
    *length = 0;
    if (++calls == 1) {
        assert(info == TokenType && buffer && size == sizeof(TOKEN_TYPE));
        return validation;
    }
    assert(calls == 2 && info == TokenSecurityAttributes && !buffer && !size);
    return query;
}
"""
        harness += function
        harness += r"""
int main(void)
{
    const NTSTATUS errors[] = {
        (NTSTATUS)0xc0000008, /* invalid handle */
        (NTSTATUS)0xc0000022, /* access denied */
        (NTSTATUS)0xc0000024  /* object type mismatch */
    };
    const NTSTATUS queries[] = {
        STATUS_NOT_IMPLEMENTED, (NTSTATUS)0xc0000023,
        (NTSTATUS)0xc0000225, 0
    };
    const intptr_t tokens[] = {0, -4660, -4};
    unsigned char package[512], app[512], guid[16], claim[8];
    const SIZE_T capacities[] = {0, 2, 512};
    unsigned int i, j, k;
    ULONG64 attributes;
    SIZE_T package_size, app_size;
    for (i = 0; i < 3; ++i) {
        expected_token = (HANDLE)tokens[i];
        for (j = 0; j < 3; ++j) {
            for (k = 0; k < 4; ++k) {
                memset(package, 0xa5, sizeof(package));
                memset(app, 0xa5, sizeof(app));
                memset(guid, 0xa5, sizeof(guid));
                memset(claim, 0xa5, sizeof(claim));
                package_size = app_size = capacities[j];
                attributes = UINT64_MAX;
                observed_attributes = &attributes;
                validation = i < 2 ? errors[i] : 0;
                query = queries[k];
                calls = 0;
                NTSTATUS result = RtlQueryPackageClaims(expected_token,
                    (WCHAR *)package, &package_size, (WCHAR *)app, &app_size,
                    (GUID *)guid, claim, &attributes);
                assert(result == (validation ? validation :
                       query ? query : STATUS_NOT_IMPLEMENTED));
                assert(calls == (validation ? 1 : 2) && attributes == 0);
                assert(package_size == capacities[j] && app_size == capacities[j]);
                for (size_t n = 0; n < sizeof(package); ++n) assert(package[n] == 0xa5);
                for (size_t n = 0; n < sizeof(app); ++n) assert(app[n] == 0xa5);
                for (size_t n = 0; n < sizeof(guid); ++n) assert(guid[n] == 0xa5);
                for (size_t n = 0; n < sizeof(claim); ++n) assert(claim[n] == 0xa5);
            }
        }
    }
    for (i = 0; i < 3; ++i) {
        validation = errors[i]; calls = 0; observed_attributes = NULL;
        assert(RtlQueryPackageClaims(expected_token, NULL, NULL, NULL, NULL,
                                    NULL, NULL, NULL) == errors[i]);
        assert(calls == 1);
    }
    validation = 0; query = STATUS_NOT_IMPLEMENTED;
    calls = 0; observed_attributes = NULL;
    assert(RtlQueryPackageClaims(expected_token, NULL, NULL, NULL, NULL,
                                NULL, NULL, NULL) == STATUS_NOT_IMPLEMENTED);
    assert(calls == 2);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "claims.c"
            executable = Path(directory) / "claims-test"
            source.write_text(harness)
            compiled = subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                 str(source), "-o", str(executable)],
                capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            subprocess.run([str(executable)], check=True, timeout=10)


if __name__ == "__main__":
    unittest.main()
