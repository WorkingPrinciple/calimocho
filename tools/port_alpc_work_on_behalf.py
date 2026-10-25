"""Accept the ALPC work-on-behalf send attribute without inventing a ticket.

Cell040 showed the app's first NtAlpcSendWaitReceivePort (CoreMessaging
+21b6) rejected with "reason=send_attrs value=0x2000000". CoreMessaging
allocates one attribute buffer with SECURITY, VIEW, CONTEXT and
WORK_ON_BEHALF (0xe2000000), marks CONTEXT and WORK_ON_BEHALF valid
(0x22000000), and both sends and receives with it. When a received message
has a valid WORK_ON_BEHALF attribute, it reads its own ticket with
RtlGetThreadWorkOnBehalfTicket and adopts the received one only if that call
succeeds; otherwise it handles the message normally (read for understanding
only).

Wine has no thread work-on-behalf tickets: both Rtl ticket functions are
explicit NOT_IMPLEMENTED stubs. So the send accepts the attribute and does
not read or carry its 8 bytes, and a receive never marks it valid. No ticket
value is invented. Send attributes are checked in one pure helper:
- valid bits not allocated return STATUS_INVALID_PARAMETER;
- CONTEXT and WORK_ON_BEHALF are accepted;
- anything else is STATUS_NOT_IMPLEMENTED with "reason=send_attrs value=".
"""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_alpc_work_on_behalf.py",)
PATHS = ("dlls/ntdll/unix/alpc.c",)

ATTRS_HELPER = """/* Wine has no thread work-on-behalf tickets (the Rtl ticket functions are stubs), so the
 * attribute is accepted on send without reading or carrying its ticket, and a receive never
 * marks it valid. FIXME reasons carry a fixed token and the unsupported mask only. */
static NTSTATUS alpc_send_attrs_status( ULONG allocated, ULONG valid )
{
    static const ULONG supported = ALPC_MESSAGE_CONTEXT_ATTRIBUTE | ALPC_MESSAGE_WORK_ON_BEHALF_ATTRIBUTE;

    if (valid & ~allocated) return STATUS_INVALID_PARAMETER;
    if (valid & ~supported)
    {
        FIXME( "reason=send_attrs value=%#x\\n", (unsigned)(valid & ~supported) );
        return STATUS_NOT_IMPLEMENTED;
    }
    return STATUS_SUCCESS;
}

"""

OLD_GATE = (
    "    if (send_attrs && (send_attrs->ValidAttributes & ~ALPC_MESSAGE_CONTEXT_ATTRIBUTE))\n"
    "    {\n"
    "        FIXME( \"reason=send_attrs value=%#x\\n\",\n"
    "               (unsigned)(send_attrs->ValidAttributes & ~ALPC_MESSAGE_CONTEXT_ATTRIBUTE) );\n"
    "        return STATUS_NOT_IMPLEMENTED;\n"
    "    }\n"
    "    if (send_attrs && (send_attrs->ValidAttributes & ~send_attrs->AllocatedAttributes))\n"
    "        return STATUS_INVALID_PARAMETER;\n")
NEW_GATE = (
    "    if (send_attrs && (status = alpc_send_attrs_status( send_attrs->AllocatedAttributes,\n"
    "                                                        send_attrs->ValidAttributes )))\n"
    "        return status;\n")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned ALPC work-on-behalf source")
    client = (source / PATHS[0]).read_text()
    if "alpc_send_attrs_status" in client:
        raise ValueError("Require fresh ALPC work-on-behalf source")
    if "alpc_send_flags_status" not in client:
        raise ValueError("Require the ALPC sync request port first")
    client = replace(client, "#define LPC_REQUEST ALPC_MESSAGE_TYPE_REQUEST\n",
                     ATTRS_HELPER + "#define LPC_REQUEST ALPC_MESSAGE_TYPE_REQUEST\n")
    begin = client.index("NTSTATUS WINAPI NtAlpcSendWaitReceivePort(")
    finish = client.index("NtAlpcImpersonateClientOfPort", begin)
    section = replace(client[begin:finish], OLD_GATE, NEW_GATE)
    client = client[:begin] + section + client[finish:]
    received = client[client.index("static NTSTATUS fill_received("):]
    received = received[:received.index("\n}\n")]
    if "WORK_ON_BEHALF" in received:
        raise ValueError("A receive must not mark the work-on-behalf attribute valid")
    (source / PATHS[0]).write_text(client)
    return {"files": {p: sha256(source / p) for p in PATHS},
            "accepted_send_attributes": "CONTEXT and WORK_ON_BEHALF",
            "work_on_behalf": "accepted on send; its ticket is not read or carried, and a receive never marks it valid",
            "invalid_parameter": "valid send attributes that are not allocated",
            "fixme_reasons": "send_attrs carries the unsupported mask"}
