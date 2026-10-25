from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.build_uwp_overlay import REPO
from tools.diagnose_package_activation import CallDiagnostics


class CoreMessagingStubTests(unittest.TestCase):
    def test_counter_admits_only_scoped_fixed_names_and_explicit_limits(self):
        diagnostic = CallDiagnostics()
        diagnostic.observe(256, 260, "pkgstatus", "diagnostic_coremessaging_stub",
                           "coremessaging-stub name=NtAlpcQueryInformation hit=1 result=c0000002")
        self.assertEqual(diagnostic.coremessaging_stub_count, 0)
        diagnostic.running.add(256)
        for index in range(1, 129):
            diagnostic.observe(256, 260, "pkgstatus", "diagnostic_coremessaging_stub",
                               f"coremessaging-stub name=NtAlpcQueryInformation hit={index} result=c0000002")
        for invalid in ("name=Secret", "name=NtAlpcQueryInformation address=123", "name=NtAlpcQueryInformation hit=129"):
            diagnostic.observe(256, 260, "pkgstatus", "diagnostic_coremessaging_stub",
                               "coremessaging-stub " + invalid + " result=c0000002")
        self.assertEqual(diagnostic.coremessaging_stub_count, 128)
        self.assertEqual(len(diagnostic.coremessaging_stubs), 128)
        diagnostic.observe(256, 260, "pkgstatus", "diagnostic_coremessaging_stub",
                           "coremessaging-stub limited=1")
        self.assertEqual(diagnostic.coremessaging_stub_limited, {256})

    def test_actual_typed_stubs_fail_loud_and_clear_only_outputs(self):
        source = REPO / "patches/wine/files/coremessaging_ntdll_stubs.c"
        self.assertTrue(source.is_file())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "wine").mkdir()
            (root / "ntstatus.h").write_text("#define STATUS_NOT_IMPLEMENTED ((NTSTATUS)0xc0000002)\n")
            (root / "windef.h").write_text("""
#include <stdint.h>
#include <stddef.h>
typedef int32_t NTSTATUS, LONG;
typedef uint32_t ULONG, UINT;
typedef uint64_t ULONGLONG;
typedef size_t SIZE_T;
typedef void *HANDLE, *PSID;
typedef unsigned char BOOLEAN;
typedef int BOOL;
#define WINAPI
static LONG InterlockedIncrement(LONG *p) { return ++*p; }
""")
            (root / "winternl.h").write_text("""
typedef struct { unsigned short Length, MaximumLength; void *Buffer; } UNICODE_STRING;
typedef struct { int unused; } OBJECT_ATTRIBUTES, ALPC_PORT_ATTRIBUTES, ALPC_PORT_MESSAGE, LARGE_INTEGER;
typedef struct { ULONG AllocatedAttributes, ValidAttributes; } ALPC_MESSAGE_ATTRIBUTES;
typedef void *PSECURITY_DESCRIPTOR;
""")
            (root / "wine/debug.h").write_text("""
#define WINE_DEFAULT_DEBUG_CHANNEL(x)
#define WINE_DECLARE_DEBUG_CHANNEL(x)
static unsigned traces, fixmes, limits;
static void trace(const char *fmt, ...) {
    if (!strcmp(fmt, "coremessaging-stub limited=1\\n")) ++limits;
    else ++traces;
}
#define TRACE_(x) trace
#define TRACE_ON(x) 1
#define FIXME(...) (++fixmes)
""")
            (root / "test.c").write_text("""
#include <assert.h>
#include <string.h>
static int active = 1;
""" + '#include "' + str(source) + '"\n' + """
BOOL WINAPI __wine_pkg_diagnostic_active(void) { return active; }
int main(void) {
    UNICODE_STRING path = { 5, 9, (void *)123 };
    ULONGLONG ticket = 0xa5a5a5a5a5a5a5a5ULL, input = ticket;
    HANDLE handle = (void *)123;
    size_t length = 17;
    ALPC_MESSAGE_ATTRIBUTES sent = { 7, 3 }, received = { 9, 5 };
    ALPC_PORT_MESSAGE message = { 42 };
    unsigned char buffer[11]; ULONG returned = 55;
    NTSTATUS (*get)(ULONGLONG *, ULONG) = RtlGetThreadWorkOnBehalfTicket;
    NTSTATUS (*set)(ULONGLONG *) = RtlSetThreadWorkOnBehalfTicket;
    assert(RtlGetAppContainerNamedObjectPath(0, 0, 0, &path) == STATUS_NOT_IMPLEMENTED);
    assert(!path.Buffer && !path.Length && !path.MaximumLength);
    assert(get(&ticket, 0) == STATUS_NOT_IMPLEMENTED && ticket == 0);
    assert(set(&input) == STATUS_NOT_IMPLEMENTED && input == 0xa5a5a5a5a5a5a5a5ULL);
    assert(NtAlpcConnectPortEx(&handle, 0, 0, 0, 0, 0, &message, &length,
                              &sent, &received, 0) == STATUS_NOT_IMPLEMENTED);
    assert(!handle && !length && sent.AllocatedAttributes == 7 && sent.ValidAttributes == 3);
    assert(received.AllocatedAttributes == 9 && !received.ValidAttributes && message.unused == 42);
    memset(buffer, 0xa5, sizeof(buffer));
    assert(NtAlpcQueryInformation(0, 0, buffer, sizeof(buffer), &returned) == STATUS_NOT_IMPLEMENTED);
    assert(!returned);
    for (unsigned i = 0; i < sizeof(buffer); ++i) assert(buffer[i] == 0);
    assert(RtlGetAppContainerNamedObjectPath(0, 0, 0, 0) == STATUS_NOT_IMPLEMENTED);
    assert(get(0, 0) == STATUS_NOT_IMPLEMENTED);
    assert(set(0) == STATUS_NOT_IMPLEMENTED);
    assert(NtAlpcConnectPortEx(0,0,0,0,0,0,0,0,0,0,0) == STATUS_NOT_IMPLEMENTED);
    assert(NtAlpcQueryInformation(0,0,0,0,0) == STATUS_NOT_IMPLEMENTED);
    assert(traces == 10 && limits == 0);
    for (unsigned i = 0; i < 130; ++i) get(0,0);
    assert(traces == 128 && limits == 1);
    active = 0; get(0,0);
    assert(traces == 128 && limits == 1 && fixmes == 141);
    return 0;
}
""")
            subprocess.run(["/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-Wno-unused-parameter", "-I" + directory, str(root / "test.c"),
                            "-o", str(root / "test")], check=True, capture_output=True)
            subprocess.run([str(root / "test")], check=True)
