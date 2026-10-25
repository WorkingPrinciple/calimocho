"""Build an explicitly scoped SCM registrar token, without inherited-token fallback."""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_registrar_service.py", "patches/wine/files/services_registrar_token.c")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned registrar service source")
    paths = ("programs/services/services.c", "programs/services/services.h",
             "programs/services/Makefile.in", "programs/services/registrar_token.c")
    if (source / paths[-1]).exists():
        raise ValueError("Require fresh registrar service source")
    services = (source / paths[0]).read_text()
    services = replace(services,
        '    if ((err = load_reg_string(hKey, L"ObjectName",  TRUE, &entry->config.lpServiceStartName))) return err;',
        '    if ((err = load_reg_string(hKey, L"ObjectName",  TRUE, &entry->config.lpServiceStartName))) return err;\n'
        '    if ((err = load_reg_dword(hKey, L"ServiceSidType", &entry->sid_type))) return err;')
    services = replace(services, "static DWORD service_start_process(",
        '#include "registrar_token.c"\n\nstatic DWORD service_start_process(')
    start = services.index("static DWORD service_start_process(")
    end = services.index("\nstatic DWORD service_wait_for_startup(", start)
    section = services[start:end]
    # The token is built by the caller before the SCM database lock (see build_registrar_token).
    section = replace(section, "                                   BOOL *shared_process)",
        "                                   BOOL *shared_process, HANDLE registrar_token)")
    section = replace(section,
        "    r = CreateProcessW(NULL, path, NULL, NULL, FALSE, CREATE_UNICODE_ENVIRONMENT | DETACHED_PROCESS, environment, NULL, &si, &pi);",
        """    if (registrar_token)
    {
        /* Entry/exit traces separate a hang inside process creation from a later startup hang. */
        WINE_TRACE("registrar process create %s\\n", debugstr_w(path));
        r = CreateProcessAsUserW( registrar_token, NULL, path, NULL, NULL, FALSE,
                                  CREATE_UNICODE_ENVIRONMENT | DETACHED_PROCESS, environment, NULL, &si, &pi );
        err = r ? ERROR_SUCCESS : GetLastError();
        WINE_TRACE("registrar process create returned %d, pid %04lx, error %lu\\n", r, r ? pi.dwProcessId : 0, err);
        SetLastError( err );
    }
    else r = CreateProcessW(NULL, path, NULL, NULL, FALSE, CREATE_UNICODE_ENVIRONMENT | DETACHED_PROCESS, environment, NULL, &si, &pi);""")
    services = services[:start] + section + services[end:]
    services = replace(services, """    BOOL shared_process;
    DWORD err;

    err = service_start_process(""", """    BOOL shared_process;
    HANDLE registrar_token = NULL;
    DWORD err;

    err = service_start_process(""")
    services = replace(services, """    err = service_start_process(service, &process, &shared_process);
""", """    if (!wcsicmp( service->name, L"CoreMessagingRegistrar" ))
    {
        if ((err = build_registrar_token( service, &registrar_token )))
        {
            WINE_ERR("registrar token construction rejected, error %lu\\n", err);
            return err;
        }
    }
    err = service_start_process(service, &process, &shared_process, registrar_token);
    if (registrar_token) CloseHandle( registrar_token );
""")
    header = replace((source / paths[1]).read_text(), "    DWORD preshutdown_timeout;",
        "    DWORD sid_type;\n    DWORD preshutdown_timeout;")
    makefile = replace((source / paths[2]).read_text(),
        "IMPORTS   = rpcrt4 advapi32 userenv setupapi", "IMPORTS   = rpcrt4 advapi32 userenv setupapi ntdll")
    for path, text in zip(paths, (services, header, makefile)):
        (source / path).write_text(text)
    (source / paths[-1]).write_bytes((REPO / SOURCES[-1]).read_bytes())
    return {"files": {p: sha256(source / p) for p in paths}, "registrar_qualified": False,
            "scope": "single configured LocalService registrar host; no unmeasured group parity claim"}
