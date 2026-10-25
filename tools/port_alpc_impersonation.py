"""Authenticate delivered ALPC connection requests without caller-PID lookup."""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_alpc_impersonation.py",)


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned ALPC impersonation source")
    paths = ("server/alpc.c", "server/token.c", "server/security.h",
             "server/protocol.def", "dlls/ntdll/unix/alpc.c")
    server = (source / paths[0]).read_text()
    if "DECL_HANDLER(alpc_impersonate_connection)" in server:
        raise ValueError("Require fresh ALPC impersonation source")
    server = replace(server, "    struct token      *creator_token;",
        "    thread_id_t        creator_tid;\n    unsigned int       impersonation_level;\n"
        "    struct token      *creator_token;")
    server = replace(server, "    port->owner_pid = get_process_id( current->process );",
        "    port->owner_pid = get_process_id( current->process );\n"
        "    port->creator_tid = get_thread_id( current );\n"
        "    port->impersonation_level = SecurityAnonymous;")
    start = server.index("DECL_HANDLER(alpc_connect_port)")
    end = server.index("\nDECL_HANDLER(", start + 1)
    section = server[start:end]
    section = replace(section, "    if (req->identity_size > len)",
        "    if (req->impersonation_level > SecurityImpersonation)\n"
        "    { release_object( conn ); set_error( STATUS_BAD_IMPERSONATION_LEVEL ); return; }\n"
        "    if (req->identity_size > len)")
    section = replace(section, "    client->connect_flags = req->connect_flags;",
        "    client->connect_flags = req->connect_flags;\n"
        "    client->impersonation_level = req->impersonation_level;")
    server = server[:start] + section + server[end:]
    server += """

/* This slice authenticates only received, unaccepted connection requests. */
DECL_HANDLER(alpc_impersonate_connection)
{
    struct alpc_port *port = get_port( req->handle );
    struct alpc_pending *pending;

    if (!port) return;
    if (port->kind != CONNECTION_PORT || port->state == ALPC_CLOSED ||
        port->owner_pid != get_process_id( current->process ))
    { set_error( STATUS_INVALID_PORT_HANDLE ); goto done; }
    LIST_FOR_EACH_ENTRY( pending, &port->pending, struct alpc_pending, entry )
    {
        struct alpc_port *client = pending->port;
        if (pending->id != req->msg_id) continue;
        if (client->kind != CLIENT_PORT || client->state != ALPC_NEW || client->conn != port ||
            req->pid != client->owner_pid || req->tid != client->creator_tid)
        { set_error( STATUS_REPLY_MESSAGE_MISMATCH ); goto done; }
        if (client->impersonation_level != SecurityImpersonation)
        { set_error( STATUS_BAD_IMPERSONATION_LEVEL ); goto done; }
        token_impersonate_alpc( client->creator_token );
        goto done;
    }
    set_error( STATUS_REPLY_MESSAGE_MISMATCH );
done:
    release_object( port );
}
"""
    token = (source / paths[1]).read_text() + """

int token_impersonate_alpc( struct token *source )
{
    struct token *copy;

    if (!thread_single_check_privilege( current, SeImpersonatePrivilege ))
    { set_error( STATUS_PRIVILEGE_NOT_HELD ); return 0; }
    if (!(copy = token_duplicate( source, 0, SecurityImpersonation, NULL, NULL, 0, NULL, 0 ))) return 0;
    if (current->token) release_object( current->token );
    current->token = copy;
    return 1;
}
"""
    security = replace((source / paths[2]).read_text(), "extern int token_alpc_identity(",
        "extern int token_impersonate_alpc( struct token * );\nextern int token_alpc_identity(")
    protocol = replace((source / paths[3]).read_text(),
        "    unsigned int  identity_kind;  /* 0 none, 1 user SID, 2 server security descriptor */",
        "    unsigned int  impersonation_level; /* client-authorized static QoS level */\n"
        "    unsigned int  identity_kind;  /* 0 none, 1 user SID, 2 server security descriptor */")
    protocol += """

/* Impersonate a server-owned delivered connection identity, never a supplied PID. */
@REQ(alpc_impersonate_connection)
    obj_handle_t handle;
    unsigned int msg_id;
    process_id_t pid;
    thread_id_t tid;
@END
"""
    client = (source / paths[4]).read_text()
    begin = client.index("static NTSTATUS connect_port(")
    end = client.index("NTSTATUS WINAPI NtAlpcConnectPort(", begin)
    section = replace(client[begin:end], "    if (pa && pa->MaxMessageLength > 0x8000) return STATUS_NOT_IMPLEMENTED;",
        "    if (pa && pa->MaxMessageLength > 0x8000) return STATUS_NOT_IMPLEMENTED;\n"
        "    if (pa && (pa->SecurityQos.Length != sizeof(pa->SecurityQos) ||\n"
        "        pa->SecurityQos.ImpersonationLevel > SecurityImpersonation ||\n"
        "        pa->SecurityQos.ContextTrackingMode != SECURITY_STATIC_TRACKING ||\n"
        "        pa->SecurityQos.EffectiveOnly)) return STATUS_NOT_IMPLEMENTED;")
    client = client[:begin] + section + client[end:]
    client = replace(client, "        req->identity_kind = identity_kind;",
        "        req->impersonation_level = pa ? pa->SecurityQos.ImpersonationLevel : SecurityAnonymous;\n"
        "        req->identity_kind = identity_kind;")
    client = replace(client,
        '    FIXME("Message-bound ALPC impersonation is not implemented.\\n");\n'
        "    return STATUS_NOT_IMPLEMENTED;",
        """    NTSTATUS status;
    if (!msg) return STATUS_ACCESS_VIOLATION;
    if (flags) return STATUS_NOT_IMPLEMENTED;
    if ((ULONG_PTR)msg->ClientId.UniqueProcess > ~(unsigned int)0 ||
        (ULONG_PTR)msg->ClientId.UniqueThread > ~(unsigned int)0) return STATUS_INVALID_CID;
    SERVER_START_REQ( alpc_impersonate_connection )
    {
        req->handle = wine_server_obj_handle( port );
        req->msg_id = msg->MessageId;
        req->pid = (ULONG_PTR)msg->ClientId.UniqueProcess;
        req->tid = (ULONG_PTR)msg->ClientId.UniqueThread;
        status = wine_server_call( req );
    }
    SERVER_END_REQ;
    return status;""")
    for path, text in zip(paths, (server, token, security, protocol, client)):
        (source / path).write_text(text)
    return {"files": {p: sha256(source / p) for p in paths}, "registrar_qualified": False,
            "scope": "delivered connection requests only; static SecurityImpersonation QoS; SeImpersonatePrivilege"}
