"""Provide the eight-byte theme color preference ABI used by native XAML."""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.probe_wine_source import sha256
from tools.qualify_coremessaging_imports import PE

SOURCES = ("tools/port_theme_color_preference.py", "patches/wine/files/uxtheme_color_preference.c")
PATHS = ("dlls/uxtheme/system.c", "dlls/uxtheme/uxtheme.spec", "dlls/uxtheme/color_preference.c")
EXPORTS = ("GetUserColorPreference", "GetColorFromPreference")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned theme source")
    system, spec = ((source / path).read_text() for path in PATHS[:2])
    if (source / PATHS[2]).exists() or any(name in spec for name in EXPORTS):
        raise ValueError("Require fresh theme preference source")
    if "BOOLEAN WINAPI ShouldAppsUseDarkMode(void)" not in system:
        raise ValueError("Require the existing Wine theme preference mechanism")
    (source / PATHS[0]).write_text(system.rstrip("\n") + '\n\n#include "color_preference.c"\n')
    (source / PATHS[1]).write_text(spec + "\n@ stdcall GetUserColorPreference(ptr long)\n"
                                "@ stdcall GetColorFromPreference(ptr long long long)\n")
    (source / PATHS[2]).write_bytes((REPO / SOURCES[1]).read_bytes())
    return {"files": {path: sha256(source / path) for path in PATHS},
            "abi_bytes": 8, "color_encoding": "opaque ABGR (COLORREF RGB plus alpha)",
            "roles": "0 application text; 1..7 light3..accent..dark3; 210..214 application background/text variants",
            "policy": "Wine app theme, system high contrast and existing AccentPalette; uncached reads",
            "limitations": "No native accent generation for a preference that differs from the current palette; "
                           "unsupported roles fail with CLR_INVALID and a fixed reason"}


def qualify(root):
    root = Path(root)
    built = root / "build/dlls/uxtheme/x86_64-windows/uxtheme.dll"
    installed = root / "install/lib/wine/x86_64-windows/uxtheme.dll"
    if sha256(built) != sha256(installed):
        raise ValueError("Built and installed uxtheme differ")
    exports = PE(installed).exports()
    if any(not isinstance(exports.get(name), int) or not exports[name] for name in EXPORTS):
        raise ValueError("Require direct nonzero AMD64 preference exports")
    return {"status": "source-pe-exports-qualified-not-executed",
            "built_path": str(built), "built_sha256": sha256(built),
            "installed_path": str(installed), "installed_sha256": sha256(installed),
            "exports": {name: exports[name] for name in EXPORTS}}
