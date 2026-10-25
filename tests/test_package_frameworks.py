from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.package_frameworks import NS, classes, resolve, version
from tools.verify_installed_appx import MICROSOFT_PUBLISHER, xml
from tools.prepare_verified_activation import graph_artifacts
import struct


class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.publisher = MICROSOFT_PUBLISHER
        self.app = self.root / "app.xml"
        self.app.write_text(self.application("1.0.0.0"))
        self.framework = self.root / "Test.Framework"
        self.framework.mkdir()
        self.manifest = self.framework / "AppxManifest.xml"
        self.manifest.write_text(self.package())
        (self.framework / "server.dll").write_bytes(b"MZfixture")

    def application(self, minimum):
        return (f'<Package xmlns="{NS[1:-1]}"><Dependencies>'
                f'<PackageDependency Name="Test.Framework" Publisher="{self.publisher}" '
                f'MinVersion="{minimum}"/></Dependencies></Package>')

    def package(self, attributes=""):
        return (f'<Package xmlns="{NS[1:-1]}"><!-- public SDK comment -->'
                f'<Identity Name="Test.Framework" Publisher="{self.publisher}" '
                f'Version="1.2.3.4" ProcessorArchitecture="x64"/>'
                '<Properties><Framework>true</Framework></Properties>'
                '<Extensions><Extension><InProcessServer><Path>server.dll</Path>'
                f'<ActivatableClass ActivatableClassId="Test.PublicClass" ThreadingModel="both" {attributes}/>'
                '</InProcessServer></Extension></Extensions></Package>')

    def test_exact_declared_framework_resolves_without_granting_package_trust(self):
        with patch("tools.package_frameworks.verify_payload", return_value={"files_verified": 2}) as verify:
            graph = resolve(self.app, self.root, [], "fixture")
        self.assertEqual(len(graph), 1)
        self.assertFalse(graph[0]["signed_context_eligible"])
        self.assertEqual(graph[0]["identity"]["full_name"], "Test.Framework_1.2.3.4_x64__8wekyb3d8bbwe")
        self.assertEqual(graph[0]["classes"][0]["dll"], str(self.framework / "server.dll"))
        verify.assert_called_once_with(self.framework, [], "fixture")

    def test_missing_wrong_version_arch_publisher_framework_or_signature_fails(self):
        original = self.manifest.read_text()
        for before, after in (("x64", "x86"), ("1.2.3.4", "0.1.0.0"),
                              ("<Framework>true", "<Framework>false"),
                              ("Test.Framework", "Other.Framework"),
                              (self.publisher, "CN=untrusted")):
            self.manifest.write_text(original.replace(before, after))
            with patch("tools.package_frameworks.verify_payload", return_value={}):
                with self.assertRaises(ValueError):
                    resolve(self.app, self.root, [], "fixture")
        self.manifest.write_text(original)
        with patch("tools.package_frameworks.verify_payload", side_effect=ValueError("bad signature")):
            with self.assertRaisesRegex(ValueError, "bad signature"):
                resolve(self.app, self.root, [], "fixture")
        self.manifest.unlink()
        with patch("tools.package_frameworks.verify_payload", return_value={}):
            with self.assertRaisesRegex(ValueError, "Missing package file"):
                resolve(self.app, self.root, [], "fixture")

    def test_unrelated_packages_not_examined_and_class_collision_rejected(self):
        (self.root / "unrelated").mkdir()
        with patch("tools.package_frameworks.verify_payload", return_value={}) as verify:
            resolve(self.app, self.root, [], "fixture")
        self.assertEqual(verify.call_count, 1)
        original = self.manifest.read_text()
        entry = '<ActivatableClass ActivatableClassId="Test.PublicClass" ThreadingModel="both" />'
        self.manifest.write_text(original.replace(entry, entry * 2))
        with patch("tools.package_frameworks.verify_payload", return_value={}):
            with self.assertRaisesRegex(ValueError, "Ambiguous"):
                resolve(self.app, self.root, [], "fixture")

    def test_path_escape_dll_symlink_and_unknown_threading_rejected(self):
        original = self.manifest.read_text()
        for before, after in (("server.dll", "..\\outside.dll"), ("both", "unknown")):
            with self.assertRaises(ValueError):
                classes(xml(original.replace(before, after).encode()), self.framework)
        (self.framework / "server.dll").unlink()
        (self.framework / "server.dll").symlink_to(self.app)
        with self.assertRaisesRegex(ValueError, "symlink"):
            classes(xml(original.encode()), self.framework)

    def test_xml_comments_allowed_but_doctype_entities_and_nuls_rejected(self):
        self.assertEqual(xml(self.package().encode()).tag, NS + "Package")
        for content in (b'<!DOCTYPE x><x/>', b'<!ENTITY x "bad"><x/>', b"<x>\0</x>"):
            with self.assertRaises(ValueError):
                xml(content)
        for text in ("1.2.3", "1.2.3.65536", "-1.2.3.4"):
            with self.assertRaises(ValueError):
                version(text)

    def test_missing_manifest_server_is_explicit_not_fabricated_payload(self):
        (self.framework / "server.dll").unlink()
        with patch("tools.package_frameworks.verify_payload", return_value={}):
            graph = resolve(self.app, self.root, [], "fixture")
        self.assertFalse(graph[0]["classes"][0]["server_file_present"])

    def test_graph_wire_and_registration_paths_bind_snapshot_and_precedence(self):
        with patch("tools.package_frameworks.verify_payload", return_value={}):
            graph = resolve(self.app, self.root, [], "fixture")
        meta = {"full_name": "Test.App_1.0.0.0_x64__8wekyb3d8bbwe",
                "family_name": "Test.App_8wekyb3d8bbwe"}
        artifacts = graph_artifacts(self.root, meta, graph)
        data = Path(artifacts["graph"]).read_bytes()
        self.assertEqual(struct.unpack_from("<III", data), (0x47505743, 1, 2))
        self.assertEqual(len(data), 12 + 2 * (256 + 256 + 1024) * 2)
        self.assertEqual(data[12:524].decode("utf-16le").rstrip("\0"), meta["full_name"])
        registration = Path(artifacts["framework_registration"]).read_text(encoding="utf-16")
        self.assertIn("Test.PublicClass", registration)
        self.assertIn("server.dll", registration)
        self.assertIn('"ThreadingModel"="both"', registration)
