from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_alpc_impersonation import port


class AlpcImpersonationTests(unittest.TestCase):
    def test_delivered_connection_snapshot_not_supplied_process_identity(self):
        baseline = REPO / "build/winehq-11.20/package-token-security-01/source"
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            for relative in ("server/alpc.c", "server/token.c", "server/security.h",
                             "server/protocol.def", "dlls/ntdll/unix/alpc.c"):
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, target)
            port(source)
            text = (source / "server/alpc.c").read_text()
            (root / "alpc_server_under_test.c").write_text(
                re.sub(r'^#include .*\n', "", text, flags=re.MULTILINE))
            token = (source / "server/token.c").read_text()
            start = token.index("int token_impersonate_alpc(")
            (root / "token_impersonation_under_test.c").write_text(token[start:])
            executable = root / "impersonation-test"
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-Wno-unused-function", "-Wno-unused-variable",
                "-Wno-missing-field-initializers", "-fsanitize=address,undefined",
                "-DALPC_IDENTITY_TEST", "-DALPC_IMPERSONATION_TEST",
                "-I" + str(root), "-I" + str(baseline / "include"),
                str(REPO / "tests/alpc_transport_host.c"), "-o", str(executable),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            client = (source / "dlls/ntdll/unix/alpc.c").read_text()
            self.assertIn("SECURITY_STATIC_TRACKING", client)
            self.assertIn("pa->SecurityQos.EffectiveOnly", client)
            self.assertNotIn("NtOpenProcessToken", client)
            with self.assertRaisesRegex(ValueError, "fresh"):
                port(source)
            (root / "CELL027-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)
