"""Replace the named-object-path guard with token-grounded namespace resolution."""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_appcontainer_object_path.py",
           "patches/wine/files/ntdll_appcontainer_object_path.c")
PATHS = ("dlls/ntdll/coremessaging_ntdll_stubs.c", "dlls/ntdll/appcontainer_object_path.c")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned named-object-path source")
    if (source / PATHS[1]).exists():
        raise ValueError("Require fresh named-object-path source")
    text = (source / PATHS[0]).read_text()
    begin = text.index("NTSTATUS WINAPI RtlGetAppContainerNamedObjectPath(")
    end = text.index("NTSTATUS WINAPI RtlGetThreadWorkOnBehalfTicket(", begin)
    old = text[begin:end]
    if 'diagnostic_coremessaging_stub("RtlGetAppContainerNamedObjectPath")' not in old:
        raise ValueError("Require the explicit predecessor stub")
    text = replace(text, old, '#include "appcontainer_object_path.c"\n\n')
    (source / PATHS[0]).write_text(text)
    (source / PATHS[1]).write_bytes((REPO / SOURCES[1]).read_bytes())
    return {"files": {p: sha256(source / p) for p in PATHS},
            "token_selection": "explicit token, else current thread token with process fallback only for NO_TOKEN",
            "namespace": "validated parent AppContainer SID and token session, never inferred from package metadata",
            "ownership": "process heap UNICODE_STRING, released by RtlFreeUnicodeString",
            "non_appcontainer": "STATUS_NOT_SUPPORTED pending authoritative current-native contract; "
                                "no empty-success or fabricated package SID",
            "limits": "child SIDs and private AppContainer namespaces are unsupported; no directory creation"}
