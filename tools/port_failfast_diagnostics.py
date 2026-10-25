"""Observe fail-fast HRESULTs and restricted-error calls without changing their behavior."""
from pathlib import Path
import shutil

from tools.build_launcher_overlay import REPO
from tools.port_uwp_activation import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_failfast_diagnostics.py", "patches/wine/files/package_failfast_diagnostics.h",
           "patches/wine/files/package_address_diagnostics.h")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned fail-fast diagnostic source")
    relative = "dlls/combase/roapi.c"
    for name in ("package_failfast_diagnostics.h", "package_address_diagnostics.h"):
        shutil.copy2(REPO / "patches/wine/files" / name, source / "dlls/combase" / name)
    replace(source, relative, '#include "package_ro_diagnostics.h"',
            '#include "package_ro_diagnostics.h"\n#include "package_failfast_diagnostics.h"')
    replace(source, relative, '    FIXME("%#lx, %lu, %p stub.\\n", error, exception_count, information);',
            '    diagnostic_error_context("RoFailFastWithErrorContextInternal2", "argument", error, __builtin_return_address(0));\n'
            '    FIXME("error context redacted stub.\\n");')
    for operation in ("RoOriginateError", "RoOriginateErrorW", "RoOriginateLanguageException"):
        replace(source, relative,
                f'    TRACE_(pkgro)("origin operation={operation} hresult=%08lx\\n", error);',
                f'    diagnostic_error_context("{operation}", "argument", error, __builtin_return_address(0));')
    for original in (
        '    FIXME("%#lx, %s, %p: stub\\n", error, debugstr_hstring(message), language_exception);',
        '    FIXME("%#lx, %s: stub\\n", error, debugstr_hstring(message));',
        '    FIXME("%#lx, %u, %p: stub\\n", error, max_len, message);',
    ):
        replace(source, relative, original, '    FIXME("error message redacted: stub\\n");')
    for operation, signature in (
        ("GetRestrictedErrorInfo", "IRestrictedErrorInfo **info"),
        ("SetRestrictedErrorInfo", "IRestrictedErrorInfo *info"),
    ):
        original = (f"HRESULT WINAPI {operation}({signature})\n{{\n"
                    '    FIXME( "(%p)\\n", info );\n    return E_NOTIMPL;\n}')
        replacement = (f"HRESULT WINAPI {operation}({signature})\n{{\n"
                       f'    diagnostic_error_context("{operation}", "return", E_NOTIMPL, __builtin_return_address(0));\n'
                       '    FIXME("restricted error info redacted: stub\\n");\n    return E_NOTIMPL;\n}')
        replace(source, relative, original, replacement)
    return {"files": {relative: sha256(source / relative) for relative in (
        relative, "dlls/combase/package_failfast_diagnostics.h", "dlls/combase/package_address_diagnostics.h")},
        "scope": "Run-scoped source, collector Initialize-through-Run-exit; argument HRESULT versus actual stub return explicitly typed"}
