import json
import hashlib
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.diagnose_package_activation import ActivationTrace, state_rows
from tools.freeze_launcher_runtime import checked_assets
from tools.probe_wine_source import sha256


ROOT = REPO / "build/winehq-11.20/package-uwp-activation-waits-01"
IID = "{17b0e613-942a-422d-904c-f90dc71a7dae}"


class ActivationWaitTests(unittest.TestCase):
    def test_frozen015_exact_source_install_commands_and_sealed_predecessor(self):
        path = ROOT / "cell015-receipt.json"
        receipt = json.loads(path.read_text())
        self.assertEqual(sha256(path), "58eccd9ec5d9aba954eb80251efadb8d8117b2f49aba6088604e981b5b50a122")
        self.assertFalse(receipt["runtime_executed"])
        self.assertEqual(receipt["producer_commit"], "b86b934db32c583aeb69e1ae8cc7e1ff2f3b30bf")
        self.assertEqual(receipt["predecessor_receipt_sha256"], "30b6d6514d58ec6ee188768345673abea86d11d5a0254fce38db9f7484646b48")
        for key in ("registry", "inventory", "build_receipt", "staging_receipt", "diagnostic_collector",
                    "helper", "native_fixture", "launcher_registration", "state_observer_build", "predecessor_receipt"):
            self.assertEqual(sha256(Path(receipt[key])), receipt[key + "_sha256"])
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)
        entry = json.loads(Path(receipt["registry"]).read_text())["engines"][0]
        checked_assets(entry)
        files = json.loads(Path(receipt["inventory"]).read_text())["files"]
        self.assertEqual(len(files), 3915)
        self.assertEqual(inventory(Path(receipt["install"])), files)
        previous = json.loads(Path(receipt["predecessor_receipt"]).read_text())
        for key in ("native_xaml_input", "native_xaml_registration", "native_mapping", "native_mapping_count",
                    "factory_observation", "protocol_table", "server_registration_table", "verification", "graph"):
            self.assertEqual(receipt[key], previous[key])
        self.assertEqual(receipt["environment"]["WINEDLLOVERRIDES"], previous["environment"]["WINEDLLOVERRIDES"])
        self.assertTrue(receipt["prefix"].endswith("xbox-calimocho-packaged-20261025-015/prefix"))
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        self.assertEqual(receipt["collector_limit_seconds"], 180)
        observer = receipt["state_observer"]
        self.assertEqual(sha256(Path(observer["path"])), observer["sha256"])
        self.assertEqual(observer["argv"][:3], receipt["activation_argv"][:3])
        self.assertEqual(observer["argv"][3], observer["path"])
        self.assertEqual(observer["offset_seconds"], [20, 60])

    def trace(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 240")
        trace.stderr('00f0:00f4:trace:pkglaunch:activate_route route scheme=L"msxboxl" '
                     'app=L"Microsoft.Xbox.AppL" pid=256 result=00000000 missing=none')
        return trace

    def emit(self, trace, channel, function, message, pid=256):
        trace.stderr(f"{pid:04x}:0104:trace:{channel}:{function} {message}")

    def test_factory_entry_exit_class_iid_and_actual_provider_before_initialize(self):
        trace = self.trace()
        self.emit(trace, "pkgro", "diagnostic_ro",
                  f"activation operation=RoGetActivationFactory phase=enter class=Windows.ApplicationModel.Core.CoreApplication iid={IID} result=00000000 module=unknown-redacted")
        self.emit(trace, "pkgro", "diagnostic_ro",
                  f"activation operation=RoGetActivationFactory phase=exit class=Windows.ApplicationModel.Core.CoreApplication iid={IID} result=00000000 module=twinapi.appcore.dll")
        rows = trace.verdict()["call_diagnostics"]["activation_calls"]
        self.assertEqual(len(rows), 2)
        self.assertNotIn("hresult", rows[0])
        self.assertEqual(rows[1]["serving_module"], "twinapi.appcore.dll")
        self.assertEqual(rows[1]["iid"], IID)

    def test_actual_thread_create_and_return_slot_are_phase_and_pid_bound(self):
        trace = self.trace()
        row = "thread phase=exit result=00000000 query=00000000 tid=352 pid=256 start=combase.dll offset=123 syscall=ntdll.dll site=456"
        self.emit(trace, "pkgthread", "diagnostic_thread", row)
        self.emit(trace, "pkgrelay", "__wine_pkg_diagnostic_phase", "phase initialize=1 xaml=1")
        self.emit(trace, "pkgthread", "diagnostic_thread", row)
        self.emit(trace, "pkgthread", "diagnostic_thread",
                  "creator phase=exit query=00000000 module=kernelbase.dll offset=789 basis=user-stack-return-slot")
        self.emit(trace, "pkgthread", "diagnostic_thread", row, 512)
        rows = trace.verdict()["call_diagnostics"]["thread_creation"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["new_tid"], 352)
        self.assertEqual(rows[0]["start_module"], "combase.dll")
        self.assertEqual(rows[1]["basis"], "user-stack-return-slot-not-a-full-stack")

    def test_semaphore_and_thread_wait_details_never_invent_event_signaler(self):
        trace = self.trace()
        self.emit(trace, "pkgrelay", "__wine_pkg_diagnostic_phase", "phase initialize=1 xaml=1")
        self.emit(trace, "pkgwait", "NtWaitForMultipleObjects",
                  "wait method=NtWaitForMultipleObjects phase=enter id=7 count=2 alertable=0 infinite=1")
        self.emit(trace, "pkgwait", "diagnostic_wait",
                  "semaphore id=7 slot=0 query=00000000 count=0 maximum=1")
        self.emit(trace, "pkgwait", "diagnostic_wait",
                  "thread id=7 slot=1 query=00000000 pid=256 tid=352 exit=00000103 start-query=00000000 module=combase.dll offset=123")
        row = trace.verdict()["call_diagnostics"]["waits_without_retained_exit"][0]
        self.assertEqual(row["semaphores"][0]["count"], 0)
        self.assertEqual(row["threads"][0]["tid"], 352)
        self.assertEqual(row["threads"][0]["signal_condition"], "this-thread-terminates")
        self.assertTrue(row["expected_signaler"].startswith("unknown"))

    def test_snapshot_genuine_liveness_start_and_top_frame_shapes(self):
        result = state_rows(
            b"state tid=352 alive=1 wait=unknown\n"
            b"state tid=352 start module=combase.dll offset=123\n"
            b"state tid=352 frame=0 module=ntdll.dll offset=456\n")
        self.assertFalse(result["format_error"])
        self.assertEqual(len(result["rows"]), 3)

    def test_public_type_parser_rejects_private_paths_and_marks_unknown_registration_abi(self):
        trace = self.trace()
        self.emit(trace, "pkgro", "diagnostic_ro",
                  f"activation operation=RoGetActivationFactory phase=enter class=C:/SECRET iid={IID} result=00000000 module=unknown-redacted")
        self.emit(trace, "pkgro", "diagnostic_ro",
                  f"activation operation=RoGetActivationFactory phase=enter class=Windows.Core iid={IID} result=00000000 module=C:/SECRET")
        trace.stderr("0100:0104:err:module:stub unimplemented function combase.dll.RoGetActivatableClassRegistration")
        result = trace.verdict()["call_diagnostics"]
        self.assertEqual(result["activation_calls"], [])
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertEqual(result["registration_abi_unavailable"], [256])

    def test_seven_module_deployment_and_generated_source_binding(self):
        build = json.loads((ROOT / "build-receipt.json").read_text())
        stage = json.loads((ROOT / "staging-receipt.json").read_text())
        self.assertFalse(build["runtime_executed"])
        self.assertEqual(build["status"], "built-not-staged-not-executed")
        self.assertEqual(len(stage["changed_files"]), 7)
        self.assertIn("lib/wine/x86_64-windows/combase.dll", stage["changed_files"])
        self.assertIn("-DCALIMOCHO_ACTIVATION_WAIT_DIAGNOSTICS", stage["helper_command"])
        self.assertEqual(inventory(ROOT / "install"), stage["files"])
        for group in ("call_diagnostics", "activation_wait_diagnostics"):
            for relative, digest in build[group]["files"].items():
                self.assertEqual(sha256(ROOT / "source" / relative), digest)
        for relative, digest in build["built_files"].items():
            self.assertEqual(sha256(ROOT / relative), digest)
        ro = (ROOT / "source/dlls/combase/roapi.c").read_text()
        self.assertIn('*served = module;', ro)
        self.assertIn('diagnostic_ro("RoGetActivationFactory", "enter"', ro)
        self.assertIn('diagnostic_ro("RoGetActivationFactory", "exit"', ro)
        spec = (ROOT / "source/dlls/combase/combase.spec").read_text()
        self.assertIn("@ stub RoGetActivatableClassRegistration", spec)
