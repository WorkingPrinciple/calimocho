"""Observe the real unhandled filter without changing its return or guessing exception layout."""
from pathlib import Path
import shutil

from tools.build_launcher_overlay import REPO
from tools.port_uwp_activation import replace
from tools.probe_wine_source import sha256

BASE = REPO / "build/winehq-11.20/package-uwp-handle-provenance-01"
SOURCES = ("tools/port_exception_diagnostics.py", "patches/wine/files/package_exception_diagnostics.h")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned017 source")
    if sha256(BASE / "cell016-receipt.json") != "b55779b754cacf0b091dac907c381a9dcf3133acdbe8169b8f18a226705d38d5":
        raise ValueError("Sealed016 predecessor changed")
    shutil.copy2(BASE / "source/dlls/ntdll/exception.c", source / "dlls/ntdll/exception.c")
    shutil.copy2(REPO / SOURCES[1], source / "dlls/ntdll/package_exception_diagnostics.h")
    replace(source, "dlls/ntdll/exception.c", "static PRTL_EXCEPTION_FILTER unhandled_exception_filter;",
            'static PRTL_EXCEPTION_FILTER unhandled_exception_filter;\n#include "package_exception_diagnostics.h"')
    replace(source, "dlls/ntdll/exception.c",
            "    if (!unhandled_exception_filter) return EXCEPTION_CONTINUE_SEARCH;",
            "    diagnostic_exception(eptr->ExceptionRecord);\n"
            "    if (!unhandled_exception_filter) return EXCEPTION_CONTINUE_SEARCH;")
    replace(source, "dlls/twinapi.appcore/core_application.c", "    BOOL initialized = FALSE;",
            "    BOOL initialized = FALSE;\n    UINT diagnostic_error_mode;")
    replace(source, "dlls/twinapi.appcore/core_application.c", "    core.thread = GetCurrentThreadId();",
            '    diagnostic_error_mode = SetErrorMode(GetErrorMode() | SEM_NOGPFAULTERRORBOX);\n'
            '    TRACE("exception-policy no-gpfault-dialog=1\\n");\n'
            "    core.thread = GetCurrentThreadId();")
    replace(source, "dlls/twinapi.appcore/core_application.c", "    core.thread = 0;",
            "    SetErrorMode(diagnostic_error_mode);\n    core.thread = 0;")
    for operation, signature in (
        ("RoOriginateError", "HRESULT error, HSTRING message"),
        ("RoOriginateLanguageException", "HRESULT error, HSTRING message, IUnknown *language_exception"),
        ("RoOriginateErrorW", "HRESULT error, UINT max_len, const WCHAR *message"),
    ):
        replace(source, "dlls/combase/roapi.c", f"BOOL WINAPI {operation}({signature})\n{{",
                f"BOOL WINAPI {operation}({signature})\n{{\n"
                f'    TRACE_(pkgro)("origin operation={operation} hresult=%08lx\\n", error);')
    return {"files": {relative: sha256(source / relative) for relative in (
        "dlls/ntdll/exception.c", "dlls/ntdll/package_exception_diagnostics.h",
        "dlls/twinapi.appcore/core_application.c", "dlls/combase/roapi.c")}}
