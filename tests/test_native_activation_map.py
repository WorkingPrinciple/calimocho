import copy
import unittest

from tools.native_activation_map import render_registrations, select, supported_factories


class NativeActivationMapTests(unittest.TestCase):
    def test_native_factory_matrix_requires_complete_unique_observation(self):
        text = ("xaml-factory index=0 factory=00000000 present=1 qi=00000000\n"
                "xaml-factory index=1 factory=80040111 present=0 qi=80004002\n"
                "xaml-factory count=2 supported=1 result=00000000\n")
        names = ["Windows.UI.Xaml.Application", "Windows.UI.Xaml.Absent"]
        self.assertEqual(supported_factories(names, text), {names[0]})
        for broken in (text.splitlines()[0], text + "SECRET\n",
                       text.replace("supported=1", "supported=2"),
                       text.replace("index=1", "index=0")):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                supported_factories(names, broken)

    def test_render_keeps_observed_value_kinds_and_never_redirects(self):
        export, _ = self.fixture()
        row = export["classes"][0]
        row["values"].update(Threading=0, TrustLevel=0)
        row["valueKinds"].update(ActivationType="DWord", Threading="DWord", TrustLevel="DWord")
        text = render_registrations([row]).decode("utf-16")
        self.assertIn('"Threading"=dword:00000000', text)
        self.assertNotIn("ThreadingModel", text)
        row["values"]["DllPath"] = r"C:\other.dll"
        with self.assertRaises(ValueError):
            render_registrations([row])

    def fixture(self):
        dll = r"C:\Windows\System32\Windows.UI.Xaml.dll"
        row = {"className": "Windows.UI.Xaml.FrameworkViewSource",
               "values": {"DllPath": dll, "ActivationType": 0, "Server": None},
               "valueKinds": {"DllPath": "String"}}
        export = {"schema": "whiny.observed-winrt-activation.v1", "registryView": "Registry64",
                  "osBuild": "26300.9711", "classCount": 1, "classes": [row],
                  "dllFiles": [{"dllPath": dll, "exists": True, "error": None, "sha256": "a" * 64}]}
        return export, [{"dll_path": dll.lower(), "sha256": "a" * 64}]

    def test_selects_only_exact_native_bytes(self):
        export, native = self.fixture()
        self.assertEqual(select(export, native)["selected"], export["classes"])
        native[0]["sha256"] = "b" * 64
        result = select(export, native)
        self.assertEqual(result["selected"], [])
        self.assertEqual(result["decisions"][0]["decision"], "native-hash-mismatch")
        self.assertEqual(select(export, [])["decisions"][0]["decision"], "native-dll-absent")

    def test_preserves_owned_core_classes_without_exact_native_match(self):
        export, _ = self.fixture()
        export["classes"][0]["className"] = "Windows.ApplicationModel.Core.CoreApplication"
        self.assertEqual(select(export, [])["decisions"][0]["decision"],
                         "preserve-wine-builtin:native-dll-absent")

    def test_duplicate_or_non_inprocess_mapping_is_rejected(self):
        export, native = self.fixture()
        export["classes"].append(copy.deepcopy(export["classes"][0]))
        export["classCount"] = 2
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            select(export, native)
        export, native = self.fixture()
        export["classes"][0]["values"]["ActivationType"] = 1
        self.assertEqual(select(export, native)["selected"], [])
        self.assertEqual(select(export, native)["decisions"][0]["decision"],
                         "unsupported-server-activation")
