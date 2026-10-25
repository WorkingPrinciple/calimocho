import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import test_exception_diagnostics
from tools.build_uwp_overlay import REPO
from tools.port_alpc_telemetry import PATHS, port

BASE = REPO / "build/winehq-11.20/package-cell036-01/source"
INPUTS = ("dlls/ntdll/unix/alpc.c", "dlls/kernelbase/debug.c", "server/alpc.c",
          "server/server_wait_completion_packet.c")


class AlpcTelemetryCollectorTests(unittest.TestCase):
    emit = test_exception_diagnostics.ExceptionDiagnosticsTests.emit
    trace = test_exception_diagnostics.ExceptionDiagnosticsTests.trace

    def test_alpc_returns_keep_fixed_classes_only(self):
        trace = self.trace()
        self.emit(trace, "pkgstatus", "diagnostic_alpc_return",
                  "alpc-return export=NtAlpcConnectPortEx result=00000000 target=registrar")
        self.emit(trace, "pkgstatus", "diagnostic_alpc_return",
                  "alpc-return export=NtAlpcSendWaitReceivePort result=00000102 target=none")
        self.emit(trace, "pkgstatus", "diagnostic_alpc_return",
                  "alpc-return export=NtAlpcConnectPortEx result=c0000034 target=\\SECRET")
        self.emit(trace, "pkgstatus", "diagnostic_alpc_return", "alpc-return limited=1")
        result = trace.verdict()["call_diagnostics"]
        self.assertEqual([(row["export"], row["result"], row["target"]) for row in result["alpc_returns"]],
                         [("NtAlpcConnectPortEx", "0x00000000", "registrar"),
                          ("NtAlpcSendWaitReceivePort", "0x00000102", "none")])
        self.assertTrue(result["alpc_return_source_limited"])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_failfast_record_is_a_distinct_stage_with_parameters(self):
        trace = self.trace()
        self.emit(trace, "pkgexception", "diagnostic_failfast",
                  "exception stage=failfast id=65 code=e0464645 flags=00000001 count=2 "
                  "module=CoreMessaging.dll offset=3f3c0 hresult=unknown failfast_flags=00000000")
        self.emit(trace, "pkgexception", "diagnostic_failfast", "parameter id=65 slot=0 kind=scalar value=c0000034")
        self.emit(trace, "pkgexception", "diagnostic_failfast",
                  "parameter id=65 slot=1 kind=address module=CoreMessaging.dll offset=91a20")
        # A failfast line without its flags, or a filter line with them, is rejected.
        self.emit(trace, "pkgexception", "diagnostic_failfast",
                  "exception stage=failfast id=66 code=e0464645 flags=00000001 count=0 "
                  "module=unknown-redacted offset=0 hresult=unknown")
        self.emit(trace, "pkgexception", "diagnostic_exception",
                  "exception stage=unhandled-filter id=1 code=e0464645 flags=00000001 count=0 "
                  "module=unknown-redacted offset=0 hresult=unknown failfast_flags=00000000")
        rows = trace.verdict()["call_diagnostics"]["unhandled_filter_exceptions"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["stage"], "raise-failfast-entry")
        self.assertEqual((rows[0]["code"], rows[0]["module"], rows[0]["offset"], rows[0]["failfast_flags"]),
                         ("0xe0464645", "CoreMessaging.dll", "3f3c0", "0x00000000"))
        self.assertEqual(rows[0]["parameters"],
                         [{"slot": 0, "kind": "scalar", "value": "0xc0000034"},
                          {"slot": 1, "kind": "address", "module": "CoreMessaging.dll", "offset": "91a20"}])


@unittest.skipUnless(BASE.exists(), "requires the cell036 owned source")
class AlpcTelemetryPortTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=REPO / "build")
        self.source = Path(self.directory.name) / "source"
        for relative in INPUTS:
            (self.source / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(BASE / relative, self.source / relative)

    def tearDown(self):
        self.directory.cleanup()

    def test_port_wraps_every_alpc_seam_once_and_refuses_reapply(self):
        receipt = port(self.source)
        self.assertEqual(sorted(receipt["files"]), sorted(PATHS))
        self.assertIn("NtAlpcConnectPortEx", receipt["unix_exports"])
        self.assertIn("NtAlpcSendWaitReceivePort", receipt["unix_exports"])
        unix = (self.source / "dlls/ntdll/unix/alpc.c").read_text()
        for export in receipt["unix_exports"]:
            self.assertEqual(unix.count("NTSTATUS WINAPI %s(" % export), 1)
            self.assertEqual(unix.count("static NTSTATUS alpc_impl_%s(" % export), 1)
            self.assertIn('diagnostic_alpc_return( "%s", status,' % export, unix)
        self.assertIn('"\\\\BaseNamedObjects\\\\CoreMessagingRegistrar", 1', unix)
        self.assertNotIn("debugstr_us( name ), status", unix)
        debug = (self.source / "dlls/kernelbase/debug.c").read_text()
        hook = debug.index("diagnostic_failfast( record, flags, __builtin_return_address(0) );")
        self.assertLess(hook, debug.index("TerminateProcess", hook))
        server = (self.source / "server/alpc.c").read_text()
        for handler in ("alpc_connect_port", "alpc_connect_result", "alpc_accept_connect_port",
                        "alpc_receive_message"):
            self.assertEqual(server.count("DECL_HANDLER(%s)" % handler), 1)
            self.assertIn("alpc_impl_%s( req, reply );" % handler, server)
        self.assertIn("wineserver: alpc queue kind=", server)
        packets = (self.source / "server/server_wait_completion_packet.c").read_text()
        self.assertEqual(packets.count("DECL_HANDLER(associate_wait_completion_packet)"), 1)
        self.assertIn('kind = "alpc-port"', packets)
        with self.assertRaisesRegex(ValueError, "already applied"):
            port(self.source)


if __name__ == "__main__":
    unittest.main()
