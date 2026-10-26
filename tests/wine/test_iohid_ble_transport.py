"""Verify winebus IOHID transport classification against the strings macOS reports.

macOS reports kIOHIDTransportKey as "Bluetooth Low Energy" (spaced) for the
Xbox One S controller over BLE, while the SDK constant is "BluetoothLowEnergy".
Without patch 0016 bus_type stays 0 and the patch 0015 remap never applies.
"""

from pathlib import Path
import argparse
import subprocess
import tempfile
import unittest

MARKER = "if ((str = IOHIDDeviceGetProperty(IOHIDDevice, CFSTR(kIOHIDTransportKey))))"


def block(source):
    start = source.index(MARKER)
    pos = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[pos] == "{") - (source[pos] == "}")
        pos += 1
    return source[start:pos]


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = r"""
#include <stdio.h>
#include <string.h>
#define CFSTR(x) x
#define kIOHIDTransportKey "Transport"
#define kIOHIDTransportBluetoothValue "Bluetooth"
#define kIOHIDTransportBluetoothLowEnergyValue "BluetoothLowEnergy"
#define kIOHIDTransportUSBValue "USB"
enum { BUS_TYPE_UNKNOWN, BUS_TYPE_USB, BUS_TYPE_BLUETOOTH };
typedef const char *CFStringRef;
static const char *transport;
static CFStringRef IOHIDDeviceGetProperty(void *device, const char *key)
{ (void)device; (void)key; return transport; }
static int CFStringCompare(CFStringRef a, CFStringRef b, int flags)
{ (void)flags; return strcmp(a, b); }
int main(int argc, char **argv)
{
    struct { int bus_type; } desc = { BUS_TYPE_UNKNOWN };
    void *IOHIDDevice = NULL;
    CFStringRef str;
    transport = argc > 1 ? argv[1] : NULL;
BLOCK
    printf("%d", desc.bus_type);
    return 0;
}
""".replace("BLOCK", block(SOURCE.read_text()))
        with tempfile.TemporaryDirectory(prefix="iohid-transport-") as directory:
            cfile = Path(directory) / "fixture.c"
            cls.executable = Path(directory) / "fixture"
            cfile.write_text(fixture)
            subprocess.run(["clang", "-std=c11", "-Wall", "-Werror", str(cfile),
                            "-o", str(cls.executable)], check=True)
            cls.results = {t: int(subprocess.check_output([str(cls.executable), t]))
                           for t in ["Bluetooth", "BluetoothLowEnergy",
                                     "Bluetooth Low Energy", "USB", "SPI", "Bluetooth Low"]}

    def test_spaced_ble_string_is_bluetooth(self):
        # Observed on macOS for 045e:0b20 (ioreg Transport = "Bluetooth Low Energy").
        self.assertEqual(self.results["Bluetooth Low Energy"], 2)

    def test_sdk_constants_unchanged(self):
        self.assertEqual(self.results["Bluetooth"], 2)
        self.assertEqual(self.results["BluetoothLowEnergy"], 2)
        self.assertEqual(self.results["USB"], 1)

    def test_other_transports_stay_unknown(self):
        self.assertEqual(self.results["SPI"], 0)
        self.assertEqual(self.results["Bluetooth Low"], 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    SOURCE = args.source
    unittest.main(argv=[__file__])
