import json
import tempfile
import unittest
from pathlib import Path

from tools.build_uwp_overlay import REPO
from tools.freeze_registrar_cell import IMAGE_PATH, registrar_sources, registrar_stack_build, registration_text
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


if __name__ == "__main__":
    unittest.main()
