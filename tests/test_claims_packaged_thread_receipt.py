import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.freeze_launcher_runtime import checked_assets
from tools.probe_wine_source import sha256


class ClaimsPackagedThreadReceiptTests(unittest.TestCase):
    def test_frozen023_complete_source_assets_telemetry_and_sealed022(self):
        path = REPO / "build/winehq-11.20/package-uwp-claims-packaged-thread-01/cell023-receipt.json"
        self.assertEqual(sha256(path), "e4899d28429cb7af93d3c311066bee13de2a13cd9e703698816347dc6837fa1f")
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt["producer_commit"], "8131ae7871edad75d1c52d6d599658c286b277f1")
        self.assertFalse(receipt["runtime_executed"])
        self.assertNotIn("claims_thread_token", receipt)
        self.assertEqual(receipt["predecessor_receipt_sha256"],
                         "f02c2ccbb85538da61c56c14fb6370b7e1882bb36cdc9267663120af7faf5b7a")
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
        self.assertEqual(len(receipt["changed_modules"]), 8)
        entry = json.loads(Path(receipt["registry"]).read_text())["engines"][0]
        checked_assets(entry)
        self.assertTrue(entry["name"].endswith("-claims-packaged-thread"))
        for argv in (receipt["activation_argv"], receipt["state_observer"]["argv"],
                     receipt["target_observer"]["argv"], receipt["aedebug_registration_argv"]):
            self.assertEqual(argv[:3], ["/usr/bin/arch", "-x86_64", entry["wine"]])
        self.assertTrue(receipt["prefix"].endswith("-023/prefix"))
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        build = json.loads(Path(receipt["build_receipt"]).read_text())
        for group in ("call_diagnostics", "activation_wait_diagnostics", "handle_provenance",
                      "exception_diagnostics", "failfast_diagnostics", "status_diagnostics", "claims_packaged_thread"):
            for relative, digest in build[group]["files"].items():
                self.assertEqual(sha256(path.parent / "source" / relative), digest)
        for step in build["steps"]:
            self.assertEqual(step["exit_code"], 0)
            self.assertFalse(step["timed_out"])
        claims = receipt["claims_packaged_thread"]
        expected = "9978669c98676693e3424653c214dae182d0a6c87f4b996c992632eb002d748a"
        self.assertEqual(claims["artifact_sha256"], expected)
        for suffix in ("h", "c"):
            self.assertEqual(claims["files"]["dlls/ntdll/package_claims_generated." + suffix], expected)
        previous = Path(receipt["predecessor_receipt"]).parent
        for relative in ("include/wine/whiny_context.h", "dlls/ntdll/package_claims_context.c",
                         "dlls/ntdll/Makefile.in"):
            self.assertEqual(sha256(previous / "source" / relative), claims["files"][relative])
        self.assertEqual(sha256(previous / "source/dlls/ntdll/package_claims_generated.h"),
                         "5acbb35eaa18c874272e91a1169b997373496aa6277f9ccbb7f3bcc3d840b9ed")
        stage = json.loads(Path(receipt["staging_receipt"]).read_text())
        self.assertIn("-DCALIMOCHO_STATUS_DIAGNOSTICS", stage["helper_command"])
        self.assertEqual(sum(map(len, receipt["call_diagnostics"]["interfaces"].values())), 133)
        self.assertEqual(receipt["collector_limit_seconds"], 180)
