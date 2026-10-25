from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.build_uwp_overlay import REPO
from tools.port_coremessaging_prerequisites import port


class WaitCompletionPacketTests(unittest.TestCase):
    def test_actual_server_packet_handlers_signal_cancel_dequeue_and_lifetime(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "packet-test"
            subprocess.run([
                "/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-parameter", "-Wno-missing-field-initializers",
                "-I" + str(REPO / "build/winehq-11.20/metal-port-11/source/include"),
                "-I" + str(REPO / "patches/wine/files"),
                str(REPO / "tests/wait_completion_packet_host.c"), "-o", str(output)
            ], check=True, capture_output=True)
            subprocess.run([str(output)], check=True)

    def test_port_preserves_frozen_source_and_is_idempotent(self):
        baseline = REPO / "build/winehq-11.20/package-uwp-onecore-transform-01/source"
        paths = (
            "include/winternl.h", "dlls/ntdll/ntdll.spec", "dlls/ntdll/Makefile.in",
            "dlls/ntdll/unix/sync.c", "server/object.h", "server/thread.c",
            "server/protocol.def", "server/completion.c",
            "dlls/ucrtbase/ucrtbase.spec",
        )
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            source = Path(directory) / "source"
            for relative in paths:
                output = source / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline / relative, output)
            first = port(source)
            self.assertEqual(first, port(source))
            completion = (source / "server/completion.c").read_text()
            self.assertIn("wait_packet_dequeued(msg);\n        free( msg );", completion)
            self.assertEqual(completion.count("wait_packet_dequeued(msg);"), 2)
            (source.parent / "CELL025-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)
