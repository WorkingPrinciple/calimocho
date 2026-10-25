import subprocess
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.check_ntdll_syscall_exports import check as check_exports, syscall_ids
from tools.port_alpc_connect_attrs import port as connect_attrs
from tools.server_request_gate import check, overflows

CELL032 = REPO / "build/winehq-11.20/package-cell032-01"


def request(name, adds):
    return "SERVER_START_REQ( %s )\n{\n%s    wine_server_call( req );\n}\nSERVER_END_REQ;\n" % (
        name, "".join("    if (x) wine_server_add_data( req, p, %d );\n" % i for i in range(adds)))


class GateTests(unittest.TestCase):
    def test_counts_conditional_chunks_per_request(self):
        text = request("ok", 5) + request("bad", 6)
        self.assertEqual(overflows(text), [("bad", 6)])

    def test_check_rejects_overflow_and_limit_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "include/wine").mkdir(parents=True)
            (root / "include/wine/server.h").write_text("#define __SERVER_MAX_DATA 5\n")
            (root / "a.c").write_text(request("fine", 5))
            self.assertEqual(check(root, ["a.c"])["max_data"], 5)
            (root / "b.c").write_text(request("create_token", 6))
            with self.assertRaisesRegex(ValueError, "create_token"):
                check(root, ["a.c", "b.c"])
            (root / "include/wine/server.h").write_text("#define __SERVER_MAX_DATA 6\n")
            with self.assertRaisesRegex(ValueError, "MAX_DATA"):
                check(root, ["a.c"])


@unittest.skipUnless((CELL032 / "source/server/alpc.c").is_file(), "cell032 source build absent")
class ConnectAttrsTests(unittest.TestCase):
    def test_client_attr_and_effective_only_reach_the_server(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            source = Path(directory) / "source"
            for relative in ("server/alpc.c", "server/token.c", "server/security.h",
                             "server/protocol.def", "dlls/ntdll/unix/alpc.c"):
                (source / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(CELL032 / "source" / relative, source / relative)
            connect_attrs(source)
            client = (source / "dlls/ntdll/unix/alpc.c").read_text()
            server = (source / "server/alpc.c").read_text()
            token = (source / "server/token.c").read_text()
            protocol = (source / "server/protocol.def").read_text()
            ex = client[client.index("NTSTATUS WINAPI NtAlpcConnectPortEx("):]
            self.assertNotIn("if (client_attr || out_attrs || in_attrs) return STATUS_NOT_IMPLEMENTED;",
                             ex[:ex.index("NTSTATUS WINAPI NtAlpcAcceptConnectPort(")])
            self.assertNotIn("pa->SecurityQos.EffectiveOnly)) return STATUS_NOT_IMPLEMENTED;", client)
            for reason in ("client_attr_root", "client_attr_name", "client_attr_attributes", "client_attr_qos",
                           "send_attributes", "send_security_flags", "send_security_qos",
                           "send_security_context", "connect_flags", "max_message_length", "connect_qos"):
                self.assertIn('FIXME( "reason=%s' % reason, client)
            self.assertNotIn("connection message attributes are not implemented", client)
            self.assertIn("if (!status && in_attrs) in_attrs->ValidAttributes = 0;", ex)
            connect = client[client.index("static NTSTATUS connect_port("):]
            self.assertNotIn("return STATUS_NOT_IMPLEMENTED;\n    if (pa", connect[:connect.index("SERVER_START_REQ")])
            self.assertIn("req->effective_only = pa && pa->SecurityQos.EffectiveOnly;", client)
            self.assertEqual(overflows(client), [])
            self.assertIn("VARARG(client_sd,bytes,client_sd_size);", protocol)
            self.assertIn("create_port( NULL, &empty_unicode_str, 0, client_sd, CLIENT_PORT )", server)
            self.assertIn("client_sd->sacl_len", server)
            self.assertIn("SE_GROUP_ENABLED | SE_GROUP_MANDATORY | SE_GROUP_USE_FOR_DENY_ONLY", token)
            self.assertIn("if (!privilege->enabled) disabled[count++].luid", token)
            with self.assertRaisesRegex(ValueError, "without connect attributes"):
                connect_attrs(source)


SEND_ATTR_HARNESS = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned int ULONG;
typedef void *HANDLE;
typedef unsigned long long ULONG_PTR;
typedef struct { ULONG Length; } SECURITY_QUALITY_OF_SERVICE;
typedef struct { ULONG AllocatedAttributes; ULONG ValidAttributes; } ALPC_MESSAGE_ATTRIBUTES;
typedef struct { ULONG Flags; SECURITY_QUALITY_OF_SERVICE *QoS; HANDLE ContextHandle; } ALPC_SECURITY_ATTR;
#define ALPC_MESSAGE_SECURITY_ATTRIBUTE 0x80000000u
#define ALPC_MESSAGE_ATTRIBUTE_ALL 0xfe000000u
#define STATUS_INVALID_PARAMETER 0xc000000du
#define STATUS_NOT_IMPLEMENTED 0xc0000002u
static char reason[64];
#define FIXME(...) snprintf( reason, sizeof(reason), __VA_ARGS__ )
#define TRACE(...) do {} while (0)
static unsigned int check( ALPC_MESSAGE_ATTRIBUTES *out_attrs )
{
    void *client_packed = malloc( 1 );
    reason[0] = 0;
SNIPPET
    free( client_packed );
    return 0;
}
int main( void )
{
    struct { ALPC_MESSAGE_ATTRIBUTES h; ALPC_SECURITY_ATTR s; } a;
    SECURITY_QUALITY_OF_SERVICE qos;
#define EXPECT(cond) do { if (!(cond)) { printf( "fail line %d reason %s\n", __LINE__, reason ); return 1; } } while (0)
    memset( &a, 0, sizeof(a) );
    EXPECT( check( NULL ) == 0 );
    EXPECT( check( &a.h ) == 0 );
    a.h.AllocatedAttributes = 0xe2000000u; a.h.ValidAttributes = 0x80000000u;
    EXPECT( check( &a.h ) == 0 && !reason[0] );
    a.s.Flags = 0x10000;
    EXPECT( check( &a.h ) == STATUS_NOT_IMPLEMENTED && !strcmp( reason, "reason=send_security_flags value=0x10000\n" ) );
    a.s.Flags = 0; a.s.QoS = &qos;
    EXPECT( check( &a.h ) == STATUS_NOT_IMPLEMENTED && !strcmp( reason, "reason=send_security_qos\n" ) );
    a.s.QoS = NULL; a.s.ContextHandle = (HANDLE)4;
    EXPECT( check( &a.h ) == STATUS_NOT_IMPLEMENTED && !strcmp( reason, "reason=send_security_context value=0x4\n" ) );
    /* CoreMessaging+0x3f495: calloc'd attribute, QoS NULL, ContextHandle (HANDLE)-2, Valid 0x80000000 */
    a.s.ContextHandle = (HANDLE)-2;
    EXPECT( check( &a.h ) == 0 && !reason[0] );
    a.s.ContextHandle = (HANDLE)-1;
    EXPECT( check( &a.h ) == STATUS_NOT_IMPLEMENTED && !strcmp( reason, "reason=send_security_context value=0xffffffffffffffff\n" ) );
    a.s.ContextHandle = (HANDLE)-2; a.s.QoS = &qos;
    EXPECT( check( &a.h ) == STATUS_NOT_IMPLEMENTED && !strcmp( reason, "reason=send_security_qos\n" ) );
    a.s.QoS = NULL;
    a.s.ContextHandle = NULL; a.h.ValidAttributes = 0xa0000000u;
    EXPECT( check( &a.h ) == STATUS_NOT_IMPLEMENTED && !strcmp( reason, "reason=send_attributes value=0xa0000000\n" ) );
    a.h.AllocatedAttributes = 0x80000000u; a.h.ValidAttributes = 0xa0000000u;
    EXPECT( check( &a.h ) == STATUS_INVALID_PARAMETER );
    a.h.AllocatedAttributes = 0x80000001u; a.h.ValidAttributes = 0;
    EXPECT( check( &a.h ) == STATUS_INVALID_PARAMETER );
    printf( "ok\n" );
    return 0;
}
"""


class SendAttributeCheckTests(unittest.TestCase):
    def test_compiled_connect_send_attribute_check(self):
        from tools.port_alpc_connect_attrs import CLIENT_ATTR_CHECK
        snippet = CLIENT_ATTR_CHECK[CLIENT_ATTR_CHECK.index("    if (out_attrs && ((out_attrs->ValidAttributes"):]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "send_attrs.c"
            source.write_text(SEND_ATTR_HARNESS.replace("SNIPPET", snippet))
            binary = Path(directory) / "send_attrs"
            subprocess.run(["clang", "-std=c99", "-Wall", "-Werror", "-fsanitize=address,undefined",
                            "-o", str(binary), str(source)], check=True)
            self.assertEqual(subprocess.run([str(binary)], capture_output=True, text=True, check=True).stdout, "ok\n")


@unittest.skipUnless((CELL032 / "install/lib/wine/x86_64-windows/ntdll.dll").is_file(), "cell032 install absent")
class NtdllExportTests(unittest.TestCase):
    def test_connect_port_ex_export_is_the_syscall_thunk(self):
        header = CELL032 / "source/dlls/ntdll/ntsyscalls.h"
        result = check_exports(CELL032 / "install/lib/wine/x86_64-windows/ntdll.dll", header)
        self.assertEqual(result["NtAlpcConnectPortEx"]["syscall"],
                         "%#x" % syscall_ids(header.read_text())["NtAlpcConnectPortEx"])
        with self.assertRaisesRegex(ValueError, "not in ALL_SYSCALLS"):
            check_exports(CELL032 / "install/lib/wine/x86_64-windows/ntdll.dll", header, ("RtlAllocateHeap",))


if __name__ == "__main__":
    unittest.main()
