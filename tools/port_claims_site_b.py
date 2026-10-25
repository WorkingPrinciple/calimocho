"""Import the byte-exact observation-backed claims artifact into an owned sibling."""
import json
from pathlib import Path
import shutil

from tools.build_launcher_overlay import REPO
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_claims_site_b.py", "patches/wine/files/package_claims_site_b_generated.h", "versions.json")
CONTEXT_FILES = {
    "dlls/ntdll/package_claims_context.c": "c6261dd56dbf4370dec9ca6cd0cb2a534e7086bd9571d799d4ff20861d2311b1",
    "include/wine/whiny_context.h": "d9f25f41c2b19149ee0a4a40a87567c3739ea6615b80a61e4ea026b5b03a4954",
    "dlls/ntdll/Makefile.in": "04875eef5b7d908ac4c12d36bdae9e5b94ce053391e266657bffba2e6e37982a",
}


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned claims sibling")
    pin = json.loads((REPO / "versions.json").read_text())["whiny_claims_site_b"]
    artifact = REPO / pin["path"]
    digest = "2924dd6c183b944d3a177fd2f2bf96571dde92b175b123eee64a938faf4b14d6"
    if pin["sha256"] != digest or sha256(artifact) != digest:
        raise ValueError("Whiny Site B artifact changed")
    header = source / "dlls/ntdll/package_claims_generated.h"
    if sha256(header) not in ("2194a9ac3f418b9af78fcfefae307faaf1260fa6b6932a85df0b8bfbffc8bb72", digest):
        raise ValueError("Unexpected prior generated claims source")
    for relative, expected in CONTEXT_FILES.items():
        if sha256(source / relative) != expected:
            raise ValueError("Genuine020 claims context or build seam changed: " + relative)
    for name in ("package_claims_generated.h", "package_claims_generated.c"):
        shutil.copy2(artifact, source / "dlls/ntdll" / name)
    return {"artifact_sha256": digest, "pin": pin,
            "files": {relative: sha256(source / relative) for relative in (
                "dlls/ntdll/package_claims_generated.h", "dlls/ntdll/package_claims_generated.c",
                "dlls/ntdll/package_claims_context.c", "include/wine/whiny_context.h",
                "dlls/ntdll/Makefile.in")},
            "scope": "unchanged generated Site B cell; existing genuine signed GamingApp context predicate unchanged"}
