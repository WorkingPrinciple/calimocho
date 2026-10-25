import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.freeze_launcher_runtime import checked_assets
from tools.prepare_native_xaml_recipe import REPO, merge_overrides
from tools.probe_wine_source import sha256


class NativeXamlRecipeTests(unittest.TestCase):
    def test_frozen010_changes_recipe_not_engine_and_retains_explicit_setup(self):
        root = REPO / "build/winehq-11.20/package-uwp-native-xaml-01"
        receipt = json.loads((root / "cell010-receipt.json").read_text())
        previous = json.loads(Path(receipt["predecessor_receipt"]).read_text())
        for key in ("engine", "install", "wine_sha256", "wineserver_sha256", "ntdll_sha256",
                    "launcher_sha256", "helper", "helper_sha256", "verification", "verification_sha256",
                    "inventory", "inventory_sha256", "graph", "protocol_table", "server_registration_table"):
            self.assertEqual(receipt[key], previous[key], key)
        for key, digest in receipt.items():
            if key.endswith("_sha256") and key[:-7] in receipt:
                path = receipt[key[:-7]]
                if isinstance(path, str) and Path(path).is_file():
                    self.assertEqual(sha256(Path(path)), digest, key)
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(
                ["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest, relative)
        registry = json.loads(Path(receipt["registry"]).read_text())
        entry = registry["engines"][0]
        checked_assets(entry)
        self.assertEqual(inventory(Path(receipt["install"])),
                         json.loads(Path(receipt["inventory"]).read_text())["files"])
        expected = "mscoree=;mshtml=;windows.ui.xaml=n"
        self.assertEqual(entry["environment"]["WINEDLLOVERRIDES"], expected)
        self.assertEqual(receipt["environment"]["WINEDLLOVERRIDES"], expected)
        self.assertEqual(receipt["server_start"]["environment"]["WINEDLLOVERRIDES"], expected)
        self.assertNotEqual(receipt["prefix"], previous["prefix"])
        self.assertEqual(receipt["collector_limit_seconds"], 180)
        self.assertFalse(receipt["runtime_executed"])
        observer = receipt["target_observer"]
        self.assertEqual(sha256(Path(observer["path"])), observer["sha256"])
        self.assertEqual(observer["app_id"], "Microsoft.Xbox.AppL")
        self.assertTrue(observer["image"].endswith("\\XboxPcApp.exe"))
        build = json.loads(Path(receipt["observer_build"]).read_text())
        self.assertEqual(build["exit_code"], 0)
        self.assertIn("-Werror", build["argv"])
        for path, digest in build["inputs"].items():
            self.assertEqual(sha256(Path(path)), digest)
        registration = Path(receipt["native_xaml_registration"]).read_text(encoding="utf-16")
        self.assertEqual(registration.count("[HKEY_"), 1)
        self.assertIn("Windows.UI.Xaml.Application]", registration)
        self.assertNotIn("ThreadingModel", registration)
        self.assertNotIn("ActivationType", registration)
        self.assertEqual(receipt["native_xaml_input"]["sha256"],
                         "16302bfe92cd6d1cdae9666767e53323fa11e10ab1c751d8142e6f95f3a82899")

    def test_retained_native_override_preserves_unrelated_baseline(self):
        result = merge_overrides("mscoree,mshtml=;amd_ags_x64=b",
                                 "mscoree,mshtml=;windows.ui.xaml=n")
        values = dict(item.split("=", 1) for item in result.split(";"))
        self.assertEqual(values, {"mscoree": "", "mshtml": "", "amd_ags_x64": "b",
                                  "windows.ui.xaml": "n"})

    def test_missing_native_only_or_malformed_settings_fail(self):
        for value in ("mscoree=", "windows.ui.xaml=b", "windows.ui.xaml=n,b",
                      "windows.ui.xaml", "windows.ui.xaml=n;SECRET=x"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                merge_overrides("mscoree,mshtml=", value)
