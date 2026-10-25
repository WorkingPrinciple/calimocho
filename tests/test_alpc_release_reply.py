from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_alpc_impersonation import port as impersonation
from tools.port_alpc_sync_request import port as sync_request
from tools.port_alpc_work_on_behalf import port as work_on_behalf
from tools.port_alpc_release_reply import port


class AlpcReleaseReplyTests(unittest.TestCase):
    def test_delivered_release_response_on_listener(self):
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
            sync_request(source)
            work_on_behalf(source)
            client = (source / "dlls/ntdll/unix/alpc.c").read_text()
            start = client.index("#define ALPC_MSGFLG_LPC_MODE")
            end = client.index("\n}\n", start) + 3
            (root / "alpc_send_flags_under_test.c").write_text(client[start:end])
            token = (source / "server/token.c").read_text()
            (root / "token_impersonation_under_test.c").write_text(
                token[token.index("int token_impersonate_alpc("):])

            def execute():
                text = (source / "server/alpc.c").read_text()
                (root / "alpc_server_under_test.c").write_text(
                    re.sub(r'^#include .*\n', "", text, flags=re.MULTILINE))
                executable = root / "release-reply-test"
                compiled = subprocess.run([
                    "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-Wno-unused-parameter", "-Wno-unused-function", "-Wno-unused-variable",
                    "-Wno-missing-field-initializers", "-fsanitize=address,undefined",
                    "-DALPC_IDENTITY_TEST", "-DALPC_IMPERSONATION_TEST", "-DALPC_SYNC_REQUEST_TEST",
                    "-DALPC_RELEASE_REPLY_TEST", "-I" + str(root), "-I" + str(baseline / "include"),
                    str(REPO / "tests/alpc_transport_host.c"), "-o", str(executable),
                ], capture_output=True, text=True)
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                return subprocess.run([str(executable)], capture_output=True, text=True)

            old = execute()
            self.assertNotEqual(old.returncode, 0, "Cell041 must reproduce the listener response failure")
            self.assertIn("Assertion failed: (!error)", old.stderr)
            port(source)
            fixed = execute()
            self.assertEqual(fixed.returncode, 0, fixed.stdout + fixed.stderr)
            client = (source / "dlls/ntdll/unix/alpc.c").read_text()
            self.assertIn("req->flags = flags & (ALPC_MSGFLG_REPLY_MESSAGE | ALPC_MSGFLG_RELEASE_MESSAGE);", client)
            self.assertIn("req->pid = (ULONG_PTR)send->ClientId.UniqueProcess;", client)
            self.assertIn("req->tid = (ULONG_PTR)send->ClientId.UniqueThread;", client)
            self.assertIn("return STATUS_INVALID_CID;", client)
            protocol = (source / "server/protocol.def").read_text()
            section = protocol[protocol.index("@REQ(alpc_send_message)"):]
            section = section[:section.index("@END")]
            self.assertIn("unsigned int  pid;", section)
            self.assertIn("unsigned int  tid;", section)
            with self.assertRaisesRegex(ValueError, "fresh"):
                port(source)
            (root / "CELL042-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)


if __name__ == "__main__":
    unittest.main()
