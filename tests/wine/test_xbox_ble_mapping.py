"""Verify real IOHID descriptor translation using the owner's observed Xbox descriptor."""

from pathlib import Path
import argparse
import subprocess
import tempfile
import unittest

OBSERVED = bytes.fromhex("""
05 01 09 05 a1 01 85 01 09 01 a1 00 09 30 09 31 15 00 27 ff ff 00 00
95 02 75 10 81 02 c0 09 01 a1 00 09 32 09 35 15 00 27 ff ff 00 00 95
02 75 10 81 02 c0 05 02 09 c5 15 00 26 ff 03 95 01 75 0a 81 02 15 00
25 00 75 06 95 01 81 03 05 02 09 c4 15 00 26 ff 03 95 01 75 0a 81 02
15 00 25 00 75 06 95 01 81 03 05 01 09 39 15 01 25 08 35 00 46 3b 01
66 14 00 75 04 95 01 81 42 75 04 95 01 15 00 25 00 35 00 45 00 65 00
81 03 05 09 19 01 29 0f 15 00 25 01 75 01 95 0f 81 02 15 00 25 00
75 01 95 01 81 03 05 0c 0a b2 00 15 00 25 01 95 01 75 01 81 02 15
00 25 00 75 07 95 01 81 03 05 0f 09 21 85 03 a1 02 09 97 15 00 25
01 75 04 95 01 91 02 15 00 25 00 75 04 95 01 91 03 09 70 15 00 25
64 75 08 95 04 91 02 09 50 66 01 10 55 0e 15 00 26 ff 00 75 08 95
01 91 02 09 a7 15 00 26 ff 00 75 08 95 01 91 02 65 00 55 00 09 7c
15 00 26 ff 00 75 08 95 01 91 02 c0 c0
""")


def function(source, signature):
    start = source.index(signature)
    pos = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[pos] == "{") - (source[pos] == "}")
        pos += 1
    return source[start:pos]


def fields(descriptor):
    """Decode short HID items into bit-offset fields (excluding the report-ID byte)."""
    page = report_id = width = count = 0
    usages = []
    usage_min = None
    offsets = {}
    result = {}
    i = 0
    while i < len(descriptor):
        prefix = descriptor[i]
        size = (0, 1, 2, 4)[prefix & 3]
        value = int.from_bytes(descriptor[i + 1:i + 1 + size], "little")
        i += 1 + size
        tag = prefix & 0xfc
        if tag == 0x04:
            page = value
        elif tag == 0x84:
            report_id = value
        elif tag == 0x74:
            width = value
        elif tag == 0x94:
            count = value
        elif tag == 0x08:
            usages.append(value)
        elif tag == 0x18:
            usage_min = value
        elif tag == 0x28:
            usages = list(range(usage_min, value + 1))
        elif tag in (0x80, 0x90):
            key = (tag, report_id)
            offset = offsets.get(key, 0)
            if not value & 1:
                assert usages, (page, count)
                for index in range(count):
                    usage = usages[min(index, len(usages) - 1)]
                    result[(tag, report_id, page, usage)] = (offset + index * width, width)
            offsets[key] = offset + count * width
        if prefix & 0x0c == 0:
            usages = []
            usage_min = None
    return result, offsets


class MappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SOURCE.read_text()
        helper = ""
        if "static NTSTATUS xbox_ble_get_report_descriptor(" in source:
            helper = function(source, "static NTSTATUS xbox_ble_get_report_descriptor(")
        method = function(source, "static NTSTATUS iohid_device_get_report_descriptor(")
        observed = ",".join(str(byte) for byte in OBSERVED)
        fixture = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef unsigned char BYTE;
typedef unsigned int UINT;
typedef int NTSTATUS;
typedef int BOOL;
typedef const BYTE *CFDataRef;
typedef unsigned char UInt8;
struct unix_device { int unused; };
struct iohid_device { struct unix_device unix_device; void *device; BOOL xbox_ble, xbox_ble_mapped; };
static struct iohid_device impl;
#define STATUS_SUCCESS 0
#define STATUS_BUFFER_TOO_SMALL 1
#define FALSE 0
#define TRUE 1
#define WARN(...) ((void)0)
#define CFSTR(x) x
#define kIOHIDReportDescriptorKey "descriptor"
typedef int IOReturn;
typedef int IOHIDReportType;
typedef unsigned int uint32_t;
typedef long CFIndex;
static int event_queue, report_count;
static BYTE queued[32];
static void bus_event_queue_input_report(void *queue, struct unix_device *iface, BYTE *report, CFIndex size)
{
    (void)queue; (void)iface;
    assert(size <= sizeof(queued));
    memcpy(queued, report, size);
    ++report_count;
}
static const BYTE observed[] = {OBSERVED};
static UINT observed_size = sizeof(observed);
static const BYTE *observed_data = observed;
static struct iohid_device *impl_from_unix_device(struct unix_device *iface)
{ (void)iface; return &impl; }
static CFDataRef IOHIDDeviceGetProperty(void *device, const char *key)
{ (void)device; (void)key; return observed_data; }
static int CFDataGetLength(CFDataRef data) { (void)data; return observed_size; }
static const BYTE *CFDataGetBytePtr(CFDataRef data) { return data; }
""".replace("OBSERVED", observed)
        callback = function(source, "static void handle_IOHIDDeviceIOHIDReportCallback(")
        fixture += helper + method + callback + r"""
int main(int argc, char **argv)
{
    BYTE buffer[2048], saved[2048], unknown[sizeof(observed)];
    UINT size = 0, saved_size = 0;
    (void)argv;
    impl.xbox_ble = argc != 2;
    assert(iohid_device_get_report_descriptor(&impl.unix_device, NULL, 0, &size)
           == STATUS_BUFFER_TOO_SMALL);
    assert(size < sizeof(buffer));
    memset(buffer, 0xa5, sizeof(buffer));
    assert(iohid_device_get_report_descriptor(&impl.unix_device, buffer, size - 1, &saved_size)
           == STATUS_BUFFER_TOO_SMALL);
    assert(buffer[0] == 0xa5 && saved_size == size);
    assert(iohid_device_get_report_descriptor(&impl.unix_device, buffer, sizeof(buffer), &size)
           == STATUS_SUCCESS);
    memcpy(saved, buffer, size);
    saved_size = size;
    assert(iohid_device_get_report_descriptor(&impl.unix_device, buffer, sizeof(buffer), &size)
           == STATUS_SUCCESS);
    assert(size == saved_size && !memcmp(saved, buffer, size));
    assert(fwrite(buffer, 1, size, stdout) == size);
    if (argc > 2)
    {
        BYTE report[17] = {1, 0,128, 0,0, 0,128, 255,255, 0,0, 0,0, 0,0,0,0};
        BYTE unchanged[17];
        memcpy(unchanged, report, sizeof(report));
        handle_IOHIDDeviceIOHIDReportCallback(&impl.unix_device, 0, NULL, 0, 1, report, sizeof(report));
        assert(report_count == 1);
        assert(!memcmp(report, unchanged, sizeof(report)));
        assert(queued[3] == 255 && queued[4] == 255);
        assert(queued[7] == 0 && queued[8] == 0);
        assert(!memcmp(queued + 9, report + 9, 8));
        report[3] = report[7] = 0;
        report[4] = report[8] = 128;
        handle_IOHIDDeviceIOHIDReportCallback(&impl.unix_device, 0, NULL, 0, 1, report, sizeof(report));
        assert(queued[3] == 255 && queued[4] == 127);
        assert(queued[7] == 255 && queued[8] == 127);
        report[16] = 1; /* Older firmware emits View as Consumer AC Back. */
        handle_IOHIDDeviceIOHIDReportCallback(&impl.unix_device, 0, NULL, 0, 1, report, sizeof(report));
        assert(queued[15] == 4 && queued[16] == 1);
        assert(report[15] == 0);
        handle_IOHIDDeviceIOHIDReportCallback(&impl.unix_device, 0, NULL, 0, 1, report, 16);
        assert(report_count == 3);
        impl.xbox_ble_mapped = 0;
        handle_IOHIDDeviceIOHIDReportCallback(&impl.unix_device, 0, NULL, 0, 1, report, sizeof(report));
        assert(report_count == 4 && !memcmp(queued, report, sizeof(report)));
    }
    /* A different firmware layout must not be rewritten with guessed offsets. */
    memcpy(unknown, observed, sizeof(unknown));
    unknown[6] = 0x86;
    observed_data = unknown;
    assert(iohid_device_get_report_descriptor(&impl.unix_device, buffer, sizeof(buffer), &size)
           == STATUS_SUCCESS);
    assert(size == sizeof(unknown) && !memcmp(buffer, unknown, size));
    observed_size = 4;
    assert(iohid_device_get_report_descriptor(&impl.unix_device, buffer, sizeof(buffer), &size)
           == STATUS_SUCCESS);
    assert(size == 4 && !memcmp(buffer, unknown, size));
    return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="xbox-ble-mapping-") as directory:
            cfile = Path(directory) / "fixture.c"
            executable = Path(directory) / "fixture"
            cfile.write_text(fixture)
            subprocess.run(["clang", "-std=c11", "-Wall", "-Werror", str(cfile),
                            "-o", str(executable)], check=True)
            cls.mapped = subprocess.check_output([str(executable)])
            cls.other = subprocess.check_output([str(executable), "other"])
            cls.directions = subprocess.check_output([str(executable), "directions", "check"])

    def test_axes_and_triggers_keep_physical_offsets(self):
        # REQ-108 correction: right-stick movement must not become acceleration.
        mapping, sizes = fields(self.mapped)
        for usage, offset, width in [(0x30, 0, 16), (0x31, 16, 16),
                                    (0x33, 32, 16), (0x34, 48, 16),
                                    (0x32, 64, 10), (0x35, 80, 10), (0x39, 96, 4)]:
            self.assertEqual(mapping.get((0x80, 1, 1, usage)), (offset, width), hex(usage))
        self.assertEqual(sizes[(0x80, 1)], 128)

    def test_face_menu_shoulders_stick_clicks(self):
        mapping, _ = fields(self.mapped)
        for usage, bit in enumerate([104, 105, 107, 108, 110, 111, 114, 115, 117, 118], 1):
            self.assertEqual(mapping.get((0x80, 1, 9, usage)), (bit, 1), usage)
        self.assertEqual(mapping.get((0x80, 1, 0xff00, 1)), (116, 1))

    def test_unrelated_controllers_and_output_unchanged(self):
        self.assertEqual(self.other, OBSERVED)
        tail = bytes.fromhex("05 0f 09 21 85 03")
        self.assertEqual(self.mapped[self.mapped.index(tail):], OBSERVED[OBSERVED.index(tail):])
        original_fields, original_sizes = fields(OBSERVED)
        mapped_fields, mapped_sizes = fields(self.mapped)
        self.assertEqual(original_sizes, mapped_sizes)
        self.assertEqual({k: v for k, v in original_fields.items() if k[0] == 0x90},
                         {k: v for k, v in mapped_fields.items() if k[0] == 0x90})

    def test_directions_and_report_guards(self):
        self.assertEqual(self.directions, self.mapped)

    def test_stick_trigger_and_button_isolation(self):
        mapping, _ = fields(self.mapped)

        def value(report, page, usage):
            offset, width = mapping[(0x80, 1, page, usage)]
            return (int.from_bytes(report[1:], "little") >> offset) & ((1 << width) - 1)

        neutral = bytearray(bytes.fromhex("01 00 80 00 80 00 80 00 80 00 00 00 00 00 00 00 00"))
        right_left = neutral.copy()
        right_left[5:7] = bytes(2)
        self.assertEqual(value(right_left, 1, 0x33), 0)
        self.assertEqual(value(right_left, 1, 0x32), 0)
        self.assertEqual(value(right_left, 1, 0x35), 0)
        rt = neutral.copy()
        rt[11:13] = bytes.fromhex("ff 03")
        self.assertEqual(value(rt, 1, 0x35), 1023)
        self.assertEqual(value(rt, 1, 0x33), 32768)
        self.assertEqual(value(rt, 1, 0x32), 0)
        self.assertFalse(any(value(rt, 9, button) for button in range(1, 11)))
        for button, bit in enumerate([104, 105, 107, 108, 110, 111, 114, 115, 117, 118], 1):
            pressed = neutral.copy()
            pressed[1 + bit // 8] |= 1 << (bit % 8)
            self.assertEqual([value(pressed, 9, other) for other in range(1, 11)],
                             [int(other == button) for other in range(1, 11)])
            self.assertEqual(value(pressed, 1, 0x35), 0)
        for hat in range(9):
            report = neutral.copy()
            report[13] = hat
            self.assertEqual(value(report, 1, 0x39), hat)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    SOURCE = args.source
    unittest.main(argv=[__file__])
