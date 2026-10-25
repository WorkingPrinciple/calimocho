"""Route a release response using its delivered message identity, not its header type."""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_alpc_release_reply.py",)
PATHS = ("server/alpc.c", "server/protocol.def", "dlls/ntdll/unix/alpc.c")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned ALPC release reply source")
    server, protocol, client = ((source / path).read_text() for path in PATHS)
    if "MSGFLG_RELEASE_MESSAGE" in server:
        raise ValueError("Require fresh ALPC release reply source")
    if "alpc_send_attrs_status" not in client:
        raise ValueError("Require the ALPC work-on-behalf port first")
    server = replace(server,
        "#define MSGFLG_REPLY_MESSAGE   ALPC_MSGFLG_REPLY_MESSAGE",
        "#define MSGFLG_REPLY_MESSAGE   ALPC_MSGFLG_REPLY_MESSAGE\n"
        "#define MSGFLG_RELEASE_MESSAGE 0x00010000")
    server = replace(server,
        "    struct alpc_port *port;      /* owned */\n};",
        "    struct alpc_port *port;      /* owned */\n"
        "    process_id_t      pid;\n"
        "    thread_id_t       tid;\n"
        "    unsigned int      callback_id;\n"
        "    int               delivered;\n};")
    server = replace(server,
        "    if (req->flags & MSGFLG_REPLY_MESSAGE)\n",
        "    if ((req->flags & MSGFLG_REPLY_MESSAGE) ||\n"
        "        ((req->flags & MSGFLG_RELEASE_MESSAGE) && req->msg_id))\n")
    server = replace(server,
        "        release_dest = 1;\n"
        "        if (port->kind == SERVER_PORT && dest != port->peer)",
        "        release_dest = 1;\n"
        "        if (!(req->flags & MSGFLG_REPLY_MESSAGE))\n"
        "        {\n"
        "            struct alpc_pending *pending;\n"
        "            LIST_FOR_EACH_ENTRY( pending, &reply_registry->pending, struct alpc_pending, entry )\n"
        "                if (pending->id == id) break;\n"
        "            /* A release response reuses a delivered header, including its original ClientId. */\n"
        "            if (!pending->delivered || pending->pid != req->pid || pending->tid != req->tid ||\n"
        "                pending->callback_id != req->callback_id ||\n"
        "                (port->kind == CONNECTION_PORT && (dest->kind != CLIENT_PORT || dest->conn != port)) ||\n"
        "                (port->kind != CONNECTION_PORT && dest != port->peer))\n"
        "            { set_error( STATUS_REPLY_MESSAGE_MISMATCH ); goto done; }\n"
        "        }\n"
        "        if (port->kind == SERVER_PORT && dest != port->peer)")
    server = replace(server,
        "        p->id = id;\n"
        "        p->port = (struct alpc_port *)grab_object( port );",
        "        p->id = id;\n"
        "        p->pid = msg->pid;\n"
        "        p->tid = msg->tid;\n"
        "        p->callback_id = msg->callback_id;\n"
        "        p->delivered = 0;\n"
        "        p->port = (struct alpc_port *)grab_object( port );")
    server = replace(server,
        "            p->id = msg->id;\n",
        "            p->id = msg->id;\n"
        "            p->pid = p->tid = p->callback_id = 0;\n"
        "            p->delivered = 0;\n")
    begin = server.index("DECL_HANDLER(alpc_receive_message)")
    section = replace(server[begin:],
        "    if (msg->size <= get_reply_max_size()) set_reply_data( msg->data, msg->size );",
        "    if (msg->type == LPC_REQUEST)\n"
        "    {\n"
        "        struct alpc_pending *pending;\n"
        "        LIST_FOR_EACH_ENTRY( pending, &port->pending, struct alpc_pending, entry )\n"
        "            if (pending->id == msg->id) { pending->delivered = 1; break; }\n"
        "    }\n\n"
        "    if (msg->size <= get_reply_max_size()) set_reply_data( msg->data, msg->size );")
    server = server[:begin] + section
    protocol = replace(protocol,
        "    int           request;        /* a reply is expected */\n",
        "    int           request;        /* a reply is expected */\n"
        "    unsigned int  pid;            /* original sender for a release response */\n"
        "    unsigned int  tid;            /* original sender for a release response */\n")
    client = replace(client,
        "            req->flags = flags & ALPC_MSGFLG_REPLY_MESSAGE;",
        "            req->flags = flags & (ALPC_MSGFLG_REPLY_MESSAGE | ALPC_MSGFLG_RELEASE_MESSAGE);\n"
        "            req->pid = (ULONG_PTR)send->ClientId.UniqueProcess;\n"
        "            req->tid = (ULONG_PTR)send->ClientId.UniqueThread;")
    client = replace(client,
        "    if (send)\n    {\n        ALPC_CONTEXT_ATTR *ctx",
        "    if (send && (flags & ALPC_MSGFLG_RELEASE_MESSAGE) && send->MessageId &&\n"
        "        ((ULONG_PTR)send->ClientId.UniqueProcess > ~(unsigned int)0 ||\n"
        "         (ULONG_PTR)send->ClientId.UniqueThread > ~(unsigned int)0)) return STATUS_INVALID_CID;\n"
        "    if (send)\n    {\n        ALPC_CONTEXT_ATTR *ctx")
    for path, text in zip(PATHS, (server, protocol, client)):
        (source / path).write_text(text)
    return {"files": {p: sha256(source / p) for p in PATHS},
            "release_response": "RELEASE plus nonzero MessageId matches a delivered pending request by original ClientId, callback and endpoint",
            "reply_header": "received LPC_REQUEST headers may be reused; the delivered response is LPC_REPLY",
            "validation": "unknown, undelivered, duplicate or cross-endpoint identities return REPLY_MESSAGE_MISMATCH",
            "native_limit": "inferred from native CoreMessaging response construction; no Windows differential run"}
