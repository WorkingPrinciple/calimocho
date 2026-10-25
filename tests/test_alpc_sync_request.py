from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_alpc_impersonation import port as impersonation
from tools.port_alpc_sync_request import port


class AlpcSyncRequestTests(unittest.TestCase):
    def test_native_reply_flag_and_synchronous_request(self):
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
            port(source)
            header = (source / "include/winternl.h").read_text()
            self.assertIn("#define ALPC_MSGFLG_REPLY_MESSAGE               0x00000001", header)
            self.assertIn("#define ALPC_MSGFLG_SYNC_REQUEST                0x00020000", header)
            client = (source / "dlls/ntdll/unix/alpc.c").read_text()
            start = client.index("#define ALPC_MSGFLG_LPC_MODE")
            end = client.index("\n}\n", start) + 3
            (root / "alpc_send_flags_under_test.c").write_text(client[start:end])
            begin = client.index("NTSTATUS WINAPI NtAlpcSendWaitReceivePort(")
            section = client[begin:client.index("NtAlpcImpersonateClientOfPort", begin)]
            self.assertIn("if ((status = alpc_send_flags_status( flags, send != NULL, recv != NULL ))) return status;",
                          section)
            self.assertIn('FIXME( "reason=send_attrs value=%#x\\n",', section)
            self.assertIn("req->flags = flags & ALPC_MSGFLG_REPLY_MESSAGE;", section)
            self.assertNotIn("ALPC_MSGFLG_REPLY_MESSAGE | ALPC_MSGFLG_WAIT_ALERTABLE", section)
            self.assertIn("match = request && (flags & ALPC_MSGFLG_SYNC_REQUEST);", section)
            self.assertNotIn("send->MessageId) flags |=", section)
            text = (source / "server/alpc.c").read_text()
            self.assertIn("#define MSGFLG_REPLY_MESSAGE   ALPC_MSGFLG_REPLY_MESSAGE", text)
            (root / "alpc_server_under_test.c").write_text(
                re.sub(r'^#include .*\n', "", text, flags=re.MULTILINE))
            token = (source / "server/token.c").read_text()
            (root / "token_impersonation_under_test.c").write_text(
                token[token.index("int token_impersonate_alpc("):])
            executable = root / "sync-request-test"
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-Wno-unused-function", "-Wno-unused-variable",
                "-Wno-missing-field-initializers", "-fsanitize=address,undefined",
                "-DALPC_IDENTITY_TEST", "-DALPC_IMPERSONATION_TEST", "-DALPC_SYNC_REQUEST_TEST",
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
