import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.freeze_launcher_runtime import checked_assets
from tools.probe_wine_source import sha256


class FailfastReceiptTests(unittest.TestCase):
    def test_frozen019_is_bound_to_original_failure_behavior_and_sealed018(self):
        path = REPO / "build/winehq-11.20/package-uwp-failfast-01/cell019-receipt.json"
        self.assertEqual(sha256(path), "245aa4ca6780a68ee8473404ba9b4055524046edf6f5adce1fa42ebfe9474233")
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt["producer_commit"], "c59d6ceb5e52c9db51527f6a40cdf7fda3123c0c")
        self.assertEqual(receipt["predecessor_receipt_sha256"],
                         "e75c54e81fec44d3bcb6984bd648b396b4d27f4dcfa7437e07e44ec62c1f4b45")
        self.assertFalse(receipt["runtime_executed"])
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)
        for field in ("registry", "inventory", "build_receipt", "staging_receipt", "helper",
                      "native_fixture", "diagnostic_collector", "launcher_registration",
                      "aedebug_registration", "state_observer_build", "predecessor_receipt"):
            self.assertEqual(sha256(Path(receipt[field])), receipt[field + "_sha256"], field)
        actual = inventory(Path(receipt["install"]))
        self.assertEqual(len(actual), 3915)
        self.assertEqual(actual, json.loads(Path(receipt["inventory"]).read_text())["files"])
        entry = json.loads(Path(receipt["registry"]).read_text())["engines"][0]
        checked_assets(entry)
        for argv in (receipt["activation_argv"], receipt["state_observer"]["argv"],
                     receipt["target_observer"]["argv"], receipt["aedebug_registration_argv"]):
            self.assertEqual(argv[:3], ["/usr/bin/arch", "-x86_64", entry["wine"]])
        self.assertTrue(receipt["prefix"].endswith("-019/prefix"))
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        build = json.loads(Path(receipt["build_receipt"]).read_text())
        self.assertEqual(receipt["failfast_diagnostics"], build["failfast_diagnostics"])
        for group in ("call_diagnostics", "activation_wait_diagnostics", "handle_provenance",
                      "exception_diagnostics", "failfast_diagnostics"):
            for relative, digest in build[group]["files"].items():
                self.assertEqual(sha256(path.parent / "source" / relative), digest)
        self.assertEqual(sum(map(len, receipt["call_diagnostics"]["interfaces"].values())), 133)
        self.assertEqual(receipt["collector_limit_seconds"], 180)
