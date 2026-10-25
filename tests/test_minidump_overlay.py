from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE = "api-ms-win-core-debug-minidump-l1-1-0"


class MinidumpOverlayTests(unittest.TestCase):
    def test_exports_forward_exact_dbghelp_abi(self):
        source = ROOT / "patches/wine/files" / MODULE
        self.assertEqual((source / (MODULE + ".spec")).read_text().splitlines(), [
            "@ stdcall MiniDumpReadDumpStream(ptr long ptr ptr ptr) dbghelp.MiniDumpReadDumpStream",
            "@ stdcall MiniDumpWriteDump(ptr long ptr long ptr ptr ptr) dbghelp.MiniDumpWriteDump",
        ])
        self.assertIn("EXTRADLLFLAGS = -Wb,--data-only",
                      (source / "Makefile.in").read_text())

    def test_built_pe_forwarding_tables(self):
        winebuild = ROOT / "build/winehq-11.20/metal-port-11/build/tools/winebuild/winebuild"
        objdump = shutil.which("x86_64-w64-mingw32-objdump")
        if not winebuild.is_file() or not objdump:
            self.skipTest("Requires existing source-built winebuild and PE objdump")
        with tempfile.TemporaryDirectory() as directory:
            for architecture, machine in (("x86_64", "pei-x86-64"), ("i386", "pei-i386")):
                with self.subTest(architecture=architecture):
                    artifact = Path(directory) / (architecture + ".dll")
                    subprocess.run([
                        str(winebuild), "--dll", "--data-only",
                        "--target=" + architecture + "-windows", "-E",
                        str(ROOT / "patches/wine/files" / MODULE / (MODULE + ".spec")),
                        "-o", str(artifact),
                    ], check=True, capture_output=True, text=True, timeout=60)
                    output = subprocess.check_output(
                        [objdump, "-p", str(artifact)], text=True, timeout=30)
                    self.assertIn(machine, output)
                    forwarders = [line.split("Forwarder RVA -- ", 1)[1].strip()
                                  for line in output.splitlines() if "Forwarder RVA -- " in line]
                    self.assertEqual(forwarders, [
                        "dbghelp.MiniDumpReadDumpStream", "dbghelp.MiniDumpWriteDump",
                    ])
                    self.assertRegex(output, r"Number in:\s+Export Address Table\s+00000002")


if __name__ == "__main__":
    unittest.main()
