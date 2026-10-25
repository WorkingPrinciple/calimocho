import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.prepare_observed_xaml_recipe import REPO, SOURCES, prepare


class ObservedXamlRecipeTests(unittest.TestCase):
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
            def git_output(command, **kwargs):
                if command[1] == "rev-parse":
                    return "owned-test-producer\n"
                relative = command[2].split(":", 1)[1]
                self.assertIn(relative, SOURCES)
                return (REPO / relative).read_bytes()
            with patch("tools.prepare_observed_xaml_recipe.subprocess.check_output", side_effect=git_output):
                with self.assertRaisesRegex(ValueError, "completed exact native-factory"):
                    prepare(output, observation, "HEAD")
            self.assertFalse(output.exists())
