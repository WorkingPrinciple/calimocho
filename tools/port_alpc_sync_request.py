"""Use native ALPC message flag values and accept synchronous requests.

Wine 11.20's winternl.h gives ALPC_MSGFLG_REPLY_MESSAGE the value 0x10000.
The native value is 0x1; 0x10000 is ALPC_MSGFLG_RELEASE_MESSAGE (phnt
ntlpcapi.h). A native server that replies with 0x1 was therefore sent as a
new message, and a native 0x10000 was read as a reply. The header now uses
0x1, so ntdll and wineserver agree with native callers.

NtAlpcSendWaitReceivePort checks flags in one pure helper:
- SYNC_REQUEST needs a send message and a receive buffer, and no reply flag.
  It sends a request and waits for the reply with the same message id on the
  same port (the existing match loop).
- RELEASE_MESSAGE with a synchronous send is STATUS_INVALID_PARAMETER, as on
  native. Otherwise it is accepted: wineserver frees a message when it is
  received, so there is no retained message to release.
- WAIT_USER_MODE and WAIT_ALERTABLE only change the wait.
- The native internal reject bit is STATUS_INVALID_PARAMETER.
- Any other bit is STATUS_NOT_IMPLEMENTED with "reason=send_flags value=".
Only the reply bit reaches wineserver. A send attribute other than CONTEXT
is STATUS_NOT_IMPLEMENTED with "reason=send_attrs value=".
A non-zero MessageId without the reply flag is not treated as a reply.
"""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_alpc_sync_request.py",)
PATHS = ("include/winternl.h", "dlls/ntdll/unix/alpc.c")

FLAG_HELPER = """#define ALPC_MSGFLG_LPC_MODE 0x00000002
#define ALPC_MSGFLG_RELEASE_MESSAGE 0x00010000
#define ALPC_MSGFLG_TRACK_PORT_REFERENCES 0x00040000
#define ALPC_MSGFLG_WAIT_USER_MODE 0x00100000
#define ALPC_MSGFLG_INTERNAL_REJECT 0x01000000

/* Native ALPC_MSGFLG values (phnt ntlpcapi.h); FIXME reasons carry fixed tokens and masks only. */
static NTSTATUS alpc_send_flags_status( ULONG flags, BOOL send, BOOL recv )
{
    static const ULONG supported = ALPC_MSGFLG_REPLY_MESSAGE | ALPC_MSGFLG_RELEASE_MESSAGE |
                                   ALPC_MSGFLG_SYNC_REQUEST | ALPC_MSGFLG_WAIT_USER_MODE |
                                   ALPC_MSGFLG_WAIT_ALERTABLE;

    if (flags & ALPC_MSGFLG_INTERNAL_REJECT) return STATUS_INVALID_PARAMETER;
    if (flags & ~supported)
    {
        FIXME( "reason=send_flags value=%#x\\n", (unsigned)(flags & ~supported) );
        return STATUS_NOT_IMPLEMENTED;
    }
    if (!(flags & ALPC_MSGFLG_SYNC_REQUEST)) return STATUS_SUCCESS;
    if (send && (flags & ALPC_MSGFLG_RELEASE_MESSAGE)) return STATUS_INVALID_PARAMETER;
    if (!send || !recv || (flags & ALPC_MSGFLG_REPLY_MESSAGE))
    {
        FIXME( "reason=sync_request_shape value=%#x\\n",
               (unsigned)((send ? 1 : 0) | (recv ? 2 : 0) | ((flags & ALPC_MSGFLG_REPLY_MESSAGE) ? 4 : 0)) );
        return STATUS_NOT_IMPLEMENTED;
    }
    return STATUS_SUCCESS;
}

"""


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned ALPC sync request source")
    header = (source / PATHS[0]).read_text()
    client = (source / PATHS[1]).read_text()
    if "alpc_send_flags_status" in client:
        raise ValueError("Require fresh ALPC sync request source")
    header = replace(header,
        "#define ALPC_MSGFLG_REPLY_MESSAGE               0x00010000 /* Message is a reply */",
        "#define ALPC_MSGFLG_REPLY_MESSAGE               0x00000001 /* Message is a reply (native value) */")

    client = replace(client, "#define ALPC_MSGFLG_WAIT_ALERTABLE 0x00200000\n",
                     "#define ALPC_MSGFLG_WAIT_ALERTABLE 0x00200000\n" + FLAG_HELPER)
    begin = client.index("NTSTATUS WINAPI NtAlpcSendWaitReceivePort(")
    finish = client.index("NtAlpcImpersonateClientOfPort", begin)
    section = client[begin:finish]
    section = replace(section,
        "    if (flags & ~(ALPC_MSGFLG_REPLY_MESSAGE | ALPC_MSGFLG_WAIT_ALERTABLE))\n"
        "        return STATUS_NOT_IMPLEMENTED;\n"
        "    if (send_attrs && (send_attrs->ValidAttributes & ~ALPC_MESSAGE_CONTEXT_ATTRIBUTE))\n"
        "        return STATUS_NOT_IMPLEMENTED;\n",
        "    if ((status = alpc_send_flags_status( flags, send != NULL, recv != NULL ))) return status;\n"
        "    if (send_attrs && (send_attrs->ValidAttributes & ~ALPC_MESSAGE_CONTEXT_ATTRIBUTE))\n"
        "    {\n"
        "        FIXME( \"reason=send_attrs value=%#x\\n\",\n"
        "               (unsigned)(send_attrs->ValidAttributes & ~ALPC_MESSAGE_CONTEXT_ATTRIBUTE) );\n"
        "        return STATUS_NOT_IMPLEMENTED;\n"
        "    }\n")
    section = replace(section, "            req->flags = flags;\n",
                      "            req->flags = flags & ALPC_MSGFLG_REPLY_MESSAGE;\n")
    client = client[:begin] + section + client[finish:]

    for path, text in zip(PATHS, (header, client)):
        (source / path).write_text(text)
    return {"files": {p: sha256(source / p) for p in PATHS},
            "reply_flag": "ALPC_MSGFLG_REPLY_MESSAGE is the native 0x1; 0x10000 is RELEASE_MESSAGE",
            "accepted_flags": "REPLY, RELEASE (no-op unless with a synchronous send), SYNC_REQUEST, WAIT_USER_MODE, WAIT_ALERTABLE",
            "sync_request": "send plus receive buffer, waits for the reply with the sent message id",
            "server_flags": "only the reply bit is sent to wineserver",
            "fixme_reasons": "send_flags, sync_request_shape and send_attrs carry one numeric mask",
            "message_id_reply": "a non-zero MessageId without the reply flag is not a reply"}
