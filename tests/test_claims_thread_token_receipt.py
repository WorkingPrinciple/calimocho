import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.freeze_launcher_runtime import checked_assets
from tools.probe_wine_source import sha256


class ClaimsThreadTokenReceiptTests(unittest.TestCase):
    def test_frozen022_binds_r8_context_diagnostics_and_sealed021(self):
        path = REPO / "build/winehq-11.20/package-uwp-claims-thread-token-01/cell022-receipt.json"
        self.assertEqual(sha256(path), "f02c2ccbb85538da61c56c14fb6370b7e1882bb36cdc9267663120af7faf5b7a")
        receipt = json.loads(path.read_text())
        self.assertTrue(receipt["producer_commit"].startswith("9a1076a"))
        self.assertFalse(receipt["runtime_executed"])
        self.assertNotIn("claims_site_b", receipt)
        self.assertEqual(receipt["predecessor_receipt_sha256"],
                         "633a1ed482e280bf73ed59781e2cfa0a1a340d37a9ea6c981e5bf50828e6164f")
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
        self.assertTrue(entry["name"].endswith("-claims-thread-token"))
        for argv in (receipt["activation_argv"], receipt["state_observer"]["argv"],
                     receipt["target_observer"]["argv"], receipt["aedebug_registration_argv"]):
            self.assertEqual(argv[:3], ["/usr/bin/arch", "-x86_64", entry["wine"]])
        self.assertTrue(receipt["prefix"].endswith("-022/prefix"))
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        build = json.loads(Path(receipt["build_receipt"]).read_text())
        for group in ("call_diagnostics", "activation_wait_diagnostics", "handle_provenance",
                      "exception_diagnostics", "failfast_diagnostics", "status_diagnostics", "claims_thread_token"):
            for relative, digest in build[group]["files"].items():
                self.assertEqual(sha256(path.parent / "source" / relative), digest)
        for step in build["steps"]:
            self.assertEqual(step["exit_code"], 0)
            self.assertFalse(step["timed_out"])
        claims = receipt["claims_thread_token"]
        expected = "5acbb35eaa18c874272e91a1169b997373496aa6277f9ccbb7f3bcc3d840b9ed"
        self.assertEqual(claims["artifact_sha256"], expected)
        for suffix in ("h", "c"):
            self.assertEqual(claims["files"]["dlls/ntdll/package_claims_generated." + suffix], expected)
        previous = Path(receipt["predecessor_receipt"]).parent
        self.assertEqual(sha256(previous / "source/include/wine/whiny_context.h"),
                         claims["files"]["include/wine/whiny_context.h"])
        self.assertEqual(claims["files"]["dlls/ntdll/package_claims_context.c"],
                         sha256(REPO / "patches/wine/files/package_claims_context_diagnostics.c"))
        stage = json.loads(Path(receipt["staging_receipt"]).read_text())
        self.assertIn("-DCALIMOCHO_STATUS_DIAGNOSTICS", stage["helper_command"])
        self.assertIn("trace+pkgstatus", (REPO / "tests/package_activation_probe.c").read_text())
        self.assertEqual(sum(map(len, receipt["call_diagnostics"]["interfaces"].values())), 133)
        self.assertEqual(receipt["collector_limit_seconds"], 180)
