import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "probe_wine_source", Path(__file__).resolve().parents[1] / "tools/probe_wine_source.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class SourceProbeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "configure").write_text("fixture; never execute")
        self.output = self.root / "build"
        self.pin = json.loads((probe.REPO / "versions.json").read_text())["winehq_probe"]

    def revision(self, command, **kwargs):
        if command[-1] == "HEAD":
            return self.pin["commit"] + "\n"
        if command[-1] == "HEAD^{tree}":
            return "pinned-tree\n"
        return ""

    def test_wrong_commit_or_modified_source_is_rejected_before_build(self):
        with patch.object(probe.subprocess, "check_output", return_value="wrong\n"):
            with self.assertRaisesRegex(ValueError, "differs from pin"):
                probe.probe(self.source, self.output)
        with patch.object(probe.subprocess, "check_output", side_effect=[
                self.pin["commit"] + "\n", " M configure\n"]):
            with self.assertRaisesRegex(ValueError, "pristine"):
                probe.probe(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_configure_failure_stops_before_compile_and_records_diagnostic(self):
        with patch.object(probe.subprocess, "check_output", side_effect=self.revision), \
                patch.object(probe.shutil, "which", return_value="/installed/bison"), \
                patch.object(probe, "run_step", return_value={
                    "exit_code": 1, "log": "configure.log", "timed_out": False}) as run:
            self.assertEqual(probe.probe(self.source, self.output), 1)
        self.assertEqual(run.call_count, 1)
        receipt = json.loads((self.output / "probe-receipt.json").read_text())
        self.assertEqual(receipt["status"], "configure-failed")
        self.assertFalse(receipt["runtime_executed"])
        self.assertFalse(receipt["installed"])

    def test_missing_fonts_can_only_be_omitted_explicitly(self):
        with patch.object(probe.subprocess, "check_output", side_effect=self.revision), \
                patch.object(probe.shutil, "which", return_value="/installed/bison"), \
                patch.object(probe, "run_step", return_value={"exit_code": 1}) as run:
            probe.probe(self.source, self.output, without_freetype=True)
        self.assertIn("--without-freetype", run.call_args.args[0])
        receipt = json.loads((self.output / "probe-receipt.json").read_text())
        self.assertTrue(receipt["without_freetype"])

    def test_success_records_nonempty_server_without_launching_it(self):
        def run(command, directory, environment, log, timeout):
            self.assertNotIn("WINEPREFIX", environment)
            self.assertNotIn("DYLD_LIBRARY_PATH", environment)
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 1800)
            if command[0] == "/usr/bin/make":
                self.assertEqual(command, ["/usr/bin/make", "-j4", "server/wineserver"])
                (directory / "server").mkdir()
                (directory / "server/wineserver").write_bytes(b"fixture, not executable")
            return {"command": command, "exit_code": 0, "timed_out": False}

        with patch.object(probe.subprocess, "check_output", side_effect=self.revision), \
                patch.object(probe.shutil, "which", return_value="/installed/bison"), \
                patch.dict("os.environ", {"WINEPREFIX": "/existing",
                                          "DYLD_LIBRARY_PATH": "/existing"}), \
                patch.object(probe, "run_step", side_effect=run):
            self.assertEqual(probe.probe(self.source, self.output), 0)
        receipt = json.loads((self.output / "probe-receipt.json").read_text())
        self.assertEqual(receipt["status"], "compiled")
        self.assertEqual(receipt["artifact"]["sha256"],
                         probe.sha256(self.output / "server/wineserver"))
        self.assertEqual(len(receipt["steps"]), 2)

    def test_source_tree_and_existing_output_are_not_mutated(self):
        with patch.object(probe.subprocess, "check_output", side_effect=self.revision):
            with self.assertRaisesRegex(ValueError, "outside the source"):
                probe.probe(self.source, self.source / "build")
        self.output.mkdir()
        retained = self.output / "retained"
        retained.write_bytes(b"preserve")
        with patch.object(probe.subprocess, "check_output", side_effect=self.revision), \
                patch.object(probe.shutil, "which", return_value="/installed/bison"):
            with self.assertRaises(FileExistsError):
                probe.probe(self.source, self.output)
        self.assertEqual(retained.read_bytes(), b"preserve")


if __name__ == "__main__":
    unittest.main()
