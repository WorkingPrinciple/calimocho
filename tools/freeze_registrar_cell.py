"""Cell027-029 additions: registrar service registration and the ALPC/token/dispatch stack it needs."""
import importlib
import json
from pathlib import Path

from tools.freeze_static_lifetime_runtime import REGISTRAR_STACK
from tools.prepare_verified_activation import dos
from tools.probe_wine_source import sha256

SERVICE = "CoreMessagingRegistrar"
GROUP = "LocalServiceNoNetwork"
IMAGE_PATH = "C:\\windows\\system32\\svchost.exe -k LocalServiceNoNetwork -p"
SERVICE_KEY = "HKEY_LOCAL_MACHINE\\System\\CurrentControlSet\\Services\\" + SERVICE
SVCHOST_KEY = "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Svchost"
# Cell028 scopes tracing to the services.exe/svchost.exe tree; activation keeps the run's WINEDEBUG.
SERVICES_WINEDEBUG = ",".join((
    "-all", "+pid", "+timestamp",
    "services.exe:err+all", "services.exe:+service", "services.exe:+process",
    "svchost.exe:err+all", "svchost.exe:fixme+all", "svchost.exe:+service", "svchost.exe:+svchost",
    "svchost.exe:+loaddll", "svchost.exe:+seh", "svchost.exe:+alpc", "svchost.exe:+process"))
DOCS = tuple("docs/ADR/%s.md" % name for name in (
    "0059-qualify-alpc-transport-before-registrar-admission",
    "0060-enforce-restricting-sids-in-source-token-checks",
    "0061-bind-alpc-connect-checks-to-creator-token",
    "0062-preserve-token-owner-group-and-source-identity",
    "0063-replace-token-session-and-integrity-success-stubs",
    "0064-authenticate-delivered-alpc-connection-impersonation",
    "0065-construct-a-scoped-registrar-service-token",
    "0066-host-coremessaging-thread-dispatch"))
TESTS = ("tests/test_alpc_transport.py", "tests/alpc_transport_host.c", "tests/test_restricted_token.py",
         "tests/restricted_token_host.c", "tests/test_alpc_identity.py", "tests/test_token_identity.py",
         "tests/token_identity_host.c", "tests/test_token_security.py", "tests/token_security_host.c",
         "tests/test_alpc_impersonation.py", "tests/test_registrar_service.py", "tests/registrar_service_host.c",
         "tests/test_coremsg_dispatch.py", "tests/coremsg_dispatch_host.c", "tests/test_server_protocol_gate.py",
         "tests/test_registrar_cell.py")


def registrar_sources():
    sources = ["tools/freeze_registrar_cell.py", "tools/server_protocol_gate.py"]
    for key in REGISTRAR_STACK:
        for relative in importlib.import_module("tools.port_" + key).SOURCES:
            if relative not in sources:
                sources.append(relative)
    return tuple(sources) + DOCS + TESTS


def registrar_stack_build(root, build):
    root = Path(root)
    result = {}
    for key in REGISTRAR_STACK:
        if key not in build:
            raise ValueError("Cell027 requires the complete registrar stack: " + key)
        for relative, value in build[key]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Registrar stack source changed: " + relative)
        result[key] = build[key]
    stage = json.loads((root / "staging-receipt.json").read_text())
    gate = stage.get("server_protocol_gate", {})
    if gate.get("status") != "passed" or not {"win32u", "server", "services"} <= set(gate["rebuilt_modules"]):
        raise ValueError("Cell027 requires a staged install with consistent server request numbering")
    result["server_protocol_gate"] = gate
    return result


def multi_sz(*values):
    data = "".join(value + "\0" for value in values) + "\0"
    return "hex(7):" + ",".join("%02x" % byte for byte in data.encode("utf-16-le"))


def registration_text():
    def escaped(value):
        return value.replace("\\", "\\\\")
    return "\r\n".join([
        "Windows Registry Editor Version 5.00", "",
        "[" + SERVICE_KEY + "]",
        '"DisplayName"="CoreMessaging"',
        '"DependOnService"=' + multi_sz("RpcSs"),
        '"ErrorControl"=dword:00000001',
        '"ImagePath"="' + escaped(IMAGE_PATH) + '"',
        '"ObjectName"="NT AUTHORITY\\\\LocalService"',
        '"ServiceSidType"=dword:00000003',
        '"Start"=dword:00000003',
        '"Type"=dword:00000020', "",
        "[" + SERVICE_KEY + "\\Parameters]",
        '"ServiceDll"="C:\\\\windows\\\\system32\\\\coremessaging.dll"', "",
        "[" + SVCHOST_KEY + "]",
        '"' + GROUP + '"=' + multi_sz(SERVICE), "", ""])


def add_registrar_handoff(root, receipt, cell=27):
    if cell not in (27, 28, 29):
        raise ValueError("Registrar handoff supports cells027-029")
    label = "%03d" % cell
    root = Path(root)
    registration = root / ("registrar-CELL%s-FROZEN.reg" % label)
    if registration.exists():
        raise FileExistsError("Refuse existing%s registrar registration" % label)
    registration.write_bytes(registration_text().encode("utf-16"))
    wine = receipt["launcher_registration_argv"][:3]
    receipt["scope"] = ("cell" + label + " native CoreMessaging with ALPC transport, scoped restricted registrar "
                        "service token and per-thread CoreMessaging dispatch; source-built, unexecuted")
    receipt["registrar_registration"] = str(registration)
    receipt["registrar_registration_sha256"] = sha256(registration)
    receipt["registrar_registration_argv"] = wine + ["regedit", "/S", dos(registration)]
    receipt["registrar_readback_argv"] = wine + ["reg", "query", SERVICE_KEY.replace("HKEY_LOCAL_MACHINE", "HKLM"), "/s"]
    receipt["services_start_argv"] = wine + ["wineboot", "--kill"]
    if cell >= 28:
        # arch -e sets the variable for wineboot only; services.exe and svchost.exe inherit it through exec.
        receipt["services_start_argv"] = wine[:2] + ["-e", "WINEDEBUG=" + SERVICES_WINEDEBUG] + wine[2:] + ["wineboot", "--kill"]
        receipt["services_diagnostics"] = {
            "winedebug": SERVICES_WINEDEBUG,
            "scope": "services_start_argv only; services.exe and svchost.exe inherit it, all later steps keep the run WINEDEBUG",
            "output": "services.exe and svchost.exe stderr inherit the services_start_argv log; lines carry timestamp:pid:tid",
            "discriminators": [
                "'registrar process create' without 'registrar process create returned': services blocked inside CreateProcessAsUserW (child never finished initialisation)",
                "'returned 1' with no svchost.exe lines after it: child created but svchost never reached its entry point",
                "svchost lines ending before ServiceMain or SetServiceStatus: hang or failure inside svchost or coremessaging.dll",
                "No 'registrar process create' line: sc never reached service_start_process (RPC or pipe side)",
            ]}
    receipt["registrar_start_argv"] = wine + ["sc", "start", SERVICE]
    receipt["registrar_query_argv"] = wine + ["sc", "query", SERVICE]
    for key in REGISTRAR_STACK:
        receipt["generated_source_sha256"].update(receipt[key]["files"])
    receipt["changed_modules"] = sorted(receipt["changed_modules"])
    receipt["preconditions"] = [item for item in receipt["preconditions"]
                                if not item.startswith("Execution owner must verify and copy only native_coremessaging")]
    receipt["preconditions"] += [
        "Execution owner must verify and copy only native_coremessaging into this fresh" + label + " prefix and read back its SHA before services_start_argv",
        "Import registrar_registration_argv with the other setup registrations, before the setup server stop; record exit and registrar_readback_argv output",
        "Immediately after server_start and before any other Wine process: run services_start_argv (starts services.exe for this prefix server only), then registrar_start_argv, then registrar_query_argv; record each exit and output",
        "If the registrar does not reach RUNNING, still run activation once and record the registrar state; do not retry or change the token",
        "First failure after this point is routed to the coordinator; no source-lane replay",
    ]
    if cell >= 28:
        receipt["preconditions"] += [
            "Redirect services_start_argv stdout and stderr to a regular evidence file, not a pipe: services.exe and svchost.exe outlive wineboot and keep writing to it",
            "Retain that file after registrar_start_argv, registrar_query_argv, activation and cleanup, including after a registrar start timeout; also record the registrar start timeout and the svchost pid if visible",
        ]
    receipt["limitations"] = [item for item in receipt["limitations"]
                              if not item.startswith("Private user32 dispatcher ordinals and unhosted API-set")]
    receipt["limitations"] += [
        "ALPC transport supports the connect, accept, datagram, reply and impersonation paths qualified by host tests; other message attributes, views and sections fail explicitly",
        "Registrar token is single-member LocalServiceNoNetwork: native companion service SIDs of a multi-member svchost group are absent, so access depending on them fails closed",
        "Eight S-1-5-32 groups seen in the native token have no derivation evidence and are not reproduced",
        "Native token values come from Windows 10.0.26300 with CoreMessaging e770ec95; the evaluated CoreMessaging is 88c7b4d6, so exact ACL parity is not proven",
        "Start=3 and the explicit services/registrar start steps are harness choices; native start mode was not measured",
        "Wine svchost ignores -p only after the -k group dispatcher returns; svchost globals helpers are not provided",
        "CoreMessaging dispatch: per-thread IOCP plus two HWND slots, WM_COREMSG 0x60; Schedule operation 2 and wait-all with the IOCP return ERROR_NOT_SUPPORTED",
        "Ten CoreMessaging delay imports remain explicit guards or stubs (combase86-88, three sechost and four combase WinRT-error functions)",
        "Cell026 ran a stale win32u.so whose renumbered server requests did not match its server; cell027 rebuilds it and the stager now rejects that mismatch",
        "Source/build and host tests only; registrar admission, NavigateToView and UI are unobserved",
    ]
    if cell >= 28:
        receipt["limitations"] += [
            "Cell027: sc start CoreMessagingRegistrar did not return within45 s under WINEDEBUG=-all; cause unobserved. Wine SCM does not start DependOnService, so RpcSs is not a start wait",
            "Cell028 adds diagnostics only (scoped WINEDEBUG and two services traces around registrar process creation); the token and start path are unchanged",
        ]


# Setup-session steps that run before the setup server stop; none needs a display.
SETUP_ARGVS = ("framework_registration_argv", "launcher_registration_argv", "native_xaml_registration_argv",
               "aedebug_registration_argv", "registrar_registration_argv", "registrar_readback_argv")


def add_headless_setup(receipt):
    """Cell029: keep winemac.drv out of the setup session; only the server_start session uses it."""
    if "prefix_init_argv" in receipt:
        raise ValueError("Headless setup already applied")
    overrides = receipt["environment"]["WINEDLLOVERRIDES"] + ";winemac.drv=d"
    setup = dict(receipt["environment"], WINEDLLOVERRIDES=overrides)
    wine = receipt["launcher_registration_argv"][:3]
    if wine[:2] != ["/usr/bin/arch", "-x86_64"]:
        raise ValueError("Unexpected setup launcher prefix")
    receipt["setup_environment"] = setup
    receipt["prefix_init_argv"] = wine + ["wineboot", "-u"]
    headless = ["-e", "WINEDLLOVERRIDES=" + overrides]
    for key in ("prefix_init_argv",) + SETUP_ARGVS:
        argv = receipt[key]
        if argv[:3] != wine:
            raise ValueError("Setup argv does not use the frozen wine: " + key)
        receipt[key] = argv[:2] + headless + argv[2:]
    receipt["preconditions"] += [
        "Run prefix_init_argv in place of the driver's own wineboot -u, with setup_environment; it and every SETUP argv carry winemac.drv=d through arch -e, so the setup session loads Wine's null display driver",
        "Stop the setup server after the registrations as before; the display driver choice is volatile and the server_start session (services, registrar, activation) uses the mac driver with environment unchanged",
    ]
    receipt["limitations"] += [
        "Cell028 wineboot -u aborted in winemac run_cocoa_app: macdrv_start_cocoa_app gives up after5 s and returns while the main thread still holds a pointer to its stack startup info, so a late run_cocoa_app sends lock to a freed object. This is an upstream Wine timing race under a stalled main thread, not a cell028 change (winemac.so is byte-identical to cell027)",
        "Headless setup avoids that race only for setup; the activation step still starts the mac driver and can hit it if its main thread stalls over5 s",
    ]
