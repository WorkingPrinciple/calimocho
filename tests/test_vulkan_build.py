import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import build_moltenvk
from tools.build_moltenvk import COMMIT, DEPENDENCIES, build


ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY = ROOT / "build/dependencies/moltenvk-1.4.2-x86_64-01"


class VulkanSourceBuildTests(unittest.TestCase):
    def test_requires_owned_output(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "worktree"):
                build(Path(directory) / "not-owned")

    def test_git_pins_are_full_and_fixed(self):
        self.assertRegex(COMMIT, r"^[a-f0-9]{40}$")
        self.assertEqual(len(DEPENDENCIES), 7)
        for _, commit in DEPENDENCIES.values():
            self.assertRegex(commit, r"^[a-f0-9]{40}$")

    def test_resume_rejects_changed_sources_before_building(self):
        for output_values, message in (
            (["0" * 40], "source identity mismatch"),
            ([COMMIT, " M MoltenVK/file.mm\n"], "tracked changes"),
        ):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                output = root / "build/candidate"
                output.mkdir(parents=True)
                previous = {"commit": COMMIT, "status": "failed",
                            "started_epoch": time.time(), "error": "original packaging failure"}
                (output / "receipt.json").write_text(json.dumps(previous))
                with patch.object(build_moltenvk, "ROOT", root), \
                        patch.object(build_moltenvk.subprocess, "check_output",
                                     side_effect=output_values), \
                        patch.object(build_moltenvk.subprocess, "Popen",
                                     side_effect=AssertionError("must not build changed sources")):
                    with self.assertRaisesRegex(ValueError, message):
                        build(output, resume=True)
                receipt = json.loads((output / "receipt.json").read_text())
                self.assertEqual(receipt["previous_attempt"], previous)
                self.assertEqual(receipt["status"], "failed")
                self.assertEqual(receipt["steps"], [])

    @unittest.skipUnless((DEPENDENCY / "receipt.json").is_file(), "Requires local source build")
    def test_local_receipt_binds_exact_source_and_x86_library(self):
        spec = importlib.util.spec_from_file_location("mvk", ROOT / "tools/build_moltenvk.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        receipt = json.loads((DEPENDENCY / "receipt.json").read_text())
        self.assertEqual(receipt["status"], "source-built-not-runtime-qualified")
        self.assertEqual(receipt["commit"], COMMIT)
        self.assertEqual(module.sha256(Path(receipt["library"])), receipt["library_sha256"])
        self.assertEqual((DEPENDENCY / "architecture.log").read_text().strip(), "x86_64")

    @unittest.skipUnless(shutil.which("x86_64-w64-mingw32-gcc") and
                         (DEPENDENCY / "source/External/Vulkan-Headers/include").is_dir(),
                         "Requires installed compiler and pinned source headers")
    def test_vulkan_probe_compiles_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "probe.o"
            subprocess.run([
                shutil.which("x86_64-w64-mingw32-gcc"), "-std=c11", "-Wall", "-Wextra",
                "-Werror", "-O2", "-I" + str(DEPENDENCY / "source/External/Vulkan-Headers/include"),
                "-c", str(ROOT / "tests/vulkan_present_probe.c"), "-o", str(output),
            ], check=True, capture_output=True, text=True, timeout=60)
            self.assertGreater(output.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
