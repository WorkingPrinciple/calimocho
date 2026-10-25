from pathlib import Path
import json
import shutil
import subprocess
import hashlib
import tempfile
import unittest

from tools.port_uwp_activation import port, REPO
from tools.build_minidump_overlay import inventory
from tools.probe_wine_source import sha256

BASE = REPO / "build/winehq-11.20/package-launcher-01/source"
FILES = ("include/wine/package.h", "include/Makefile.in", "server/process.h", "server/process.c",
         "dlls/windows.system.launcher/main.c",
         "server/token.c", "server/security.h", "server/protocol.def", "dlls/ntdll/unix/process.c")


class UwpActivationTests(unittest.TestCase):
    def test_new_deployment_has_exact_six_module_delta_and_compiled_probe(self):
        root = REPO / "build/winehq-11.20/package-uwp-01"
        receipt = json.loads((root / "staging-receipt.json").read_text())
        before = inventory(BASE.parent / "install")
        actual = inventory(root / "install")
        self.assertEqual(actual, receipt["files"])
        self.assertEqual({key for key in actual.keys() | before.keys()
                          if actual.get(key) != before.get(key)}, set(receipt["changed_files"]))
        self.assertEqual(len(receipt["changed_files"]), 6)
        self.assertEqual(sha256(Path(receipt["probe"])), receipt["probe_sha256"])
        self.assertEqual(sha256(Path(receipt["helper"])), receipt["helper_sha256"])
        self.assertFalse(receipt["runtime_executed"])
        build = json.loads((root / "build-receipt.json").read_text())
        self.assertEqual(build["status"], "built-not-staged-not-executed")
        for step in build["steps"]:
            self.assertEqual(step["exit_code"], 0)
            self.assertFalse(step["timed_out"])
        for relative, digest in build["source_inputs"].items():
            frozen = json.loads((root / "cell009-receipt.json").read_text())
            blob = subprocess.check_output(["git", "show", frozen["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)

    def test_record_is_process_owned_and_caller_is_server_derived(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in FILES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(BASE / relative, path)
            port(root)
            process = (root / "server/process.c").read_text()
            self.assertIn("caller = token_get_package_identity( current->process->token )", process)
            self.assertIn("caller->verified_gamingapp", process)
            self.assertIn("caller->app_id, sizeof(caller->app_id)", process)
            self.assertIn("package ? sizeof(*package) : 0", process)
            self.assertIn("process->activation      = NULL", process)
            self.assertIn("free( process->activation )", process)
            self.assertIn("current->process->activation", process)
            self.assertIn("if (handle != GetCurrentProcess()) return STATUS_ACCESS_DENIED",
                          (root / "dlls/ntdll/unix/process.c").read_text())
            launcher = (root / "dlls/windows.system.launcher/main.c").read_text()
            self.assertIn("activation.activation.kind = WINE_ACTIVATION_PROTOCOL", launcher)
            self.assertNotIn("missing=uwp-protocol-activation", launcher)
            with self.assertRaisesRegex(ValueError, "already applied"):
                port(root)
