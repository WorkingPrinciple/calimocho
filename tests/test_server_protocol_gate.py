import tempfile
import unittest
from pathlib import Path

from tools.server_protocol_gate import require_consistent


def tree(root, requests, consumers):
    (root / "include/wine").mkdir(parents=True)
    body = "".join("    REQ_%s,\n" % name for name in requests)
    (root / "include/wine/server_protocol.h").write_text("enum request\n{\n" + body + "    REQ_NB_REQUESTS\n};\n")
    for relative, names in consumers.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join("SERVER_START_REQ( %s )\n" % name for name in names))


class ServerProtocolGateTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.base, self.new, self.install = root / "base", root / "new", root / "install"
        consumers = {"dlls/win32u/window.c": ["alloc_user_handle"], "dlls/user32/misc.c": ["get_window_info"]}
        tree(self.base, ["get_window_info", "alloc_user_handle"], consumers)
        tree(self.new, ["get_window_info", "alpc_connect_port", "alloc_user_handle"], consumers)
        (self.install / "lib/wine/x86_64-unix").mkdir(parents=True)
        (self.install / "lib/wine/x86_64-unix/win32u.so").write_text("")
        (self.install / "lib/wine/x86_64-windows").mkdir(parents=True)
        (self.install / "lib/wine/x86_64-windows/user32.dll").write_text("")

    def tearDown(self):
        self.directory.cleanup()

    def test_unrebuilt_consumer_of_shifted_request_fails(self):
        with self.assertRaisesRegex(ValueError, "win32u: alloc_user_handle"):
            require_consistent(self.base, self.new, self.install, ["build/server/wineserver"])

    def test_rebuilt_consumer_passes(self):
        rebuilt = require_consistent(self.base, self.new, self.install,
                                     ["build/server/wineserver", "build/dlls/win32u/win32u.so"])
        self.assertEqual(rebuilt, ["server", "win32u"])

    def test_uninstalled_consumer_is_ignored(self):
        (self.install / "lib/wine/x86_64-unix/win32u.so").unlink()
        require_consistent(self.base, self.new, self.install, ["build/server/wineserver"])


if __name__ == "__main__":
    unittest.main()
