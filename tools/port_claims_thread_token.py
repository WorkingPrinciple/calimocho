"""Import unchanged r8 claims and add bounded genuine-context observations."""
import json
from pathlib import Path
import shutil

from tools.build_launcher_overlay import REPO
from tools.probe_wine_source import sha256
from tools.port_claims_site_b import CONTEXT_FILES

SOURCES = ("tools/port_claims_thread_token.py", "tools/port_claims_site_b.py",
           "patches/wine/files/package_claims_thread_token_generated.h",
           "patches/wine/files/package_claims_context_diagnostics.c", "versions.json")
DIGEST = "5acbb35eaa18c874272e91a1169b997373496aa6277f9ccbb7f3bcc3d840b9ed"


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned thread-token sibling")
    pin = json.loads((REPO / "versions.json").read_text())["whiny_claims_thread_token"]
    artifact = REPO / pin["path"]
    if pin["sha256"] != DIGEST or sha256(artifact) != DIGEST:
        raise ValueError("Whiny r8 artifact changed")
    wrapper = REPO / "patches/wine/files/package_claims_context_diagnostics.c"
    for relative, expected in CONTEXT_FILES.items():
        allowed = (expected, sha256(wrapper)) if relative.endswith("package_claims_context.c") else (expected,)
        if sha256(source / relative) not in allowed:
            raise ValueError("Genuine claims context or build seam changed: " + relative)
    header = source / "dlls/ntdll/package_claims_generated.h"
    if sha256(header) not in ("2194a9ac3f418b9af78fcfefae307faaf1260fa6b6932a85df0b8bfbffc8bb72", DIGEST):
        raise ValueError("Unexpected generated claims source")
    for name in ("package_claims_generated.h", "package_claims_generated.c"):
        shutil.copy2(artifact, source / "dlls/ntdll" / name)
    shutil.copy2(wrapper, source / "dlls/ntdll/package_claims_context.c")
    return {"artifact_sha256": DIGEST, "pin": pin,
            "files": {relative: sha256(source / relative) for relative in (
                "dlls/ntdll/package_claims_generated.h", "dlls/ntdll/package_claims_generated.c",
                *CONTEXT_FILES)},
            "scope": "unchanged r8; sampled genuine contexts and pointer presence, not selected-branch tracing"}
