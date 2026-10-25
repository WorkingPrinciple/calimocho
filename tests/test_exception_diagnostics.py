import json
import unittest

from tools.build_uwp_overlay import REPO
from tools.diagnose_package_activation import ActivationTrace
from tools.probe_wine_source import sha256


ROOT = REPO / "build/winehq-11.20/package-uwp-exception-01"


class ExceptionDiagnosticsTests(unittest.TestCase):
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
