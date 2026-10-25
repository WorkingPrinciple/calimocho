from pathlib import Path
import tempfile
import unittest

from tools.build_uwp_overlay import REPO, build
from tools.freeze_uwp_runtime import freeze
from tools.stage_uwp_overlay import stage


class UwpFreezeTests(unittest.TestCase):
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
