from pathlib import Path
import tempfile
import unittest
from tools.package_activation import identity, publisher_id


MANIFEST = """<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10">
<Identity Name="Calimocho.Fixture" Publisher="CN=Fixture" Version="1.2.3.4"
 ProcessorArchitecture="x64"/>
<Applications><Application Id="App" Executable="app.exe"/></Applications>
</Package>"""


class PackageActivationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest = self.root / "AppxManifest.xml"
        self.manifest.write_text(MANIFEST)
        (self.root / "app.exe").write_bytes(b"owned fixture, never executed")

    def test_known_microsoft_publisher_identifier(self):
        self.assertEqual(publisher_id(
            "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US"),
            "8wekyb3d8bbwe")

    def test_explicit_application_identity_and_fixed_wire_shape(self):
        metadata, blob = identity(self.manifest, "App")
        self.assertEqual(len(blob), 1548)
        self.assertEqual(blob[:8], b"\x02\0\0\0\x0c\x06\0\0")
        self.assertEqual(blob[-4:], b"\0" * 4)
        self.assertEqual(metadata["app_id"], "App")
        self.assertEqual(metadata["executable"], str((self.root / "app.exe").resolve()))
        self.assertTrue(metadata["full_name"].startswith("Calimocho.Fixture_1.2.3.4_x64__"))
        self.assertNotIn("trust", metadata)

    def test_unknown_or_duplicate_application_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact manifest"):
            identity(self.manifest, "Other")
        self.manifest.write_text(MANIFEST.replace(
            "</Applications>", '<Application Id="App" Executable="app.exe"/></Applications>'))
        with self.assertRaisesRegex(ValueError, "exact manifest"):
            identity(self.manifest, "App")

    def test_external_entities_and_executable_escape_rejected(self):
        self.manifest.write_text("<!DOCTYPE x>" + MANIFEST)
        with self.assertRaisesRegex(ValueError, "entities"):
            identity(self.manifest, "App")
        for path in ("..\\app.exe", "C:\\app.exe", "\\app.exe"):
            self.manifest.write_text(MANIFEST.replace("app.exe", path))
            with self.assertRaises(ValueError):
                identity(self.manifest, "App")

    def test_symlink_executable_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as external:
            target = Path(external) / "outside.exe"
            target.write_bytes(b"external")
            (self.root / "app.exe").unlink()
            (self.root / "app.exe").symlink_to(target)
            with self.assertRaisesRegex(ValueError, "escapes"):
                identity(self.manifest, "App")

    def test_malformed_identity_and_version_rejected(self):
        for old, new in (("1.2.3.4", "1.2.3.65536"),
                         ('Name="Calimocho.Fixture"', 'Name="../bad"'),
                         ('ProcessorArchitecture="x64"', 'ProcessorArchitecture="arm64"')):
            self.manifest.write_text(MANIFEST.replace(old, new))
            with self.assertRaises(ValueError):
                identity(self.manifest, "App")


if __name__ == "__main__":
    unittest.main()
