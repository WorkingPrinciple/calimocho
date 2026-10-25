import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools.build_uwp_overlay import REPO
from tools.port_onecore_transform import port


class OneCoreTransformTests(unittest.TestCase):
    def test_actual_query_bool_void_matches_observed_inactive_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "windef.h").write_text("typedef int BOOL;\n#define WINAPI\n#define FALSE 0\n")
            (path / "winbase.h").write_text("")
            (path / "query.c").write_bytes((REPO / "patches/wine/files/onecore_transform.c").read_bytes())
            (path / "test.c").write_text(
                '#include <assert.h>\n#include "query.c"\n'
                'int main(void) { BOOL (*query)(void) = IsOneCoreTransformMode; '
                'assert(query() == 0); assert(query() == 0); return 0; }\n')
            subprocess.run(["/usr/bin/clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I" + directory, str(path / "test.c"), "-o", str(path / "test")],
                           check=True, capture_output=True)
            subprocess.run([str(path / "test")], check=True)

    def test_port_adds_only_query_export_and_preserves_apiset(self):
        baseline = REPO / "build/winehq-11.20/package-uwp-claims-packaged-thread-01/source"
        with tempfile.TemporaryDirectory(dir=REPO / "build") as directory:
            source = Path(directory) / "source"
            module = source / "dlls/user32"
            module.mkdir(parents=True)
            for name in ("user32.spec", "Makefile.in"):
                shutil.copy2(baseline / "dlls/user32" / name, module / name)
            before = (module / "user32.spec").read_text()
            self.assertIn("# @ stub IsOneCoreTransformMode", before)
            record = port(source)
            after = (module / "user32.spec").read_text()
            self.assertEqual(after, before.replace("# @ stub IsOneCoreTransformMode",
                                                    "@ stdcall IsOneCoreTransformMode()"))
            self.assertEqual(port(source), record)
            self.assertIn("# @ stub EnableOneCoreTransformMode", after)
            self.assertFalse((source / "dlls/apisetschema").exists())
            (source.parent / "CELL024-FROZEN").touch()
            with self.assertRaisesRegex(ValueError, "unfrozen owned"):
                port(source)

    def test_reference_scope_and_full_output_hashes_are_pinned(self):
        pin = json.loads((REPO / "versions.json").read_text())["onecore_transform_reference"]
        self.assertEqual(pin["unpackaged_output_sha256"],
                         "945ae1f2b3d4fdbe311253b9658cf02187684bdb14a81a8c1f01f87a2bc372ee")
        self.assertEqual(pin["packaged_output_sha256"],
                         "12b6c7b5ab380c7b55f5dc01d4fa5995a13de4f5994e6b6557873ae8a970b14f")
        self.assertIn("unobserved", pin["scope"])
