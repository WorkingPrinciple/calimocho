import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.probe_wine_source import sha256
from tools.prepare_observed_xaml_recipe import REPO, SOURCES, prepare


class ObservedXamlRecipeTests(unittest.TestCase):
    @staticmethod
    def git_output(command, **kwargs):
        if command[1] == "rev-parse":
            return "owned-test-producer\n"
        relative = command[2].split(":", 1)[1]
        if relative not in SOURCES:
            raise AssertionError("Unexpected producer source")
        return (REPO / relative).read_bytes()

    def test_complete_owned_fixture_derives_only_supported_mapping_and_preserves_core(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as temporary:
            directory = Path(temporary)
            probe = json.loads((REPO / "build/winehq-11.20/native-xaml-factory-probe-02/build-receipt.json").read_text())
            classes = Path(probe["classes"]).read_text().splitlines()
            selected = {"Windows.UI.Xaml.Application", "Windows.UI.Xaml.FrameworkViewSource"}
            output = directory / "synthetic-factory-results.txt"
            lines = [
                "xaml-factory index=%d factory=%s present=%d qi=%s" %
                (index, "00000000" if name in selected else "80040111",
                 name in selected, "00000000" if name in selected else "80004002")
                for index, name in enumerate(classes)]
            lines.append("xaml-factory count=%d supported=2 result=00000000" % len(classes))
            output.write_text("\n".join(lines) + "\n")
            observation = directory / "synthetic-observation.json"
            observation.write_text(json.dumps({
                "scope": "owned synthetic test, not native evidence",
                "probe_sha256": probe["probe_sha256"], "classes_sha256": probe["classes_sha256"],
                "native_sha256": "16302bfe92cd6d1cdae9666767e53323fa11e10ab1c751d8142e6f95f3a82899",
                "exit_code": 0, "timed_out": False, "cleanup_complete": True,
                "output": str(output), "output_sha256": sha256(output),
            }))
            exists = Path.exists
            def fixture_exists(path):
                if str(path) == "/Users/dragoshont/xodus-runs/xbox-calimocho-packaged-20261025-011":
                    return False
                return exists(path)
            with patch("tools.prepare_observed_xaml_recipe.subprocess.check_output", side_effect=self.git_output), \
                    patch.object(Path, "exists", fixture_exists):
                receipt_path = prepare(directory / "owned-synthetic-output", observation, "HEAD")
            receipt = json.loads(receipt_path.read_text())
            previous = json.loads(Path(receipt["predecessor_receipt"]).read_text())
            self.assertEqual(receipt["install"], previous["install"])
            self.assertEqual(receipt["registry"], previous["registry"])
            self.assertEqual(receipt["native_mapping_count"], 2)
            mapping = json.loads(Path(receipt["native_mapping"]).read_text())
            self.assertEqual(set(mapping["selected_classes"]), selected)
            self.assertTrue(any(item["class"] == "Windows.ApplicationModel.Core.CoreApplication"
                                and item["decision"].startswith("preserve-wine-builtin:")
                                for item in mapping["decisions"]))
            registration = Path(receipt["native_xaml_registration"]).read_text(encoding="utf-16")
            self.assertEqual(registration.count("[HKEY_"), 2)
            self.assertNotIn("CoreApplication", registration)
            self.assertIn("cross-build mapping", receipt["native_mapping_basis"])
            self.assertFalse(receipt["runtime_executed"])

    def test_existing_output_is_rejected_before_reading_external_observation(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as temporary:
            root = Path(temporary)
            observation = root / "observation.json"
            observation.write_text("{}")
            with self.assertRaisesRegex(ValueError, "new owned011"):
                prepare(root, observation, "HEAD")
            self.assertEqual(list(root.iterdir()), [observation])

    def test_failed_probe_observation_cannot_create011_output(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as temporary:
            directory = Path(temporary)
            output = directory / "new011"
            probe = json.loads((REPO / "build/winehq-11.20/native-xaml-factory-probe-02/build-receipt.json").read_text())
            observation = directory / "observation.json"
            observation.write_text(json.dumps({
                "probe_sha256": probe["probe_sha256"], "classes_sha256": probe["classes_sha256"],
                "native_sha256": "16302bfe92cd6d1cdae9666767e53323fa11e10ab1c751d8142e6f95f3a82899",
                "exit_code": 1, "timed_out": False, "cleanup_complete": True,
            }))
            with patch("tools.prepare_observed_xaml_recipe.subprocess.check_output", side_effect=self.git_output):
                with self.assertRaisesRegex(ValueError, "completed exact native-factory"):
                    prepare(output, observation, "HEAD")
            self.assertFalse(output.exists())
