from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


COMPILER = shutil.which("x86_64-w64-mingw32-gcc")


@unittest.skipUnless(COMPILER, "Requires the installed MinGW x86_64 PE compiler")
class PresentProbeBuildTests(unittest.TestCase):
    def test_owned_present_probe_compiles_warning_free_as_pe64(self):
        for api in ("d3d12", "d3d11"):
            with self.subTest(api=api):
                self.compile_probe(api)

    def compile_probe(self, api):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "probe.exe"
            subprocess.run(
                [COMPILER, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
                 str(Path(__file__).with_name(f"{api}_present_probe.c")), "-o", str(output),
                 f"-l{api}", "-ldxgi", "-ldxguid", "-lole32", "-luuid", "-lgdi32"],
                check=True, capture_output=True, text=True, timeout=60,
            )
            data = output.read_bytes()
            self.assertEqual(data[:2], b"MZ")
            pe_offset = int.from_bytes(data[60:64], "little")
            self.assertEqual(data[pe_offset:pe_offset + 4], b"PE\0\0")
            self.assertEqual(data[pe_offset + 4:pe_offset + 6], b"\x64\x86")
            self.assertGreater(len(data), 0)


if __name__ == "__main__":
    unittest.main()
