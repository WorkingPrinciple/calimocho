"""Source checks for the REQ-120 NVAPI stub (tools/nvapi_stub), no Wine needed.

Run: python3 -m unittest tests/test_nvapi_stub.py
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
STUB = REPO / "tools/nvapi_stub"
MINGW = shutil.which("x86_64-w64-mingw32-gcc")
OBJDUMP = shutil.which("x86_64-w64-mingw32-objdump")

HOST_PROBE = r"""
#include <stdio.h>
#include "nvapi_version.h"
int main(void)
{
    static const char *cases[] = {"32.0.16.1656", "32.0.15.6094", "31.0.15.5222", "32.0.26005.1001",
                                  "", "32.0.16", "32..16.1656", "32.0.16.1656.1", "a.b.c.d",
                                  "32.0.16.1656 ", "1.2.3.999999", 0};
    for (int i = 0; cases[i]; i++) printf("%s=%u\n", cases[i], calimocho_nvapi_version_from_string(cases[i]));
    return 0;
}
"""


def build_stub(directory):
    """Same command as tools/release_engine.py build_nvapi_stub."""
    work = Path(directory) / "nvapi_stub"
    shutil.copytree(STUB, work)
    subprocess.run([MINGW, "-shared", "-O2", "-Wall", "-Wextra", "-Werror", "-nostdlib", "-s",
                    "-Wl,--no-insert-timestamp", "-Wl,-e,DllMain",
                    "-ffile-prefix-map=" + f"{work}/=nvapi_stub/",
                    "-o", "nvapi64.dll", "nvapi64.c", "nvapi64.def", "-lkernel32", "-ladvapi32"],
                   cwd=work, check=True, capture_output=True, text=True)
    return work / "nvapi64.dll"


class VersionParsing(unittest.TestCase):
    def test_nvidia_version_mapping(self):
        # REQ-120: the NVAPI driver number must match the registry DriverVersion of patch 0012
        # (32.0.16.1656 -> 616.56), which is above FH6's documented minimum 596.36 (FH301).
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "probe.c"
            source.write_text(HOST_PROBE)
            subprocess.run(["xcrun", "clang", "-std=c99", "-Wall", "-Werror", "-I", str(STUB),
                            "-o", str(Path(tmp) / "probe"), str(source)], check=True)
            result = subprocess.run([str(Path(tmp) / "probe")], check=True, capture_output=True, text=True)
        got = dict(line.rsplit("=", 1) for line in result.stdout.splitlines())
        self.assertEqual(got["32.0.16.1656"], "61656")
        self.assertEqual(got["32.0.15.6094"], "56094")
        self.assertEqual(got["31.0.15.5222"], "55222")
        self.assertEqual(got["32.0.26005.1001"], "51001")
        self.assertGreaterEqual(int(got["32.0.16.1656"]), 59636)
        for bad in ("", "32.0.16", "32..16.1656", "32.0.16.1656.1", "a.b.c.d", "32.0.16.1656 ", "1.2.3.999999"):
            self.assertEqual(got[bad], "0", bad)


@unittest.skipUnless(MINGW and OBJDUMP, "mingw-w64 is required")
class StubImage(unittest.TestCase):
    def test_exports_imports_and_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            dll = build_stub(tmp)
            dump = subprocess.run([OBJDUMP, "-p", str(dll)], check=True, capture_output=True, text=True).stdout
        exports = [line.split()[-1] for line in dump.splitlines() if "+base[" in line and "Export RVA" not in line]
        self.assertEqual(exports, ["nvapi_QueryInterface"])
        imports = sorted(line.split(":", 1)[1].strip() for line in dump.splitlines() if "DLL Name:" in line)
        self.assertEqual(imports, ["ADVAPI32.dll", "KERNEL32.dll"])
        stamps = [line.split()[-1] for line in dump.splitlines() if line.startswith("Time/Date stamp")]
        self.assertEqual(stamps, ["0"])
        self.assertIn("nvapi64.dll", dump)

    def test_reproducible_across_directories(self):
        # ADR-0081: identical bytes from different build directories.
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first = hashlib.sha256(build_stub(a).read_bytes()).hexdigest()
            second = hashlib.sha256(build_stub(b).read_bytes()).hexdigest()
        self.assertEqual(first, second)

    def test_answers_only_identity_queries(self):
        source = (STUB / "nvapi64.c").read_text()
        served = {"0x0150e828", "0xd22bdd7e", "0x6c2d048c", "0x01053fa5", "0x2926aaad", "0xf951a4d1",
                  "0xe5ac921f", "0xceee8e9f", "0x2ddfb66e", "0xd8265d24", "0xc33baeb1",
                  "0xadd604d1", "0x0694d52e"}
        cases = {line.split()[1].rstrip(":") for line in source.splitlines()
                 if line.strip().startswith("case 0x") and "function = " in line}
        self.assertEqual(cases, served)
        self.assertIn("vendor_id != 0x10de", source)


class Pins(unittest.TestCase):
    def test_versions_json_pins_the_stub(self):
        pin = json.loads((REPO / "versions.json").read_text())["release_engine"]
        stub = next(item for item in pin["native_shims"] if item["name"] == "nvapi_stub")
        for name, item in stub["files"].items():
            self.assertEqual(hashlib.sha256((STUB / name).read_bytes()).hexdigest(), item["sha256"], name)
        self.assertTrue(stub["install_path"].startswith("lib/calimocho/"))
        self.assertIn("tools/nvapi_stub", pin["source_bundle_files"])
        steps = " ".join(pin["opt_ins"]["fh6"]["profile_steps"])
        self.assertNotIn("nvapi64", steps)
        for name, item in pin["opt_ins"].items():
            if name != "fh6":
                self.assertNotIn("nvapi64", json.dumps(item))


if __name__ == "__main__":
    unittest.main()
