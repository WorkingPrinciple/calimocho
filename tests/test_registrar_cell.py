import json
import tempfile
import unittest
from pathlib import Path

from tools.build_uwp_overlay import REPO
from tools.freeze_registrar_cell import (IMAGE_PATH, SERVICES_WINEDEBUG, add_registrar_handoff, registrar_sources,
                                         registrar_stack_build, registration_text)
from tools.freeze_static_lifetime_runtime import REGISTRAR_STACK


def multi_sz(text, name):
    line = next(item for item in text.splitlines() if item.startswith('"%s"=hex(7):' % name))
    data = bytes(int(value, 16) for value in line.split(":", 1)[1].split(","))
    return data.decode("utf-16-le").split("\0")


class RegistrarCellTest(unittest.TestCase):
    def test_registration_matches_scoped_registrar_contract(self):
        text = registration_text()
        # services_registrar_token.c admits only this exact ImagePath, account, SID type and share type.
        self.assertIn('"ImagePath"="%s"' % IMAGE_PATH.replace("\\", "\\\\"), text)
        self.assertIn('"ObjectName"="NT AUTHORITY\\\\LocalService"', text)
        self.assertIn('"ServiceSidType"=dword:00000003', text)
        self.assertIn('"Type"=dword:00000020', text)
        self.assertIn('"ServiceDll"="C:\\\\windows\\\\system32\\\\coremessaging.dll"', text)
        # The registrar requires a single-member group: exactly the name, one terminator and the list end.
        self.assertEqual(multi_sz(text, "LocalServiceNoNetwork"), ["CoreMessagingRegistrar", "", ""])
        self.assertEqual(multi_sz(text, "DependOnService"), ["RpcSs", "", ""])

    def test_sources_are_tracked_files(self):
        sources = registrar_sources()
        self.assertEqual(len(sources), len(set(sources)))
        for relative in sources:
            self.assertTrue((REPO / relative).is_file(), relative)

    def test_stack_requires_every_component_and_protocol_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = {key: {"files": {}} for key in REGISTRAR_STACK}
            (root / "staging-receipt.json").write_text(json.dumps({"server_protocol_gate": {
                "status": "passed", "rebuilt_modules": ["server", "services", "win32u"]}}))
            self.assertIn("server_protocol_gate", registrar_stack_build(root, build))
            missing = dict(build)
            del missing["coremsg_dispatch"]
            with self.assertRaisesRegex(ValueError, "coremsg_dispatch"):
                registrar_stack_build(root, missing)
            (root / "staging-receipt.json").write_text(json.dumps({"server_protocol_gate": {
                "status": "passed", "rebuilt_modules": ["server", "services"]}}))
            with self.assertRaisesRegex(ValueError, "server request numbering"):
                registrar_stack_build(root, build)

    def handoff(self, root, cell):
        wine = ["/usr/bin/arch", "-x86_64", "/x/install/bin/wine"]
        receipt = {"launcher_registration_argv": wine + ["regedit"], "generated_source_sha256": {},
                   "changed_modules": [], "preconditions": [], "limitations": [],
                   "launcher_argv": wine + ["start"]}
        receipt.update({key: {"files": {}} for key in REGISTRAR_STACK})
        add_registrar_handoff(root, receipt, cell)
        return wine, receipt

    def test_cell027_handoff_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            wine, receipt = self.handoff(Path(directory), 27)
            self.assertEqual(receipt["services_start_argv"], wine + ["wineboot", "--kill"])
            self.assertNotIn("services_diagnostics", receipt)
            self.assertTrue((Path(directory) / "registrar-CELL027-FROZEN.reg").is_file())

    def test_cell028_scopes_winedebug_to_services_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wine, receipt = self.handoff(root, 28)
            self.assertEqual(receipt["services_start_argv"], wine[:2] + ["-e", "WINEDEBUG=" + SERVICES_WINEDEBUG]
                             + wine[2:] + ["wineboot", "--kill"])
            # Every later step keeps the run environment: no WINEDEBUG override.
            for key in ("registrar_registration_argv", "registrar_start_argv", "registrar_query_argv", "launcher_argv"):
                self.assertNotIn("-e", receipt[key][:3], key)
            channels = SERVICES_WINEDEBUG.split(",")
            self.assertEqual(channels[0], "-all")
            self.assertIn("+pid", channels)
            self.assertIn("services.exe:+service", channels)
            self.assertIn("svchost.exe:+svchost", channels)
            self.assertTrue(all(":" in item for item in channels[3:]), "process-scoped channels only")
            self.assertTrue(any("regular evidence file" in item for item in receipt["preconditions"]))
            self.assertTrue(any("fresh028 prefix" in item for item in receipt["preconditions"]))
            self.assertTrue(receipt["scope"].startswith("cell028 "))
            self.assertTrue((root / "registrar-CELL028-FROZEN.reg").is_file())
            with self.assertRaises(FileExistsError):
                self.handoff(root, 28)
            with self.assertRaises(ValueError):
                self.handoff(root, 29)


if __name__ == "__main__":
    unittest.main()
