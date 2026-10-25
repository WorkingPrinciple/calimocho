"""Frozen017 regression evidence: the native consumer overruns the admitted ABI."""
import hashlib
from pathlib import Path
import struct
import subprocess
import unittest

from tools.build_uwp_overlay import REPO


NATIVE = Path("/Users/dragoshont/xodus-runs/rt-v20b/drive_c/windows/system32/"
              "Windows.UI.Xaml.dll.pre-claims-import-fix")
FROZEN = REPO / "build/winehq-11.20/package-uwp-exception-01"


class NativeLifetimeAbiTests(unittest.TestCase):
    def test_exact_native_consumer_calls_slots11_and12_on_17b0_interface(self):
        data = NATIVE.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         "16302bfe92cd6d1cdae9666767e53323fa11e10ab1c751d8142e6f95f3a82899")
        disassembly = subprocess.check_output([
            "x86_64-w64-mingw32-objdump", "-d", "-Mintel",
            "--start-address=0x180577524", "--stop-address=0x1805777d0", str(NATIVE),
        ], text=True)
        self.assertIn("mov    rdi,QWORD PTR [rax+0x58]", disassembly)
        self.assertIn("mov    rax,QWORD PTR [rax+0x60]", disassembly)
        self.assertIn("lea    rdx,[rip+0x9b658e]", disassembly)
        self.assertIn("# 0x180f2dd40", disassembly)
        self.assertIn("mov    r8,rsi", disassembly)
        self.assertIn("mov    rdx,QWORD PTR [rax]", disassembly)
        iid = subprocess.check_output([
            "x86_64-w64-mingw32-objdump", "-s",
            "--start-address=0x180f2dd40", "--stop-address=0x180f2dd50", str(NATIVE),
        ], text=True)
        self.assertIn("13e6b017 2a942d42 904cf90d c71a7dae", iid)

    def test_frozen017_slot11_is_adjacent_getiids_not_a_native_callback_method(self):
        path = FROZEN / "install/lib/wine/x86_64-windows/twinapi.appcore.dll"
        data = path.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         "ba8b06b756fbfb33cfacf0f42c9bc4cbf235a046fab9985951d51f68b6339b5d")
        # Frozen017 .rdata has equal file offset and RVA, independently
        # checked against its PE section table before fixing these offsets.
        slots = struct.unpack_from("<21Q", data, 0x10ec0)
        self.assertEqual(slots[11], 0x180007560)
        self.assertEqual(slots[8:], struct.unpack_from("<13Q", data, 0x10f00))
        disassembly = subprocess.check_output([
            "x86_64-w64-mingw32-objdump", "-d", "-Mintel",
            "--start-address=0x180007560", "--stop-address=0x180007600", str(path),
        ], text=True)
        self.assertIn("<diagnostic_collection_vtable_GetIids>", disassembly)
        self.assertIn("mov    DWORD PTR [rbx],0x2", disassembly)
        self.assertIn("mov    QWORD PTR [rsi],rax", disassembly)


if __name__ == "__main__":
    unittest.main()
