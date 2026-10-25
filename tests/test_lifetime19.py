import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.build_uwp_overlay import REPO
from tools.diagnose_package_activation import CallDiagnostics
from tools.port_call_diagnostics import slots


ROOT = REPO / "build/winehq-11.20/package-uwp-lifetime19-01"


class Lifetime19Tests(unittest.TestCase):
    def test_generated_typed_table_and_forwarders_cover_all_nineteen_slots(self):
        header = ROOT / "diagnostic-abi/package_activation.h"
        names = [item[1] for item in slots(header, "IStaticLifetime")]
        self.assertEqual(len(names), 19)
        self.assertEqual(names[6:8], ["Reserved", "GetCollection"])
        self.assertEqual(names[11:13], ["AddCallback", "RemoveCallback"])
        self.assertEqual(set(names), CallDiagnostics.COMMON | CallDiagnostics.METHODS["StaticLifetime"])
        build = json.loads((ROOT / "build-receipt.json").read_text())
        self.assertEqual(sum(map(len, build["call_diagnostics"]["interfaces"].values())), 133)
        self.assertEqual(build["call_diagnostics"]["interfaces"]["StaticLifetime"], names)

    def test_actual_callback_implementation_and_exact_output_widths(self):
        source = (REPO / "patches/wine/files/core_application_activated.c").read_text()
        implementation = source[source.index("static HRESULT lifetime_unknown("):
                                source.index("static const IStaticLifetimeVtbl lifetime_vtable")]
        program = r"""
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef int32_t HRESULT;
typedef int64_t INT64;
typedef uint32_t UINT32;
typedef unsigned char boolean;
typedef struct { int unused; } IStaticLifetime, IInspectable, GUID;
typedef struct { unsigned refs; } IUnknown;
#define WINAPI
#define S_OK 0
#define E_POINTER ((HRESULT)0x80004003)
#define E_NOTIMPL ((HRESULT)0x80004001)
#define E_OUTOFMEMORY ((HRESULT)0x8007000e)
#define FALSE 0
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define TRACE(...) ((void)0)
static unsigned locks;
static int handler_lock;
static void AcquireSRWLockExclusive(int *lock) { (void)lock; assert(!locks++); }
static void ReleaseSRWLockExclusive(int *lock) { (void)lock; assert(locks-- == 1); }
static void IUnknown_AddRef(IUnknown *object) { assert(!locks); ++object->refs; }
static void IUnknown_Release(IUnknown *object) { assert(!locks && object->refs); --object->refs; }
static struct {
    struct { INT64 token; IUnknown *callback; } lifetime_callbacks[32];
    INT64 next_token;
} core;
""" + implementation + r"""
int main(void)
{
    IUnknown callback = {1};
    INT64 tokens[32], token = -1;
    struct { uint64_t left; IInspectable *out; uint64_t right; } pointer = {99, (void *)1, 77};
    struct { unsigned char left, value, right; } byte = {99, 1, 77};
    struct { UINT32 left, value, right; } scalar = {99, 1, 77};
    unsigned i;
    assert(lifetime_add_callback(NULL, &callback, NULL) == E_POINTER && callback.refs == 1);
    assert(lifetime_add_callback(NULL, NULL, &token) == E_POINTER && token == 0);
    for (i = 0; i < 32; ++i) {
        assert(lifetime_add_callback(NULL, &callback, &tokens[i]) == S_OK);
        assert(tokens[i] > 0 && (!i || tokens[i] > tokens[i-1]));
    }
    assert(callback.refs == 33);
    token = -1;
    assert(lifetime_add_callback(NULL, &callback, &token) == E_OUTOFMEMORY && token == 0);
    assert(callback.refs == 33);
    for (i = 0; i < 32; ++i) {
        assert(lifetime_remove_callback(NULL, tokens[i]) == S_OK);
        assert(lifetime_remove_callback(NULL, tokens[i]) == S_OK);
    }
    assert(callback.refs == 1);
    assert(lifetime_remove_callback(NULL, 0) == S_OK);
    assert(lifetime_add_callback(NULL, &callback, &token) == S_OK && token > tokens[31]);
    assert(lifetime_remove_callback(NULL, token) == S_OK && callback.refs == 1);
    core.next_token = INT64_MAX;
    assert(lifetime_add_callback(NULL, &callback, &token) == E_OUTOFMEMORY && token == 0);
    assert(callback.refs == 1);
#define POINTER(call) do { pointer.out = (void *)1; assert((call) == E_NOTIMPL); \
    assert(!pointer.out && pointer.left == 99 && pointer.right == 77); } while (0)
    POINTER(lifetime_slot8(NULL, 3, &pointer.out));
    POINTER(lifetime_slot9(NULL, 3, &pointer.out));
    POINTER(lifetime_slot10(NULL, &pointer.out));
    POINTER(lifetime_slot13(NULL, 3, &pointer.out));
    POINTER(lifetime_slot15(NULL, NULL, &pointer.out));
    POINTER(lifetime_slot16(NULL, 3, &pointer.out));
    POINTER(lifetime_slot18(NULL, 3, &pointer.out));
    assert(lifetime_slot14(NULL, &byte.value) == E_NOTIMPL);
    assert(!byte.value && byte.left == 99 && byte.right == 77);
    assert(lifetime_slot17(NULL, &callback, &scalar.value) == E_NOTIMPL);
    assert(!scalar.value && scalar.left == 99 && scalar.right == 77);
    assert(lifetime_slot8(NULL, 0, NULL) == E_POINTER);
    assert(lifetime_slot14(NULL, NULL) == E_POINTER);
    assert(lifetime_slot17(NULL, NULL, NULL) == E_POINTER);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "test.c").write_text(program)
            subprocess.run(["/usr/bin/clang", "-Wall", "-Wextra", "-Werror",
                            "-Wno-unused-parameter", str(path / "test.c"),
                            "-o", str(path / "test")], check=True)
            subprocess.run([str(path / "test")], check=True)
