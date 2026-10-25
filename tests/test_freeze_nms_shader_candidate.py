import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "freeze", Path(__file__).resolve().parents[1] / "tools/freeze_nms_shader_candidate.py")
freeze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freeze)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.install = Path("/owned/candidate/install")
        self.original = {
            "schema_version": 1,
            "engines": [{
                "name": "old", "version": "Wine 11.20", "install_path": "/base/install",
                "wine": "/base/install/bin/wine",
                "environment": {"WINELOADER": "/base/install/bin/wine",
                                "MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS": "1",
                                "MTL_HUD_ENABLED": "1"},
                "source_patches": [],
                "dependencies": [{"path": "/base/install/" + str(freeze.LIBRARY), "sha256": "old"}],
                "profile_assets": {"files": [
                    {"path": "/external/apple", "sha256": "apple"},
                    {"path": "/base/install/" + str(freeze.LIBRARY), "sha256": "old"},
                ]},
                "gptk_symlink_map": [{"path": "/base/install/d3d12.dll",
                                     "target": "/external/apple"}],
                "smoke_test": {"status": "pass"},
                "graphics_tests": [{"status": "pass"}],
                "tls_positive_test": {"status": "pass"},
                "tls_negative_test": {"status": "pass"},
                "integrity": {"status": "unchanged", "manifest_path": "/old/manifest"},
                "build_evidence": {"old": "receipt"},
            }],
        }

    def derive(self):
        with patch.object(freeze, "digest", return_value="new-digest"):
            return freeze.derive_registry(self.original, self.install)["engines"][0]

    def test_base_is_not_mutated(self):
        before = copy.deepcopy(self.original)
        self.derive()
        self.assertEqual(self.original, before)

    def test_no_inherited_runtime_success(self):
        entry = self.derive()
        self.assertEqual(entry["smoke_test"]["status"], "not-run")
        for key in ("graphics_tests", "tls_positive_test", "tls_negative_test",
                    "integrity", "build_evidence"):
            self.assertNotIn(key, entry)
        self.assertIn("Not tested", entry["game_acceptance"])

    def test_only_install_paths_are_rebased(self):
        entry = self.derive()
        self.assertEqual(entry["wine"], "/owned/candidate/install/bin/wine")
        self.assertEqual(entry["environment"]["WINELOADER"], entry["wine"])
        self.assertEqual(entry["gptk_symlink_map"][0]["path"], "/owned/candidate/install/d3d12.dll")
        self.assertEqual(entry["gptk_symlink_map"][0]["target"], "/external/apple")
        self.assertEqual(entry["profile_assets"]["files"][0], {"path": "/external/apple", "sha256": "apple"})

    def test_candidate_library_pins_are_updated(self):
        entry = self.derive()
        self.assertEqual(entry["dependencies"][0]["sha256"], "new-digest")
        self.assertEqual(entry["profile_assets"]["files"][1]["sha256"], "new-digest")
        self.assertEqual(len(entry["source_patches"]), 1)

    def test_sampler_environment_remains_unchanged(self):
        entry = self.derive()
        self.assertEqual(entry["environment"]["MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS"], "1")
        self.assertEqual(entry["environment"]["MTL_HUD_ENABLED"], "1")

    def test_multiple_engines_are_rejected(self):
        self.original["engines"] *= 2
        with self.assertRaises(ValueError):
            self.derive()


if __name__ == "__main__":
    unittest.main()
