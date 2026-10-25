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
            self.assertIn("client port root/name/attributes/QoS are not implemented", client)
            self.assertIn("req->effective_only = pa && pa->SecurityQos.EffectiveOnly;", client)
            self.assertEqual(overflows(client), [])
            self.assertIn("VARARG(client_sd,bytes,client_sd_size);", protocol)
            self.assertIn("create_port( NULL, &empty_unicode_str, 0, client_sd, CLIENT_PORT )", server)
            self.assertIn("client_sd->sacl_len", server)
            self.assertIn("SE_GROUP_ENABLED | SE_GROUP_MANDATORY | SE_GROUP_USE_FOR_DENY_ONLY", token)
            self.assertIn("if (!privilege->enabled) disabled[count++].luid", token)
            with self.assertRaisesRegex(ValueError, "without connect attributes"):
                connect_attrs(source)


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
