import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.freeze_launcher_runtime import checked_assets
from tools.probe_wine_source import sha256
from tools.qualify_coremessaging_imports import PE, qualify


class CoreMessagingReceiptTests(unittest.TestCase):
    def test_frozen025_source_native_input_imports_assets_and_distinct_hold(self):
        path = REPO / "build/winehq-11.20/package-uwp-coremessaging-01/cell025-receipt.json"
        self.assertEqual(sha256(path), "71a7fe33b08a27dea78a58e59972b26a0882b0b3bf588a7296fbb0a2f7fc70e8")
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt["producer_commit"], "f6a6117ff1de11acc865c324bc56511d6c45b7c6")
        self.assertFalse(receipt["runtime_executed"])
        self.assertIn("distinct explicit cell025 user resume", receipt["runtime_execution_hold"])
        self.assertEqual(receipt["preconditions"][0], receipt["runtime_execution_hold"])
        self.assertEqual(receipt["predecessor_receipt_sha256"],
                         "ba82f32c76a161273ad171065fd1de0eeaa8ce26ed76fe26b0652c5148ec952f")
        previous = json.loads(Path(receipt["predecessor_receipt"]).read_text())
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest, relative)
        for field in ("registry", "inventory", "build_receipt", "staging_receipt", "helper",
                      "native_fixture", "diagnostic_collector", "launcher_registration",
                      "aedebug_registration", "state_observer_build", "predecessor_receipt"):
            self.assertEqual(sha256(Path(receipt[field])), receipt[field + "_sha256"], field)
        actual = inventory(Path(receipt["install"]))
        self.assertEqual(len(actual), 3915)
        self.assertEqual(actual, json.loads(Path(receipt["inventory"]).read_text())["files"])
        self.assertEqual(len(receipt["changed_modules"]), 10)
        self.assertIn("lib/wine/x86_64-windows/ucrtbase.dll", receipt["changed_modules"])
        entry = json.loads(Path(receipt["registry"]).read_text())["engines"][0]
        checked_assets(entry)
        self.assertTrue(entry["name"].endswith("-native-coremessaging"))
        self.assertTrue(receipt["prefix"].endswith("-025/prefix"))
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        overrides = previous["environment"]["WINEDLLOVERRIDES"] + ";coremessaging=n"
        for environment in (receipt["environment"], receipt["server_start"]["environment"],
                            entry["environment"]):
            self.assertEqual(environment["WINEDLLOVERRIDES"], overrides)
        native = receipt["native_coremessaging"]
        self.assertEqual(sha256(Path(native["path"])), native["sha256"])
        self.assertEqual(Path(native["path"]).stat().st_size, native["size"])
        self.assertEqual(native["override"], "coremessaging=n")
        self.assertEqual(native["destination"], receipt["prefix"] + "/drive_c/windows/system32/CoreMessaging.dll")
        self.assertFalse(Path(native["path"]).is_relative_to(REPO))
        for relative, item in actual.items():
            if "sha256" in item:
                self.assertNotEqual(item["sha256"], native["sha256"], relative)
        installed = Path(receipt["install"]) / "lib/wine/x86_64-windows"
        self.assertEqual(sha256(installed / "coremessaging.dll"),
                         sha256(Path(previous["install"]) / "lib/wine/x86_64-windows/coremessaging.dll"))
        self.assertEqual(PE(installed / "ucrtbase.dll").exports()["__C_specific_handler_noexcept"],
                         "ntdll.__C_specific_handler")
        exports = PE(installed / "ntdll.dll").exports()
        for name in ("NtCreateWaitCompletionPacket", "NtAssociateWaitCompletionPacket",
                     "NtCancelWaitCompletionPacket", "RtlGetAppContainerNamedObjectPath",
                     "RtlGetThreadWorkOnBehalfTicket", "RtlSetThreadWorkOnBehalfTicket",
                     "NtAlpcConnectPortEx", "NtAlpcQueryInformation"):
            self.assertIn(name, exports)
        self.assertEqual(qualify(native["path"], receipt["install"], path.parent / "source"),
                         receipt["native_coremessaging_import_qualification"])
        build = json.loads(Path(receipt["build_receipt"]).read_text())
        for group in ("call_diagnostics", "activation_wait_diagnostics", "handle_provenance",
                      "exception_diagnostics", "failfast_diagnostics", "status_diagnostics",
                      "claims_packaged_thread", "onecore_transform", "coremessaging_prerequisites"):
            for relative, digest in build[group]["files"].items():
                self.assertEqual(sha256(path.parent / "source" / relative), digest, relative)
        for step in build["steps"]:
            self.assertEqual(step["exit_code"], 0)
            self.assertFalse(step["timed_out"])
        for relative in ("dlls/apisetschema/apisetschema.spec", "dlls/ntdll/loader.c",
                         "include/wine/whiny_context.h", "dlls/ntdll/package_claims_context.c",
                         "dlls/ntdll/package_claims_generated.h"):
            self.assertEqual(sha256(path.parent / "source" / relative),
                             sha256(Path(receipt["predecessor_receipt"]).parent / "source" / relative))
        self.assertEqual(sum(map(len, receipt["call_diagnostics"]["interfaces"].values())), 133)
        self.assertEqual(receipt["collector_limit_seconds"], 180)
