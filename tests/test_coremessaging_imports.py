import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools.build_uwp_overlay import REPO
from tools.probe_wine_source import sha256
from tools.qualify_coremessaging_imports import PE, qualify, qualify_ordinal_guards


class CoreMessagingImportTests(unittest.TestCase):
    def setUp(self):
        self.root = REPO / "build/winehq-11.20/package-uwp-coremessaging-01"
        self.pins = json.loads((REPO / "versions.json").read_text())["native_coremessaging_reference"]
        self.native = Path(self.pins["path"])

    def test_actual_public_native_and_source_built_crt_forwarders_match(self):
        self.assertEqual(sha256(self.native), self.pins["sha256"])
        self.assertEqual(self.native.stat().st_size, self.pins["size"])
        native_crt = self.native.with_name("ucrtbase.dll")
        self.assertEqual(sha256(native_crt), self.pins["native_ucrtbase_sha256"])
        built = PE(self.root / "install/lib/wine/x86_64-windows/ucrtbase.dll")
        self.assertEqual(PE(native_crt).exports()["__C_specific_handler_noexcept"],
                         self.pins["observed_noexcept_forwarder"])
        self.assertEqual(built.exports()["__C_specific_handler_noexcept"],
                         self.pins["observed_noexcept_forwarder"])
        old = PE(REPO / "build/winehq-11.20/package-uwp-onecore-transform-01/install"
                 "/lib/wine/x86_64-windows/ucrtbase.dll")
        self.assertNotIn("__C_specific_handler_noexcept", old.exports())
        self.assertEqual(PE(self.native).exports()["CoreUICreate"], 0x83290)

    def test_actual_mandatory_import_closure_and_unqualified_delayed_imports(self):
        result = qualify(self.native, self.root / "install", self.root / "source")
        self.assertEqual(len(PE(self.native).imports()), 31)
        self.assertEqual(result["mandatory_import_count"], 178)
        self.assertEqual(len(result["resolved_module_sha256"]), 6)
        self.assertEqual(len(result["delayed_imports_unqualified"]), 19)
        noexcept = [item for item in result["mandatory_imports"]
                    if item["symbol"] == "__C_specific_handler_noexcept"]
        self.assertEqual(len(noexcept), 1)
        self.assertEqual(noexcept[0]["resolution"],
                         ["ucrtbase.dll!__C_specific_handler_noexcept", "ntdll.dll!__C_specific_handler"])
        previous = REPO / "build/winehq-11.20/package-uwp-onecore-transform-01"
        with self.assertRaisesRegex(ValueError, "Missing mandatory export"):
            qualify(self.native, previous / "install", previous / "source")

    def test_wrong_machine_and_unmapped_rva_are_rejected(self):
        pe = PE(self.native)
        with self.assertRaisesRegex(ValueError, "Unmapped PE RVA"):
            pe.raw(0xffffffff)
        data = bytearray(self.native.read_bytes())
        offset = struct.unpack_from("<I", data, 60)[0]
        struct.pack_into("<H", data, offset + 4, 0x14c)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong-machine.dll"
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "Require AMD64"):
                PE(path)

    def test_guarded_combase_preserves_other_ordinals_and_all_named_exports(self):
        guarded = REPO / "build/winehq-11.20/package-uwp-coremessaging-guard-01/install"
        before = PE(self.root / "install/lib/wine/x86_64-windows/combase.dll").exports()
        after = PE(guarded / "lib/wine/x86_64-windows/combase.dll").exports()
        self.assertEqual({n for n in before if isinstance(n, str)},
                         {n for n in after if isinstance(n, str)})

        def names(exports, ordinal):
            return {n for n, value in exports.items()
                    if isinstance(n, str) and value == exports[ordinal]}

        for ordinal in (n for n in before if isinstance(n, int)):
            if ordinal in (86, 87, 88):
                self.assertFalse(names(after, ordinal))
                self.assertEqual(names(before, ordinal), names(after, ordinal + 270))
            else:
                self.assertEqual(names(before, ordinal), names(after, ordinal))
        result = qualify_ordinal_guards(guarded)
        self.assertEqual([g["ordinal"] for g in result["guards"]], [86, 87, 88])
        with self.assertRaisesRegex(ValueError, "aliases a named API"):
            qualify_ordinal_guards(self.root / "install")
