"""Cell027-042 additions: registrar service registration and the ALPC/token/dispatch stack it needs."""
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
# Cell034: CoreMessaging's ServiceMain reads this ALPC port descriptor before creating its port.
TRANSIENT_KEY = ("HKEY_LOCAL_MACHINE\\Software\\Microsoft\\SecurityManager\\TransientObjects\\"
                 "%5C%5C.%5CAlpcPort%5CWM_RegistrarServer")
# Self-relative SD (264 bytes): owner/group absent; DACL CREATOR OWNER, SYSTEM, Administrators 0x111fffff and
# GENERIC_READ for IU, AU, one S-1-5-32 SID with 8 more subauthorities, ALL APPLICATION PACKAGES and one capability SID.
# Re-authored from the value an earlier lane provisioned (rt-v20b system.reg); no machine SID; native origin unmeasured.
TRANSIENT_SD = bytes.fromhex(
    "01000480000000000000000000000000140000000200f4000800000000001400ffff1f110101000000000003000000000000"
    "140000000080010100000000000504000000000014000000008001010000000000050b00000000001400ffff1f1101010000"
    "000000051200000000001800ffff1f11010200000000000520000000200200000000340000000080010900000000000520000000"
    "ce4a9359b9cf0b7575c0f29bb2b4c298d446ddf9027a87ec14651177d6e996550000180000000080010200000000000f02000000"
    "010000000000380000000080010a00000000000f0300000000040000ce4a9359b9cf0b7575c0f29bb2b4c298d446ddf9027a87ec"
    "14651177d6e99655")
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
    "0066-host-coremessaging-thread-dispatch",
    "0067-read-transient-alpc-port-security-descriptor",
    "0068-validate-transient-descriptor-and-admit-default-connect-security",
    "0069-admit-coremessaging-connect-security-sentinel",
    "0070-wake-waitable-alpc-ports-and-trace-connect",
    "0071-check-ownerless-alpc-server-requirements",
    "0072-impersonate-alpc-clients-at-their-requested-level",
    "0073-use-native-alpc-message-flags-and-sync-requests",
    "0074-accept-alpc-work-on-behalf-send-attribute",
    "0075-route-alpc-release-responses-by-delivered-message-identity"))
TESTS = ("tests/test_alpc_transport.py", "tests/alpc_transport_host.c", "tests/test_restricted_token.py",
         "tests/restricted_token_host.c", "tests/test_alpc_identity.py", "tests/test_token_identity.py",
         "tests/token_identity_host.c", "tests/test_token_security.py", "tests/token_security_host.c",
         "tests/test_alpc_impersonation.py", "tests/test_registrar_service.py", "tests/registrar_service_host.c",
         "tests/test_coremsg_dispatch.py", "tests/coremsg_dispatch_host.c", "tests/test_server_protocol_gate.py",
         "tests/test_registrar_cell.py", "tests/test_sechost_services.py", "tests/sechost_services_host.c",
         "tests/test_server_request_limits.py", "tests/test_alpc_telemetry.py",
         "tests/test_wait_completion_packet.py", "tests/wait_completion_packet_host.c",
         "tests/test_alpc_sync_request.py", "tests/test_alpc_work_on_behalf.py",
         "tests/test_alpc_release_reply.py")


def registrar_sources():
    sources = ["tools/freeze_registrar_cell.py", "tools/server_protocol_gate.py"]
    for key in REGISTRAR_STACK + ("sechost_services", "alpc_connect_attrs", "alpc_sync_request",
                                 "alpc_work_on_behalf", "alpc_release_reply"):
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
    if "sechost_services" in build:
        for relative, value in build["sechost_services"]["files"].items():
            if sha256(root / "source" / relative) != value:
                raise ValueError("Sechost source changed: " + relative)
        result["sechost_services"] = build["sechost_services"]
    return result


def multi_sz(*values):
    data = "".join(value + "\0" for value in values) + "\0"
    return "hex(7):" + ",".join("%02x" % byte for byte in data.encode("utf-16-le"))


def registration_text(transient=False):
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
        '"' + GROUP + '"=' + multi_sz(SERVICE), ""] + ([
        "[" + TRANSIENT_KEY + "]",
        '"SecurityDescriptor"=hex:' + ",".join("%02x" % byte for byte in TRANSIENT_SD), ""] if transient else []) + [""])


def add_registrar_handoff(root, receipt, cell=27):
    if cell not in (27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42):
        raise ValueError("Registrar handoff supports cells027-042")
    label = "%03d" % cell
    root = Path(root)
    registration = root / ("registrar-CELL%s-FROZEN.reg" % label)
    if registration.exists():
        raise FileExistsError("Refuse existing%s registrar registration" % label)
    if cell >= 34 and "sechost_services" not in receipt:
        raise ValueError("Cell034 requires the sechost transient descriptor and WaitServiceState build")
    registration.write_bytes(registration_text(transient=cell >= 34).encode("utf-16"))
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
    if cell >= 34:
        receipt["registrar_transient_readback_argv"] = wine + ["reg", "query", TRANSIENT_KEY.replace("HKEY_LOCAL_MACHINE", "HKLM")]
    for key in REGISTRAR_STACK + (("sechost_services",) if cell >= 34 else ()):
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
    if cell >= 30:
        # Cell029 showed a loaded host needs ~47 s for first boot with the mac driver.
        receipt["setup_wineboot_timeout_seconds"] = 120
        receipt["preconditions"] += [
            "Bound the driver's setup wineboot -u by setup_wineboot_timeout_seconds; setup uses the run environment with the mac driver, as in cell027",
        ]
    if cell >= 28:
        receipt["limitations"] += [
            "Cell027: sc start CoreMessagingRegistrar did not return within45 s under WINEDEBUG=-all; cause unobserved. Wine SCM does not start DependOnService, so RpcSs is not a start wait",
            "Cell028 adds diagnostics only (scoped WINEDEBUG and two services traces around registrar process creation); the token and start path are unchanged",
        ]
    if cell >= 32:
        receipt["services_diagnostics"]["discriminators"] = [
            "'registrar token worker start' then the last 'registrar token step <name>' line before silence or a 'wine client error' line: the construction step that lost the worker thread",
            "'registrar token worker did not finish' (10 s) or 'ended without a result': the worker hung or died; sc start returns an error and the SCM lock stays free",
            "'registrar token construction rejected, error N': construction failed closed; no registrar process is created",
        ] + receipt["services_diagnostics"]["discriminators"]
        receipt["limitations"] += [
            "Cell031: services.exe thread 0060 logged the image path, then 'wine client error:60: read: Bad file descriptor' (client protocol abort) while holding the scmdatabase lock; the failing call inside token construction is unobserved",
            "Cell032 builds the registrar token on a worker thread before the SCM lock, waits at most 10 s and fails closed; this contains the loss but does not fix its cause",
        ]
    if cell >= 33:
        receipt["services_diagnostics"]["discriminators"] = [
            "'wineserver: create_token pid ...' on wineserver stderr: the create_token request reached the server intact; its absence before a 'wine client error' line means the client aborted first",
        ] + receipt["services_diagnostics"]["discriminators"]
        receipt["limitations"] += [
            "Cell032 diagnosis: NtCreateToken added six request data chunks (objattr, identity, user, groups, privileges, DACL) where __SERVER_MAX_DATA is5; the registrar DACL wrote past the client request buffer. Cell033 sends identity with the user SID (five chunks) and a build gate rejects any request above five",
            "Cell033 also fixes a latent six-chunk new_process request (package identity) by appending identity to the job list buffer",
            "Cell032 app 0xC0000002 came from this build's NtAlpcConnectPortEx NOT_IMPLEMENTED paths (client object attributes, EffectiveOnly QoS), not a stub; the ntdll export was already the syscall thunk",
            "Cell033 accepts an unnamed unrooted client port with an optional SACL-free security descriptor and static EffectiveOnly (disabled privileges and disabled optional groups dropped); other client attribute fields and message attributes still return STATUS_NOT_IMPLEMENTED with a FIXME",
            "Identification-level ALPC impersonation still returns STATUS_BAD_IMPERSONATION_LEVEL; CoreMessaging requests SecurityIdentification",
            "Wine treats ALPC port flag 0x40000 as non-blocking receive; CoreMessaging sets port flags 0x70000; native meaning of that bit is unverified here",
        ]
    if cell >= 34:
        receipt["services_diagnostics"]["discriminators"] = [
            "'transient sd type 8 name' then 'transient sd status 0 size 264' (svchost, +service): the registrar read its ALPC port descriptor; a nonzero status names the failed open or query",
            "'reason=transient_type' FIXME: CoreMessaging asked for a transient object type other than the ALPC port",
            "'unimplemented function sechost.dll.' on a svchost thread: another sechost stub stops ServiceMain (cell033 stopped at QueryTransientObjectSecurityDescriptor)",
        ] + receipt["services_diagnostics"]["discriminators"]
        receipt["preconditions"] += [
            "Run registrar_transient_readback_argv right after registrar_readback_argv in the setup session and record its exit and output; a missing SecurityDescriptor value is a setup failure, not an app result",
        ]
        receipt["limitations"] += [
            "Cell033 diagnosis: the svchost thread that ran CoreMessaging ServiceMain aborted in the sechost stub QueryTransientObjectSecurityDescriptor (stub RVA 0x119be), so the service stayed START_PENDING. The SvchostPushServiceGlobals fixme is not the blocker: coremessaging.dll exports it as an empty function (c2 00 00, ret 0)",
            "Cell034 implements QueryTransientObjectSecurityDescriptor for type 8 (ALPC port) from a builtin relay trace of an earlier lane, not native documentation; other types fail closed with STATUS_NOT_IMPLEMENTED and open/query NTSTATUS values are returned unchanged (native failure convention unmeasured)",
            "The WM_RegistrarServer descriptor value is re-authored from an earlier lane's provisioned prefix; its native origin and parity with Windows 26300 are unmeasured",
            "WaitServiceState follows the documented contract with 50 ms QueryServiceStatusEx polling, not service status notifications",
            "NtAlpcConnectPortEx now accepts a receive message attribute buffer (returned with no valid attributes) and refuses send attributes; every remaining NOT_IMPLEMENTED connect path logs a fixed reason token that the collector keeps",
        ]
    if cell >= 35:
        receipt["services_diagnostics"]["discriminators"] = [
            "'transient sd status 0 size 264' (svchost, +service): the structural descriptor check accepted the registered value; 0xc0000079 now means the bytes themselves are malformed",
        ] + receipt["services_diagnostics"]["discriminators"]
        receipt["limitations"] += [
            "Cell034 diagnosis: the 264-byte descriptor is well formed; Wine 11.20 RtlValidRelativeSecurityDescriptor is a semi-stub that compares the BOOLEAN from RtlValidSecurityDescriptor with STATUS_SUCCESS and rejects every valid descriptor, so svchost got 0xc0000079",
            "Cell035 sechost validates the self-relative descriptor structurally (revision, SE_SELF_RELATIVE, owner/group SIDs, SACL/DACL revision, size, ACE count, ACE size alignment and ACE SIDs); the exact frozen .reg bytes and ten corruptions run through that code in a host test",
            "Cell034 app diagnosis: NtAlpcConnectPortEx reason=send_attributes value=0x80000000, the security attribute only",
            "Cell035 admits a connect send security attribute only with Flags 0, no QoS and no context handle, which selects the connection security context already captured at connect; other flags, a QoS, a context handle or any other valid send attribute still fail with reason=send_security_flags|send_security_qos|send_security_context|send_attributes",
            "Valid send attributes outside the allocated set, or allocated bits outside ALPC_MESSAGE_ATTRIBUTE_ALL, return STATUS_INVALID_PARAMETER",
        ]
    if cell >= 36:
        receipt["services_diagnostics"]["discriminators"] = [
            "'reason=send_security_context value=0x...' (alpc FIXME): the connect carried a security context handle other than NULL or (HANDLE)-2; the value names it",
        ] + receipt["services_diagnostics"]["discriminators"]
        receipt["limitations"] += [
            "Cell035 diagnosis: the registrar reached RUNNING; the app connect failed with reason=send_security_context. CoreMessaging (+0x3f428..0x3f4a9) calloc's the security attribute, sets QoS NULL and ContextHandle (HANDLE)-2 and does not import NtAlpcCreateSecurityContext",
            "Cell036 takes ContextHandle (HANDLE)-2 like NULL (the connection security context captured at connect); this native meaning is inferred from CoreMessaging's use, not from public documentation (phnt names no -2 constant)",
            "Any other non-NULL ContextHandle still fails with reason=send_security_context and its value; NtAlpcCreateSecurityContext and NtAlpcDeleteSecurityContext remain unimplemented because CoreMessaging does not call them",
        ]
    if cell >= 37:
        receipt["services_diagnostics"]["discriminators"] = [
            "'wineserver: wait-packet associate target=alpc-port status=00000000' (registered-server-start.log): the registrar re-armed its port wait; status c0000024 would be the cell036 type mismatch",
            "'wineserver: alpc queue kind=0 type=...' (0 is the connection port) then 'alpc alpc_receive_message ... status=00000000 ... type=...' (registered-server-start.log): a connect request was queued on the registrar port and the server dequeued it",
            "'alpc alpc_accept_connect_port ... accept=1' and 'alpc alpc_connect_result ... state=...' (registered-server-start.log): the registrar accepted and the client collected the reply",
            "'return NtAlpc... status ... target ...' (svchost +alpc in services-start.log): registrar-side ALPC syscall statuses",
        ] + receipt["services_diagnostics"]["discriminators"]
        receipt["limitations"] += [
            "Cell036 diagnosis: the registrar port is created with flags 0x70000; 0x40000 (ALPC_PORTFLG_NON_BLOCKING_RECEIVE in Wine's winternl.h, a waitable port in phnt) makes an empty receive return STATUS_UNSUCCESSFUL, which CoreMessaging (+0x277b) treats as no message and then waits through NtAssociateWaitCompletionPacket",
            "Cell036 wineserver accepted only event, timer, semaphore, thread and process wait-packet targets, so the registrar's port wait was rejected with STATUS_OBJECT_TYPE_MISMATCH and the server never woke for the queued connect; that the target handle is the port is inferred from CoreMessaging's call sequence, not traced",
            "Cell037 accepts any ALPC port as a wait-packet target, signalled by the existing queue state; whether native also allows ports created without the waitable flag is unmeasured",
            "Cell037 telemetry is bounded and redacted: app NtAlpc* unix returns (256 lines, pkgstatus, fixed target class registrar|registrar-relative|other|none, no port names), RaiseFailFastException records (8, pkgexception, code/flags/count/module+offset and parameters as 32-bit scalars or module+offset), wineserver connect/accept/receive/queue/wait-packet lines (512 on stderr)",
        ]
    if cell >= 38:
        receipt["services_diagnostics"]["discriminators"] = [
            "'wineserver: alpc alpc_connect_port pid ... status=c00002a0' (registered-server-start.log): the server identity check still rejected the registrar token; status=00000000 with a non-zero handle means the requirement matched",
        ] + receipt["services_diagnostics"]["discriminators"]
        receipt["limitations"] += [
            "Cell037 diagnosis: both app NtAlpcConnectPortEx calls returned STATUS_SERVER_SID_MISMATCH. CoreMessaging passes ServerSecurityRequirements from SDDL D:(A;;0x01;;;S-1-5-80-1021139062-1866602279-1255292388-1008060685-2498416891), the CoreMessagingRegistrar service SID, with no owner or group; Wine's user-mode style access check rejected that descriptor as invalid",
            "Cell038 evaluates the server requirement for port connect (1) from the DACL, deny ACEs, inherit-only flags and restricting SIDs only, because ownership never grants access 1; that the native check omits an owner/group requirement is inferred from kernel SeAccessCheck behavior, not traced",
            "The registrar token carries the service SID as an enabled group (attributes 0xe) and as a restricting SID; the eight unexplained S-1-5-32 groups are still not reproduced",
        ]
    if cell >= 39:
        receipt["services_diagnostics"]["discriminators"] = [
            "'return NtAlpcImpersonateClientOfPort status ...' (svchost +alpc in services-start.log): 0 means the registrar impersonated the client; c00000a5 is a level outside Identification..Impersonation, c0000037 a lost connection, c0000042 a wrong port kind",
            "'reason=impersonate_flags' or 'reason=impersonate_message_on_communication_port' (alpc FIXME): an impersonation shape outside cell039's two supported forms",
        ] + receipt["services_diagnostics"]["discriminators"]
        receipt["limitations"] += [
            "Cell038 diagnosis: identity passed and the registrar received the 0x18-byte connection request, but NtAlpcImpersonateClientOfPort returned STATUS_BAD_IMPERSONATION_LEVEL because only SecurityImpersonation was admitted; CoreMessaging connects at SecurityIdentification, then refused the connection (app 0xC0000041)",
            "Cell039 impersonates at the client's requested level (Identification or Impersonation) for a delivered connection request, and for a NULL message on an accepted server communication port (CoreMessaging +874f1); Anonymous still fails with STATUS_BAD_IMPERSONATION_LEVEL because Wine has no anonymous logon token",
            "Wine's object access checks do not refuse Identification-level thread tokens, so object opens while impersonating at Identification use the client's access where native returns STATUS_BAD_IMPERSONATION_LEVEL; CoreMessaging +7af2c only calls OpenThreadToken(TOKEN_QUERY, OpenAsSelf TRUE) and RevertToSelf",
            "A message-bound impersonation on a server communication port still returns STATUS_NOT_IMPLEMENTED",
        ]
    if cell >= 40:
        receipt["services_diagnostics"]["discriminators"] = [
            "'NtAlpcSendWaitReceivePort status ...' (app alpc telemetry, CoreMessaging +21b6): 0 means the synchronous request got its reply; 0x102 is a timeout waiting for the registrar's reply; c0000002 must now be preceded by an alpc FIXME reason",
            "'reason=send_flags value=...', 'reason=sync_request_shape value=...' or 'reason=send_attrs value=...' (alpc FIXME): a message flag or send attribute outside cell040's supported set",
            "registrar 'RECV port ... type 1' then its NtAlpcSendWaitReceivePort status (services-start.log): type 1 is LPC_REQUEST; a non-zero status on the registrar's reply, such as c000021f, names a reply that did not match the pending request",
        ] + receipt["services_diagnostics"]["discriminators"]
        receipt["limitations"] += [
            "Cell039 diagnosis: the handshake succeeded, then the app's first NtAlpcSendWaitReceivePort (CoreMessaging +21b6) returned STATUS_NOT_IMPLEMENTED from an unlabeled flag gate; the call carries ALPC_MSGFLG_SYNC_REQUEST (0x20000) and a CONTEXT attribute",
            "Wine 11.20's winternl.h defined ALPC_MSGFLG_REPLY_MESSAGE as 0x10000, which is the native RELEASE_MESSAGE; cell040 uses the native 0x1 (phnt ntlpcapi.h), so a native reply is now routed as a reply",
            "RELEASE_MESSAGE is a no-op outside a synchronous send because wineserver frees each message when it is received; TRACK_PORT_REFERENCES, LPC_MODE and the remaining bits still return STATUS_NOT_IMPLEMENTED with a reason",
            "A non-zero MessageId without the reply flag is sent as a new message; whether native treats it as a reply was not traced",
        ]
    if cell >= 41:
        receipt["services_diagnostics"]["discriminators"] = [
            "'reason=send_attrs value=...' (alpc FIXME): a send attribute other than CONTEXT or WORK_ON_BEHALF; value=0x2000000 must no longer appear",
            "'RtlGetThreadWorkOnBehalfTicket' or 'RtlSetThreadWorkOnBehalfTicket' coremessaging-stub hits: a caller reached the ticket functions; a received message never carries a valid WORK_ON_BEHALF attribute in cell041",
        ] + receipt["services_diagnostics"]["discriminators"]
        receipt["limitations"] += [
            "Cell040 diagnosis: the app's first NtAlpcSendWaitReceivePort (CoreMessaging +21b6) returned STATUS_NOT_IMPLEMENTED with 'reason=send_attrs value=0x2000000'; CoreMessaging allocates 0xe2000000 attributes and marks CONTEXT and WORK_ON_BEHALF (0x22000000) valid on the buffer it sends and receives with; the app then failed fast with 0xd0000002",
            "Cell041 accepts the WORK_ON_BEHALF send attribute without reading or carrying its 8-byte ticket, and a receive never marks it valid; Wine has no thread work-on-behalf tickets (both Rtl ticket functions are NOT_IMPLEMENTED stubs), and CoreMessaging's receive path handles a message without the attribute normally (read for understanding only)",
            "Native propagates the sender's work-on-behalf ticket to the receiver for priority and accounting; that propagation is not reproduced",
        ]
    if cell >= 42:
        receipt["services_diagnostics"]["discriminators"] = [
            "registrar SENDHEADER on listener 0x74 with flags 0x10000, Type=1 and original MessageId/ClientId: its NtAlpcSendWaitReceivePort must route the response rather than return STATUS_INVALID_PORT_HANDLE",
            "wineserver queue type=2 with the request id, followed by the app's matching receive: a correlated RELEASE response reached the client; c000021f is a missing, undelivered, reused or mismatched pending identity",
        ] + receipt["services_diagnostics"]["discriminators"]
        receipt["limitations"] += [
            "Cell041 ran once but the collector timed out with a truncated trace; target state is unknown. The recovered request id257 was delivered to the registrar, whose RELEASE_MESSAGE response reused the received Type=1 header on listener 0x74 and returned STATUS_INVALID_PORT_HANDLE",
            "Cell042 supersedes cell040's RELEASE no-op and nonzero-MessageId limitations for RELEASE plus nonzero MessageId: a response must match a delivered pending request by original ClientId, callback and endpoint, and consumes that pending record exactly once",
            "This release-response contract is inferred from CoreMessaging's response construction (read for understanding only) and tested against our real server handlers, not measured on native Windows; other ALPC retained-message, callback and release-only forms are not implemented",
        ]


# Setup-session steps that run before the setup server stop; none needs a display.
SETUP_ARGVS = ("framework_registration_argv", "launcher_registration_argv", "native_xaml_registration_argv",
               "aedebug_registration_argv", "registrar_registration_argv", "registrar_readback_argv")


def add_headless_setup(receipt):
    """Cell029 only: winemac.drv=d setup. Superseded in cell030: explorer /desktop hangs after imm32 with
    the driver disabled, because a disabled module is not Wine's null driver fallback."""
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
