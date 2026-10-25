from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.build_uwp_overlay import build
from tools.freeze_static_lifetime_runtime import freeze
from tools.port_appcontainer_object_path import PATHS, port

BASE = REPO / "build/winehq-11.20/package-cell043-01/source"


class AppContainerObjectPathTests(unittest.TestCase):
    def test_research_requires_fresh_dispatch_build(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            with self.assertRaisesRegex(ValueError, "fresh CoreMessaging"):
                build(Path(directory) / "unused", appcontainer_object_path=True)
            self.assertFalse((Path(directory) / "unused").exists())

    def test_research_cannot_be_frozen_even_without_blocker_label(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            (root / "build-receipt.json").write_text(json.dumps({"appcontainer_object_path": {}}))
            with self.assertRaisesRegex(ValueError, "no admitted current-native"):
                freeze(root, "HEAD", cell=43)
            self.assertEqual(list(root.glob("*FROZEN*")), [])

    @unittest.skipUnless(BASE.is_dir(), "cell043 source absent")
    def test_observed_abi_namespace_lifetime_and_failures(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            target = source / PATHS[0]
            target.parent.mkdir(parents=True)
            shutil.copy2(BASE / PATHS[0], target)
            self.assertIn('diagnostic_coremessaging_stub("RtlGetAppContainerNamedObjectPath")',
                          target.read_text())
            record = port(source)
            self.assertEqual(set(record["files"]), set(PATHS))
            self.assertNotIn('diagnostic_coremessaging_stub("RtlGetAppContainerNamedObjectPath")',
                             target.read_text())
            self.assertIn('diagnostic_coremessaging_stub("RtlGetThreadWorkOnBehalfTicket")',
                          target.read_text())
            shutil.copy2(source / PATHS[1], root / "object_path_under_test.c")
            executable = root / "object-path-test"
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-fshort-wchar", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-fsanitize=address,undefined", "-I" + str(root),
                str(REPO / "tests/appcontainer_object_path_host.c"), "-o", str(executable),
            ], capture_output=True, text=True, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            with self.assertRaisesRegex(ValueError, "fresh"):
                port(source)
            (root / "CELL044-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen"):
                port(source)


if __name__ == "__main__":
    unittest.main()
