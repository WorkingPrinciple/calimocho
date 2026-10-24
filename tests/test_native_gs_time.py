import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
DEPENDENCY = "@loader_path/libnative-gs-localtime.dylib"


@unittest.skipUnless(sys.platform == "darwin" and Path("/usr/bin/clang").is_file(),
                     "Requires the authorized Darwin x86_64 compiler/runtime")
class NativeTimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.helper = cls.root / "libnative-gs-localtime.dylib"
        cls.probe = cls.root / "probe"
        cls.linked = cls.root / "probe-linked"
        compiler = ["/usr/bin/clang", "-arch", "x86_64", "-Wall", "-Wextra", "-Werror"]
        subprocess.run(compiler + [
            "-dynamiclib", f"-Wl,-install_name,{DEPENDENCY}",
            str(REPO / "tools/native_gs_localtime.c"), "-o", str(cls.helper),
        ], check=True, capture_output=True, timeout=30)
        source = str(REPO / "tests/native_gs_localtime_probe.c")
        subprocess.run(compiler + [source, "-o", str(cls.probe)],
                       check=True, capture_output=True, timeout=30)
        subprocess.run(compiler + [
            source, f"-Wl,-needed_library,{cls.helper}", "-o", str(cls.linked),
        ], check=True, capture_output=True, timeout=30)
        cls.environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith("DYLD_")
        }

    def run_probe(self, executable, function):
        return subprocess.run(
            [str(executable), function], env=self.environment,
            capture_output=True, text=True, timeout=20,
        )

    def test_localtime_and_ctime_reproduce_corruption_without_helper(self):
        for function in ("localtime", "ctime"):
            with self.subTest(function=function):
                result = self.run_probe(self.probe, function)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("succeeded=1 mirrored_peb_changed=1 slot_changed=0", result.stdout)

    def test_linked_helper_preserves_slot_for_audited_time_functions(self):
        for function in (
            "localtime", "ctime", "gmtime", "localtime_r", "gmtime_r",
            "ctime_r", "asctime", "asctime_r", "mktime", "timegm", "strftime",
        ):
            with self.subTest(function=function):
                result = self.run_probe(self.linked, function)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("succeeded=1 mirrored_peb_changed=0 slot_changed=0", result.stdout)

    def test_dependency_is_required_and_relative_to_relocated_loader(self):
        commands = subprocess.check_output(
            ["otool", "-l", str(self.linked)], text=True, timeout=30)
        self.assertRegex(
            commands,
            r"cmd LC_LOAD_DYLIB\s+cmdsize \d+\s+name "
            r"@loader_path/libnative-gs-localtime\.dylib \(offset \d+\)",
        )
        relocated = self.root / "relocated"
        relocated.mkdir()
        executable = relocated / "probe"
        shutil.copy2(self.linked, executable)
        missing = self.run_probe(executable, "ctime")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("Library not loaded: " + DEPENDENCY, missing.stderr)
        self.assertNotIn("succeeded=", missing.stdout)
        shutil.copy2(self.helper, relocated / self.helper.name)
        restored = self.run_probe(executable, "ctime")
        self.assertEqual(restored.returncode, 0, restored.stderr)


if __name__ == "__main__":
    unittest.main()
