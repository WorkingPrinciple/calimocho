"""Bind ALPC connect identity checks to the server's captured creator token."""
from pathlib import Path

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_alpc_identity.py",)


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned ALPC identity source")
    paths = ("server/alpc.c", "server/token.c", "server/security.h",
             "server/protocol.def", "dlls/ntdll/unix/alpc.c")
    server = (source / "server/alpc.c").read_text()
    if "creator_token" in server:
        raise ValueError("Require fresh ALPC identity source")
    server = replace(server,
        "    process_id_t       owner_pid;",
        "    process_id_t       owner_pid;\n    struct token      *creator_token;")
    server = replace(server, "    if (port->sync) release_object( port->sync );",
        "    if (port->sync) release_object( port->sync );\n"
        "    if (port->creator_token) release_object( port->creator_token );")
    server = replace(server, "    port->sync = NULL;",
        "    port->creator_token = NULL;\n    port->sync = NULL;")
    server = replace(server,
        "    if (!(port->sync = create_internal_sync( 1, 0 )))",
        "    if (!(port->creator_token = token_duplicate( thread_get_impersonation_token( current ),\n"
        "                                                   0, SecurityImpersonation, NULL, NULL, 0, NULL, 0 )))\n"
        "    {\n        release_object( port );\n        return NULL;\n    }\n"
        "    if (!(port->sync = create_internal_sync( 1, 0 )))")
    server = replace(server,
        "    if (len > 0x8000 || (conn->max_msg_len && len > conn->max_msg_len))",
        "    if (req->identity_size > len)\n"
        "    {\n        release_object( conn );\n        set_error( STATUS_INVALID_PARAMETER );\n        return;\n    }\n"
        "    if (req->identity_kind)\n"
        "    {\n"
        "        int matches;\n"
        "        if (req->identity_kind == 1)\n"
        "        {\n"
        "            const struct sid *sid = data;\n"
        "            if (!sid_valid_size( sid, req->identity_size ) || sid_len( sid ) != req->identity_size)\n"
        "            { release_object( conn ); set_error( STATUS_INVALID_SID ); return; }\n"
        "            matches = token_alpc_identity( conn->creator_token, sid, NULL, &alpc_port_type.mapping );\n"
        "        }\n"
        "        else if (req->identity_kind == 2)\n"
        "        {\n"
        "            const struct security_descriptor *sd = data;\n"
        "            if (!sd_is_valid( sd, req->identity_size ))\n"
        "            { release_object( conn ); set_error( STATUS_INVALID_SECURITY_DESCR ); return; }\n"
        "            matches = token_alpc_identity( conn->creator_token, NULL, sd, &alpc_port_type.mapping );\n"
        "        }\n"
        "        else { release_object( conn ); set_error( STATUS_INVALID_PARAMETER ); return; }\n"
        "        if (!matches)\n"
        "        { release_object( conn ); set_error( STATUS_SERVER_SID_MISMATCH ); return; }\n"
        "    }\n"
        "    else if (req->identity_size)\n"
        "    { release_object( conn ); set_error( STATUS_INVALID_PARAMETER ); return; }\n"
        "    data = (const char *)data + req->identity_size;\n    len -= req->identity_size;\n"
        "    if (len > 0x8000 || (conn->max_msg_len && len > conn->max_msg_len))")
    protocol = (source / "server/protocol.def").read_text()
    protocol = replace(protocol,
        "    unsigned int  connect_flags;  /* synchronous or asynchronous connection */",
        "    unsigned int  connect_flags;  /* synchronous or asynchronous connection */\n"
        "    unsigned int  identity_kind;  /* 0 none, 1 user SID, 2 server security descriptor */\n"
        "    data_size_t   identity_size;  /* identity bytes before connection message */")
    protocol = replace(protocol,
        "    VARARG(message,bytes);        /* connection message (after objattr) */",
        "    VARARG(identity,bytes,identity_size); /* required server identity */\n"
        "    VARARG(message,bytes);        /* connection message (after objattr and identity) */")
    token = (source / "server/token.c").read_text()
    token = replace(token, "const struct acl *token_get_default_dacl(",
        """int token_alpc_identity( struct token *token, const struct sid *user,
                          const struct security_descriptor *sd, const struct generic_map *mapping )
{
    unsigned int status, granted;

    if (user) return equal_sid( token->user, user );
    return token_access_check( token, sd, 1, NULL, NULL, mapping, &granted, &status ) == STATUS_SUCCESS &&
           status == STATUS_SUCCESS && (granted & 1);
}

const struct acl *token_get_default_dacl(""")
    security = (source / "server/security.h").read_text()
    security = replace(security, "extern int check_object_access(",
        "extern int token_alpc_identity( struct token *, const struct sid *,\n"
        "                                const struct security_descriptor *, const struct generic_map * );\n"
        "extern int check_object_access(")
    client = (source / "dlls/ntdll/unix/alpc.c").read_text()
    client = replace(client,
        "                              const LARGE_INTEGER *timeout, void *context )",
        "                              const LARGE_INTEGER *timeout, void *context,\n"
        "                              const void *identity, data_size_t identity_size, unsigned int identity_kind )")
    client = replace(client, "        req->connect_flags = flags;",
        "        req->connect_flags = flags;\n"
        "        req->identity_kind = identity_kind;\n        req->identity_size = identity_size;")
    client = replace(client,
        "        if (msg_size) wine_server_add_data( req, msg + 1, msg_size );",
        "        if (identity_size) wine_server_add_data( req, identity, identity_size );\n"
        "        if (msg_size) wine_server_add_data( req, msg + 1, msg_size );")
    client = client.replace("if (sd || client_attr || out_attrs || in_attrs)", "if (client_attr || out_attrs || in_attrs)")
    begin = client.index("NTSTATUS WINAPI NtAlpcConnectPort(")
    end = client.index("NTSTATUS WINAPI NtAlpcConnectPortEx(", begin)
    normal = client[begin:end]
    normal = replace(normal,
        "    InitializeObjectAttributes( &attr, name, 0, 0, NULL );",
        "    if (sd && (((SID *)sd)->Revision != SID_REVISION ||\n"
        "        ((SID *)sd)->SubAuthorityCount > SID_MAX_SUB_AUTHORITIES)) return STATUS_INVALID_SID;\n"
        "    InitializeObjectAttributes( &attr, name, 0, 0, NULL );")
    normal = replace(normal,
        "timeout, NULL );",
        "timeout, NULL, sd,\n"
        "                         sd ? offsetof(SID, SubAuthority[((SID *)sd)->SubAuthorityCount]) : 0, sd ? 1 : 0 );")
    client = client[:begin] + normal + client[end:]
    begin = client.index("NTSTATUS WINAPI NtAlpcConnectPortEx(")
    end = client.index("/***********************************************************************", begin)
    extended = client[begin:end]
    body = extended.index("\n{") + 2
    extended = extended[:body] + """
    OBJECT_ATTRIBUTES security_attr;
    struct object_attributes *packed = NULL;
    data_size_t packed_size;
    NTSTATUS status;
""" + extended[body:]
    extended = replace(extended,
        "    return connect_port( handle, port_attr, pa, flags, msg, length, out_attrs, in_attrs, timeout, NULL );",
        "    if (sd)\n"
        "    {\n"
        "        InitializeObjectAttributes( &security_attr, NULL, 0, NULL, sd );\n"
        "        if ((status = wine_server_alloc_object_attributes( &security_attr, &packed, &packed_size ))) return status;\n"
        "    }\n"
        "    status = connect_port( handle, port_attr, pa, flags, msg, length, out_attrs, in_attrs, timeout,\n"
        "                           NULL, packed ? packed + 1 : NULL, packed ? packed->sd_len : 0, packed ? 2 : 0 );\n"
        "    free( packed );\n    return status;")
    client = client[:begin] + extended + client[end:]
    for relative, text in zip(paths, (server, token, security, protocol, client)):
        (source / relative).write_text(text)
    return {"files": {p: sha256(source / p) for p in paths}, "registrar_qualified": False,
            "server_identity": "creator effective token snapshot; no client PID or caller-supplied token"}
