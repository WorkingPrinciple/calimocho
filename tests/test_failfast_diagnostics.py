import json
import unittest

from tests import test_exception_diagnostics
from tools.build_uwp_overlay import REPO
from tools.probe_wine_source import sha256


class FailfastDiagnosticsTests(unittest.TestCase):
    emit = test_exception_diagnostics.ExceptionDiagnosticsTests.emit
    trace = test_exception_diagnostics.ExceptionDiagnosticsTests.trace

    def begin(self, trace):
        self.emit(trace, "pkgrelay", "__wine_pkg_diagnostic_phase", "phase initialize=1 xaml=1")

    def context(self, trace, operation="RoFailFastWithErrorContextInternal2", kind="argument", pid=256,
                result="80004005", module="Windows.UI.Xaml.dll", offset="33f121"):
        self.emit(trace, "pkgro", "diagnostic_error_context",
                  f"error-context operation={operation} kind={kind} hresult={result} module={module} offset={offset}", pid)

    def test_first_actual_hresult_and_last30_owned_calls_bound_at_failfast(self):
        trace = self.trace()
        self.begin(trace)
        for index in range(40):
            self.emit(trace, "pkgrelay", "diagnostic_relay",
                      f"relay module=combase export=RoGetActivationFactory caller=Windows.UI.Xaml.dll offset={index:x}")
            self.emit(trace, "pkgiface", "diagnostic_interface",
                      "interface object=StaticLifetime method=AddCallback phase=exit iid=none kind=HRESULT result=00000000")
        self.context(trace)
        self.context(trace, pid=512)
        self.emit(trace, "pkgrelay", "diagnostic_relay",
                  "relay module=combase export=RoGetActivationFactory caller=Windows.UI.Xaml.dll offset=fff")
        rows = trace.verdict()["call_diagnostics"]["failfast_error_context"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["hresult"], "0x80004005")
        self.assertEqual(rows[0]["hresult_kind"], "argument")
        self.assertEqual(rows[0]["caller_offset"], "33f121")
        self.assertEqual(len(rows[0]["relay_tail"]), 30)
        self.assertEqual(rows[0]["relay_tail"][0]["caller_offset"], "a")
        self.assertEqual(len(rows[0]["interface_tail"]), 30)
        self.assertNotIn("termination", rows[0])

    def test_restricted_error_calls_are_scoped_and_never_decode_private_messages(self):
        trace = self.trace()
        self.context(trace)
        self.begin(trace)
        for operation in ("RoOriginateError", "RoOriginateErrorW", "RoOriginateLanguageException"):
            self.context(trace, operation=operation, result="80070057")
        for operation in ("GetRestrictedErrorInfo", "SetRestrictedErrorInfo"):
            self.context(trace, operation=operation, kind="return", result="80004001")
        self.context(trace, module="/Users/SECRET")
        self.context(trace, offset="7fff12345678")
        self.context(trace, operation="GetRestrictedErrorInfo", kind="argument")
        self.context(trace, operation="SECRET")
        self.emit(trace, "pkgiface", "diagnostic_interface",
                  "interface object=CoreApplication method=Run phase=exit iid=none kind=HRESULT result=00000000")
        self.context(trace)
        result = trace.verdict()["call_diagnostics"]
        self.assertEqual(len(result["restricted_error_context"]), 5)
        self.assertEqual(result["failfast_error_context"], [])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_caps_and_overwrites_are_explicit_and_preserve_first_failfast(self):
        trace = self.trace()
        self.begin(trace)
        for _ in range(520):
            self.context(trace, operation="RoOriginateError")
        for _ in range(34):
            self.context(trace)
        self.emit(trace, "pkgro", "diagnostic_error_context", "error-context limited=operations")
        result = trace.verdict()["call_diagnostics"]
        self.assertEqual(result["error_context_tail_overwritten"], 8)
        self.assertTrue(result["error_context_source_limited"])
        self.assertEqual(len(result["failfast_error_context"]), 32)

    def test_source_instruments_actual_export_without_changing_failure_behavior(self):
        root = REPO / "build/winehq-11.20/package-uwp-failfast-01"
        build = json.loads((root / "build-receipt.json").read_text())
        self.assertFalse(build["runtime_executed"])
        for relative, digest in build["failfast_diagnostics"]["files"].items():
            self.assertEqual(sha256(root / "source" / relative), digest)
        source = (root / "source/dlls/combase/roapi.c").read_text()
        failfast = source.split("void WINAPI RoFailFastWithErrorContextInternal2(", 1)[1].split("\n}", 1)[0]
        self.assertIn('"argument", error, __builtin_return_address(0)', failfast)
        self.assertIn("RaiseFailFastException(NULL, NULL, 0);", failfast)
        for operation in ("RoOriginateError", "RoOriginateErrorW", "RoOriginateLanguageException"):
            body = source.split("BOOL WINAPI " + operation + "(", 1)[1].split("\n}", 1)[0]
            self.assertIn('"argument", error, __builtin_return_address(0)', body)
            self.assertIn("return FALSE;", body)
            self.assertNotIn("debugstr_", body)
        for operation in ("GetRestrictedErrorInfo", "SetRestrictedErrorInfo"):
            body = source.split("HRESULT WINAPI " + operation + "(", 1)[1].split("\n}", 1)[0]
            self.assertIn('"return", E_NOTIMPL, __builtin_return_address(0)', body)
            self.assertIn("return E_NOTIMPL;", body)
            self.assertNotIn("*info =", body)
