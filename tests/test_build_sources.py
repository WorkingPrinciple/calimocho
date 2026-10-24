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

    def test_output_overlap_check_rejects_equal_ancestor_and_descendant(self):
        source = (self.root / "winehq-source").resolve()
        source.mkdir()
        for output in (source, source / "candidate", self.root):
            with self.subTest(output=output):
                with self.assertRaisesRegex(ValueError, "overlap WineHQ source"):
                    cw.ensure_output_disjoint(
                        output.resolve(), source, "WineHQ source")

    def test_output_inside_pristine_winehq_source_is_rejected_before_writing(self):
        self.archive_source("cw")
        source = self.root / "winehq-source"
        source.mkdir()
        marker = source / "tracked-file"
        marker.write_text("preserve")
        output = source / "candidate"
        pin = self.pins["winehq_probe"]["commit"]

        def git_output(command, **kwargs):
            if command[0] == "git" and "rev-parse" in command:
                return f"{pin}\n"
            if command[0] == "git" and "status" in command:
                return ""
            return self.check_output(command, **kwargs)

        with patch.object(cw.subprocess, "check_output", side_effect=git_output), \
                patch.object(cw.subprocess, "run",
                             side_effect=AssertionError("source archive must not run")), \
                patch.object(cw.shutil, "which", return_value="/usr/bin/true"), \
                patch.object(cw, "toolchain_identity", return_value={}):
            with self.assertRaisesRegex(ValueError, "overlap.*WineHQ source"):
                cw.build(self.archive, output, self.freetype, winehq_source=source)

        self.assertFalse(output.exists())
        self.assertEqual(marker.read_text(), "preserve")

    def test_output_using_var_alias_inside_freetype_prefix_is_rejected(self):
        self.archive_source("cw")
        prefix = self.freetype.resolve()
        if Path("/var").resolve() == Path("/private/var").resolve():
            alias = Path(str(prefix).replace("/private/var/", "/var/", 1))
        else:
            alias_root = self.root.parent / f"{self.root.name}-var-alias"
            alias_root.symlink_to(self.root, target_is_directory=True)
            alias = alias_root / "ft"
        self.assertEqual(alias.resolve(), prefix)
        output = alias / "candidate"

        with patch.object(cw.subprocess, "run",
                          side_effect=AssertionError("patch must not run")):
            with self.assertRaisesRegex(ValueError, "overlap.*FreeType prefix"):
                cw.build(self.archive, output, self.freetype)

        self.assertFalse(output.exists())
        self.assertTrue((prefix / "lib/libfreetype.6.dylib").is_file())

    def test_wrong_architecture_is_not_silently_accepted(self):
        self.archive_source("cw")
        with patch.object(cw.subprocess, "check_output", return_value="Mach-O arm64"):
            with self.assertRaisesRegex(ValueError, "x86_64"):
                cw.build(self.archive, self.output, self.freetype)
        self.assertFalse(self.output.exists())

    def test_tls_prefix_missing_library_is_rejected_before_build(self):
        self.archive_source("cw")
        tls = self.root / "tls"
        tls.mkdir()
        with patch.object(cw.subprocess, "check_output", side_effect=self.check_output):
            with self.assertRaisesRegex(ValueError, "GnuTLS library and pkg-config"):
                cw.build(self.archive, self.output, self.freetype, tls=tls)
        self.assertFalse(self.output.exists())

    def test_tls_configure_requires_gnutls_and_blocks_compile_without_soname(self):
        self.archive_source("cw")
        tls = self.root / "tls"
        (tls / "lib/pkgconfig").mkdir(parents=True)
        (tls / "lib/libgnutls.dylib").write_bytes(b"fixture")
        (tls / "lib/pkgconfig/gnutls.pc").write_text("fixture")

        def configure(command, directory, environment, log, timeout):
            self.assertIn("--with-gnutls", command)
            self.assertIn(f"--prefix={self.output / 'install'}", command)
            self.assertEqual(environment["PKG_CONFIG_PATH"], str(tls / "lib/pkgconfig"))
            self.assertEqual(environment["ac_cv_lib_soname_gnutls"],
                             "@rpath/libgnutls.dylib")
            self.assertIn(f"-Wl,-rpath,{tls / 'lib'}", environment["LDFLAGS"])
            (directory / "include").mkdir()
            (directory / "include/config.h").write_text("/* no GnuTLS */")
            return {"exit_code": 0}

        with patch.object(cw.subprocess, "check_output", side_effect=self.check_output), \
                patch.object(cw.shutil, "which", return_value="/usr/bin/true"), \
                patch.object(cw, "toolchain_identity", return_value={}), \
                patch.object(cw, "run_step", side_effect=configure) as run:
            with self.assertRaisesRegex(ValueError, "no GnuTLS SONAME"):
                cw.build(self.archive, self.output, self.freetype, tls=tls)
        self.assertEqual(run.call_count, 1)

    def test_tls_only_build_targets_crypto_modules_without_full_build(self):
        self.archive_source("cw")
        tls = self.root / "tls"
        (tls / "lib/pkgconfig").mkdir(parents=True)
        (tls / "lib/libgnutls.dylib").write_bytes(b"fixture")
        (tls / "lib/pkgconfig/gnutls.pc").write_text("fixture")
        commands = []

        def run(command, directory, environment, log, timeout):
            commands.append(command)
            if "configure" in command[0]:
                (directory / "include").mkdir()
                (directory / "include/config.h").write_text(
                    '#define SONAME_LIBGNUTLS "@rpath/libgnutls.dylib"\n')
            if command[-3:] == list(cw.TLS_TARGETS):
                for relative in cw.TLS_ARTIFACTS:
                    artifact = directory / relative
                    artifact.parent.mkdir(parents=True, exist_ok=True)
                    artifact.write_bytes(b"fixture")
            return {"command": command, "exit_code": 0}

        with patch.object(cw.subprocess, "check_output", side_effect=self.check_output), \
                patch.object(cw.shutil, "which", return_value="/usr/bin/true"), \
                patch.object(cw, "toolchain_identity", return_value={}), \
                patch.object(cw, "run_step", side_effect=run):
            self.assertEqual(cw.build(self.archive, self.output, self.freetype,
                                      tls=tls, tls_only=True), 0)
        self.assertEqual(commands[-1], ["/usr/bin/make", "-j4"] + list(cw.TLS_TARGETS))
        self.assertIn("libucrtbase.a", commands[1][-1])
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["status"], "tls-modules-compiled-not-runtime-qualified")
        self.assertFalse(receipt["runtime_executed"])

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
        self.assertIn("programs/wineboot/x86_64-windows/wineboot.exe",
                      cw.FULL_ARTIFACTS)
        self.assertNotIn("programs/wineboot/i386-windows/wineboot.exe",
                         cw.FULL_ARTIFACTS)

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

    def test_winehq_build_requires_and_binds_launch_loaded_interposer(self):
        self.archive_source("cw")
        source = self.root / "winehq-input"
        source.mkdir()
        helper = self.repo / "tools/native_gs_localtime.c"
        helper.parent.mkdir()
        helper.write_bytes((self.real_repo / "tools/native_gs_localtime.c").read_bytes())
        (helper.parent / "port_d3dmetal.py").write_bytes(
            (self.real_repo / "tools/port_d3dmetal.py").read_bytes())
        pin = self.pins["winehq_probe"]["commit"]

        def check_output(command, **kwargs):
            if command[0] == "git":
                return f"{pin}\n" if "rev-parse" in command else ""
            if command[:2] == ["otool", "-l"]:
                return (
                    "cmd LC_LOAD_DYLIB\ncmdsize 80\n"
                    "name @loader_path/libnative-gs-localtime.dylib (offset 24)\n"
                ) if mode != "missing-load-command" else "cmd LC_LOAD_WEAK_DYLIB\n"
            return self.check_output(command, **kwargs)

        def archive(command, **kwargs):
            destination = Path(next(arg.split("=", 1)[1] for arg in command
                                    if arg.startswith("--output=")))
            with tarfile.open(destination, "w") as stream:
                staging = self.root / "staging/sources/wine"
                for name in ("configure", "VERSION"):
                    stream.add(staging / name, arcname=name)

        for mode in (
            "success", "compiler-failure", "loader-link-failure",
            "missing-artifact", "missing-load-command",
        ):
            output = self.root / mode

            def run(command, directory, environment, log, timeout):
                if command[0] == "/usr/bin/make":
                    if "-W" in command and mode == "loader-link-failure":
                        return {"command": command, "exit_code": 1}
                    for relative in cw.FULL_ARTIFACTS:
                        path = directory / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(b"fixture")
                if command[0] == "/usr/bin/clang":
                    self.assertIn("-arch", command)
                    self.assertIn("x86_64", command)
                    self.assertIn("-dynamiclib", command)
                    self.assertNotIn("DYLD_INSERT_LIBRARIES", environment)
                    if mode == "compiler-failure":
                        return {"command": command, "exit_code": 1}
                    if mode in ("success", "missing-load-command", "loader-link-failure"):
                        Path(command[command.index("-o") + 1]).write_bytes(b"helper")
                return {"command": command, "exit_code": 0}

            with self.subTest(mode=mode), \
                    patch.object(cw.subprocess, "check_output", side_effect=check_output), \
                    patch.object(cw.subprocess, "run", side_effect=archive), \
                    patch.object(cw.shutil, "which", return_value="/usr/bin/true"), \
                    patch.object(cw, "toolchain_identity", return_value={}), \
                    patch.object(cw, "port", return_value={}), \
                    patch.object(cw, "run_step", side_effect=run):
                if mode in ("missing-artifact", "missing-load-command"):
                    expected = "artifact missing" if mode == "missing-artifact" else "LC_LOAD_DYLIB"
                    with self.assertRaisesRegex(ValueError, expected):
                        cw.build(self.archive, output, self.freetype, True, source)
                else:
                    self.assertEqual(cw.build(
                        self.archive, output, self.freetype, True, source),
                        1 if mode in ("compiler-failure", "loader-link-failure") else 0)
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertEqual(receipt["native_gs_interposer_source"]["sha256"],
                             cw.sha256(helper))
            self.assertNotIn("DYLD_INSERT_LIBRARIES", receipt["runtime_environment"])
            dependency = receipt["runtime_dependencies"][0]
            self.assertEqual(dependency["loader_dependency"],
                             "@loader_path/libnative-gs-localtime.dylib")
            self.assertEqual(dependency["required_load_command"], "LC_LOAD_DYLIB")
            self.assertEqual(dependency["path"],
                             str(output / "build/loader/libnative-gs-localtime.dylib"))
            if mode == "success":
                self.assertEqual(receipt["artifacts"][-1]["sha256"],
                                 cw.sha256(output / "build/loader/libnative-gs-localtime.dylib"))
                self.assertEqual(receipt["steps"][-1]["command"][:5],
                                 ["/usr/bin/make", "-W", "loader/main.o", "loader/wine",
                                  f"LDFLAGS=-L{self.freetype / 'lib'} -Wl,-needed_library,"
                                  f"{output / 'build/loader/libnative-gs-localtime.dylib'}"])
            if mode == "compiler-failure":
                self.assertEqual(receipt["status"], "native-gs-interposer-failed")
            if mode == "loader-link-failure":
                self.assertEqual(receipt["status"], "native-gs-loader-link-failed")

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
