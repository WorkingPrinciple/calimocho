from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_token_identity import port
from tools.server_request_gate import overflows


class TokenIdentityTests(unittest.TestCase):
    def test_owned_identity_and_distinct_source_query_rights(self):
        baseline = REPO / "build/winehq-11.20/package-alpc-identity-01/source"
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            for relative in ("server/token.c", "server/protocol.def", "dlls/ntdll/unix/security.c"):
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, target)
            port(source)
            text = (source / "server/token.c").read_text()
            start = text.index("DECL_HANDLER(get_token_identity)")
            (root / "token_identity_query_under_test.c").write_text(text[start:])
            start = text.index("DECL_HANDLER(create_token)")
            end = text.index("\n/* open a security token */", start)
            (root / "token_create_under_test.c").write_text(
                text[start:end].replace("token = create_token(", "token = construct_token("))
            executable = root / "identity-test"
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-Wno-sign-compare", "-fsanitize=address,undefined",
                "-I" + str(root), "-I" + str(baseline / "include"),
                "-I" + str(source / "server"), str(REPO / "tests/token_identity_host.c"),
                "-o", str(executable),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            self.assertIn("token_copy_identity( token, src_token )", text)
            self.assertIn("newpriv->def = privilege->def;", text)
            client = (source / "dlls/ntdll/unix/security.c").read_text()
            self.assertNotIn("AuthenticationId.LowPart  = 0;", client)
            # __SERVER_MAX_DATA is 5: the identity rides with the user SID (cell032 EBADF).
            self.assertEqual(overflows(client), [])
            self.assertIn("wine_server_add_data( req, head, head_size );", client)
            self.assertIn("wineserver: create_token pid", text)
            with self.assertRaisesRegex(ValueError, "fresh"):
                port(source)
            (root / "CELL027-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)
