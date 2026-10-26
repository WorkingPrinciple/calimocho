import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("bisect", TOOLS / "freeze_req104_bisect.py")
bisect = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bisect)


def macho(linkedit_vmsize, tail=b"payload"):
    header = struct.pack("<IiiIIIII", 0xFEEDFACF, 7, 3, 6, 2, 72 * 2, 0, 0)
    text = struct.pack("<II16sQQQQiiII", 0x19, 72, b"__TEXT", 0, 0x1000, 0, 0x1000, 5, 5, 0, 0)
    linkedit = struct.pack("<II16sQQQQiiII", 0x19, 72, b"__LINKEDIT", 0x1000, linkedit_vmsize,
                           0x1000, 0x10, 1, 1, 0, 0)
    return header + text + linkedit + tail


class LinkeditTests(unittest.TestCase):
    def test_only_linkedit_vmsize_may_differ(self):
        self.assertTrue(bisect.same_except_linkedit_vmsize(macho(0x17C000), macho(0x16C000)))

    def test_rejects_any_other_change(self):
        self.assertFalse(bisect.same_except_linkedit_vmsize(macho(0x16C000, b"payloaD"), macho(0x16C000)))
        self.assertFalse(bisect.same_except_linkedit_vmsize(macho(0x16C000, b"payload!"), macho(0x16C000)))

    def test_rejects_non_macho(self):
        self.assertFalse(bisect.same_except_linkedit_vmsize(b"\0" * 64, b"\0" * 64))


class RegistryTests(unittest.TestCase):
    def setUp(self):
        library = "/base/install/" + str(bisect.LIBRARY)
        self.base = {"schema_version": 1, "engines": [{
            "name": "old", "version": "Wine 11.20", "install_path": "/base/install",
            "wine": "/base/install/bin/wine", "environment": {"WINELOADER": "/base/install/bin/wine"},
            "source_patches": [], "dependencies": [{"path": library, "sha256": "old"}],
            "profile_assets": {"files": [{"path": "/external/apple", "sha256": "apple"},
                                         {"path": library, "sha256": "old"}]},
            "smoke_test": {"status": "pass"}, "graphics_tests": [{"status": "pass"}],
            "integrity": {"status": "unchanged"}, "build_evidence": {"old": "receipt"}}]}

    def derive(self, label):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as scratch:
            install = Path(scratch) / "install"
            (install / bisect.LIBRARY).parent.mkdir(parents=True)
            (install / bisect.LIBRARY).write_bytes(b"new library")
            with patch.object(bisect, "digest", side_effect=lambda path: "sha:" + Path(path).name):
                return bisect.derive_registry(self.base, install, label, bisect.CANDIDATES[label]), install

    def test_only_install_paths_and_library_hash_change(self):
        registry, install = self.derive("A")
        entry = registry["engines"][0]
        self.assertEqual(entry["name"], "calimocho-req104-A-sampler")
        self.assertEqual(entry["wine"], str(install / "bin/wine"))
        self.assertEqual(entry["profile_assets"]["files"][0], {"path": "/external/apple", "sha256": "apple"})
        self.assertEqual(entry["dependencies"][0]["sha256"], "sha:libMoltenVK.dylib")
        self.assertEqual(entry["smoke_test"]["status"], "not-run")
        for key in ("graphics_tests", "integrity", "build_evidence"):
            self.assertNotIn(key, entry)

    def test_patch_stacks(self):
        names = {}
        for label in ("A", "B", "C"):
            registry, _ = self.derive(label)
            names[label] = [Path(item["path"]).name for item in registry["engines"][0]["source_patches"]]
        self.assertEqual(names["A"], [Path(bisect.PUSH_PATCH).name, Path(bisect.NAMESPACE_PATCH).name])
        self.assertEqual(names["B"], [Path(bisect.NAMESPACE_PATCH).name, Path(bisect.PR2719_PATCH).name])
        self.assertEqual(names["C"], [Path(bisect.PUSH_PATCH).name, Path(bisect.NAMESPACE_PATCH).name,
                                      Path(bisect.REUSE_PATCH).name])

    def test_candidates_are_distinct(self):
        namespaces = {spec["namespace"] for spec in bisect.CANDIDATES.values()}
        engines = {spec["engine"] for spec in bisect.CANDIDATES.values()}
        self.assertEqual(len(namespaces), 3)
        self.assertEqual(len(engines), 3)
        self.assertNotIn("00000000", namespaces)
        for spec in bisect.CANDIDATES.values():
            self.assertIn("REQ104_CACHE_NAMESPACE=0x" + spec["namespace"], spec["defines"])


if __name__ == "__main__":
    unittest.main()
