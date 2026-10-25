"""Implement the sechost transient object security descriptor lookup and WaitServiceState.

CoreMessaging's registrar ServiceMain calls QueryTransientObjectSecurityDescriptor
for its ALPC port before creating it; the Wine stub aborted the svchost thread.
The Xbox app calls WaitServiceState after its registrar connect fails. Both
were spec stubs in Wine 11.20.
"""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_sechost_services.py", "patches/wine/files/sechost_transient_wait.c")
PATHS = ("dlls/sechost/service.c", "dlls/sechost/sechost.spec", "dlls/sechost/transient_wait.c")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned sechost source")
    if (source / PATHS[2]).exists():
        raise ValueError("Require fresh sechost source")
    service = (source / PATHS[0]).read_text()
    service = replace(service, '#include "windef.h"\n',
                      '#include "ntstatus.h"\n#define WIN32_NO_STATUS\n#include "windef.h"\n')
    service = service.rstrip("\n") + '\n\n#include "transient_wait.c"\n'
    spec = (source / PATHS[1]).read_text()
    spec = replace(spec, "@ stub FreeTransientObjectSecurityDescriptor\n",
                   "@ stdcall FreeTransientObjectSecurityDescriptor(ptr)\n")
    spec = replace(spec, "@ stub QueryTransientObjectSecurityDescriptor\n",
                   "@ stdcall QueryTransientObjectSecurityDescriptor(long wstr ptr)\n")
    spec = replace(spec, "@ stub WaitServiceState\n", "@ stdcall WaitServiceState(long long long long)\n")
    (source / PATHS[0]).write_text(service)
    (source / PATHS[1]).write_text(spec)
    (source / PATHS[2]).write_text((REPO / SOURCES[1]).read_text())
    return {"files": {p: sha256(source / p) for p in PATHS},
            "transient_sd": "type 8 (ALPC port) only; registry value read and validated; open/query NTSTATUS "
                            "returned unchanged (native failure convention unmeasured)",
            "wait_service_state": "documented contract via 50 ms QueryServiceStatusEx polling"}
