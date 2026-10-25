from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO, build
from tools.freeze_launcher_runtime import checked_assets
from tools.freeze_uwp_runtime import freeze
from tools.probe_wine_source import sha256
from tools.stage_uwp_overlay import stage


class UwpFreezeTests(unittest.TestCase):
    def test_frozen_handoff_matches_committed_source_deployment_and_execution_bounds(self):
        root = REPO / "build/winehq-11.20/package-uwp-01"
        receipt_path = root / "cell009-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        for key, digest in receipt.items():
            if key.endswith("_sha256") and key[:-7] in receipt:
                value = receipt[key[:-7]]
                if isinstance(value, str) and Path(value).is_file():
                    self.assertEqual(sha256(Path(value)), digest, key)
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(
                ["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest, relative)
        frozen = json.loads(Path(receipt["inventory"]).read_text())
        self.assertEqual(inventory(Path(receipt["install"])), frozen["files"])
        registry = json.loads(Path(receipt["registry"]).read_text())
        entry = registry["engines"][0]
        checked_assets(entry)
        self.assertEqual(entry["install_path"], receipt["install"])
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        self.assertEqual(receipt["server_start"]["environment"]["CALIMOCHO_PACKAGE_REGISTRATION"],
                         receipt["server_registration_table"])
        self.assertEqual(receipt["activation_limit_seconds"], 45)
        self.assertEqual(receipt["collector_limit_seconds"], 60)
        self.assertFalse(receipt["runtime_executed"])
        self.assertEqual(receipt["diagnostic_collector_argv"][1:3],
                         [receipt["diagnostic_collector"], str(receipt_path)])
        for key in ("framework_registration_argv", "launcher_registration_argv"):
            self.assertEqual(receipt[key][:4],
                             ["/usr/bin/arch", "-x86_64", entry["wine"], "regedit"])
            self.assertEqual(receipt[key][4], "/S")
        verification = json.loads(Path(receipt["verification"]).read_text())
        self.assertEqual(receipt["application_class_count"], len(verification["application_classes"]))
        self.assertEqual(receipt["application_class_count"], 442)
        self.assertTrue(all(item["server_file_present"] for item in verification["application_classes"]))
        previous_path = Path(receipt["predecessor_receipt"])
        self.assertEqual(sha256(previous_path),
                         "ac5b627263c409b804e3f812160c6dd0ba8d39cec52910255725939de12915bc")
        previous = json.loads(previous_path.read_text())
        self.assertEqual(inventory(Path(previous["install"])),
                         json.loads(Path(previous["inventory"]).read_text())["files"])

    def test_all_producer_commands_refuse_frozen_sibling_before_mutation(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as temporary:
            root = Path(temporary)
            marker = root / "inventory-CELL009-FROZEN.json"
            marker.write_text("sealed")
            for command in (lambda: build(root, resume=True),
                            lambda: stage(root, resume=True),
                            lambda: freeze(root, "HEAD")):
                with self.assertRaisesRegex(ValueError, "[Ff]rozen"):
                    command()
                self.assertEqual(list(root.iterdir()), [marker])
                self.assertEqual(marker.read_text(), "sealed")

    def test_restaging_requires_explicit_resume(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as temporary:
            root = Path(temporary)
            (root / "install").mkdir()
            with self.assertRaisesRegex(ValueError, "explicit resume"):
                stage(root)
