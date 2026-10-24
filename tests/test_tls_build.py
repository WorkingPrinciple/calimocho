import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_tls
sys.path.pop(0)


class TLSBuildTests(unittest.TestCase):
    def test_corrupt_archive_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            pin = {"name": "gmp", "url": "https://example.invalid/gmp.tar",
                   "sha256": "0" * 64}
            (root / "gmp.tar").write_bytes(b"not pinned")
            (root / "versions.json").write_text(json.dumps({"tls_sources": [pin]}))
            with patch.object(build_tls, "REPO", root):
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    build_tls.build(root, root / "output")
            self.assertFalse((root / "output").exists())

    def test_build_failure_has_receipt_and_never_installs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            archives = root / "archives"
            archives.mkdir()
            configure = root / "configure"
            configure.write_text("fixture")
            archive = archives / "gmp.tar"
            with tarfile.open(archive, "w") as stream:
                stream.add(configure, arcname="gmp-6.3.0/configure")
            pin = {"name": "gmp", "version": "6.3.0",
                   "url": "https://example.invalid/gmp.tar",
                   "sha256": build_tls.sha256(archive)}
            (root / "versions.json").write_text(json.dumps({"tls_sources": [pin]}))
            output = root / "output"
            with patch.object(build_tls, "REPO", root), \
                    patch.object(build_tls, "run_step",
                                 return_value={"exit_code": 2, "log": "fixture"}) as run:
                with self.assertRaisesRegex(ValueError, "configure failed"):
                    build_tls.build(archives, output)
            self.assertEqual(run.call_count, 1)
            command, _, environment, _, timeout = run.call_args.args
            self.assertIn(f"--prefix={output / 'prefix'}", command)
            self.assertEqual(environment["CC"], "/usr/bin/clang -arch x86_64")
            self.assertEqual(environment["PKG_CONFIG_LIBDIR"],
                             str(output / "prefix/lib/pkgconfig"))
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 1800)
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertEqual(receipt["status"], "gmp-configure")
            self.assertEqual(receipt["steps"][0]["exit_code"], 2)

    @unittest.skipUnless(shutil.which("x86_64-w64-mingw32-gcc"), "Requires installed MinGW")
    def test_owned_https_probe_builds_with_certificate_checks_enabled(self):
        import subprocess
        source = Path(__file__).with_name("winhttp_https_probe.c")
        text = source.read_text()
        self.assertNotIn("SECURITY_FLAG_IGNORE", text)
        self.assertNotIn("WINHTTP_OPTION_SECURITY_FLAGS", text)
        self.assertIn("WINHTTP_FLAG_SECURE", text)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "probe.exe"
            subprocess.run(
                ["x86_64-w64-mingw32-gcc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-O2", str(source), "-o", str(output), "-lwinhttp"],
                check=True, capture_output=True, timeout=60,
            )
            self.assertEqual(output.read_bytes()[:2], b"MZ")


if __name__ == "__main__":
    unittest.main()
