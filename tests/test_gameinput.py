"""Source/build checks; installed no-device behavior belongs to gameinput_probe.c."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.build_gameinput_overlay import BASE, build, compile_flags, IDL_SHA, WINE
from tools.probe_wine_source import sha256
from tools.build_minidump_overlay import inventory

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "patches/wine/files/gameinput"
CANDIDATE = REPO / "build/winehq-11.20/metal-port-11e-gameinput-04"


class GameInputTests(unittest.TestCase):
    def test_build_rejects_reuse_and_unowned_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            outside = Path(temporary) / "candidate"
            for target in (Path(temporary), outside):
                with self.assertRaises(ValueError):
                    build(target)
            self.assertFalse(outside.exists())

    def test_exact_exports_and_native_preference(self):
        self.assertEqual((SOURCE / "gameinput.spec").read_text().splitlines(), [
            "@ stdcall GameInputCreate(ptr)", "@ stdcall GameInputInitialize(ptr ptr)",
            "@ stdcall -private DllCanUnloadNow()",
            "@ stdcall -private DllGetClassObject(ptr ptr ptr)",
        ])
        self.assertIn("--prefer-native", (SOURCE / "Makefile.in").read_text())

    def test_versioned_interfaces_and_probe_compile_warning_free(self):
        compiler = shutil.which("x86_64-w64-mingw32-gcc")
        widl = WINE / "build/tools/widl/widl"
        if not compiler or not widl.is_file():
            self.skipTest("Requires existing pinned Wine tools and MinGW")
        self.assertEqual(sha256(WINE / "source/include/gameinput.idl"), IDL_SHA)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run([str(widl), "-h", "-o", str(root / "gameinput.h"),
                            "-I", str(WINE / "source/include"),
                            str(WINE / "source/include/gameinput.idl")],
                           check=True, capture_output=True, timeout=30)
            for source in (SOURCE / "main.c", REPO / "tests/gameinput_probe.c"):
                subprocess.run([compiler, "-c", *compile_flags(root), str(source),
                                "-o", str(root / (source.stem + ".o"))],
                               check=True, capture_output=True, timeout=30)

    def test_actual_pe_exports_and_no_renderer_dependency(self):
        objdump = shutil.which("x86_64-w64-mingw32-objdump")
        module = CANDIDATE / "install/lib/wine/x86_64-windows/gameinput.dll"
        if not objdump or not module.is_file():
            self.skipTest("Requires isolated source-built GameInput PE")
        parsed = subprocess.check_output([objdump, "-p", str(module)], text=True, timeout=30)
        self.assertIn(b"Wine builtin DLL", module.read_bytes())
        self.assertRegex(parsed, r"Number in:\s+Export Address Table\s+00000004")
        names = parsed.split("[Ordinal/Name Pointer] Table -- Ordinal Base 1\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual([line.split()[-1] for line in names.splitlines()
                          if line.lstrip().startswith("[")],
                         ["DllCanUnloadNow", "DllGetClassObject", "GameInputCreate", "GameInputInitialize"])
        self.assertIn("QueryPerformanceCounter", parsed)
        self.assertNotIn("DLL Name: d3d12", parsed)
        self.assertNotIn("DLL Name: user32", parsed)

    def test_registry_is_unqualified_and_one_module_only_not_ags6(self):
        path = CANDIDATE / "receipt.json"
        if not path.is_file():
            self.skipTest("Requires isolated built candidate")
        receipt = json.loads(path.read_text())
        self.assertFalse(receipt["qualified"])
        self.assertFalse(receipt["runtime_executed"])
        self.assertTrue(receipt["base_unchanged"])
        self.assertTrue(receipt["only_one_x64_gameinput_replaced"])
        self.assertEqual(receipt["source_files"], inventory(SOURCE))
        actual = inventory(CANDIDATE / "install")
        baseline = inventory(BASE / "install")
        self.assertEqual(actual, receipt["installed_files"])
        self.assertEqual(
            {name for name in actual.keys() | baseline.keys() if actual.get(name) != baseline.get(name)},
            {"lib/wine/x86_64-windows/gameinput.dll"},
        )
        self.assertEqual(sha256(CANDIDATE / "gameinput-probe.exe"), receipt["probe_sha256"])
        for tool in receipt["build_tools"].values():
            self.assertEqual(sha256(Path(tool["path"])), tool["sha256"])
        self.assertTrue(all(command["exit_code"] == 0 for command in receipt["commands"]))
        entry = json.loads((CANDIDATE / "gameinput.registry.local.UNQUALIFIED.json").read_text())["engines"][0]
        self.assertEqual(entry["smoke_test"]["status"], "not-run")
        self.assertNotIn("runtime_qualification", entry)
        self.assertNotIn("graphics_tests", entry)
        self.assertEqual(entry["environment"]["WINEDLLOVERRIDES"], "mscoree,mshtml=")
        self.assertEqual(entry["environment"]["WINELOADER"], entry["wine"])
        self.assertEqual(entry["environment"]["WINESERVER"], entry["wineserver"])
