import json
import hashlib
from pathlib import Path
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.diagnose_package_activation import ActivationTrace
from tools.freeze_launcher_runtime import checked_assets
from tools.probe_wine_source import sha256


ROOT = REPO / "build/winehq-11.20/package-uwp-exception-01"


class ExceptionDiagnosticsTests(unittest.TestCase):
    def test_frozen017_sources_registry_all_assets_and_original_recipe(self):
        path = ROOT / "cell017-receipt.json"
        receipt = json.loads(path.read_text())
        self.assertEqual(sha256(path), "0a757c6da94c8f6b3b5cabaa3130597c878082a6e9ab861b78b08646efa94389")
        self.assertFalse(receipt["runtime_executed"])
        self.assertEqual(receipt["producer_commit"], "bbb8dddf85b21a07ee5c8d2a9adac3571e57cada")
        self.assertEqual(receipt["predecessor_receipt_sha256"], "b55779b754cacf0b091dac907c381a9dcf3133acdbe8169b8f18a226705d38d5")
        for key in ("registry", "inventory", "build_receipt", "staging_receipt", "diagnostic_collector",
                    "helper", "native_fixture", "launcher_registration", "state_observer_build",
                    "predecessor_receipt", "aedebug_registration"):
            self.assertEqual(sha256(Path(receipt[key])), receipt[key + "_sha256"])
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)
        files = json.loads(Path(receipt["inventory"]).read_text())["files"]
        self.assertEqual(len(files), 3915)
        self.assertEqual(inventory(Path(receipt["install"])), files)
        checked_assets(json.loads(Path(receipt["registry"]).read_text())["engines"][0])
        previous = json.loads(Path(receipt["predecessor_receipt"]).read_text())
        for key in ("native_xaml_input", "native_xaml_registration", "native_mapping", "native_mapping_count",
                    "factory_observation", "protocol_table", "server_registration_table", "verification", "graph"):
            self.assertEqual(receipt[key], previous[key])
        registration = Path(receipt["aedebug_registration"]).read_text(encoding="utf-16")
        self.assertIn('"Auto"="0"', registration)
        self.assertNotIn('"Debugger"', registration)
        self.assertEqual(receipt["aedebug_registration_argv"][:3], receipt["activation_argv"][:3])
        self.assertEqual(receipt["collector_limit_seconds"], 180)
        self.assertEqual(receipt["state_observer"]["offset_seconds"], [20, 60])
        self.assertTrue(receipt["prefix"].endswith("xbox-calimocho-packaged-20261025-017/prefix"))
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        self.assertEqual(sha256(Path(receipt["state_observer"]["path"])), receipt["state_observer"]["sha256"])

    def trace(self):
        trace = ActivationTrace()
        trace.stdout("calimocho-activation child_pid 240")
        trace.stderr('00f0:00f4:trace:pkglaunch:activate_route route scheme=L"msxboxl" '
                     'app=L"Microsoft.Xbox.AppL" pid=256 result=00000000 missing=none')
        self.emit(trace, "pkgiface", "diagnostic_interface",
                  "interface object=CoreApplication method=Run phase=enter iid=none kind=HRESULT result=00000000")
        return trace

    def emit(self, trace, channel, function, message, pid=256):
        trace.stderr(f"{pid:04x}:0104:trace:{channel}:{function} {message}")

    def exception(self, trace, pid=256):
        self.emit(trace, "pkgexception", "diagnostic_exception",
                  "exception stage=unhandled-filter id=1 code=e06d7363 flags=00000001 count=4 "
                  "module=vcruntime140.dll offset=123 hresult=unknown", pid)

    def test_actual_exception_retains_last50_relay_and_safe_parameters(self):
        trace = self.trace()
        for i in range(60):
            self.emit(trace, "pkgrelay", "diagnostic_relay",
                      f"relay module=combase export=RoGetActivationFactory caller=Windows.UI.Xaml.dll offset={i:x}")
        self.emit(trace, "pkgro", "RoOriginateError",
                  "origin operation=RoOriginateError hresult=80004002")
        self.exception(trace)
        self.emit(trace, "pkgcore", "application_run", "exception-policy no-gpfault-dialog=1")
        self.emit(trace, "pkgexception", "diagnostic_exception",
                  "parameter id=1 slot=0 kind=cpp-magic value=19930520")
        self.emit(trace, "pkgexception", "diagnostic_exception",
                  "parameter id=1 slot=1 kind=address module=unknown-redacted offset=0")
        self.exception(trace, pid=512)
        rows = trace.verdict()["call_diagnostics"]["unhandled_filter_exceptions"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["code"], "0xe06d7363")
        self.assertIsNone(row["hresult"])
        self.assertEqual(len(row["relay_tail"]), 50)
        self.assertEqual(row["relay_tail"][0]["caller_offset"], "a")
        self.assertEqual(row["origin_candidates"][0]["hresult"], "0x80004002")
        self.assertEqual(len(row["parameters"]), 2)
        self.assertEqual(row["parameters"][1]["module"], "unknown-redacted")
        self.assertNotIn("termination", row)
        self.assertEqual(trace.verdict()["call_diagnostics"]["no_gpfault_dialog_policy_observed"], [256])

    def test_privacy_and_source_limit_are_explicit(self):
        trace = self.trace()
        self.exception(trace)
        self.emit(trace, "pkgexception", "diagnostic_exception",
                  "parameter id=1 slot=1 kind=address module=/Users/SECRET offset=123")
        self.emit(trace, "pkgexception", "diagnostic_exception",
                  "parameter id=1 slot=1 kind=raw value=SECRET")
        self.emit(trace, "pkgexception", "diagnostic_exception", "exception limited=1")
        result = trace.verdict()["call_diagnostics"]
        self.assertTrue(result["exception_source_limited"])
        self.assertEqual(result["unhandled_filter_exceptions"][0]["parameters"], [])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_real_filter_original_results_no_guessed_cpp_layout(self):
        build = json.loads((ROOT / "build-receipt.json").read_text())
        self.assertFalse(build["runtime_executed"])
        for relative, digest in build["exception_diagnostics"]["files"].items():
            self.assertEqual(sha256(ROOT / "source" / relative), digest)
        exception = (ROOT / "source/dlls/ntdll/exception.c").read_text()
        self.assertIn("diagnostic_exception(eptr->ExceptionRecord);", exception)
        self.assertIn("return unhandled_exception_filter( eptr );", exception)
        core = (ROOT / "source/dlls/twinapi.appcore/core_application.c").read_text()
        self.assertIn("SetErrorMode(GetErrorMode() | SEM_NOGPFAULTERRORBOX)", core)
        self.assertIn("SetErrorMode(diagnostic_error_mode);", core)
        header = (ROOT / "source/dlls/ntdll/package_exception_diagnostics.h").read_text()
        self.assertIn("hresult=unknown", header)
        self.assertNotIn("debugstr_", header)
        self.assertNotIn("ExceptionInformation[1])", header)


if __name__ == "__main__":
    unittest.main()
