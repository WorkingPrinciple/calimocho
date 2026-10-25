import json
import subprocess
import unittest

from tests import test_exception_diagnostics
from tools.build_uwp_overlay import REPO
from tools.port_call_diagnostics import slots
from tools.probe_wine_source import sha256


class StatusDiagnosticsTests(unittest.TestCase):
    emit = test_exception_diagnostics.ExceptionDiagnosticsTests.emit
    trace = test_exception_diagnostics.ExceptionDiagnosticsTests.trace

    def test_fixme_keeps_function_only_in_actual_run_scope(self):
        trace = self.trace()
        trace.stderr("0100:0104:fixme:thread:NtQueryInformationThread SECRET /Users/private 0x12345678")
        trace.stderr("0200:0104:fixme:thread:Other SECRET")
        self.emit(trace, "pkgiface", "diagnostic_interface",
                  "interface object=CoreApplication method=Run phase=exit iid=none kind=HRESULT result=00000000")
        trace.stderr("0100:0104:fixme:thread:AfterRun SECRET")
        result = trace.verdict()["call_diagnostics"]
        self.assertEqual(len(result["run_fixme_fingerprints"]), 1)
        self.assertEqual(result["run_fixme_fingerprints"][0]["function"], "NtQueryInformationThread")
        self.assertEqual(result["run_fixme_fingerprints"][0]["arguments"], "redacted")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_scalar_relay_status_and_owned_hresult_are_not_conflated(self):
        trace = self.trace()
        for status in ("c0000002", "d0000002"):
            self.emit(trace, "pkgstatus", "diagnostic_status_return",
                      f"status-return module=ntdll export=RtlExample result={status} caller=Windows.UI.Xaml.dll offset=123")
        self.emit(trace, "pkgiface", "diagnostic_interface",
                  "interface object=CoreApplicationView method=get_CoreWindow phase=exit iid=none kind=HRESULT result=d0000002")
        self.emit(trace, "pkgstatus", "diagnostic_status_return",
                  "status-return module=ntdll export=RtlExample result=c0000002 caller=/Users/SECRET offset=123")
        self.emit(trace, "pkgstatus", "diagnostic_status_return",
                  "status-return module=ntdll export=RtlExample result=c0000002 caller=Unknown offset=7fff12345678")
        result = trace.verdict()["call_diagnostics"]
        self.assertEqual(len(result["not_implemented_returns"]), 3)
        self.assertEqual(result["not_implemented_returns"][0]["source"], "actual-relay-return")
        self.assertEqual(result["not_implemented_returns"][2]["source"], "owned-COM-HRESULT")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_limits_are_explicit(self):
        trace = self.trace()
        for _ in range(140):
            trace.stderr("0100:0104:fixme:thread:Example PRIVATE")
            self.emit(trace, "pkgstatus", "diagnostic_status_return",
                      "status-return module=ntdll export=RtlExample result=c0000002 caller=unknown-redacted offset=0")
        self.emit(trace, "pkgstatus", "diagnostic_status_return", "status-return limited=1")
        result = trace.verdict()["call_diagnostics"]
        self.assertEqual(len(result["run_fixme_fingerprints"]), 128)
        self.assertEqual(result["run_fixme_fingerprints_not_retained"], 12)
        self.assertEqual(result["status_return_tail_overwritten"], 12)
        self.assertTrue(result["status_return_source_limited"])

    def test_frozen019_export_passes_original_ecx_to_status_helper(self):
        dll = REPO / "build/winehq-11.20/package-uwp-failfast-01/install/lib/wine/x86_64-windows/combase.dll"
        disassembly = subprocess.check_output([
            "x86_64-w64-mingw32-objdump", "-d", "-Mintel",
            "--disassemble=RoFailFastWithErrorContextInternal2", str(dll)], text=True)
        copy = disassembly.index("mov    r8d,ecx")
        change = disassembly.index("lea    rcx", copy)
        call = disassembly.index("<diagnostic_error_context>", change)
        self.assertLess(copy, change)
        self.assertLess(change, call)
        self.assertEqual(0xc0000002 | 0x10000000, 0xd0000002)

    def test_compiled020_preserves_view_abi_and_filters_real_returns(self):
        root = REPO / "build/winehq-11.20/package-uwp-status-01"
        build = json.loads((root / "build-receipt.json").read_text())
        self.assertFalse(build["runtime_executed"])
        for relative, digest in build["status_diagnostics"]["files"].items():
            self.assertEqual(sha256(root / "source" / relative), digest)
        relay = (root / "source/dlls/ntdll/relay.c").read_text().split("#elif defined(__x86_64__)", 1)[1]
        body = relay.split("void WINAPI relay_trace_exit(", 1)[1].split("\n}", 1)[0]
        self.assertIn("diagnostic_status_return(descr->private, LOWORD(idx), (void *)retaddr, (UINT)retval)", body)
        self.assertNotIn("TRACE(", body)
        header = (root / "source/dlls/ntdll/package_status_diagnostics.h").read_text()
        self.assertIn("result != 0xc0000002 && result != 0xd0000002", header)
        self.assertIn("sequence > 128", header)
        self.assertNotIn("debugstr_", header)
        methods = [method for _, method, _ in slots(
            root / "build/include/windows.applicationmodel.core.h", "ICoreApplicationView")]
        self.assertEqual(len(methods), 11)
        self.assertEqual(methods[6:], ["get_CoreWindow", "add_Activated", "remove_Activated", "get_IsMain", "get_IsHosted"])
        self.assertEqual(build["call_diagnostics"]["interfaces"]["CoreApplicationView"], methods)
        stage = json.loads((root / "staging-receipt.json").read_text())
        self.assertIn("-DCALIMOCHO_STATUS_DIAGNOSTICS", stage["helper_command"])
        helper = (REPO / "tests/package_activation_probe.c").read_text()
        self.assertIn("XboxPcApp.exe:fixme+all", helper)
