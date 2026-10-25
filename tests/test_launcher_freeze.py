import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.freeze_launcher_runtime import checked_assets, committed_sources
from tools.probe_wine_source import sha256


class LauncherFreezeTests(unittest.TestCase):
    def test_asset_check_requires_exact_engine_environment_and_individual_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "bin").mkdir()
            for name in ("wine", "wineserver"):
                (root / "bin" / name).write_bytes(name.encode())
            module = root / "launcher.dll"
            module.write_bytes(b"fixture module")
            entry = {
                "install_path": str(root), "wine": str(root / "bin/wine"),
                "wineserver": str(root / "bin/wineserver"),
                "sha256": sha256(root / "bin/wine"),
                "wineserver_sha256": sha256(root / "bin/wineserver"),
                "environment": {"WINELOADER": str(root / "bin/wine"),
                                "WINESERVER": str(root / "bin/wineserver")},
                "profile_assets": {"files": [{"path": str(module), "sha256": sha256(module)}]},
                "dependencies": [],
            }
            checked_assets(entry)
            changed = copy.deepcopy(entry)
            changed["environment"]["WINESERVER"] = "/wrong/server"
            with self.assertRaisesRegex(ValueError, "environment"):
                checked_assets(changed)
            changed = copy.deepcopy(entry)
            changed["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "identity"):
                checked_assets(changed)
            module.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "asset"):
                checked_assets(entry)

    def test_producer_does_not_accept_a_non_commit(self):
        with self.assertRaises(subprocess.CalledProcessError):
            committed_sources("not-a-calimocho-commit")
