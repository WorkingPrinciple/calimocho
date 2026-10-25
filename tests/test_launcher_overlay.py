import json
from pathlib import Path
import tempfile
import unittest

from tools.build_launcher_overlay import BASE, REPO, registry_for
from tools.build_minidump_overlay import inventory
from tools.port_package_protocols import port, SERVER_DECLARATION, OLD_ADMISSION
from tools.probe_wine_source import sha256

ROOT = REPO / "build/winehq-11.20/package-launcher-01"


class LauncherOverlayTests(unittest.TestCase):
    def test_port_is_exact_and_refuses_reapplication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "server").mkdir()
            target = root / "server/process.c"
            target.write_text((BASE / "source/server/process.c").read_text())
            port(root)
            changed = target.read_text()
            self.assertNotIn(SERVER_DECLARATION, changed)
            self.assertNotIn(OLD_ADMISSION, changed)
            self.assertIn("header.count > PACKAGE_REGISTRATION_MAX", changed)
            self.assertIn("registered_package_image( package,", changed)
            self.assertIn("Plain executable creation does not inherit", changed)
            with self.assertRaises(ValueError):
                port(root)

    def test_exact_server_and_one_added_module_only(self):
        receipt = json.loads((ROOT / "build-receipt.json").read_text())
        self.assertEqual(receipt["status"], "built-not-runtime-qualified")
        actual, previous = inventory(ROOT / "install"), inventory(BASE / "install")
        self.assertEqual(actual, receipt["files"])
        self.assertEqual(
            {name for name in actual.keys() | previous.keys() if actual.get(name) != previous.get(name)},
            {"bin/wineserver", "lib/wine/x86_64-windows/windows.system.launcher.dll"},
        )
        self.assertEqual((ROOT / "source/server/process.c").read_text().count(
            "registered_package_image( package,"), 1)
        self.assertTrue(all(step["exit_code"] == 0 for step in receipt["steps"]))

    def test_registry_rebases_all_runtime_paths_and_hashes(self):
        data = registry_for(ROOT / "install", ROOT / "windows.system.launcher.dll")
        self.assertEqual(data, json.loads((ROOT / "launcher.registry.local.UNQUALIFIED.json").read_text()))
        entry = data["engines"][0]
        self.assertEqual(entry["wine"], str(ROOT / "install/bin/wine"))
        self.assertEqual(entry["environment"]["WINELOADER"], entry["wine"])
        self.assertEqual(entry["environment"]["WINESERVER"], entry["wineserver"])
        self.assertEqual(entry["wineserver_sha256"], sha256(Path(entry["wineserver"])))
        self.assertNotIn(str(BASE / "install"), json.dumps(data))
        for asset in entry["profile_assets"]["files"] + entry["dependencies"]:
            if "path" in asset and "sha256" in asset:
                self.assertEqual(sha256(Path(asset["path"])), asset["sha256"])
        self.assertEqual(entry["smoke_test"]["status"], "not-run")
        self.assertEqual(entry["integrity"]["status"], "candidate-only")
