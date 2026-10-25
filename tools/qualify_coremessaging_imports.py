"""Read public AMD64 PE metadata and qualify native CoreMessaging's import closure."""
from pathlib import Path
import re
import struct

from tools.probe_wine_source import sha256


class PE:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if self.data[:2] != b"MZ":
            raise ValueError("Missing DOS signature: " + str(path))
        pe = self.u32(60)
        if self.data[pe:pe + 4] != b"PE\0\0" or self.u16(pe + 4) != 0x8664:
            raise ValueError("Require AMD64 PE: " + str(path))
        optional = pe + 24
        if self.u16(optional) != 0x20b:
            raise ValueError("Require PE32+")
        count = self.u16(pe + 6)
        section_offset = optional + self.u16(pe + 20)
        self.sections = [struct.unpack_from("<IIII", self.data, section_offset + index * 40 + 8)
                         for index in range(count)]
        self.directories = [struct.unpack_from("<II", self.data, optional + 112 + index * 8)
                            for index in range(min(self.u32(optional + 108), 16))]

    def u16(self, offset):
        return struct.unpack_from("<H", self.data, offset)[0]

    def u32(self, offset):
        return struct.unpack_from("<I", self.data, offset)[0]

    def raw(self, rva):
        for virtual, start, size, offset in self.sections:
            if start <= rva < start + size:
                result = offset + rva - start
                if result < len(self.data):
                    return result
        raise ValueError("Unmapped PE RVA: " + hex(rva))

    def string(self, rva):
        start = self.raw(rva)
        end = self.data.find(b"\0", start, start + 512)
        if end < 0:
            raise ValueError("Unterminated public PE identifier")
        value = self.data[start:end].decode("ascii")
        if not value or any(ord(char) < 33 or ord(char) > 126 for char in value):
            raise ValueError("Invalid public PE identifier")
        return value

    def exports(self):
        rva, size = self.directories[0]
        if not rva:
            return {}
        table = self.raw(rva)
        base, count, names, functions_rva, names_rva, ordinals_rva = struct.unpack_from(
            "<IIIIII", self.data, table + 16)
        result = {}
        for index in range(count):
            address = self.u32(self.raw(functions_rva) + index * 4)
            if address:
                result[base + index] = self.string(address) if rva <= address < rva + size else address
        for index in range(names):
            name = self.string(self.u32(self.raw(names_rva) + index * 4))
            ordinal = base + self.u16(self.raw(ordinals_rva) + index * 2)
            if ordinal not in result:
                raise ValueError("Named PE export points to absent function")
            result[name] = result[ordinal]
        return result

    def imports(self, delayed=False):
        index = 13 if delayed else 1
        if index >= len(self.directories) or not self.directories[index][0]:
            return []
        rva, size = self.directories[index]
        offset = self.raw(rva)
        width = 32 if delayed else 20
        result = []
        for position in range(0, size, width):
            row = struct.unpack_from("<" + "I" * (width // 4), self.data, offset + position)
            if not any(row):
                return result
            if delayed:
                if row[0] != 1:
                    raise ValueError("Require RVA-based PE delay descriptors")
                name, thunk = row[1], row[4]
            else:
                name, thunk = row[3], row[0] or row[4]
            imports = []
            start = self.raw(thunk)
            for slot in range(len(self.data) // 8):
                value = struct.unpack_from("<Q", self.data, start + slot * 8)[0]
                if not value:
                    break
                imports.append(value & 0xffff if value & (1 << 63) else self.string(value + 2))
            else:
                raise ValueError("Unterminated PE import table")
            result.append((self.string(name), imports))
        raise ValueError("Unterminated PE descriptor table")


def qualify(native, install, source):
    native, install, source = Path(native), Path(install), Path(source)
    schema = source / "dlls/apisetschema/apisetschema.spec"
    mappings = {name.rsplit("-", 1)[0].lower(): target.lower()
                for name, target in re.findall(r"^apiset\s+(\S+)\s*=\s*(\S+)", schema.read_text(), re.M)}
    modules, identities = {}, {}

    def resolve(module, symbol, chain=()):
        module = module.lower()
        if not module.endswith(".dll"):
            module += ".dll"
        if not re.fullmatch(r"[a-z0-9_.-]+\.dll", module):
            raise ValueError("Invalid import DLL identifier")
        module = mappings.get(module[:-4].rsplit("-", 1)[0], module)
        key = (module, symbol)
        if key in chain or len(chain) >= 16:
            raise ValueError("Cyclic or excessive PE forwarder chain")
        if module not in modules:
            path = install / "lib/wine/x86_64-windows" / module
            modules[module] = PE(path).exports()
            identities[module] = sha256(path)
        if symbol not in modules[module]:
            raise ValueError("Missing mandatory export: " + module + "!" + str(symbol))
        target = modules[module][symbol]
        if isinstance(target, str):
            host, separator, name = target.rpartition(".")
            if not separator:
                raise ValueError("Malformed PE forwarder")
            return [module + "!" + str(symbol)] + resolve(
                host, int(name[1:]) if name.startswith("#") else name, chain + (key,))
        return [module + "!" + str(symbol)]

    pe = PE(native)
    resolved = []
    for module, symbols in pe.imports():
        for symbol in symbols:
            resolved.append({"module": module, "symbol": symbol, "resolution": resolve(module, symbol)})
    delayed = [{"module": module, "symbols": symbols} for module, symbols in pe.imports(delayed=True)]
    return {"native_sha256": sha256(native), "schema_sha256": sha256(schema),
            "mandatory_import_count": len(resolved), "mandatory_imports": resolved,
            "resolved_module_sha256": identities, "delayed_imports_unqualified": delayed,
            "core_ui_create_rva": pe.exports().get("CoreUICreate"),
            "scope": "Static public import/forwarder resolution only, not implementation or runtime acceptance"}


def qualify_ordinal_guards(install):
    path = Path(install) / "lib/wine/x86_64-windows/combase.dll"
    pe = PE(path)
    exports = pe.exports()
    guards = []
    targets = set()
    for ordinal in (86, 87, 88):
        rva = exports[ordinal]
        if not isinstance(rva, int) or any(
                isinstance(name, str) and value == rva for name, value in exports.items()):
            raise ValueError("Combase ordinal guard aliases a named API")
        offset = pe.raw(rva)
        code = pe.data[offset:offset + 22]
        if (code[:7] != bytes.fromhex("4883ec28488d0d")
                or code[11:14] != bytes.fromhex("488d15") or code[18] != 0xe8):
            raise ValueError("Combase ordinal is not the generated x64 Wine stub")
        module = pe.string(rva + 11 + struct.unpack_from("<i", code, 7)[0])
        identifier = pe.string(rva + 18 + struct.unpack_from("<i", code, 14)[0])
        if module.lower() != "combase.dll" or identifier != (
                "__wine_unsupported_coremessaging_ordinal_" + str(ordinal)):
            raise ValueError("Combase stub identifiers changed")
        targets.add(rva + 23 + struct.unpack("<i", pe.data[offset + 19:offset + 23])[0])
        guards.append({"ordinal": ordinal, "rva": rva, "diagnostic_identifier": identifier})
    if len(targets) != 1:
        raise ValueError("Combase guards do not call the same generated stub handler")
    return {"sha256": sha256(path), "guards": guards,
            "scope": "Static x64 Wine-generated unimplemented stubs; no native ABI or runtime success"}
