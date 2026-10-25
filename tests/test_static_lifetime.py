import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.probe_wine_source import sha256


class StaticLifetimeTests(unittest.TestCase):
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
