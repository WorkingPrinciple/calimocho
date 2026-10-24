from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.check_mouse_probe import check_log


LOG = (
    "READY pid=12 hwnd=00010020 clip=1 left=80 top=100 right=480 bottom=400 duration_ms=5000\n"
    "RAW flags=0 dx=8 dy=-4 foreground=1\n"
    "CLEANUP clip_restored=1 raw_removed=1 cursor_show_calls=1\n"
    "SUMMARY relative=1 nonzero=1 absolute=0 moves=0 elapsed_ms=5004 aborted=0 errors=0\n"
)


class RawMouseReceiptTests(unittest.TestCase):
    def test_accepts_nonzero_foreground_relative_packet(self):
        self.assertEqual(check_log(LOG, 0, expected_clip=True)["nonzero"], 1)

    def test_requires_the_requested_clip_mode(self):
        unclipped = LOG.replace("clip=1", "clip=0")
        self.assertEqual(check_log(unclipped, 0, expected_clip=False)["nonzero"], 1)
        with self.assertRaises(ValueError):
            check_log(unclipped, 0, expected_clip=True)
        with self.assertRaises(ValueError):
            check_log(LOG, 0, expected_clip=False)

    def test_rejects_incomplete_or_misleading_evidence(self):
        for text, code in (
            (LOG, 1), (LOG.replace("dx=8 dy=-4", "dx=0 dy=0"), 0),
            (LOG.replace("foreground=1", "foreground=0"), 0),
            (LOG.replace("elapsed_ms=5004", "elapsed_ms=400"), 0),
            (LOG.replace("aborted=0", "aborted=1"), 0),
            (LOG.replace("flags=0", "flags=1"), 0),
            (LOG.replace("relative=1", "relative=2"), 0),
            (LOG.replace("clip_restored=1", "clip_restored=0"), 0),
            (LOG.replace("raw_removed=1", "raw_removed=0"), 0),
            (LOG.replace("cursor_show_calls=1", "cursor_show_calls=0"), 0),
            (LOG + "ERROR cleanup failed\n", 0), (LOG + LOG, 0),
            (LOG.split("SUMMARY")[0], 0),
        ):
            with self.subTest(text=text, code=code), self.assertRaises(ValueError):
                check_log(text, code, expected_clip=True)

    @unittest.skipUnless(shutil.which("x86_64-w64-mingw32-gcc"), "Requires installed MinGW")
    def test_probe_compiles_warning_free_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "raw-mouse-probe.exe"
            subprocess.run(
                [shutil.which("x86_64-w64-mingw32-gcc"), "-std=c11",
                 "-Wall", "-Wextra", "-Werror", "-O2",
                 str(Path(__file__).with_name("raw_mouse_probe.c")),
                 "-o", str(output), "-luser32"],
                check=True, capture_output=True, text=True, timeout=60,
            )
            data = output.read_bytes()
            offset = int.from_bytes(data[60:64], "little")
            self.assertEqual(data[:2], b"MZ")
            self.assertEqual(data[offset:offset + 6], b"PE\0\0\x64\x86")


if __name__ == "__main__":
    unittest.main()
