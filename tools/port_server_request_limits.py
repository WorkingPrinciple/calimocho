"""Keep every client server request within __SERVER_MAX_DATA data chunks, then gate the tree."""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256
from tools.server_request_gate import check

SOURCES = ("tools/port_server_request_limits.py", "tools/server_request_gate.py")
PROCESS = "dlls/ntdll/unix/process.c"


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned source")
    process = (source / PROCESS).read_text()
    # Patch 0006 added the package identity as a sixth possible chunk; append it to the job list
    # buffer instead. The server still reads jobs_size bytes of jobs, then package_size bytes.
    process = replace(process, "    /* create the socket for the new process */\n",
        "    if (package_attr)\n    {\n"
        "        /* One chunk for jobs and package identity: a request carries at most __SERVER_MAX_DATA chunks. */\n"
        "        obj_handle_t *joined = realloc( jobs, jobs_size + package_attr->Size );\n"
        "        if (!joined)\n        {\n            status = STATUS_NO_MEMORY;\n"
        "            free( objattr );\n            free( handles );\n            free( jobs );\n            goto done;\n        }\n"
        "        memcpy( (char *)joined + jobs_size, package_attr->ValuePtr, package_attr->Size );\n"
        "        jobs = joined;\n    }\n\n"
        "    /* create the socket for the new process */\n")
    process = replace(process,
        "        wine_server_add_data( req, jobs, jobs_size );\n"
        "        if (package_attr) wine_server_add_data( req, package_attr->ValuePtr, package_attr->Size );\n",
        "        wine_server_add_data( req, jobs, jobs_size + req->package_size );\n")
    (source / PROCESS).write_text(process)
    paths = [str(p.relative_to(source)) for root in ("dlls", "programs") for p in (source / root).rglob("*.c")]
    gate = check(source, paths)
    return {"files": {PROCESS: sha256(source / PROCESS)}, "max_data": gate["max_data"],
            "checked_files": len(gate["checked"])}
