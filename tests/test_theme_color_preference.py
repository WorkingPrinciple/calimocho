from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.build_launcher_overlay import REPO
from tools.port_theme_color_preference import PATHS, port, qualify
from tools.qualify_coremessaging_imports import PE

BASELINE = REPO / "build/winehq-11.20/package-cell042-01/source"


class ThemeColorPreferenceTests(unittest.TestCase):
    @unittest.skipUnless(BASELINE.is_dir(), "cell042 source absent")
    def test_predecessor_has_no_direct_preference_exports(self):
        exports = PE(BASELINE.parent / "install/lib/wine/x86_64-windows/uxtheme.dll").exports()
        self.assertNotIn("GetUserColorPreference", exports)
        self.assertNotIn("GetColorFromPreference", exports)

    @unittest.skipUnless(BASELINE.is_dir(), "cell042 source absent")
    def test_port_and_real_preference_code(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            for relative in PATHS[:2]:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(BASELINE / relative, path)
            before = (source / PATHS[1]).read_text()
            self.assertNotIn("GetUserColorPreference", before)
            self.assertNotIn("GetColorFromPreference", before)
            result = port(source)
            self.assertEqual(set(result["files"]), set(PATHS))
            spec = (source / PATHS[1]).read_text()
            self.assertEqual(spec, before + "\n@ stdcall GetUserColorPreference(ptr long)\n"
                             "@ stdcall GetColorFromPreference(ptr long long long)\n")
            self.assertTrue((source / PATHS[0]).read_text().endswith(
                '#include "color_preference.c"\n'))
            shutil.copy2(source / PATHS[2], root / "color_preference_under_test.c")
            executable = root / "theme-test"
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-fshort-wchar", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-fsanitize=address,undefined",
                "-I" + str(root), str(REPO / "tests/theme_color_preference_host.c"), "-o", str(executable),
            ], capture_output=True, text=True, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            with self.assertRaisesRegex(ValueError, "fresh"):
                port(source)
            (root / "CELL043-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen"):
                port(source)

    def test_qualification_rejects_missing_forwarded_or_mismatched_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            built = root / "build/dlls/uxtheme/x86_64-windows/uxtheme.dll"
            installed = root / "install/lib/wine/x86_64-windows/uxtheme.dll"
            built.parent.mkdir(parents=True)
            installed.parent.mkdir(parents=True)
            built.write_bytes(b"fixture")
            installed.write_bytes(b"fixture")
            with patch("tools.port_theme_color_preference.PE") as pe:
                pe.return_value.exports.return_value = {
                    "GetUserColorPreference": 0x1000, "GetColorFromPreference": 0x2000}
                record = qualify(root)
                self.assertEqual(record["status"], "source-pe-exports-qualified-not-executed")
                self.assertEqual(record["built_sha256"], record["installed_sha256"])
                pe.return_value.exports.return_value["GetColorFromPreference"] = "other.forward"
                with self.assertRaisesRegex(ValueError, "direct"):
                    qualify(root)
                del pe.return_value.exports.return_value["GetColorFromPreference"]
                with self.assertRaisesRegex(ValueError, "direct"):
                    qualify(root)
                installed.write_bytes(b"stale")
                with self.assertRaisesRegex(ValueError, "differ"):
                    qualify(root)


if __name__ == "__main__":
    unittest.main()
