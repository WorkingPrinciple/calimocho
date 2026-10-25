"""Generate exact typed diagnostic vtables and redacted relay/wait hooks in owned Wine source."""
from pathlib import Path
import re
import shutil

from tools.build_launcher_overlay import REPO
from tools.port_uwp_activation import replace
from tools.probe_wine_source import sha256

BASE = REPO / "build/winehq-11.20/package-uwp-state-01"
FILES = REPO / "patches/wine/files"


def slots(header, interface):
    text = Path(header).read_text()
    alias = re.search(r"#define " + interface + r"Vtbl (\w+)", text)
    full = alias[1] if alias else interface + "Vtbl"
    match = re.search(r"typedef struct " + full + r"\s*\{(.*?)\}\s*" + full + r";", text, re.S)
    if not match:
        raise ValueError("Missing exact vtable " + interface)
    methods = re.findall(r"(HRESULT|ULONG)\s+\(STDMETHODCALLTYPE \*(\w+)\)\((.*?)\);", match[1], re.S)
    if len(methods) < 6 or len(methods) != match[1].count("STDMETHODCALLTYPE"):
        raise ValueError("Unsupported method signature " + interface)
    return [(kind, name, " ".join(args.split())) for kind, name, args in methods]


def wrappers(header, interface, table, label):
    methods = slots(header, interface)
    result = []
    for kind, name, arguments in methods:
        names = [re.search(r"(\w+)$", part.strip())[1] for part in arguments.split(",")]
        iid = names[1] if name == "QueryInterface" else "NULL"
        wrapper = "diagnostic_" + table + "_" + name
        result.append("static " + kind + " WINAPI " + wrapper + "(" + arguments + ")\n{\n"
                      "    " + kind + " result;\n")
        if label == "CoreApplication" and name == "Run":
            result.append("    __wine_pkg_diagnostic_phase(1, NULL);\n")
        result.append('    diagnostic_interface("' + label + '", "' + name + '", "enter", ' + iid + ', 0, "' + kind + '");\n')
        result.append("    result = implementation_" + table + "." + name + "(" + ", ".join(names) + ");\n")
        result.append('    diagnostic_interface("' + label + '", "' + name + '", "exit", ' + iid + ', result, "' + kind + '");\n')
        if label == "CoreApplication" and name == "Run":
            result.append("    __wine_pkg_diagnostic_phase(4, NULL);\n")
        result.append("    return result;\n}\n")
    result.append("static const " + interface + "Vtbl " + table + " = {\n    "
                  + ", ".join("diagnostic_" + table + "_" + name for _, name, _ in methods) + "\n};\n")
    return "".join(result), [name for _, name, _ in methods]


def instrument(source, relative, definitions, inputs, coverage):
    path = source / relative
    text = path.read_text()
    text = text.replace("static struct core core;", '#include "package_call_diagnostics.h"\nstatic struct core core;', 1) if "struct core" in text else text.replace(
        "#define DISPATCH_MESSAGE", '#include "package_call_diagnostics.h"\n#define DISPATCH_MESSAGE', 1)
    for interface, table, header, label in definitions:
        generated, names = wrappers(header, interface, table, label)
        inputs[str(header)] = sha256(header)
        pattern = r"static const " + interface + "Vtbl " + table + r" = \{.*?\n\};"
        matches = list(re.finditer(pattern, text, re.S))
        if len(matches) != 1:
            raise ValueError("Unexpected implementation vtable " + table)
        match = matches[0]
        implementation = match[0].replace("Vtbl " + table, "Vtbl implementation_" + table, 1)
        text = text[:match.start()] + implementation + "\n" + generated + text[match.end():]
        coverage[label] = names
    if "CoreApplication" in coverage and relative.endswith("core_application.c"):
        old = "        hr = IFrameworkView_Initialize(view, &core.ICoreApplicationView_iface);"
        if text.count(old) != 1:
            raise ValueError("Missing Initialize seam")
        text = text.replace(old, '        __wine_pkg_diagnostic_phase(2, GetModuleHandleW(L"windows.ui.xaml.dll"));\n'
                            + old + "\n        __wine_pkg_diagnostic_phase(3, NULL);", 1)
    path.write_text(text)
    shutil.copy2(FILES / "package_call_diagnostics.h", path.parent / "package_call_diagnostics.h")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned build source")
    inputs, coverage = {}, {}
    # These three files have no UWP overlay changes before this diagnostic port.
    # Rebase them explicitly on resume instead of applying an instrumentation twice.
    for relative in ("dlls/ntdll/relay.c", "dlls/ntdll/ntdll.spec", "dlls/ntdll/unix/sync.c", "dlls/ntdll/loader.c"):
        shutil.copy2(BASE / "source" / relative, source / relative)
    include = BASE / "build/include"
    instrument(source, "dlls/twinapi.appcore/core_application.c", (
        ("IActivationFactory", "core_vtable", include / "activation.h", "CoreFactory"),
        ("ICoreApplication", "application_vtable", include / "windows.applicationmodel.core.h", "CoreApplication"),
        ("ICoreApplicationView", "view_vtable", include / "windows.applicationmodel.core.h", "CoreApplicationView"),
        ("IStaticLifetime", "lifetime_vtable", BASE / "build/dlls/twinapi.appcore/package_activation.h", "StaticLifetime"),
        ("IMap_HSTRING_IInspectable", "collection_vtable", include / "windows.foundation.h", "StaticCollection"),
    ), inputs, coverage)
    instrument(source, "dlls/windows.ui/corewindow_host.c", (
        ("ICoreWindow", "window_vtable", include / "windows.ui.core.h", "CoreWindow"),
        ("ICoreDispatcher", "dispatcher_vtable", include / "windows.ui.core.h", "CoreDispatcher"),
    ), inputs, coverage)
    makefile = source / "dlls/windows.ui/Makefile.in"
    text = makefile.read_text()
    match = re.search(r"^IMPORTS\s*=.*$", text, re.M)
    if not match:
        raise ValueError("Missing windows.ui imports")
    if "ntdll" not in match[0].split():
        makefile.write_text(text[:match.end()] + " ntdll" + text[match.end():])
    shutil.copy2(FILES / "package_relay_diagnostics.h", source / "dlls/ntdll/package_relay_diagnostics.h")
    relay = source / "dlls/ntdll/relay.c"
    text = relay.read_text()
    marker = "static const WCHAR **debug_relay_excludelist;"
    if text.count(marker) != 1:
        raise ValueError("Missing relay private-data seam")
    text = text.replace(marker, '#include "package_relay_diagnostics.h"\n\n' + marker, 1)
    start = text.index("#elif defined(__x86_64__)")
    end = text.index("\nextern INT_PTR WINAPI relay_call", start)
    block = text[start:end]
    entry = block.index('    TRACE( "\\1Call %s(",')
    tail = block.index("\n    return entry_point->orig_func;", entry)
    block = block[:entry] + (
        "    for (i = 0; !is_ret_val(arg_types[i]); ++i) {}\n"
        "    *nb_args = i;\n"
        "    diagnostic_relay(data, ordinal, stack[-1]);") + block[tail:]
    exit_start = block.index("    TRACE(", block.index("void WINAPI relay_trace_exit"))
    exit_end = block.index("\n}", exit_start)
    block = block[:exit_start] + "    /* No raw results, strings or absolute return addresses. */" + block[exit_end:]
    relay.write_text(text[:start] + block + text[end:])
    replace(source, "dlls/ntdll/relay.c", "static const char *func_name( struct relay_private_data *data, unsigned int ordinal )",
            "#ifndef __x86_64__\nstatic const char *func_name( struct relay_private_data *data, unsigned int ordinal )")
    replace(source, "dlls/ntdll/relay.c", "    else TRACE( \"%08Ix\", ptr );\n}\n\n#ifdef __i386__",
            "    else TRACE( \"%08Ix\", ptr );\n}\n#endif\n\n#ifdef __i386__")
    replace(source, "dlls/ntdll/relay.c",
            "        if (!descr->entry_point_offsets[i]) continue;   /* not a normal function */",
            "        if (!descr->entry_point_offsets[i]) continue;   /* not a normal function */\n"
            "        if (TRACE_ON(pkgrelay) && !diagnostic_selected(data->dllname, data->entry_points[i].name)) continue;")
    replace(source, "dlls/ntdll/relay.c",
            "    if (!data->entry_points[ordinal].orig_func) return proc;  /* not a relayed function */",
            "    if (!data->entry_points[ordinal].orig_func) return proc;  /* not a relayed function */\n"
            '    if (TRACE_ON(pkgrelay) && user && wcsicmp(user, L"windows.ui.xaml.dll"))\n'
            "        return data->entry_points[ordinal].orig_func;")
    replace(source, "dlls/ntdll/loader.c", "WINE_DECLARE_DEBUG_CHANNEL(relay);",
            "WINE_DECLARE_DEBUG_CHANNEL(relay);\nWINE_DECLARE_DEBUG_CHANNEL(pkgrelay);")
    replace(source, "dlls/ntdll/loader.c", "if (TRACE_ON(relay))\n    {\n        size_t len",
            "if (TRACE_ON(relay) && !TRACE_ON(pkgrelay))\n    {\n        size_t len")
    replace(source, "dlls/ntdll/loader.c", 'if (TRACE_ON(relay))\n        TRACE_(relay)("\\1Ret  PE DLL',
            'if (TRACE_ON(relay) && !TRACE_ON(pkgrelay))\n        TRACE_(relay)("\\1Ret  PE DLL')
    spec = source / "dlls/ntdll/ntdll.spec"
    spec.write_text(spec.read_text() +
                    "\n@ stdcall __wine_pkg_diagnostic_active()\n"
                    "@ stdcall __wine_pkg_diagnostic_phase(long ptr)\n")
    shutil.copy2(FILES / "package_wait_diagnostics.h", source / "dlls/ntdll/unix/package_wait_diagnostics.h")
    replace(source, "dlls/ntdll/unix/sync.c", "HANDLE keyed_event = 0;",
            '#include "package_address_diagnostics.h"\n#include "package_wait_diagnostics.h"\n\nHANDLE keyed_event = 0;')
    shutil.copy2(FILES / "package_address_diagnostics.h", source / "dlls/ntdll/unix/package_address_diagnostics.h")
    sync = source / "dlls/ntdll/unix/sync.c"
    text = sync.read_text()
    for name, args, call, count, handles, wait_type in (
        ("NtWaitForSingleObject", "HANDLE handle, BOOLEAN alertable, const LARGE_INTEGER *timeout",
         "handle, alertable, timeout", "1", "&handle", "1"),
        ("NtWaitForMultipleObjects",
         "DWORD count, const HANDLE *handles, WAIT_TYPE type, BOOLEAN alertable, const LARGE_INTEGER *timeout",
         "count, handles, type, alertable, timeout", "count", "handles", "(unsigned int)type"),
        ("NtSignalAndWaitForSingleObject",
         "HANDLE signal, HANDLE wait, BOOLEAN alertable, const LARGE_INTEGER *timeout",
         "signal, wait, alertable, timeout", "1", "&wait", "1"),
    ):
        original = "NTSTATUS WINAPI " + name + "("
        if text.count(original) != 1:
            raise ValueError("Missing actual wait seam " + name)
        text = text.replace(original, "static NTSTATUS diagnostic_original_" + name + "(", 1)
        text += "\nNTSTATUS WINAPI " + name + "(" + args + ")\n{\n" + (
            "    NTSTATUS result;\n"
            "    unsigned int sequence, i;\n"
            "    const HANDLE *objects = " + handles + ";\n"
            "    if (!TRACE_ON(pkgwait)) return diagnostic_original_" + name + "(" + call + ");\n"
            "    sequence = InterlockedIncrement(&diagnostic_wait_sequence);\n"
            '    TRACE_(pkgwait)("wait method=' + name + ' phase=enter id=%u count=%u alertable=%u infinite=%u waittype=%u\\n",\n'
            "                    sequence, (unsigned int)" + count + ", alertable, !timeout, " + wait_type + ");\n"
            "    if (" + count + " <= MAXIMUM_WAIT_OBJECTS)\n"
            "        for (i = 0; i < " + count + "; ++i) diagnostic_wait(objects[i], sequence, i);\n"
            "    result = diagnostic_original_" + name + "(" + call + ");\n"
            '    TRACE_(pkgwait)("wait method=' + name + ' phase=exit id=%u result=%08x\\n", sequence, (unsigned int)result);\n'
            "    return result;\n}\n")
    sync.write_text(text)
    return {"headers": inputs, "interfaces": coverage,
            "files": {relative: sha256(source / relative) for relative in (
                "dlls/twinapi.appcore/core_application.c", "dlls/windows.ui/corewindow_host.c",
                "dlls/ntdll/relay.c", "dlls/ntdll/ntdll.spec", "dlls/ntdll/unix/sync.c", "dlls/ntdll/loader.c")}}
