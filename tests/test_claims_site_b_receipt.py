import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.freeze_launcher_runtime import checked_assets
from tools.probe_wine_source import sha256


class ClaimsSiteBReceiptTests(unittest.TestCase):
    def test_frozen021_binds_unchanged_generated_source_and_preserves020_diagnostics(self):
        path = REPO / "build/winehq-11.20/package-uwp-claims-site-b-01/cell021-receipt.json"
        self.assertEqual(sha256(path), "633a1ed482e280bf73ed59781e2cfa0a1a340d37a9ea6c981e5bf50828e6164f")
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt["producer_commit"], "cef3f7340131e041b7b8822b66eace51e7d0c012")
        self.assertFalse(receipt["runtime_executed"])
        self.assertEqual(receipt["predecessor_receipt_sha256"],
                         "014ba68ad3c03834a0dbda2cd0c904bf276a7a6f8ef168a4d274458c726213ee")
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
        self.assertTrue(entry["name"].endswith("-claims-site-b"))
        for argv in (receipt["activation_argv"], receipt["state_observer"]["argv"],
                     receipt["target_observer"]["argv"], receipt["aedebug_registration_argv"]):
            self.assertEqual(argv[:3], ["/usr/bin/arch", "-x86_64", entry["wine"]])
        self.assertTrue(receipt["prefix"].endswith("-021/prefix"))
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        build = json.loads(Path(receipt["build_receipt"]).read_text())
        for group in ("call_diagnostics", "activation_wait_diagnostics", "handle_provenance",
                      "exception_diagnostics", "failfast_diagnostics", "status_diagnostics", "claims_site_b"):
            for relative, digest in build[group]["files"].items():
                self.assertEqual(sha256(path.parent / "source" / relative), digest)
        for step in build["steps"]:
            self.assertEqual(step["exit_code"], 0)
            self.assertFalse(step["timed_out"])
        claims = receipt["claims_site_b"]
        expected = "2924dd6c183b944d3a177fd2f2bf96571dde92b175b123eee64a938faf4b14d6"
        self.assertEqual(claims["artifact_sha256"], expected)
        self.assertEqual(claims["files"]["dlls/ntdll/package_claims_generated.h"], expected)
        self.assertEqual(claims["files"]["dlls/ntdll/package_claims_generated.c"], expected)
        previous = Path(receipt["predecessor_receipt"]).parent
        for relative in ("dlls/ntdll/package_claims_context.c", "include/wine/whiny_context.h",
                         "dlls/ntdll/Makefile.in"):
            self.assertEqual(sha256(previous / "source" / relative), claims["files"][relative])
        self.assertEqual(sha256(previous / "source/dlls/ntdll/package_claims_generated.h"),
                         "2194a9ac3f418b9af78fcfefae307faaf1260fa6b6932a85df0b8bfbffc8bb72")
        stage = json.loads(Path(receipt["staging_receipt"]).read_text())
        self.assertIn("-DCALIMOCHO_STATUS_DIAGNOSTICS", stage["helper_command"])
        self.assertEqual(sum(map(len, receipt["call_diagnostics"]["interfaces"].values())), 133)
        self.assertEqual(receipt["collector_limit_seconds"], 180)
