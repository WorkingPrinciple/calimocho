"""Select only observed WinRT mappings backed by exact retained native bytes."""
import re


def select(export, native_files):
    if (export["schema"] != "whiny.observed-winrt-activation.v1"
            or export["registryView"] != "Registry64"
            or export["classCount"] != len(export["classes"])):
        raise ValueError("Require complete observed Registry64 map")
    natives = {}
    for item in native_files:
        key = item["dll_path"].lower()
        if key in natives or not re.fullmatch("[0-9a-f]{64}", item["sha256"]):
            raise ValueError("Duplicate or invalid native DLL identity")
        natives[key] = item
    observed = {}
    for item in export["dllFiles"]:
        key = item["dllPath"].lower()
        if key in observed:
            raise ValueError("Ambiguous exported DLL identity")
        observed[key] = item
    selected, decisions = [], []
    names = set()
    builtins = {"Windows.ApplicationModel.Core.CoreApplication", "Windows.UI.Core.CoreWindow"}
    for row in export["classes"]:
        name = row["className"]
        if name in names:
            raise ValueError("Duplicate observed class")
        names.add(name)
        dll = row["values"]["DllPath"]
        native = natives.get(dll.lower()) if isinstance(dll, str) else None
        actual = observed.get(dll.lower()) if isinstance(dll, str) else None
        reason = "native-dll-absent"
        if native:
            reason = "native-hash-mismatch"
            if actual and actual["exists"] and not actual["error"] and actual["sha256"] == native["sha256"]:
                if row["values"]["Server"] is not None or row["values"]["ActivationType"] not in (None, 0):
                    reason = "unsupported-server-activation"
                elif row["valueKinds"]["DllPath"] not in ("String", "ExpandString"):
                    reason = "unsupported-path-kind"
                else:
                    reason = "exact-native-hash"
                    selected.append(row)
        if name in builtins and reason != "exact-native-hash":
            reason = "preserve-wine-builtin:" + reason
        decisions.append({"class": name, "dll_path": dll, "decision": reason})
    return {"selected": selected, "decisions": decisions, "os_build": export["osBuild"]}


def supported_factories(classes, text):
    if not classes or len(classes) != len(set(classes)):
        raise ValueError("Require unique probe class order")
    rows = {}
    summary = None
    for line in text.splitlines():
        match = re.fullmatch(
            r"xaml-factory index=([0-9]+) factory=([0-9a-f]{8}) present=([01]) qi=([0-9a-f]{8})", line)
        if match:
            index = int(match[1])
            if index >= len(classes) or index in rows:
                raise ValueError("Duplicate or invalid probe index")
            rows[index] = int(match[2], 16) < 0x80000000 and match[3] == "1" and int(match[4], 16) < 0x80000000
            continue
        match = re.fullmatch(r"xaml-factory count=([0-9]+) supported=([0-9]+) result=00000000", line)
        if not match or summary is not None:
            raise ValueError("Unexpected or failed native probe output")
        summary = (int(match[1]), int(match[2]))
    if (set(rows) != set(range(len(classes))) or summary != (len(classes), sum(rows.values()))):
        raise ValueError("Incomplete or inconsistent native factory observation")
    return {name for index, name in enumerate(classes) if rows[index]}


def render_registrations(rows):
    text = "Windows Registry Editor Version 5.00\r\n\r\n"
    for row in rows:
        if (not re.fullmatch(r"Windows\.UI\.Xaml\.[A-Za-z0-9_.]{1,495}", row["className"])
                or row["values"]["DllPath"].lower() != r"c:\windows\system32\windows.ui.xaml.dll"
                or row["values"]["Server"] is not None):
            raise ValueError("Only supported system32 XAML in-process rows may be imported")
        text += ("[HKEY_LOCAL_MACHINE\\Software\\Microsoft\\WindowsRuntime\\ActivatableClassId\\"
                 + row["className"] + "]\r\n")
        for key, value in row["values"].items():
            if value is None:
                continue
            kind = row["valueKinds"][key]
            if key == "DllPath" and kind == "String":
                text += '"DllPath"="' + value.replace("\\", "\\\\") + '"\r\n'
            elif key in ("ActivationType", "Threading", "TrustLevel") and kind == "DWord" and type(value) is int and 0 <= value <= 0xffffffff:
                text += '"' + key + '"=dword:%08x\r\n' % value
            else:
                raise ValueError("Unsupported native registration value")
        text += "\r\n"
    return text.encode("utf-16")
