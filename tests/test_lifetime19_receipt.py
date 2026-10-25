import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.freeze_launcher_runtime import checked_assets
from tools.probe_wine_source import sha256


class Lifetime19ReceiptTests(unittest.TestCase):
    def test_frozen018_sources_assets_commands_and_unchanged017(self):
        path = REPO / "build/winehq-11.20/package-uwp-lifetime19-01/cell018-receipt.json"
        self.assertEqual(sha256(path), "e75c54e81fec44d3bcb6984bd648b396b4d27f4dcfa7437e07e44ec62c1f4b45")
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt["producer_commit"], "d65bf3c17d547aeda6c3230bfec9a1abb3fad8f4")
        self.assertFalse(receipt["runtime_executed"])
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)
        for field in ("registry", "inventory", "build_receipt", "staging_receipt", "helper",
                      "native_fixture", "diagnostic_collector", "launcher_registration",
                      "aedebug_registration", "state_observer_build", "predecessor_receipt"):
            self.assertEqual(sha256(Path(receipt[field])), receipt[field + "_sha256"], field)
        self.assertEqual(receipt["predecessor_receipt_sha256"],
                         "0a757c6da94c8f6b3b5cabaa3130597c878082a6e9ab861b78b08646efa94389")
        actual = inventory(Path(receipt["install"]))
        self.assertEqual(actual, json.loads(Path(receipt["inventory"]).read_text())["files"])
        self.assertEqual(len(actual), 3915)
        entry = json.loads(Path(receipt["registry"]).read_text())["engines"][0]
        checked_assets(entry)
        for argv in (receipt["activation_argv"], receipt["state_observer"]["argv"],
                     receipt["target_observer"]["argv"], receipt["aedebug_registration_argv"]):
            self.assertEqual(argv[:3], ["/usr/bin/arch", "-x86_64", entry["wine"]])
        self.assertTrue(receipt["prefix"].endswith("-018/prefix"))
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        self.assertEqual(receipt["server_stop"], [entry["wineserver"], "-k"])
        self.assertEqual(receipt["server_wait"], [entry["wineserver"], "-w"])
        self.assertEqual(receipt["lifetime_abi"]["slots"], 19)
        self.assertEqual(receipt["lifetime_abi"]["unknown_slots"], [8, 9, 10, 13, 14, 15, 16, 17, 18])
        self.assertEqual(len(receipt["call_diagnostics"]["interfaces"]["StaticLifetime"]), 19)
        self.assertEqual(sum(map(len, receipt["call_diagnostics"]["interfaces"].values())), 133)
        self.assertEqual(receipt["exception_diagnostics"],
                         json.loads(Path(receipt["build_receipt"]).read_text())["exception_diagnostics"])
