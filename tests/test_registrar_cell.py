import json
import tempfile
import unittest
from pathlib import Path

from tools.build_uwp_overlay import REPO
from tools.freeze_registrar_cell import (IMAGE_PATH, SERVICES_WINEDEBUG, SETUP_ARGVS, add_headless_setup,
                                         add_registrar_handoff, registrar_sources,
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

    @staticmethod
    def _mk(path):
        path.mkdir()
        return path

    def handoff(self, root, cell):
        wine = ["/usr/bin/arch", "-x86_64", "/x/install/bin/wine"]
        receipt = {"launcher_registration_argv": wine + ["regedit"], "generated_source_sha256": {},
                   "changed_modules": [], "preconditions": [], "limitations": [],
                   "launcher_argv": wine + ["start"]}
        receipt.update({key: {"files": {}} for key in REGISTRAR_STACK})
        receipt["environment"] = {"WINEDLLOVERRIDES": "mscoree=;coremessaging=n", "WINEDEBUG": "-all"}
        for key in ("framework_registration_argv", "native_xaml_registration_argv", "aedebug_registration_argv"):
            receipt[key] = wine + ["regedit", "/S", key]
        receipt["activation_argv"] = wine + ["probe.exe"]
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
                self.handoff(root, 34)

    def test_cell029_setup_is_headless_and_session_steps_are_not(self):
        with tempfile.TemporaryDirectory() as directory:
            wine, receipt = self.handoff(Path(directory), 29)
            before = {key: list(receipt[key]) for key in ("services_start_argv", "registrar_start_argv",
                                                          "registrar_query_argv", "activation_argv", "launcher_argv")}
            environment = dict(receipt["environment"])
            add_headless_setup(receipt)
            headless = ["-e", "WINEDLLOVERRIDES=mscoree=;coremessaging=n;winemac.drv=d"]
            self.assertEqual(receipt["prefix_init_argv"], wine[:2] + headless + wine[2:] + ["wineboot", "-u"])
            for key in SETUP_ARGVS:
                self.assertEqual(receipt[key][:4], wine[:2] + headless, key)
                self.assertEqual(receipt[key][4], wine[2], key)
            self.assertEqual(receipt["setup_environment"]["WINEDLLOVERRIDES"], headless[1].split("=", 1)[1])
            # The server_start session (services, registrar, activation) keeps the mac driver.
            self.assertEqual(receipt["environment"], environment)
            for key, argv in before.items():
                self.assertEqual(receipt[key], argv, key)
            with self.assertRaisesRegex(ValueError, "already"):
                add_headless_setup(receipt)

    def test_cell030_restores_mac_driver_setup_with_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            wine, receipt = self.handoff(Path(directory), 30)
            self.assertEqual(receipt["setup_wineboot_timeout_seconds"], 120)
            self.assertNotIn("prefix_init_argv", receipt)
            self.assertNotIn("setup_environment", receipt)
            for key in SETUP_ARGVS:
                self.assertEqual(receipt[key][:3], wine, key)
            # Cell028 services diagnostics are kept.
            self.assertEqual(receipt["services_start_argv"][2:4], ["-e", "WINEDEBUG=" + SERVICES_WINEDEBUG])
            self.assertIn("services_diagnostics", receipt)

    def test_cell031_reruns_cell030_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            _, cell030 = self.handoff(self._mk(Path(directory) / "a"), 30)
            _, cell031 = self.handoff(self._mk(Path(directory) / "b"), 31)
            self.assertEqual(set(cell030), set(cell031))
            self.assertEqual(cell031["setup_wineboot_timeout_seconds"], 120)
            self.assertNotIn("prefix_init_argv", cell031)
            self.assertEqual(cell031["services_start_argv"], cell030["services_start_argv"])
            self.assertTrue(cell031["scope"].startswith("cell031 "))

    def test_cell032_adds_token_worker_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            _, cell031 = self.handoff(self._mk(Path(directory) / "a"), 31)
            _, cell032 = self.handoff(self._mk(Path(directory) / "b"), 32)
            self.assertEqual(set(cell031), set(cell032))
            self.assertEqual(cell032["services_start_argv"], cell031["services_start_argv"])
            self.assertEqual(cell032["setup_wineboot_timeout_seconds"], 120)
            self.assertTrue(cell032["services_diagnostics"]["discriminators"][0].startswith("'registrar token worker start'"))
            self.assertTrue(any(item.startswith("Cell032 builds the registrar token") for item in cell032["limitations"]))
            self.assertFalse(any("token worker" in item for item in cell031["services_diagnostics"]["discriminators"]))

    def test_cell033_records_request_limit_and_connect_fixes(self):
        with tempfile.TemporaryDirectory() as directory:
            _, cell032 = self.handoff(self._mk(Path(directory) / "a"), 32)
            _, cell033 = self.handoff(self._mk(Path(directory) / "b"), 33)
            self.assertEqual(set(cell032), set(cell033))
            self.assertEqual(cell033["services_start_argv"], cell032["services_start_argv"])
            self.assertEqual(cell033["setup_wineboot_timeout_seconds"], 120)
            self.assertTrue(cell033["services_diagnostics"]["discriminators"][0].startswith("'wineserver: create_token"))
            self.assertEqual(cell033["services_diagnostics"]["discriminators"][1:],
                             cell032["services_diagnostics"]["discriminators"])
            self.assertTrue(any("__SERVER_MAX_DATA is5" in item for item in cell033["limitations"]))
            self.assertTrue(any("not a stub" in item for item in cell033["limitations"]))
            self.assertFalse(any("__SERVER_MAX_DATA" in item for item in cell032["limitations"]))


if __name__ == "__main__":
    unittest.main()
