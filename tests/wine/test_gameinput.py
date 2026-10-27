"""Compile Wine's real dlls/gameinput/gameinput.c on the host and call it (REQ-158).

No Wine, prefix or game is started. The test needs a configured Wine build's include
directory for the widl-generated headers (gameinput.h, unknwn.h and so on).
"""

import argparse
from pathlib import Path
import subprocess
import tempfile
import unittest


DEBUG_STUB = r"""
#define WINE_DEFAULT_DEBUG_CHANNEL(x)
#define TRACE(...) ((void)0)
#define FIXME(...) ((void)0)
#define WARN(...) ((void)0)
#define ERR(...) ((void)0)
static inline const char *debugstr_guid(const void *guid) { (void)guid; return ""; }
"""

PRELUDE = r"""
#include <assert.h>
#include <stdlib.h>
#include GAMEINPUT_C
"""


class GameInputTests(unittest.TestCase):
    def compile_run(self, body):
        with tempfile.TemporaryDirectory(prefix="gameinput-") as temporary:
            temporary = Path(temporary)
            (temporary / "wine").mkdir()
            (temporary / "wine/debug.h").write_text(DEBUG_STUB)
            source = temporary / "fixture.c"
            executable = temporary / "fixture"
            source.write_text(PRELUDE + body)
            subprocess.run(
                ["clang", "-arch", "x86_64", "-std=gnu11", "-w",
                 "-I", str(temporary), "-I", str(ROOT / "include"), "-I", str(BUILD_INCLUDE),
                 "-D_GAMEINPUT_", "-D__WINESRC__",
                 f'-DGAMEINPUT_C="{ROOT / "dlls/gameinput/gameinput.c"}"',
                 str(source), "-o", str(executable)],
                check=True,
            )
            subprocess.run([str(executable)], check=True)

    def test_create_returns_a_shared_object(self):
        # REQ-158: stock Wine returns E_NOTIMPL and never writes *out; Witcher 3 then
        # calls through the unwritten pointer. A caller must get S_OK and a usable object.
        self.compile_run(r"""
int main(void)
{
    v0_IGameInput *first = NULL, *second = NULL;
    assert(GameInputCreate(&first) == S_OK);
    assert(first != NULL);
    assert(GameInputCreate(&second) == S_OK);
    assert(second == first);
    assert(v0_IGameInput_Release(second) == 1);
    assert(v0_IGameInput_Release(first) == 0);
    /* After the last release a new object is created, not the freed one. */
    assert(GameInputCreate(&first) == S_OK && first != NULL);
    assert(v0_IGameInput_Release(first) == 0);
    return 0;
}
""")

    def test_interfaces_and_safe_calls(self):
        # REQ-158: QueryInterface and the unimplemented methods must be safe to call.
        self.compile_run(r"""
int main(void)
{
    v0_IGameInput *input = NULL;
    IUnknown *unknown = NULL;
    v1_IGameInput *v1 = NULL;
    v0_IGameInputReading *reading = NULL;
    void *other = (void *)1;
    static const GUID unknown_iid = {0x12345678, 0x1234, 0x1234, {1, 2, 3, 4, 5, 6, 7, 8}};

    assert(GameInputCreate(&input) == S_OK);
    assert(v0_IGameInput_QueryInterface(input, &IID_IUnknown, (void **)&unknown) == S_OK);
    assert(unknown == (IUnknown *)input);
    IUnknown_Release(unknown);
    assert(v0_IGameInput_QueryInterface(input, &IID_v1_IGameInput, (void **)&v1) == S_OK);
    assert(v1 != NULL);
    v1_IGameInput_Release(v1);
    assert(v0_IGameInput_QueryInterface(input, &unknown_iid, &other) == E_NOINTERFACE);
    assert(other == NULL);
    assert(FAILED(v0_IGameInput_GetCurrentReading(input, GameInputKindGamepad, NULL, &reading)));
    assert(reading == NULL);
    assert(v0_IGameInput_Release(input) == 0);
    return 0;
}
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="patched Wine source tree")
    parser.add_argument("--build-include", type=Path, required=True,
                        help="include/ of a configured Wine build (widl-generated headers)")
    args = parser.parse_args()
    ROOT = args.source.resolve()
    BUILD_INCLUDE = args.build_include.resolve()
    unittest.main(argv=[__file__])
