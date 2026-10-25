from pathlib import Path
import struct
import tempfile
import unittest

from tools.package_protocols import artifacts, routes, REGISTRATION_SIZE
from tools.package_activation import identity
from tools.verify_installed_appx import MICROSOFT_PUBLISHER


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.package = self.root / "package"
        self.package.mkdir()
        for name in ("entry.exe", "target.exe", "tray.exe"):
            (self.package / name).write_bytes(b"MZfixture")
        self.manifest = self.package / "AppxManifest.xml"
        self.original = (
            '<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" '
            'xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10">'
            f'<Identity Name="Microsoft.GamingApp" Publisher="{MICROSOFT_PUBLISHER}" '
            'Version="1.0.0.0" ProcessorArchitecture="x64"/>'
            '<Applications><Application Id="Entry" Executable="entry.exe"/>'
            '<Application Id="Target" Executable="target.exe" EntryPoint="Target.App">'
            '<Extensions><uap:Extension Category="windows.protocol">'
            '<uap:Protocol Name="msxboxl"/></uap:Extension>'
            '<uap:Extension Category="windows.protocol" Executable="tray.exe" '
            'EntryPoint="Windows.FullTrustApplication"><uap:Protocol Name="msgamelaunch"/>'
            '</uap:Extension></Extensions></Application></Applications></Package>')
        self.manifest.write_text(self.original)

    def test_routes_bind_exact_target_and_extension_override(self):
        result = routes(self.package)
        self.assertEqual([item["scheme"] for item in result], ["msxboxl", "msgamelaunch"])
        self.assertEqual([Path(item["metadata"]["executable"]).name for item in result],
                         ["target.exe", "tray.exe"])
        self.assertEqual(result[0]["app_id"], "Target")
        self.assertEqual(result[0]["entry_point"], "Target.App")
        self.assertEqual(result[1]["entry_point"], "Windows.FullTrustApplication")
        self.assertTrue(all(len(item["registration"]) == REGISTRATION_SIZE for item in result))

    def test_rejects_duplicate_scheme_invalid_scheme_and_path_escape(self):
        for before, after in (("msgamelaunch", "msxboxl"), ("msxboxl", "https://secret"),
                              ('Executable="tray.exe"', 'Executable="..\\outside.exe"'),
                              ('Id="Target"', 'Id="Entry"')):
            self.manifest.write_text(self.original.replace(before, after))
            with self.subTest(after=after), self.assertRaises(ValueError):
                routes(self.package)

    def test_artifacts_require_actual_verified_owned_snapshot(self):
        record = {"snapshot": str(self.package), "installed_content_verified": True,
                  "signed_context_eligible": True}
        for key in ("installed_content_verified", "signed_context_eligible"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                artifacts(self.root, {**record, key: False})
        metadata, blob = identity(self.manifest, "Entry")
        image = ("\\??\\Z:" + metadata["executable"].replace("/", "\\")).encode("utf-16le")
        (self.root / "registration.bin").write_bytes(blob + (image + b"\0\0").ljust(2048, b"\0"))
        result = artifacts(self.root, record)
        table = Path(result["server_registration_table"]).read_bytes()
        self.assertEqual(struct.unpack("<III", table[:12]), (0x52505743, 1, 3))
        self.assertEqual(len(table), 12 + 3 * REGISTRATION_SIZE)
        protocols = Path(result["protocol_table"]).read_bytes()
        self.assertEqual(struct.unpack("<III", protocols[:12]), (0x50505743, 1, 2))
        self.assertEqual(len(protocols), 12 + 2 * (128 + REGISTRATION_SIZE + 512))
