from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_registrar_service import port


class RegistrarServiceTests(unittest.TestCase):
    def test_configuration_privilege_scope_and_readback_fail_closed(self):
        baseline = REPO / "build/winehq-11.20/package-alpc-impersonation-01/source"
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            for relative in ("programs/services/services.c", "programs/services/services.h",
                             "programs/services/Makefile.in"):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, path)
            port(source)
            text = (source / "programs/services/registrar_token.c").read_text()
            end = text.index("static DWORD create_registrar_token(")
            (root / "registrar_checks_under_test.c").write_text(text[:end])
            executable = root / "registrar-test"
            compiled = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-fsanitize=address,undefined",
                "-I" + str(root), str(REPO / "tests/registrar_service_host.c"),
                "-o", str(executable),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            executed = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(executed.returncode, 0, executed.stdout + executed.stderr)
            services = (source / "programs/services/services.c").read_text()
            self.assertIn("CreateProcessAsUserW( registrar_token", services)
            # Cell028 diagnostics: entry and exit traces must bracket the registrar process creation call.
            entry = services.index('WINE_TRACE("registrar process create %s')
            call = services.index("CreateProcessAsUserW( registrar_token")
            exit_trace = services.index('WINE_TRACE("registrar process create returned')
            self.assertLess(entry, call)
            self.assertLess(call, exit_trace)
            for line in ('WINE_TRACE("registrar process create %s\\n", debugstr_w(path));',
                         'WINE_TRACE("registrar process create returned %d, pid %04lx, error %lu\\n", '):
                self.assertIn(line, services)
            # Cell032: the token is built on a bounded worker before the SCM database lock is taken.
            self.assertNotIn("create_registrar_token( service_entry", services)
            body = services[services.index("DWORD service_start(struct service_entry *service, DWORD"):]
            build = body.index("build_registrar_token( service, &registrar_token )")
            self.assertLess(build, body.index("err = service_start_process(service, &process, &shared_process, registrar_token);"))
            self.assertNotIn("service_lock", body[:build])
            locked = services[services.index("static DWORD service_start_process("):
                              services.index("DWORD service_start(struct service_entry *service, DWORD")]
            self.assertNotIn("registrar_token )", locked.split("CreateProcessAsUserW")[0])
            self.assertNotIn("ExitProcess", text)
            self.assertIn("WaitForSingleObject( thread, 10000 )", text)
            self.assertIn("return ERROR_PROCESS_ABORTED;", text)
            self.assertEqual(text.count('WINE_TRACE("registrar token step '), 10)
            with self.assertRaisesRegex(ValueError, "fresh"):
                port(source)
            (root / "CELL027-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)
