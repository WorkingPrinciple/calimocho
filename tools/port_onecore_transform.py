"""Expose only the observed zero-argument transform-mode query in user32."""
from pathlib import Path
import shutil

from tools.build_launcher_overlay import REPO
from tools.port_uwp_activation import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_onecore_transform.py", "patches/wine/files/onecore_transform.c", "versions.json")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned OneCore-query sibling")
    spec = source / "dlls/user32/user32.spec"
    old = "# @ stub IsOneCoreTransformMode"
    new = "@ stdcall IsOneCoreTransformMode()"
    if old in spec.read_text():
        replace(source, "dlls/user32/user32.spec", old, new)
    elif spec.read_text().count(new) != 1:
        raise ValueError("Unexpected OneCore query export")
    make = source / "dlls/user32/Makefile.in"
    if "\tonecore_transform.c \\" not in make.read_text():
        replace(source, "dlls/user32/Makefile.in", "\tnonclient.c \\",
                "\tnonclient.c \\\n\tonecore_transform.c \\")
    shutil.copy2(REPO / "patches/wine/files/onecore_transform.c",
                 source / "dlls/user32/onecore_transform.c")
    return {"files": {relative: sha256(source / relative) for relative in (
        "dlls/user32/user32.spec", "dlls/user32/Makefile.in", "dlls/user32/onecore_transform.c")},
        "scope": "observed BOOL(void) query false in unpackaged desktop and signed GamingApp; other modes unobserved"}
