from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_alpc_impersonation import port as impersonation
from tools.port_alpc_sync_request import port as sync_request
from tools.port_alpc_work_on_behalf import port


class AlpcWorkOnBehalfTests(unittest.TestCase):
    def test_work_on_behalf_send_attribute(self):
        baseline = REPO / "build/winehq-11.20/package-token-security-01/source"
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            for relative in ("server/alpc.c", "server/token.c", "server/security.h",
                             "server/protocol.def", "dlls/ntdll/unix/alpc.c", "include/winternl.h"):
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, target)
            impersonation(source)
            with self.assertRaisesRegex(ValueError, "sync request port first"):
                port(source)
            sync_request(source)
            port(source)
            header = (source / "include/winternl.h").read_text()
            self.assertRegex(header, r"#define ALPC_MESSAGE_WORK_ON_BEHALF_ATTRIBUTE\s+0x0*2000000")
            client = (source / "dlls/ntdll/unix/alpc.c").read_text()
            start = client.index("#define ALPC_MSGFLG_LPC_MODE")
            end = client.index("\n}\n", start) + 3
            (root / "alpc_send_flags_under_test.c").write_text(client[start:end])
            start = client.index("static NTSTATUS alpc_send_attrs_status(")
            end = client.index("\n}\n", start) + 3
            (root / "alpc_send_attrs_under_test.c").write_text(client[start:end])
            begin = client.index("NTSTATUS WINAPI NtAlpcSendWaitReceivePort(")
            section = client[begin:client.index("NtAlpcImpersonateClientOfPort", begin)]
            self.assertIn("alpc_send_attrs_status( send_attrs->AllocatedAttributes,", section)
            self.assertNotIn("ValidAttributes & ~ALPC_MESSAGE_CONTEXT_ATTRIBUTE", section)
            self.assertNotIn("WORK_ON_BEHALF", section)
            received = client[client.index("static NTSTATUS fill_received("):]
            received = received[:received.index("\n}\n")]
            self.assertIn("attrs->ValidAttributes = 0;", received)
            self.assertNotIn("WORK_ON_BEHALF", received)
            text = (source / "server/alpc.c").read_text()
            (root / "alpc_server_under_test.c").write_text(
                re.sub(r'^#include .*\n', "", text, flags=re.MULTILINE))
            token = (source / "server/token.c").read_text()
            (root / "token_impersonation_under_test.c").write_text(
                token[token.index("int token_impersonate_alpc("):])
            executable = root / "work-on-behalf-test"
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-Wno-unused-function", "-Wno-unused-variable",
                "-Wno-missing-field-initializers", "-fsanitize=address,undefined",
                "-DALPC_IDENTITY_TEST", "-DALPC_IMPERSONATION_TEST", "-DALPC_SYNC_REQUEST_TEST",
                "-DALPC_WORK_ON_BEHALF_TEST",
                "-I" + str(root), "-I" + str(baseline / "include"),
                str(REPO / "tests/alpc_transport_host.c"), "-o", str(executable),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            with self.assertRaisesRegex(ValueError, "fresh"):
                port(source)
            (root / "CELL027-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)


if __name__ == "__main__":
    unittest.main()
