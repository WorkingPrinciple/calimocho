import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.probe_wine_source import sha256
from tools.freeze_launcher_runtime import checked_assets
from tools.freeze_static_lifetime_runtime import freeze


class StaticLifetimeTests(unittest.TestCase):
    def test_frozen012_binds_producer_modules_and_reuses_exact_observed011_recipe(self):
        path = REPO / "build/winehq-11.20/package-uwp-static-lifetime-01/cell012-receipt.json"
        receipt = json.loads(path.read_text())
        previous = json.loads(Path(receipt["predecessor_receipt"]).read_text())
        self.assertEqual(sha256(Path(receipt["predecessor_receipt"])), receipt["predecessor_receipt_sha256"])
        entry = json.loads(Path(receipt["registry"]).read_text())["engines"][0]
        checked_assets(entry)
        self.assertEqual(sha256(Path(receipt["registry"])), receipt["registry_sha256"])
        files = json.loads(Path(receipt["inventory"]).read_text())["files"]
        self.assertEqual(inventory(Path(receipt["install"])), files)
        self.assertEqual(len(files), 3915)
        old_files = json.loads(Path(previous["inventory"]).read_text())["files"]
        self.assertEqual({key for key in old_files.keys() | files.keys() if old_files.get(key) != files.get(key)},
                         set(receipt["changed_modules"]))
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(
                ["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)
        root = path.parent
        for relative, digest in receipt["generated_source_sha256"].items():
            self.assertEqual(sha256(root / "source" / relative), digest)
        for key in ("registry", "inventory", "staging_receipt", "build_receipt",
                    "helper", "native_fixture", "diagnostic_collector", "launcher_registration"):
            self.assertEqual(sha256(Path(receipt[key])), receipt[key + "_sha256"])
        for key in ("native_xaml_registration", "native_mapping", "factory_observation",
                    "factory_results", "verification", "graph", "framework_registration",
                    "protocol_table", "server_registration_table"):
            self.assertEqual(receipt[key], previous[key])
            self.assertEqual(sha256(Path(receipt[key])), previous[key + "_sha256"])
        self.assertEqual(receipt["native_mapping_count"], 558)
        self.assertEqual(receipt["native_xaml_input"], previous["native_xaml_input"])
        self.assertEqual(receipt["environment"]["WINEDLLOVERRIDES"], "mscoree=;mshtml=;windows.ui.xaml=n")
        for key in ("WINELOADER", "WINESERVER"):
            self.assertEqual(receipt["environment"][key], entry["environment"][key])
        self.assertEqual(receipt["environment"], {
            key: value for key, value in receipt["server_start"]["environment"].items()
            if key != "CALIMOCHO_PACKAGE_REGISTRATION"})
        for key in ("activation_argv", "framework_registration_argv", "launcher_registration_argv",
                    "native_xaml_registration_argv", "native_fixture_argv"):
            self.assertEqual(receipt[key][:3], ["/usr/bin/arch", "-x86_64", entry["wine"]])
        self.assertEqual(receipt["activation_argv"][3], receipt["helper"])
        self.assertEqual(receipt["target_observer"]["argv"][:3], receipt["activation_argv"][:3])
        self.assertEqual(receipt["collector_limit_seconds"], 180)
        self.assertFalse(receipt["runtime_executed"])
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            freeze(root, receipt["producer_commit"])
        self.assertEqual(path.read_bytes(), before)

    def test_new_source_build_has_real_map_and_correct_private_abi_slots(self):
        root = REPO / "build/winehq-11.20/package-uwp-static-lifetime-01"
        stage = json.loads((root / "staging-receipt.json").read_text())
        build = json.loads((root / "build-receipt.json").read_text())
        self.assertEqual(inventory(root / "install"), stage["files"])
        for step in build["steps"]:
            self.assertEqual(step["exit_code"], 0)
            self.assertFalse(step["timed_out"])
        for relative, digest in build["source_inputs"].items():
            self.assertEqual(sha256(REPO / relative), digest)
        for key in ("helper", "probe"):
            self.assertEqual(sha256(Path(stage[key])), stage[key + "_sha256"])
        source = (root / "source/dlls/twinapi.appcore/core_application.c").read_text()
        self.assertIn("RoActivateInstance(name, &instance)", source)
        self.assertIn("IMap_HSTRING_IInspectable_Insert(lifetime_map, key, value, replaced)", source)
        self.assertIn("IMap_HSTRING_IInspectable_Clear(lifetime_map)", source)
        self.assertIn("InitOnceExecuteOnce", source)
        self.assertIn("StaticLifetime.Reserved result=80004001", source)
        idl = (root / "source/dlls/twinapi.appcore/package_activation.idl").read_text()
        self.assertLess(idl.index("HRESULT Reserved()"), idl.index("HRESULT GetCollection("))
        self.assertIn("17b0e613-942a-422d-904c-f90dc71a7dae", idl)

    def test_sealed011_source_is_still_its_original_producer(self):
        frozen = json.loads((REPO / "build/winehq-11.20/package-uwp-01/cell009-receipt.json").read_text())
        for relative in ("patches/wine/files/core_application_activated.c",
                         "patches/wine/files/package_activation.idl"):
            blob = subprocess.check_output(
                ["git", "show", frozen["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), frozen["source_inputs"][relative])
