from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_coremsg_dispatch import port

FILES = ("dlls/win32u/ntuser_private.h", "dlls/win32u/win32u_private.h", "include/ntuser.h",
         "dlls/win32u/sysparams.c", "dlls/user32/user32.spec", "dlls/apisetschema/apisetschema.spec",
         "dlls/win32u/input.c", "dlls/user32/misc.c", "dlls/win32u/message.c")


class CoreMessagingDispatchTests(unittest.TestCase):
    def test_packets_slots_drain_and_spec_hosting(self):
        baseline = REPO / "build/winehq-11.20/package-registrar-service-03/source"
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            for relative in FILES:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, path)
            result = port(source)
            self.assertFalse(result["registrar_qualified"])
            spec = (source / "dlls/user32/user32.spec").read_text()
            for line in ("2541 stdcall -noname GetQueueStatusReadonly(long)",
                         "2669 stdcall -noname InitThreadCoreMessagingIocp2(long ptr)",
                         "2670 stdcall -noname DrainThreadCoreMessagingCompletions2(long)",
                         "@ stdcall GetQueueStatusForCoreMessaging(long)",
                         "@ stdcall ScheduleCoreMessagingDispatch(long long long long ptr)"):
                self.assertIn(line, spec)
            self.assertNotIn("stub -noname InitThreadCoreMessagingIocp2", spec)
            apiset = (source / "dlls/apisetschema/apisetschema.spec").read_text()
            self.assertIn("apiset ext-ms-win-rtcore-minuser-private-ext-l1-1-3 = user32.dll\n", apiset)
            self.assertNotIn("minuser-private-ext-l1-1-1", apiset)
            user32 = (source / "dlls/user32/coremsg.c").read_text()
            self.assertIn("case 2:", user32)
            self.assertIn("ERROR_NOT_SUPPORTED", user32)
            message = (source / "dlls/win32u/message.c").read_text()
            self.assertIn("(flags & MWMO_WAITALL)", message)
            executable = root / "coremsg-test"
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-Wno-unused-function", "-fsanitize=address,undefined",
                "-I" + str(source / "dlls/win32u"), str(REPO / "tests/coremsg_dispatch_host.c"),
                "-o", str(executable),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            with self.assertRaisesRegex(ValueError, "fresh"):
                port(source)
            (root / "CELL027-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)


if __name__ == "__main__":
    unittest.main()
