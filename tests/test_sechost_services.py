from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_sechost_services import PATHS, port

BASELINE = REPO / "build/winehq-11.20/package-cell033-01/source"


@unittest.skipUnless((BASELINE / "dlls/sechost/sechost.spec").is_file(), "cell033 source build absent")
class SechostServicesTests(unittest.TestCase):
    def test_transient_sd_and_wait_service_state(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            for relative in PATHS[:2]:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(BASELINE / relative, path)
            result = port(source)
            self.assertEqual(sorted(result["files"]), sorted(PATHS))
            spec = (source / PATHS[1]).read_text()
            for line in ("@ stdcall QueryTransientObjectSecurityDescriptor(long wstr ptr)",
                         "@ stdcall FreeTransientObjectSecurityDescriptor(ptr)",
                         "@ stdcall WaitServiceState(long long long long)"):
                self.assertIn(line + "\n", spec)
            self.assertNotIn("@ stub WaitServiceState", spec)
            service = (source / PATHS[0]).read_text()
            self.assertIn('#include "ntstatus.h"\n#define WIN32_NO_STATUS\n#include "windef.h"', service)
            self.assertTrue(service.endswith('#include "transient_wait.c"\n'))
            shutil.copy2(source / PATHS[2], root / "transient_wait_under_test.c")
            executable = root / "sechost-test"
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-fshort-wchar", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-Wno-unused-function", "-fsanitize=address,undefined",
                "-I" + str(root), str(REPO / "tests/sechost_services_host.c"), "-o", str(executable),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            with self.assertRaisesRegex(ValueError, "fresh"):
                port(source)


if __name__ == "__main__":
    unittest.main()
