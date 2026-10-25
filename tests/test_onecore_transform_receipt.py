import hashlib
import json
from pathlib import Path
import struct
import subprocess
import unittest

from tools.build_minidump_overlay import inventory
from tools.build_uwp_overlay import REPO
from tools.freeze_launcher_runtime import checked_assets
from tools.probe_wine_source import sha256


def export_code(path, name):
    data = path.read_bytes()
    pe = struct.unpack_from("<I", data, 60)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional = pe + 24
    size = struct.unpack_from("<H", data, pe + 20)[0]
    sections = [struct.unpack_from("<IIII", data, optional + size + i * 40 + 8)
                for i in range(count)]

    def raw(rva):
        for virtual_size, address, raw_size, offset in sections:
            if address <= rva < address + max(virtual_size, raw_size):
                return offset + rva - address
        raise ValueError("Unmapped export RVA")

    if struct.unpack_from("<H", data, optional)[0] != 0x20b:
        raise ValueError("Require PE32+")
    export = raw(struct.unpack_from("<I", data, optional + 112)[0])
    names_count, functions, names, ordinals = struct.unpack_from("<IIII", data, export + 24)
    for i in range(names_count):
        start = raw(struct.unpack_from("<I", data, raw(names) + i * 4)[0])
        label = data[start:data.index(b"\0", start)].decode("ascii")
        if label == name:
            ordinal = struct.unpack_from("<H", data, raw(ordinals) + i * 2)[0]
            code = raw(struct.unpack_from("<I", data, raw(functions) + ordinal * 4)[0])
            return data[code:code + 8]
    return None


class OneCoreTransformReceiptTests(unittest.TestCase):
    def test_frozen024_user32_export_assets_sources_and_screen_hold(self):
        path = REPO / "build/winehq-11.20/package-uwp-onecore-transform-01/cell024-receipt.json"
        self.assertEqual(sha256(path), "ba82f32c76a161273ad171065fd1de0eeaa8ce26ed76fe26b0652c5148ec952f")
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt["producer_commit"], "e3a42da81f73affb55009738e2beae479889b4e8")
        self.assertFalse(receipt["runtime_executed"])
        self.assertIn("explicit user resume required", receipt["runtime_execution_hold"])
        self.assertEqual(receipt["preconditions"][0], receipt["runtime_execution_hold"])
        self.assertEqual(receipt["predecessor_receipt_sha256"],
                         "e4899d28429cb7af93d3c311066bee13de2a13cd9e703698816347dc6837fa1f")
        for relative, digest in receipt["source_inputs"].items():
            blob = subprocess.check_output(["git", "show", receipt["producer_commit"] + ":" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)
        for field in ("registry", "inventory", "build_receipt", "staging_receipt", "helper",
                      "native_fixture", "diagnostic_collector", "launcher_registration",
                      "aedebug_registration", "state_observer_build", "predecessor_receipt"):
            self.assertEqual(sha256(Path(receipt[field])), receipt[field + "_sha256"], field)
        actual = inventory(Path(receipt["install"]))
        self.assertEqual(len(actual), 3915)
        self.assertEqual(actual, json.loads(Path(receipt["inventory"]).read_text())["files"])
        self.assertEqual(len(receipt["changed_modules"]), 9)
        self.assertIn("lib/wine/x86_64-windows/user32.dll", receipt["changed_modules"])
        entry = json.loads(Path(receipt["registry"]).read_text())["engines"][0]
        checked_assets(entry)
        self.assertTrue(entry["name"].endswith("-onecore-transform"))
        self.assertTrue(receipt["prefix"].endswith("-024/prefix"))
        self.assertEqual(receipt["environment"]["WINEPREFIX"], receipt["prefix"])
        build = json.loads(Path(receipt["build_receipt"]).read_text())
        for group in ("call_diagnostics", "activation_wait_diagnostics", "handle_provenance",
                      "exception_diagnostics", "failfast_diagnostics", "status_diagnostics",
                      "claims_packaged_thread", "onecore_transform"):
            for relative, digest in build[group]["files"].items():
                self.assertEqual(sha256(path.parent / "source" / relative), digest)
        for step in build["steps"]:
            self.assertEqual(step["exit_code"], 0)
            self.assertFalse(step["timed_out"])
        previous = Path(receipt["predecessor_receipt"]).parent
        user32 = Path("lib/wine/x86_64-windows/user32.dll")
        self.assertIsNone(export_code(previous / "install" / user32, "IsOneCoreTransformMode"))
        code = export_code(Path(receipt["install"]) / user32, "IsOneCoreTransformMode")
        self.assertIsNotNone(code)
        self.assertTrue(code.startswith(b"\x31\xc0\xc3"), code.hex())
        for relative in ("dlls/apisetschema/apisetschema.spec", "dlls/ntdll/loader.c",
                         "include/wine/whiny_context.h", "dlls/ntdll/package_claims_context.c",
                         "dlls/ntdll/package_claims_generated.h"):
            self.assertEqual(sha256(path.parent / "source" / relative),
                             sha256(previous / "source" / relative))
        for argv in (receipt["activation_argv"], receipt["state_observer"]["argv"],
                     receipt["target_observer"]["argv"], receipt["aedebug_registration_argv"]):
            self.assertEqual(argv[:3], ["/usr/bin/arch", "-x86_64", entry["wine"]])
        self.assertEqual(sum(map(len, receipt["call_diagnostics"]["interfaces"].values())), 133)
        self.assertEqual(receipt["collector_limit_seconds"], 180)
