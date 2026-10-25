from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_restricted_token import port, WRITE_MATRIX


class RestrictedTokenTests(unittest.TestCase):
    def test_actual_access_check_enforces_second_pass_and_restriction_ownership(self):
        baseline = REPO / "build/winehq-11.20/package-alpc-transport-04/source"
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            for relative in ("server/token.c", "server/protocol.def", "dlls/ntdll/unix/security.c"):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, path)
            result = port(source)
            self.assertFalse(result["registrar_qualified"])
            text = (source / "server/token.c").read_text()
            start = text.index("static unsigned int token_access_check(")
            end = text.index("\nconst struct acl *token_get_default_dacl", start)
            (root / "token_access_under_test.c").write_text(text[start:end])
            start = text.index("DECL_HANDLER(filter_token)")
            end = text.index("\n/* checks the specified privileges", start)
            handler = text[start:end]
            start = text.index("DECL_HANDLER(get_token_groups)")
            end = text.index("\nDECL_HANDLER(get_token_info)", start)
            (root / "token_handlers_under_test.c").write_text(handler + "\n" + text[start:end])
            output = root / "restricted-test"
            command = ["/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                       "-Wno-unused-parameter", "-Wno-unused-function",
                       "-fsanitize=address,undefined", "-I" + str(root),
                       "-I" + str(baseline / "include"),
                       "-I" + str(REPO / "patches/wine/files"),
                       str(REPO / "tests/restricted_token_host.c"), "-o", str(output)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            native = subprocess.check_output([
                "git", "--no-replace-objects", "show",
                WRITE_MATRIX["commit"] + ":" + WRITE_MATRIX["path"],
            ], cwd=WRITE_MATRIX["repository"], text=True)
            expected = [row for row in native.splitlines() if row.startswith("OVERLAP map=")]
            observed = [row for row in executed.stdout.splitlines() if row.startswith("OVERLAP map=")]
            self.assertEqual(len(expected), 60)
            self.assertEqual(observed, expected)
            self.assertIn("case TokenRestrictedSids:", (source / "dlls/ntdll/unix/security.c").read_text())
            self.assertIn("token_copy_restrictions( token, src_token )", text)
            self.assertIn("token_add_restrictions( token, source", text)
            with self.assertRaisesRegex(ValueError, "fresh source"):
                port(source)
            (root / "CELL027-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)
