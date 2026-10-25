from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
import unittest

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import port
from tools.freeze_static_lifetime_runtime import freeze


class AlpcTransportTests(unittest.TestCase):
    def test_actual_handlers_preserve_async_reply_ownership_and_buffer_retry(self):
        baseline = REPO / "build/winehq-11.20/package-uwp-coremessaging-guard-01/source"
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            source = root / "source"
            paths = ("server/protocol.def", "dlls/ntdll/coremessaging_ntdll_stubs.c",
                     "dlls/ntdll/ntdll.spec")
            for relative in paths:
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, target)
            (source / "dlls/ntdll/unix").mkdir()
            first = port(source)
            self.assertEqual(first, port(source))
            server = (source / "server/alpc.c").read_text()
            (root / "alpc_server_under_test.c").write_text(
                re.sub(r'^#include .*\n', "", server, flags=re.MULTILINE))
            output = root / "alpc-test"
            result = subprocess.run([
                "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-Wno-unused-function", "-Wno-unused-variable",
                "-Wno-missing-field-initializers", "-fsanitize=address,undefined",
                "-I" + str(baseline / "include"), "-I" + str(root),
                str(REPO / "tests/alpc_transport_host.c"), "-o", str(output),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            client = (source / "dlls/ntdll/unix/alpc.c").read_text()
            self.assertNotIn("hexdump_str", client)
            self.assertNotIn("NtOpenProcess", client)
            self.assertNotIn("tid | (1ull", client)
            self.assertNotIn("if (status == STATUS_REPLY_MESSAGE_MISMATCH", client)
            self.assertNotIn("send->MessageId) flags |=", client)
            self.assertIn("ALPC_PORT_MESSAGE *msg", client)
            self.assertIn("if (sd || client_attr || out_attrs || in_attrs)", client)
            self.assertIn("Message-bound ALPC impersonation is not implemented.", client)
            self.assertEqual((source / "server/protocol.def").read_text().count("@REQ(alpc_query_port)"), 1)
            (root / "CELL027-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)

    def test_transport_build_cannot_be_frozen_for_runtime(self):
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            root = Path(directory)
            (root / "build-receipt.json").write_text(json.dumps({
                "alpc_transport": {"registrar_qualified": False}
            }))
            with self.assertRaisesRegex(ValueError, "not registrar-qualified"):
                freeze(root, "HEAD", cell=27)
