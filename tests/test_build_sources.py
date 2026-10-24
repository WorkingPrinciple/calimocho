import contextlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import build_cw_candidate as cw
import build_freetype as ft
sys.path.pop(0)


class SourceBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.output = self.root / "output"
        self.freetype = self.root / "ft"
        (self.freetype / "lib").mkdir(parents=True)
        (self.freetype / "lib/libfreetype.6.dylib").write_bytes(b"fixture")
        self.archive = self.root / "source.tar"
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.pins = json.loads((cw.REPO / "versions.json").read_text())
        self.real_repo = cw.REPO
        for module in (cw, ft):
            self.enterContext(patch.object(module, "REPO", self.repo))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def archive_source(self, component):
        if component == "cw":
            root = "sources/wine"
            sources = {
                "configure": "fixture",
                "VERSION": "Wine version 11.0\n",
                "dlls/win32u/vulkan.c": (
                    '    if (!(libvulkan = getenv( "CX_LIBVULKAN" )) ||\n'
                    '        !(graphics_backend = getenv( "CX_ACTIVE_GRAPHICS_BACKEND" )) ||\n'
                    '        strcmp( graphics_backend, "wined3d" ))\n'
                    '        libvulkan = SONAME_LIBVULKAN;\n'
                    '    else\n'
                    '        ERR( "Using %s\\n", libvulkan );\n\n'
                ),
            }
        else:
            root = "freetype-2.13.3"
            sources = {"configure": "fixture"}
        staging = self.root / "staging"
        staging.mkdir()
        with tarfile.open(self.archive, "w") as stream:
            for name, content in sources.items():
                file = staging / root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content)
                stream.add(file, arcname=f"{root}/{name}", recursive=False)
        pin = "cw_candidate_sources" if component == "cw" else "freetype_source"
        self.pins[pin]["sha256"] = cw.sha256(self.archive)
        (self.repo / "versions.json").write_text(json.dumps(self.pins))
        if component == "cw":
            destination = self.repo / "patches/cw26.3"
            destination.mkdir(parents=True)
            patch_file = "0001-guard-absent-vulkan-soname.patch"
            (destination / patch_file).write_bytes(
                (self.real_repo / "patches/cw26.3" / patch_file).read_bytes())

    def check_output(self, command, **kwargs):
        if command[0] == "file":
            return f"{command[-1]}: Mach-O 64-bit x86_64\n"
        if command[0] == "otool":
            return "fixture system linkage\n"
        return "fixture tool version\n"

    def test_bad_archive_never_creates_output(self):
        self.archive_source("cw")
        self.archive.write_bytes(b"wrong source")
        for module, arguments in (
                (cw, (self.archive, self.output, self.freetype)),
                (ft, (self.archive, self.output))):
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                module.build(*arguments)
        self.assertFalse(self.output.exists())

    def test_wrong_architecture_is_not_silently_accepted(self):
        self.archive_source("cw")
        with patch.object(cw.subprocess, "check_output", return_value="Mach-O arm64"):
            with self.assertRaisesRegex(ValueError, "x86_64"):
                cw.build(self.archive, self.output, self.freetype)
        self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        self.archive_source("cw")
        self.output.mkdir()
        retained = self.output / "retained"
        retained.write_bytes(b"preserve")
        with patch.object(cw.subprocess, "check_output", side_effect=self.check_output), \
                patch.object(cw.shutil, "which", return_value="/usr/bin/true"):
            with self.assertRaises(FileExistsError):
                cw.build(self.archive, self.output, self.freetype)
        self.assertEqual(retained.read_bytes(), b"preserve")

    def test_patch_applies_and_configure_failure_prevents_compile(self):
        self.archive_source("cw")
        with patch.object(cw.subprocess, "check_output", side_effect=self.check_output), \
                patch.object(cw.shutil, "which", return_value="/usr/bin/true"), \
                patch.object(cw, "toolchain_identity", return_value={}), \
                patch.object(cw, "run_step", return_value={"exit_code": 1}) as run:
            self.assertEqual(cw.build(self.archive, self.output, self.freetype), 1)
        self.assertEqual(run.call_count, 1)
        content = (self.output / "sources/wine/dlls/win32u/vulkan.c").read_text()
        self.assertIn("#ifdef SONAME_LIBVULKAN", content)
        self.assertIn("return;", content)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["status"], "configure-failed")
        self.assertNotEqual(receipt["pristine_source_tree_sha256"],
                            receipt["source_tree_sha256"])

    def test_full_build_is_explicit_and_never_launches_or_installs(self):
        self.archive_source("cw")

        def run(command, directory, environment, log, timeout):
            self.assertNotIn("WINEPREFIX", environment)
            self.assertNotIn("DYLD_LIBRARY_PATH", environment)
            self.assertNotIn("CXXFLAGS", environment)
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 1800)
            if command[0] == "/usr/bin/make":
                self.assertEqual(command, ["/usr/bin/make", "-j4"])
                for relative in cw.FULL_ARTIFACTS:
                    path = directory / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"not executable")
            return {"command": command, "exit_code": 0}

        with patch.object(cw.subprocess, "check_output", side_effect=self.check_output), \
                patch.object(cw.shutil, "which", return_value="/usr/bin/true"), \
                patch.object(cw, "toolchain_identity", return_value={}), \
                patch.dict("os.environ", {"WINEPREFIX": "/existing",
                                          "DYLD_LIBRARY_PATH": "/existing",
                                          "CXXFLAGS": "contamination"}), \
                patch.object(cw, "run_step", side_effect=run):
            self.assertEqual(cw.build(
                self.archive, self.output, self.freetype, build_all=True), 0)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["status"], "full-build-compiled-not-runtime-qualified")
        self.assertFalse(receipt["runtime_executed"])
        self.assertFalse(receipt["installed"])
        self.assertFalse(receipt["apple_payloads_copied"])
        self.assertEqual(len(receipt["artifacts"]), len(cw.FULL_ARTIFACTS))

    def test_freetype_failure_stops_before_local_install(self):
        self.archive_source("ft")
        with patch.object(ft.subprocess, "check_output", side_effect=self.check_output), \
                patch.object(ft, "run_step", return_value={"exit_code": 2}) as run:
            self.assertEqual(ft.build(self.archive, self.output), 2)
        self.assertEqual(run.call_count, 1)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["status"], "configure-failed")
        self.assertFalse((self.output / "prefix").exists())

    def test_tree_hash_binds_names_contents_and_symlink_targets(self):
        tree = self.root / "tree"
        tree.mkdir()
        (tree / "file").write_bytes(b"original")
        (tree / "link").symlink_to("file")
        original = cw.tree_hash(tree)
        (tree / "file").write_bytes(b"changed")
        self.assertNotEqual(original, cw.tree_hash(tree))
        (tree / "file").write_bytes(b"original")
        (tree / "link").unlink()
        (tree / "link").symlink_to("other")
        self.assertNotEqual(original, cw.tree_hash(tree))


if __name__ == "__main__":
    unittest.main()
