"""Add a bounded scalar-return discriminator to real x64 relay exits."""
from pathlib import Path
import shutil

from tools.build_launcher_overlay import REPO
from tools.port_uwp_activation import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_status_diagnostics.py", "patches/wine/files/package_status_diagnostics.h")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned status diagnostic source")
    for name in ("package_status_diagnostics.h",):
        shutil.copy2(REPO / "patches/wine/files" / name, source / "dlls/ntdll" / name)
    replace(source, "dlls/ntdll/relay.c", '#include "package_relay_diagnostics.h"',
            '#include "package_relay_diagnostics.h"\n#include "package_status_diagnostics.h"')
    # Existing entry logging stays narrow. Only matching return statuses are
    # admitted by the new exit filter, across all actual relayed exports.
    replace(source, "dlls/ntdll/relay.c",
            "if (TRACE_ON(pkgrelay) && !diagnostic_selected(data->dllname, data->entry_points[i].name)) continue;",
            "if (TRACE_ON(pkgrelay) && !TRACE_ON(pkgstatus) && !diagnostic_selected(data->dllname, data->entry_points[i].name)) continue;")
    replace(source, "dlls/ntdll/relay.c",
            'if (TRACE_ON(pkgrelay) && user && wcsicmp(user, L"windows.ui.xaml.dll")',
            'if (TRACE_ON(pkgrelay) && !TRACE_ON(pkgstatus) && user && wcsicmp(user, L"windows.ui.xaml.dll")')
    replace(source, "dlls/ntdll/relay.c",
            "    /* No raw results, strings or absolute return addresses. */",
            "    const char *type = descr->args_string + HIWORD(idx);\n"
            "    while (!is_ret_val(*type)) ++type;\n"
            "    if (*type == 'I') diagnostic_status_return(descr->private, LOWORD(idx), (void *)retaddr, (UINT)retval);")
    return {"files": {relative: sha256(source / relative) for relative in (
        "dlls/ntdll/relay.c", "dlls/ntdll/package_status_diagnostics.h")},
        "coverage": "actual x64 relay thunks with scalar I return; norelay/syscalls and native-to-native bypasses unavailable"}
