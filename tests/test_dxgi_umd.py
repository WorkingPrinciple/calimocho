"""Source checks for the REQ-120 DXGI front-end (tools/dxgi_umd), no Wine needed.

Run: python3 -m unittest tests/test_dxgi_umd.py
Needs Xcode clang and Homebrew mingw-w64 (x86_64-w64-mingw32-gcc).
"""
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SHIM = REPO / "tools/dxgi_umd"
MINGW = shutil.which("x86_64-w64-mingw32-gcc")
OBJDUMP = shutil.which("x86_64-w64-mingw32-objdump")
# Apple's D3DMetal dxgi.dll (GPTK 4.0b3) exports exactly these; the front-end must forward all of them.
APPLE_EXPORTS = ["CreateDXGIFactory", "CreateDXGIFactory1", "CreateDXGIFactory2", "DXGID3D10CreateDevice",
                 "DXGID3D10RegisterLayers", "DXGIDeclareAdapterRemovalSupport", "DXGIGetDebugInterface1"]

HOST_PROBE = r"""
#include <stdio.h>
#include "umd_version.h"
int main(void)
{
    static const char *cases[] = {"32.0.16.1656", "32.0.26005.1001", "0.0.0.0", "65535.65535.65535.65535",
                                  "65536.0.0.0", "32.0.16", "32..16.1656", "32.0.16.1656.1", "", "x.0.0.0", 0};
    for (int i = 0; cases[i]; i++)
    {
        unsigned int p[4];
        int ok = calimocho_parse_driver_version(cases[i], p);
        printf("%s=%d:%u.%u.%u.%u\n", cases[i], ok, p[0], p[1], p[2], p[3]);
    }
    return 0;
}
"""

SLOT_PROBE = r"""
#define COBJMACROS
#include <windows.h>
#include <stddef.h>
#include <dxgi1_6.h>
#define SLOT(vtbl, name) (offsetof(vtbl, name) / sizeof(void *))
_Static_assert(SLOT(IDXGIAdapterVtbl, CheckInterfaceSupport) == 9, "CheckInterfaceSupport");
_Static_assert(SLOT(IDXGIFactoryVtbl, EnumAdapters) == 7, "EnumAdapters");
_Static_assert(SLOT(IDXGIFactory1Vtbl, EnumAdapters1) == 12, "EnumAdapters1");
_Static_assert(SLOT(IDXGIFactory4Vtbl, EnumAdapterByLuid) == 26, "EnumAdapterByLuid");
_Static_assert(SLOT(IDXGIFactory6Vtbl, EnumAdapterByGpuPreference) == 29, "EnumAdapterByGpuPreference");
_Static_assert(sizeof(IDXGIAdapter4Vtbl) / sizeof(void *) == 19, "IDXGIAdapter4 size");
_Static_assert(sizeof(IDXGIFactory7Vtbl) / sizeof(void *) == 32, "IDXGIFactory7 size");
int slot_probe;
"""


def build(directory):
    """Same command as tools/release_engine.py build_native_shims."""
    work = Path(directory) / "dxgi_umd"
    shutil.copytree(SHIM, work)
    subprocess.run([MINGW, "-shared", "-O2", "-fno-builtin", "-Wall", "-Wextra", "-Werror", "-nostdlib", "-s",
                    "-Wl,--no-insert-timestamp", "-Wl,-e,DllMain", "-ffile-prefix-map=" + f"{work}/=dxgi_umd/",
                    "-o", "dxgi.dll", "dxgi.c", "dxgi.def", "-lkernel32", "-ladvapi32"],
                   cwd=work, check=True, capture_output=True, text=True)
    return work / "dxgi.dll"


class VersionParsing(unittest.TestCase):
    def test_driver_version(self):
        # REQ-120: CheckInterfaceSupport must report the registry DriverVersion (32.0.16.1656), not 65535 x4.
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "probe.c"
            source.write_text(HOST_PROBE)
            subprocess.run(["xcrun", "clang", "-std=c99", "-Wall", "-Werror", "-I", str(SHIM),
                            "-o", str(Path(tmp) / "probe"), str(source)], check=True)
            out = subprocess.run([str(Path(tmp) / "probe")], check=True, capture_output=True, text=True).stdout
        got = dict(line.rsplit("=", 1) for line in out.splitlines())
        self.assertEqual(got["32.0.16.1656"], "1:32.0.16.1656")
        self.assertEqual(got["32.0.26005.1001"], "1:32.0.26005.1001")
        self.assertEqual(got["65535.65535.65535.65535"], "1:65535.65535.65535.65535")
        for bad in ("65536.0.0.0", "32.0.16", "32..16.1656", "32.0.16.1656.1", "", "x.0.0.0"):
            self.assertTrue(got[bad].startswith("0:"), bad)


@unittest.skipUnless(MINGW and OBJDUMP, "mingw-w64 is required")
class Image(unittest.TestCase):
    def test_vtable_slots_match_the_com_abi(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "slots.c"
            source.write_text(SLOT_PROBE)
            subprocess.run([MINGW, "-c", "-o", str(Path(tmp) / "slots.o"), str(source)], check=True)

    def test_exports_imports_and_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            dump = subprocess.run([OBJDUMP, "-p", str(build(tmp))], check=True, capture_output=True, text=True).stdout
        exports = [line.split()[-1] for line in dump.splitlines() if "+base[" in line and "Export RVA" not in line]
        self.assertEqual(sorted(exports), sorted(APPLE_EXPORTS))
        imports = sorted(line.split(":", 1)[1].strip() for line in dump.splitlines() if "DLL Name:" in line)
        self.assertEqual(imports, ["ADVAPI32.dll", "KERNEL32.dll"])
        stamps = [line.split()[-1] for line in dump.splitlines() if line.startswith("Time/Date stamp")]
        self.assertEqual(stamps, ["0"])

    def test_reproducible_across_directories(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.assertEqual(hashlib.sha256(build(a).read_bytes()).hexdigest(),
                             hashlib.sha256(build(b).read_bytes()).hexdigest())

    def test_never_writes_apple_code(self):
        # Rule 1 / GPTK SLA: no VirtualProtect, WriteProcessMemory or file writes outside the opt-in log.
        source = (SHIM / "dxgi.c").read_text()
        for forbidden in ("VirtualProtect", "WriteProcessMemory", "FlushInstructionCache"):
            self.assertNotIn(forbidden, source)
        self.assertIn("D3DM_VENDOR_ID", source)


class Pins(unittest.TestCase):
    def test_versions_json(self):
        pin = json.loads((REPO / "versions.json").read_text())["release_engine"]
        shim = next(item for item in pin["native_shims"] if item["name"] == "dxgi_umd")
        for name, item in shim["files"].items():
            self.assertEqual(hashlib.sha256((SHIM / name).read_bytes()).hexdigest(), item["sha256"], name)
        self.assertEqual(shim["install_path"], "lib/calimocho/x86_64-windows/dxgi.dll")
        self.assertIn("tools/dxgi_umd", pin["source_bundle_files"])
        self.assertNotIn("dxgi=native,builtin", " ".join(pin["opt_ins"]["fh6"]["profile_steps"]))
        for name, item in pin["opt_ins"].items():
            if name != "fh6":
                self.assertNotIn("dxgi", json.dumps(item))


if __name__ == "__main__":
    unittest.main()
