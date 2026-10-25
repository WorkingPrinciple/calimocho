"""Host check: installed ntdll.dll exports resolve to syscall thunks, not stubs.

Parses the PE export table without third-party modules, then requires each
named export's code to start with the x86_64 Wine syscall thunk
`mov eax, <id>` where <id> is the entry from ALL_SYSCALLS in ntsyscalls.h.
"""
import argparse
import json
import re
import struct
import sys
from pathlib import Path

DEFAULT = ("NtAlpcConnectPort", "NtAlpcConnectPortEx", "NtAlpcSendWaitReceivePort",
           "NtAlpcAcceptConnectPort", "NtAlpcCreatePort", "NtAlpcImpersonateClientOfPort",
           "NtCreateToken")


def syscall_ids(header_text):
    block = header_text[header_text.index("#define ALL_SYSCALLS \\"):]
    return {name: int(number, 16) for number, name in
            re.findall(r"SYSCALL_ENTRY\( (0x[0-9a-f]+), (\w+), \d+ \)", block)}


def exports(image):
    if image[:2] != b"MZ":
        raise ValueError("not a PE image")
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    if image[pe:pe + 4] != b"PE\0\0":
        raise ValueError("missing PE signature")
    sections_count = struct.unpack_from("<H", image, pe + 6)[0]
    optional_size = struct.unpack_from("<H", image, pe + 20)[0]
    optional = pe + 24
    if struct.unpack_from("<H", image, optional)[0] != 0x20B:
        raise ValueError("not PE32+")
    export_rva = struct.unpack_from("<I", image, optional + 112)[0]
    sections = []
    for index in range(sections_count):
        base = optional + optional_size + index * 40
        size, rva, raw_size, raw = struct.unpack_from("<IIII", image, base + 8)
        sections.append((rva, max(size, raw_size), raw))

    def offset(rva):
        for start, size, raw in sections:
            if start <= rva < start + size:
                return raw + rva - start
        raise ValueError("RVA %#x outside sections" % rva)

    directory = offset(export_rva)
    ordinal_base, functions, names, functions_rva, names_rva, ordinals_rva = struct.unpack_from(
        "<IIIIII", image, directory + 16)
    result = {}
    for index in range(names):
        name_rva = struct.unpack_from("<I", image, offset(names_rva) + 4 * index)[0]
        end = image.index(b"\0", offset(name_rva))
        name = image[offset(name_rva):end].decode()
        ordinal = struct.unpack_from("<H", image, offset(ordinals_rva) + 2 * index)[0]
        rva = struct.unpack_from("<I", image, offset(functions_rva) + 4 * ordinal)[0]
        result[name] = (rva, offset(rva))
    return result


def check(dll, header, names=DEFAULT):
    image = Path(dll).read_bytes()
    ids = syscall_ids(Path(header).read_text())
    table = exports(image)
    results = {}
    for name in names:
        if name not in ids:
            raise ValueError("%s is not in ALL_SYSCALLS" % name)
        if name not in table:
            raise ValueError("%s is not exported" % name)
        rva, file_offset = table[name]
        code = image[file_offset:file_offset + 16]
        expected = b"\xb8" + struct.pack("<I", ids[name])
        if expected not in code[:8]:
            raise ValueError("%s at RVA %#x is not the syscall %#x thunk: %s"
                             % (name, rva, ids[name], code.hex()))
        results[name] = {"rva": "%#x" % rva, "syscall": "%#x" % ids[name], "prefix": code[:8].hex()}
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="package build root with source/ and install/")
    args = parser.parse_args(argv)
    try:
        result = check(args.root / "install/lib/wine/x86_64-windows/ntdll.dll",
                       args.root / "source/dlls/ntdll/ntsyscalls.h")
    except ValueError as error:
        print("ntdll syscall export check failed: %s" % error, file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
