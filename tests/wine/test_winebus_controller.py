"""Compile real Wine controller selection code without starting Wine or a prefix."""

import argparse
from pathlib import Path
import subprocess
import tempfile
import unittest


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


PRELUDE = r"""
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "wine/list.h"
typedef int BOOL;
typedef uint16_t WORD;
typedef unsigned int UINT;
typedef unsigned int DWORD;
typedef wchar_t WCHAR;
typedef struct { WORD Usage, UsagePage; } USAGE_AND_PAGE;
typedef struct { const WCHAR *Buffer; } UNICODE_STRING;
typedef struct { DWORD TitleIndex, Type, DataLength; unsigned char Data[1]; }
    KEY_VALUE_PARTIAL_INFORMATION;
struct device_options { struct list entry; UINT vid, pid; int hidraw; };
struct bus_options
{
    BOOL disable_sdl, disable_hidraw, disable_input, disable_udevd;
    BOOL split_controllers, map_controllers;
    UINT mappings_count;
    struct list devices;
    char **mappings;
};
static struct bus_options options;
#define TRUE 1
#define FALSE 0
#define MAX_PATH 260
#define WARN(...) ((void)0)
#define FIELD_OFFSET(type, field) offsetof(type, field)
#define ARRAY_SIZE(array) (sizeof(array) / sizeof((array)[0]))
#define HID_USAGE_PAGE_DIGITIZER 13
#define HID_USAGE_PAGE_GENERIC 1
#define HID_USAGE_GENERIC_MOUSE 2
#define HID_USAGE_GENERIC_KEYBOARD 6
#define HID_USAGE_GENERIC_JOYSTICK 4
#define HID_USAGE_GENERIC_GAMEPAD 5
#define KeyValuePartialInformation 2
#define GetProcessHeap() NULL
static int driver_key;
static int NtQueryValueKey(int key, UNICODE_STRING *str, int kind,
                          void *buffer, size_t size, DWORD *out)
{
    (void)key; (void)str; (void)kind; (void)buffer; (void)size; (void)out;
    return -1;
}
static void RtlInitUnicodeString(UNICODE_STRING *str, const WCHAR *value)
{ str->Buffer = value; }
#define wcsnicmp wcsncmp
"""


class ControllerTests(unittest.TestCase):
    def compile_run(self, body):
        with tempfile.TemporaryDirectory(prefix="winebus-controller-") as temporary:
            source = Path(temporary) / "fixture.c"
            executable = Path(temporary) / "fixture"
            source.write_text(body)
            subprocess.run(
                ["clang", "-std=c11", "-Wall", "-Werror", "-Wno-unused-function",
                 "-Wno-unused-variable", "-I", str(ROOT / "include"),
                 str(source), "-o", str(executable)],
                check=True,
            )
            subprocess.run([str(executable)], check=True)

    def test_xbox_ble_identity(self):
        # REQ-108 controller handoff: observed Xbox BLE 045e:0b20 needs XInput identity.
        helpers = "\n".join(function(HEADER, f"static inline BOOL {name}(")
                            for name in ("is_xbox_gamepad",))
        self.compile_run(PRELUDE + helpers + r"""
int main(void)
{
    assert(is_xbox_gamepad(0x045e, 0x0b20));
    assert(is_xbox_gamepad(0x045e, 0x028e));
    assert(is_xbox_gamepad(0x045e, 0x0b13));
    assert(!is_xbox_gamepad(0x054c, 0x0b20));
    assert(!is_xbox_gamepad(0x045e, 0xffff));
    return 0;
}
""")

    def test_backend_fallback_and_dedup(self):
        helpers = "\n".join(function(HEADER, f"static inline BOOL {name}(")
                            for name in ("is_dualshock4_gamepad", "is_dualsense_gamepad"))
        start = MAIN.index("        if (!sdl_driver_init())")
        end = MAIN.index("        iohid_driver_init();", start) + len("        iohid_driver_init();")
        startup = MAIN[start:end]
        self.compile_run(PRELUDE + helpers
                         + function(MAIN, "static BOOL is_hidraw_enabled(") + r"""
static int sdl_status, udev_status, iohid_calls;
static int sdl_driver_init(void) { return options.disable_sdl ? -1 : sdl_status; }
static int udev_driver_init(void) { return udev_status; }
static void iohid_driver_init(void) { ++iohid_calls; }
static void start(void)
{
""" + startup + r"""
}
int main(void)
{
    USAGE_AND_PAGE gamepad = {5, 1}, keyboard = {6, 1}, digitizer = {1, 13};
    struct device_options override = {{0}, 0x045e, 0x0b20, 0};
    unsigned sdl, udev, disabled;
    for (sdl = 0; sdl < 2; ++sdl)
    for (udev = 0; udev < 2; ++udev)
    for (disabled = 0; disabled < 2; ++disabled)
    {
        memset(&options, 0, sizeof(options));
        list_init(&options.devices);
        options.disable_sdl = disabled;
        sdl_status = sdl ? -1 : 0;
        udev_status = udev ? -1 : 0;
        start();
        /* Only absent SDL and absent UDEV permit generic raw gamepads.
         * Repeated evaluation also covers the selection used by later hotplug events. */
        for (unsigned event = 0; event < 2; ++event)
            assert(!!is_hidraw_enabled(0x045e, 0x0b20, &gamepad, 16)
                   == ((sdl || disabled) && udev));
        assert(is_hidraw_enabled(0x054c, 0x05c4, &gamepad, 16));
        assert(!is_hidraw_enabled(0x045e, 0x0b20, &keyboard, 16));
        assert(!is_hidraw_enabled(0x045e, 0x0b20, &digitizer, 16));
        /* Explicit per-device and global disable still override fallback. */
        list_add_head(&options.devices, &override.entry);
        assert(!is_hidraw_enabled(0x045e, 0x0b20, &gamepad, 16));
        override.hidraw = 1;
        assert(is_hidraw_enabled(0x045e, 0x0b20, &gamepad, 16));
        options.disable_hidraw = 1;
        assert(!is_hidraw_enabled(0x045e, 0x0b20, &gamepad, 16));
        list_remove(&override.entry);
        override.hidraw = 0;
    }
    assert(iohid_calls == 8);
    return 0;
}
""")

    def test_cleanup_after_sdl_failure(self):
        self.compile_run(PRELUDE + r"""
static unsigned frees;
static void RtlFreeHeap(void *heap, int flags, void *ptr)
{ (void)heap; (void)flags; if (ptr) { ++frees; free(ptr); } }
""" + function(MAIN, "static void sdl_bus_free_mappings(")
                         + function(MAIN, "static void bus_options_cleanup(") + r"""
int main(void)
{
    list_init(&options.devices);
    options.disable_sdl = 1; /* Mapping load preceded failed SDL startup. */
    options.mappings_count = 1;
    options.mappings = malloc(sizeof(char *));
    options.mappings[0] = malloc(1);
    bus_options_cleanup();
    assert(frees == 2);
    assert(!options.mappings && !options.mappings_count);
    bus_options_cleanup();
    assert(frees == 2);
    return 0;
}
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--main-source", type=Path, help="Compare against a preserved main.c baseline")
    args = parser.parse_args()
    ROOT = args.source.resolve()
    MAIN = (args.main_source or ROOT / "dlls/winebus.sys/main.c").read_text()
    HEADER = (ROOT / "dlls/winebus.sys/unixlib.h").read_text()
    unittest.main(argv=[__file__])
