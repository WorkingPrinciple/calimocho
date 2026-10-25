from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_token_security import port


class TokenSecurityTests(unittest.TestCase):
    def test_privileged_session_and_integrity_state_and_failure_paths(self):
        baseline = REPO / "build/winehq-11.20/package-token-identity-02/source"
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            for relative in ("server/token.c", "server/protocol.def", "dlls/ntdll/unix/security.c"):
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, target)
            port(source)
            executable = root / "security-test"
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-fsanitize=address,undefined",
                "-I" + str(baseline / "include"), "-I" + str(source / "server"),
                str(REPO / "tests/token_security_host.c"), "-o", str(executable),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            client = (source / "dlls/ntdll/unix/security.c").read_text()
            self.assertNotIn("TokenSessionId stub!", client)
            self.assertNotIn("TokenIntegrityLevel stub!", client)
            self.assertNotIn('report always "S-1-16-12288"', client)
            with self.assertRaisesRegex(ValueError, "fresh"):
                port(source)
            (root / "CELL027-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)
