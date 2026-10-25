from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_alpc_identity import port


class AlpcIdentityTests(unittest.TestCase):
    def test_actual_handlers_check_creator_token_and_report_sid_mismatch(self):
        baseline = REPO / "build/winehq-11.20/package-restricted-token-02/source"
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            for relative in ("server/alpc.c", "server/token.c", "server/security.h",
                             "server/protocol.def", "dlls/ntdll/unix/alpc.c"):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, path)
            port(source)
            text = (source / "server/alpc.c").read_text()
            (root / "alpc_server_under_test.c").write_text(
                re.sub(r'^#include .*\n', "", text, flags=re.MULTILINE))
            output = root / "identity-test"
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-Wno-unused-function", "-Wno-unused-variable",
                "-Wno-missing-field-initializers", "-fsanitize=address,undefined",
                "-DALPC_IDENTITY_TEST", "-I" + str(root), "-I" + str(baseline / "include"),
                str(REPO / "tests/alpc_transport_host.c"), "-o", str(output),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            client = (source / "dlls/ntdll/unix/alpc.c").read_text()
            self.assertIn("packed ? packed->sd_len : 0", client)
            self.assertNotIn("if (sd || client_attr", client)
            self.assertIn("return (token_restricted_access( token, sd, mapping, granted ) & 1) != 0;", (source / "server/token.c").read_text())
            token = (source / "server/token.c").read_text()
            start = token.index("static unsigned int token_access_check(")
            end = token.index("\nconst struct acl *token_get_default_dacl", start)
            (root / "token_access_under_test.c").write_text(token[start:end])
            start = token.index("DECL_HANDLER(filter_token)")
            end = token.index("\n/* checks the specified privileges", start)
            handlers = token[start:end]
            start = token.index("DECL_HANDLER(get_token_groups)")
            end = token.index("\nDECL_HANDLER(get_token_info)", start)
            (root / "token_handlers_under_test.c").write_text(handlers + "\n" + token[start:end])
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-Wno-unused-function",
                "-fsanitize=address,undefined", "-DALPC_IDENTITY_TEST",
                "-I" + str(root), "-I" + str(baseline / "include"),
                "-I" + str(REPO / "patches/wine/files"),
                str(REPO / "tests/restricted_token_host.c"), "-o", str(output),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            (root / "CELL027-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)
