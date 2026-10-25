"""Port the pinned local Wine ALPC transport into an unfrozen owned source tree."""
import hashlib
from pathlib import Path
import re
import subprocess

from tools.build_launcher_overlay import REPO
from tools.probe_wine_source import sha256

HISTORICAL = Path("/Users/dragoshont/xodus-runs/wine-v20-src")
COMMIT = "3ee99fb8caee9af215021f407d6710c9f0d25b4c"
SOURCES = ("tools/port_alpc_transport.py",)
CREATOR_ACCESS_EVIDENCE = {
    "repository": "/Users/dragoshont/xbox-install/xm",
    "commit": "c1ad52800417fa8be1c3783b733b3cacffcd59aa",
    "path": "scripts/macos/compatibility/xaml-startup/probe-outputs/native-alpc-creator-access.txt",
    "sha256": "5462b0d29a1c108e5a4ce91fccec1e1372a1f6f01e7c71b3bba85092d3d5844b",
}


def historical(relative):
    return subprocess.check_output(
        ["git", "--no-replace-objects", "show", COMMIT + ":" + relative], cwd=HISTORICAL).decode()


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Unexpected ALPC source seam: " + old[:100])
    return text.replace(old, new)


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned ALPC source")
    evidence = CREATOR_ACCESS_EVIDENCE
    blob = subprocess.check_output([
        "git", "--no-replace-objects", "show", evidence["commit"] + ":" + evidence["path"],
    ], cwd=evidence["repository"])
    if hashlib.sha256(blob).hexdigest() != evidence["sha256"]:
        raise ValueError("Native creator-access evidence changed")
    inputs = {}

    def read(relative):
        text = historical(relative)
        inputs[relative] = hashlib.sha256(text.encode()).hexdigest()
        return text

    server = read("server/alpc.c")
    client = read("dlls/ntdll/unix/alpc.c")
    protocol = read("server/protocol.def")
    server = replace(server, "#define MSGFLG_REPLY_MESSAGE   0x1",
                     "#define MSGFLG_REPLY_MESSAGE   ALPC_MSGFLG_REPLY_MESSAGE")
    server = replace(server, "#define ALPC_SYNC_CONNECTION   0x20000\n", "")
    server = replace(server, "#define ALPC_PORTFLG_NON_BLOCKING_RECEIVE 0x40000\n", "")

    # Use Wine11.20's object initializer and default object operations.
    start = server.index("static const struct object_ops alpc_port_ops =")
    end = server.index("\nstatic void alpc_port_dump", start)
    server = server[:start] + """static const struct object_ops alpc_port_ops =
{
    .size = sizeof(struct alpc_port),
    .type = &alpc_port_type,
    .dump = alpc_port_dump,
    .add_queue = add_queue,
    .remove_queue = remove_queue,
    .signaled = alpc_port_signaled,
    .get_sync = alpc_port_get_sync,
    .map_access = default_map_access,
    .set_sd = default_set_sd,
    .get_full_name = default_get_full_name,
    .destroy = alpc_port_destroy,
};
""" + server[end:]
    server = replace(server, '#include "process.h"', '#include "process.h"\n#include "security.h"')
    server = replace(server,
        "    if (port->kind == CLIENT_PORT && port->state == ALPC_NEW) return 0;",
        "    if (port->kind == CLIENT_PORT && port->state == ALPC_NEW) return 0;\n"
        "    if (port->kind == CLIENT_PORT && port->state == ALPC_CONNECTED && port->reply_msg) return 1;")
    server = replace(server, "    else reset_sync( port->sync );",
        "    else reset_sync( port->sync );\n"
        "    wake_up( &port->obj, 0 );")
    server = replace(server,
        "    if (!(port = create_named_object( root, &alpc_port_ops, name, attr, sd ))) return NULL;",
        "    struct object_params params = { .ops = &alpc_port_ops, .root = root,\n"
        "                                    .name = *name, .attr = attr, .sd = sd };\n"
        "    if (!(port = create_named_object( &params ))) return NULL;")
    # Server request data owns its object attributes; never grant unrestricted handles.
    server = replace(server,
        "    const struct security_descriptor *sd;\n"
        "    const struct object_attributes *objattr = get_req_object_attributes( &sd, &name, &root );\n\n"
        "    if (!objattr) return;",
        "    struct object_params params = { .ops = &alpc_port_ops };\n"
        "    if (!get_req_object_attributes( &params )) return;\n"
        "    root = params.root;\n"
        "    name = params.name;\n"
        "    const struct security_descriptor *sd = params.sd;\n"
        "    const struct object_attributes *objattr = params.objattr;")
    server = replace(server,
        "    const struct security_descriptor *sd;\n"
        "    const struct object_attributes *objattr = get_req_object_attributes( &sd, &name, &root );\n"
        "    data_size_t len = 0;\n"
        "    const void *data;\n\n"
        "    if (!objattr) return;",
        "    struct object_params params = { .ops = &alpc_port_ops };\n"
        "    data_size_t len = 0;\n"
        "    const void *data;\n\n"
        "    if (!get_req_object_attributes( &params )) return;\n"
        "    root = params.root;\n"
        "    name = params.name;\n"
        "    const struct object_attributes *objattr = params.objattr;")
    server = replace(server,
        "    conn = open_named_object( root, &alpc_port_ops, &name, objattr->attributes );",
        "    params.access = 1; /* PORT_CONNECT */\n"
        "    conn = open_named_object( &params );")
    # Native creator handles receive full port access; named client opens still check PORT_CONNECT.
    server = replace(server,
        "get_handle_obj( current->process, handle, 0, &alpc_port_ops )",
        "get_handle_obj( current->process, handle, 1, &alpc_port_ops )")
    # Pending records own the endpoint until consumed. No raw weak pointer may outlive it.
    server = replace(server,
        "    struct alpc_port *port;      /* weak */",
        "    struct alpc_port *port;      /* owned */")
    server = replace(server, "    client = msg->src;\n",
        "    client = (struct alpc_port *)grab_object( msg->client );\n")
    server = replace(server, "    struct alpc_port *client;\n\n    if (!conn)",
        "    struct alpc_port *client = NULL;\n\n    if (!conn)")
    server = replace(server, "    if (server) release_object( server );\n",
        "    if (client) release_object( client );\n    if (server) release_object( server );\n")
    server = replace(server, "            p->port = msg->src;\n",
        "            p->port = (struct alpc_port *)grab_object( msg->src );\n")
    server = replace(server, "        p->port = port;\n",
        "        p->port = (struct alpc_port *)grab_object( port );\n")
    # These two cleanup loops discard pending records rather than transfer their reference.
    server = server.replace("        list_remove( &p->entry );\n        free( p );",
                            "        list_remove( &p->entry );\n        release_object( p->port );\n        free( p );")
    server = replace(server,
        "        port = p->port;\n        list_remove( &p->entry );\n"
        "        release_object( p->port );\n        free( p );",
        "        port = p->port;\n        list_remove( &p->entry );\n        free( p );")
    server = replace(server, "        return port;\n", "        return port; /* reference transferred to sender */\n")
    server = replace(server,
        "        port = p->port;\n        list_remove( &p->entry );\n        free( p );\n"
        "        return port; /* reference transferred to sender */",
        "        port = (struct alpc_port *)grab_object( p->port );\n"
        "        return port;")
    server = replace(server, "    unsigned int type, id;\n",
        "    unsigned int type, id;\n    int release_dest = 0;\n")
    server = replace(server,
        "            if (!(dest = find_reply_target( port, id ))) { set_error( STATUS_REPLY_MESSAGE_MISMATCH ); goto done; }",
        "            if (!(dest = find_reply_target( port, id ))) { set_error( STATUS_REPLY_MESSAGE_MISMATCH ); goto done; }\n"
        "            release_dest = 1;")
    # Only the send handler has this exact following comment.
    server = replace(server,
        "done:\n    release_object( port );\n}\n\n/* Receive",
        "done:\n    if (release_dest) release_object( dest );\n    release_object( port );\n}\n\n/* Receive")
    server = replace(server,
        "    queue_msg( dest, msg );\n    reply->msg_id = id;",
        "    if (release_dest)\n"
        "    {\n"
        "        struct alpc_pending *p, *next;\n"
        "        LIST_FOR_EACH_ENTRY_SAFE( p, next, &port->pending, struct alpc_pending, entry )\n"
        "        {\n"
        "            if (p->id != id) continue;\n"
        "            list_remove( &p->entry );\n"
        "            release_object( p->port );\n"
        "            free( p );\n            break;\n"
        "        }\n    }\n"
        "    queue_msg( dest, msg );\n    reply->msg_id = id;")
    begin = server.index("    if (req->flags & MSGFLG_REPLY_MESSAGE)")
    end = server.index("\n    else\n", begin)
    server = server[:begin] + """    if (req->flags & MSGFLG_REPLY_MESSAGE)
    {
        type = LPC_REPLY;
        id = req->msg_id;
        reply_registry = port->kind == SERVER_PORT ? port->conn : port;
        if (!reply_registry || !(dest = find_reply_target( reply_registry, id )))
        { set_error( STATUS_REPLY_MESSAGE_MISMATCH ); goto done; }
        release_dest = 1;
        if (port->kind == SERVER_PORT && dest != port->peer)
        { set_error( STATUS_REPLY_MESSAGE_MISMATCH ); goto done; }
    }""" + server[end:]
    server = replace(server,
        "    struct alpc_port *dest = NULL, *conn_for_pending = NULL;",
        "    struct alpc_port *dest = NULL, *conn_for_pending = NULL, *reply_registry = NULL;")
    server = replace(server,
        "        LIST_FOR_EACH_ENTRY_SAFE( p, next, &port->pending, struct alpc_pending, entry )\n"
        "        {\n            if (p->id != id) continue;",
        "        LIST_FOR_EACH_ENTRY_SAFE( p, next, &reply_registry->pending, struct alpc_pending, entry )\n"
        "        {\n            if (p->id != id) continue;")
    server = replace(server, "            conn_for_pending = NULL;", "            conn_for_pending = dest;")
    # Do not consume a message when its caller cannot receive the whole payload.
    server = replace(server,
        "    reply->type = msg->type;",
        "    if (msg->size > get_reply_max_size())\n"
        "    {\n"
        "        reply->size = msg->size;\n"
        "        set_error( STATUS_BUFFER_TOO_SMALL );\n"
        "        goto done;\n"
        "    }\n"
        "    reply->type = msg->type;")
    server = replace(server,
        "        if (p)\n        {\n",
        "        if (!p) { set_error( STATUS_NO_MEMORY ); goto done; }\n"
        "        {\n")
    # Prohibit self-cycles on datagrams: connection-port self-wake has no source.
    # Normal handle closure severs peers and drops pending records, not just refcount destruction.
    server = replace(server, "static void alpc_port_destroy( struct object *obj );",
        "static void alpc_port_destroy( struct object *obj );\n"
        "static int alpc_port_close_handle( struct object *, struct process *, obj_handle_t );")
    server = replace(server, "    .destroy = alpc_port_destroy,",
        "    .close_handle = alpc_port_close_handle,\n    .destroy = alpc_port_destroy,")
    server = replace(server, "static struct alpc_port *create_port(",
        """        static void disconnect_port( struct alpc_port *port )
        {
            struct alpc_pending *p, *next;
            struct alpc_msg *msg, *mnext;
    if (port->conn) forget_source( port->conn, port );
    if (port->peer)
    {
        forget_source( port->peer, port );
        port->peer->peer = NULL;
        port->peer->state = ALPC_CLOSED;
        update_signal( port->peer );
        port->peer = NULL;
    }
    port->state = ALPC_CLOSED;
    LIST_FOR_EACH_ENTRY_SAFE( msg, mnext, &port->queue, struct alpc_msg, entry )
    {
        list_remove( &msg->entry );
        if (msg->client)
        {
            msg->client->state = ALPC_CLOSED;
            update_signal( msg->client );
        }
        free_msg( msg );
    }
    LIST_FOR_EACH_ENTRY_SAFE( p, next, &port->pending, struct alpc_pending, entry )
    {
        list_remove( &p->entry );
        p->port->state = ALPC_CLOSED;
        update_signal( p->port );
        release_object( p->port );
        free( p );
    }
    update_signal( port );
}

static int alpc_port_close_handle( struct object *obj, struct process *process, obj_handle_t handle )
{
    if (obj->handle_count == 1) disconnect_port( (struct alpc_port *)obj );
    return 1;
}

static struct alpc_port *create_port(""")
    server = replace(server, "    data = get_req_data_after_objattr( objattr, &len );",
                     "    data = get_req_data_after_objattr( &params, &len );")
    # Keep declarations before statements for Wine's compiler settings.
    server = replace(server,
        "    if (!get_req_object_attributes( &params )) return;\n"
        "    root = params.root;\n"
        "    name = params.name;\n"
        "    const struct security_descriptor *sd = params.sd;\n"
        "    const struct object_attributes *objattr = params.objattr;",
        "    const struct security_descriptor *sd;\n"
        "    const struct object_attributes *objattr;\n\n"
        "    if (!get_req_object_attributes( &params )) return;\n"
        "    root = params.root;\n    name = params.name;\n"
        "    sd = params.sd;\n    objattr = params.objattr;")
    server = replace(server,
        "    struct unicode_str name;\n    struct object *root;\n"
        "    struct object_params params = { .ops = &alpc_port_ops };\n"
        "    data_size_t len = 0;",
        "    struct object *root;\n"
        "    struct object_params params = { .ops = &alpc_port_ops };\n"
        "    data_size_t len = 0;")
    server = replace(server,
        "    name = params.name;\n    const struct object_attributes *objattr = params.objattr;\n", "")
    server = replace(server, "    struct alpc_port *port;\n\n    struct object_params params",
                     "    struct alpc_port *port;\n    struct object_params params")
    # Snapshot the destination context, rather than dereference a weak sender on receive.
    server = replace(server,
        "    struct alpc_port *src;       /* port the message was sent from (weak), or NULL */",
        "    client_ptr_t      port_context;")
    server = replace(server,
        "    struct alpc_msg *msg;\n    struct alpc_pending *p, *next;\n\n"
        "    LIST_FOR_EACH_ENTRY( msg, &port->queue, struct alpc_msg, entry ) if (msg->src == dead) msg->src = NULL;",
        "    struct alpc_msg *msg, *mnext;\n    struct alpc_pending *p, *next;\n\n"
        "    LIST_FOR_EACH_ENTRY_SAFE( msg, mnext, &port->queue, struct alpc_msg, entry )\n"
        "    {\n"
        "        if (msg->client != dead) continue;\n"
        "        list_remove( &msg->entry );\n        free_msg( msg );\n"
        "    }")
    server = replace(server, "            msg->src = client;\n", "")
    server = replace(server,
        "    msg->src = port->kind == CONNECTION_PORT ? NULL : port;",
        "    msg->port_context = port->peer ? port->peer->context : 0;")
    server = replace(server, "    struct alpc_port *ctx_port;\n", "")
    server = replace(server,
        "    ctx_port = msg->src ? msg->src->peer : NULL;\n"
        "    if (port->kind != CONNECTION_PORT) ctx_port = port;\n"
        "    reply->port_context = ctx_port ? ctx_port->context : 0;",
        "    reply->port_context = port->kind == CONNECTION_PORT ? msg->port_context : port->context;")
    server = replace(server,
        "            p->port = (struct alpc_port *)grab_object( msg->src );",
        "            p->port = (struct alpc_port *)grab_object( msg->client );")
    server = replace(server,
        "    if (conn->kind != CONNECTION_PORT)\n    {\n        release_object( conn );",
        "    if (conn->state == ALPC_CLOSED)\n"
        "    {\n        release_object( conn );\n        set_error( STATUS_PORT_DISCONNECTED );\n        return;\n    }\n"
        "    if (conn->kind != CONNECTION_PORT)\n    {\n        release_object( conn );")
    server = replace(server,
        "}\n\nstatic void alpc_port_destroy",
        "    update_signal( port );\n}\n\nstatic void alpc_port_destroy")
    begin = server.index("DECL_HANDLER(alpc_disconnect_port)")
    end = server.index("\n/* Query", begin)
    server = server[:begin] + """DECL_HANDLER(alpc_disconnect_port)
{
    struct alpc_port *port = get_port( req->handle );
    if (!port) return;
    disconnect_port( port );
    release_object( port );
}
""" + server[end:]
    server = replace(server,
        "    if (!(msg = alloc_msg( type, get_req_data(), get_req_data_size() ))) goto done;",
        "    if (!dest || dest->state == ALPC_CLOSED)\n"
        "    { set_error( STATUS_PORT_DISCONNECTED ); goto done; }\n"
        "    if ((port->max_msg_len && get_req_data_size() > port->max_msg_len) ||\n"
        "        (dest->max_msg_len && get_req_data_size() > dest->max_msg_len) ||\n"
        "        get_req_data_size() > 0xffff - sizeof(ALPC_PORT_MESSAGE))\n"
        "    { set_error( STATUS_PORT_MESSAGE_TOO_LONG ); goto done; }\n"
        "    if (!(msg = alloc_msg( type, get_req_data(), get_req_data_size() ))) goto done;")
    server = replace(server,
        "            queue_msg( conn, msg );\n"
        "            reply->handle = alloc_handle_no_access_check( current->process, client, ALPC_PORT_ALL_ACCESS_MASK, 0 );",
        "            reply->handle = alloc_handle_no_access_check( current->process, client, ALPC_PORT_ALL_ACCESS_MASK, 0 );\n"
        "            if (reply->handle) queue_msg( conn, msg );\n            else free_msg( msg );")
    server = replace(server,
        "        server->peer = client;\n        client->peer = server;\n"
        "        client->state = ALPC_CONNECTED;\n"
        "        reply->handle = alloc_handle_no_access_check( current->process, server, ALPC_PORT_ALL_ACCESS_MASK, 0 );",
        "        reply->handle = alloc_handle_no_access_check( current->process, server, ALPC_PORT_ALL_ACCESS_MASK, 0 );\n"
        "        if (!reply->handle) goto done;\n"
        "        server->peer = client;\n        client->peer = server;\n        client->state = ALPC_CONNECTED;")
    server = replace(server,
        "            reply->size = msg->size;\n        }\n    }\n    release_object( client );",
        "            reply->size = msg->size;\n"
        "            if (msg->size > get_reply_max_size()) set_error( STATUS_BUFFER_TOO_SMALL );\n"
        "            else\n"
        "            {\n                client->reply_msg = NULL;\n                free_msg( msg );\n"
        "                update_signal( client );\n            }\n"
        "        }\n    }\n    release_object( client );")
    server = replace(server,
        "    else if (client->state == ALPC_NEW) set_error( STATUS_PENDING );",
        "    else if (client->state == ALPC_NEW) set_error( STATUS_PENDING );\n"
        "    else if (client->state == ALPC_CLOSED) set_error( STATUS_PORT_DISCONNECTED );")
    server = replace(server,
        "done:\n    if (client) release_object( client );\n    if (server) release_object( server );",
        "done:\n"
        "    if (client && get_error() && client->state == ALPC_NEW)\n"
        "    {\n        client->state = ALPC_REFUSED;\n        update_signal( client );\n    }\n"
        "    if (client) release_object( client );\n    if (server) release_object( server );")
    server = server.replace("= req->max_msg_len;", "= req->max_msg_len ? req->max_msg_len : 0x8000;")
    server = replace(server,
        "    if ((client = create_port( NULL, &empty_unicode_str, 0, NULL, CLIENT_PORT )))",
        "    if (len > 0x8000 || (conn->max_msg_len && len > conn->max_msg_len))\n"
        "    {\n        release_object( conn );\n        set_error( STATUS_PORT_MESSAGE_TOO_LONG );\n        return;\n    }\n"
        "    if ((client = create_port( NULL, &empty_unicode_str, 0, NULL, CLIENT_PORT )))")

    client = replace(client, "return alloc_object_attributes( attr, objattr, len );",
                     "return wine_server_alloc_object_attributes( attr, objattr, len );")
    # Never manufacture kernel identity metadata or silently override a real failure.
    begin = client.index("        if (type != LPC_CONNECTION_REQUEST && (ctx = get_attribute( attrs, ALPC_MESSAGE_WORK_ON_BEHALF_ATTRIBUTE )))")
    end = client.index("\n    }\n    return status;", begin)
    client = client[:begin] + client[end:]
    client = replace(client,
        "        if (status == STATUS_REPLY_MESSAGE_MISMATCH && (flags & ALPC_MSGFLG_RELEASE_MESSAGE)) status = STATUS_SUCCESS;\n", "")
    begin = client.index("    OBJECT_ATTRIBUTES attr = { sizeof(attr) };", client.index("NTSTATUS WINAPI NtAlpcImpersonateClientOfPort"))
    client = client[:begin] + """    FIXME("Message-bound ALPC impersonation is not implemented.\\n");
    return STATUS_NOT_IMPLEMENTED;
}
"""
    # This is transport-only until SID matching and authenticated impersonation are available.
    client = replace(client, "    if (!handle || !name) return STATUS_ACCESS_VIOLATION;",
        "    if (!handle || !name) return STATUS_ACCESS_VIOLATION;\n"
        "    *handle = NULL;\n"
        "    if (sd || client_attr || out_attrs || in_attrs) return STATUS_NOT_IMPLEMENTED;")
    client = replace(client, "    if (!handle || !port_attr) return STATUS_ACCESS_VIOLATION;",
        "    if (!handle || !port_attr) return STATUS_ACCESS_VIOLATION;\n"
        "    *handle = NULL;\n"
        "    if (sd || client_attr || out_attrs || in_attrs) return STATUS_NOT_IMPLEMENTED;")
    # Remove payload dumps, which can expose application messages to general Wine logs.
    begin = client.index("static const char *hexdump_str(")
    end = client.index("static NTSTATUS connect_port(", begin)
    client = client[:begin] + client[end:]
    client = re.sub(r'\s*TRACE\( "[^"]*(?:data %s|RECVDATA)[^"]*".*?;\n', "\n", client, flags=re.S)
    # Use the actual Wine11.20 ABI, not lookalike structure types from the old experiment.
    begin = client.index("#define ALPC_MESSAGE_SECURITY_ATTRIBUTE")
    end = client.index("static const ULONG attr_sizes", begin)
    client = client[:begin] + """#define ALPC_MSGFLG_WAIT_ALERTABLE 0x00200000
#define LPC_REQUEST ALPC_MESSAGE_TYPE_REQUEST
#define LPC_CONNECTION_REQUEST ALPC_MESSAGE_TYPE_CONNECTION_REQUEST

""" + client[end:]
    for old, new in (
        ("struct alpc_message", "ALPC_PORT_MESSAGE"),
        ("struct alpc_attributes", "ALPC_MESSAGE_ATTRIBUTES"),
        ("struct alpc_context_attr", "ALPC_CONTEXT_ATTR"),
        ("struct alpc_port_attributes", "ALPC_PORT_ATTRIBUTES"),
    ):
        client = client.replace(old, new)
    fields = {
        "data_length": "DataLength", "total_length": "TotalLength",
        "type": "Type", "message_id": "MessageId",
        "callback_or_view_size": "ClientViewSize",
        "allocated": "AllocatedAttributes", "valid": "ValidAttributes",
        "port_context": "PortContext", "message_context": "MessageContext",
        "callback_id": "CallbackId", "sequence": "Sequence",
        "flags": "Flags", "max_message_length": "MaxMessageLength",
    }
    for variable in ("msg", "send", "attrs", "send_attrs", "ctx", "pa", "port_attr"):
        for old, new in fields.items():
            client = re.sub(r"\b" + variable + r"->" + old + r"\b",
                            variable + "->" + new, client)
    client = client.replace("msg->pid = pid;", "msg->ClientId.UniqueProcess = (HANDLE)(ULONG_PTR)pid;")
    client = client.replace("msg->tid = tid;", "msg->ClientId.UniqueThread = (HANDLE)(ULONG_PTR)tid;")
    client = client.replace("msg->pid = reply->pid;",
                            "msg->ClientId.UniqueProcess = (HANDLE)(ULONG_PTR)reply->pid;")
    client = client.replace("msg->tid = reply->tid;",
                            "msg->ClientId.UniqueThread = (HANDLE)(ULONG_PTR)reply->tid;")
    client = client.replace("send->pid", "(ULONG_PTR)send->ClientId.UniqueProcess")
    client = client.replace("send->tid", "(ULONG_PTR)send->ClientId.UniqueThread")
    # NtAlpcConnectPort takes a SID; ConnectPortEx takes a security descriptor.
    begin = client.index("NTSTATUS WINAPI NtAlpcConnectPort(")
    end = client.index("NTSTATUS WINAPI NtAlpcConnectPortEx(", begin)
    client = client[:begin] + client[begin:end].replace("PSECURITY_DESCRIPTOR sd", "PSID sd") + client[end:]
    client = replace(client,
        "    if (send && send->MessageId) flags |= ALPC_MSGFLG_REPLY_MESSAGE;\n", "")
    client = replace(client, "    if (!handle) return STATUS_ACCESS_VIOLATION;",
        "    if (!handle) return STATUS_ACCESS_VIOLATION;\n    *handle = NULL;\n"
        "    if (port_attr && port_attr->MaxMessageLength > 0x8000) return STATUS_NOT_IMPLEMENTED;")
    client = replace(client,
        '    TRACE( "connect port flags %#x\\n", pa ? (unsigned)pa->Flags : 0 );',
        '    TRACE( "connect port flags %#x\\n", pa ? (unsigned)pa->Flags : 0 );\n'
        "    if (flags & ~ALPC_SYNC_CONNECTION) return STATUS_NOT_IMPLEMENTED;\n"
        "    if (pa && pa->MaxMessageLength > 0x8000) return STATUS_NOT_IMPLEMENTED;\n"
        "    if (msg && (!length || *length < sizeof(*msg) ||\n"
        "        msg->TotalLength < sizeof(*msg) || msg->TotalLength > *length ||\n"
        "        msg->DataLength > msg->TotalLength - sizeof(*msg))) return STATUS_INVALID_PARAMETER;")
    begin = client.index("        {\n            LARGE_INTEGER delay, now;")
    end = client.index("\n    }\n    TRACE", begin)
    client = client[:begin] + (
        "        if ((status = wait_port( port, FALSE, pabs ))) break;\n"
    ) + client[end:]
    # A reply buffer smaller than the connection response must fail, not return success.
    client = replace(client,
        "                        if (avail >= sizeof(*msg) + size) memcpy( msg + 1, buffer, size );",
        "                        if (avail >= sizeof(*msg) + size) memcpy( msg + 1, buffer, size );\n"
        "                        else status = STATUS_BUFFER_TOO_SMALL;")
    client = replace(client,
        "                    SIZE_T avail = length ? *length : 0;\n"
        "                    data_size_t size = wine_server_reply_size( reply );",
        "                    SIZE_T avail = length ? *length : 0;\n"
        "                    data_size_t size = reply->size;\n"
        "                    if (size > sizeof(buffer)) status = STATUS_BUFFER_TOO_SMALL;")
    client = replace(client,
        "                        if (avail >= sizeof(*msg) + size) memcpy( msg + 1, buffer, size );\n"
        "                        else status = STATUS_BUFFER_TOO_SMALL;",
        "                        if (avail >= sizeof(*msg) + size && size <= sizeof(buffer))\n"
        "                            memcpy( msg + 1, buffer, size );\n"
        "                        else status = STATUS_BUFFER_TOO_SMALL;")
    # Unsupported message attributes must not appear to have been consumed.
    client = replace(client, "    if (!msg) return STATUS_INVALID_PARAMETER;",
        "    if (!msg || (accept && !handle)) return STATUS_INVALID_PARAMETER;\n"
        "    if (handle) *handle = NULL;\n"
        "    if (flags || attr || attrs) return STATUS_NOT_IMPLEMENTED;\n"
        "    if (pa && pa->MaxMessageLength > 0x8000) return STATUS_NOT_IMPLEMENTED;\n"
        "    if (msg->TotalLength < sizeof(*msg) ||\n"
        "        msg->DataLength > msg->TotalLength - sizeof(*msg)) return STATUS_INVALID_PARAMETER;")
    client = replace(client,
        "    if (send)\n    {\n",
        "    if (flags & ~(ALPC_MSGFLG_REPLY_MESSAGE | ALPC_MSGFLG_WAIT_ALERTABLE))\n"
        "        return STATUS_NOT_IMPLEMENTED;\n"
        "    if (send_attrs && (send_attrs->ValidAttributes & ~ALPC_MESSAGE_CONTEXT_ATTRIBUTE))\n"
        "        return STATUS_NOT_IMPLEMENTED;\n"
        "    if (send_attrs && (send_attrs->ValidAttributes & ~send_attrs->AllocatedAttributes))\n"
        "        return STATUS_INVALID_PARAMETER;\n"
        "    if (recv && (!length || *length < sizeof(*recv))) return STATUS_BUFFER_TOO_SMALL;\n"
        "    if (send && (send->TotalLength < sizeof(*send) ||\n"
        "        send->DataLength > send->TotalLength - sizeof(*send))) return STATUS_INVALID_PARAMETER;\n"
        "    if (send)\n    {\n")
    client = replace(client,
        "            wine_server_set_reply( req, buffer, sizeof(buffer) );\n"
        "            status = wine_server_call( req );\n"
        "            if (!status || status == STATUS_BUFFER_OVERFLOW)",
        "            wine_server_set_reply( req, buffer,\n"
        "                min( sizeof(buffer), *length - sizeof(*recv) ));\n"
        "            status = wine_server_call( req );\n"
        "            if (status == STATUS_BUFFER_TOO_SMALL) *length = sizeof(*recv) + reply->size;\n"
        "            if (!status || status == STATUS_BUFFER_OVERFLOW)")
    client = replace(client, "        unsigned char buffer[0x2000];",
                     "        unsigned char buffer[0x8000];")
    client = replace(client,
        '    TRACE( "(%p, %#x)\\n", handle, (int)flags );',
        '    TRACE( "(%p, %#x)\\n", handle, (int)flags );\n'
        "    if (flags) return STATUS_NOT_IMPLEMENTED;")

    start = protocol.index("@REQ(alpc_create_port)")
    end = protocol.index("@END", protocol.index("@REQ(alpc_query_port)", start)) + len("@END")
    requests = protocol[start:end]
    current_protocol = source / "server/protocol.def"
    current = current_protocol.read_text()
    start = current.index("@REQ(alpc_create_port)")
    last = current.index("@REQ(alpc_query_port)", start) if "@REQ(alpc_query_port)" in current else start
    end = current.index("@END", last) + len("@END")
    current_protocol.write_text(current[:start] + requests + current[end:])
    (source / "server/alpc.c").write_text(server)
    (source / "dlls/ntdll/unix/alpc.c").write_text(client)
    stubs = source / "dlls/ntdll/coremessaging_ntdll_stubs.c"
    text = stubs.read_text()
    if "NTSTATUS WINAPI NtAlpcConnectPortEx(" in text:
        begin = text.index("NTSTATUS WINAPI NtAlpcConnectPortEx(")
        stubs.write_text(text[:begin])
    spec = source / "dlls/ntdll/ntdll.spec"
    text = spec.read_text()
    for name in ("NtAlpcConnectPortEx", "NtAlpcQueryInformation"):
        if "@ stdcall -syscall " + name not in text:
            text = replace(text, "@ stdcall " + name, "@ stdcall -syscall " + name)
    spec.write_text(text)
    paths = ("server/alpc.c", "server/protocol.def", "dlls/ntdll/unix/alpc.c",
             "dlls/ntdll/coremessaging_ntdll_stubs.c", "dlls/ntdll/ntdll.spec")
    return {"commit": COMMIT, "historical_inputs": inputs, "registrar_qualified": False,
            "creator_access_evidence": CREATOR_ACCESS_EVIDENCE,
            "files": {p: sha256(source / p) for p in paths},
            "limitations": [
                "Transport candidate only; no registrar admission",
                "Security descriptor matching, client attributes and message-bound impersonation remain explicit unsupported",
                "No synthesized work-on-behalf identity or suppressed reply errors",
                "Synchronous message requests remain explicitly unsupported",
            ]}
