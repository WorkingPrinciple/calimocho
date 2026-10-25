"""Bounded, redacted ALPC and fail-fast telemetry for the CoreMessaging connect path.

Unix side: every NtAlpc* syscall keeps its body unchanged under a static
alpc_impl_* name and gains a wrapper that reports the export, the returned
status and, for connects, a fixed target class (registrar, registrar-relative,
other, none). Port names are never printed. Lines go to pkgstatus (the app
collector admits it) and to the alpc channel (the registrar services log
enables it).

kernelbase: RaiseFailFastException reports the record (code, flags, count,
address as module+offset, parameters as 32-bit scalars or module+offset) on
pkgexception before any termination path; behavior is unchanged.

wineserver: connect, connect-result, accept, receive and wait-packet
association report their final status on stderr, and queue_msg reports
whether a waiter (thread or wait packet) is registered on the port sync.
"""
from pathlib import Path
import re
import shutil

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_alpc_telemetry.py", "patches/wine/files/package_kernelbase_failfast.h")
PATHS = ("dlls/ntdll/unix/alpc.c", "dlls/kernelbase/debug.c", "dlls/kernelbase/package_kernelbase_failfast.h",
         "server/alpc.c", "server/server_wait_completion_packet.c")
MARK = "/* alpc telemetry */"

UNIX_HELPERS = MARK + r"""
WINE_DECLARE_DEBUG_CHANNEL(pkgstatus);

static int diagnostic_alpc_suffix( const UNICODE_STRING *name, const char *ascii, int whole )
{
    size_t count = strlen( ascii ), length = name->Length / sizeof(WCHAR), i;
    if (length < count || (whole && length != count)) return 0;
    for (i = 0; i < count; i++)
    {
        WCHAR c = name->Buffer[length - count + i];
        char a = ascii[i];
        if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
        if (a >= 'A' && a <= 'Z') a += 'a' - 'A';
        if (c != (WCHAR)(unsigned char)a) return 0;
    }
    return 1;
}

/* Fixed class only; the port name itself is never emitted. */
static const char *diagnostic_alpc_target( const UNICODE_STRING *name, HANDLE root )
{
    if (!name || !name->Buffer || !name->Length) return "none";
    if (!root && diagnostic_alpc_suffix( name, "\\BaseNamedObjects\\CoreMessagingRegistrar", 1 )) return "registrar";
    if (diagnostic_alpc_suffix( name, "\\CoreMessagingRegistrar", 0 )
        || (root && diagnostic_alpc_suffix( name, "CoreMessagingRegistrar", 1 ))) return "registrar-relative";
    return "other";
}

static void diagnostic_alpc_return( const char *export, NTSTATUS status, const char *target )
{
    static LONG hits;
    LONG sequence;
    TRACE( "return %s status %#x target %s\n", export, (int)status, target );
    if (!TRACE_ON(pkgstatus)) return;
    sequence = InterlockedIncrement( &hits );
    if (sequence > 256)
    {
        if (sequence == 257) TRACE_(pkgstatus)( "alpc-return limited=1\n" );
        return;
    }
    TRACE_(pkgstatus)( "alpc-return export=%s result=%08x target=%s\n", export, (unsigned int)status, target );
}
"""

SERVER_HELPERS = MARK + r"""
static int alpc_telemetry_admit(void)
{
    static unsigned int lines;
    if (++lines <= 512) return 1;
    if (lines == 513) fprintf( stderr, "wineserver: alpc telemetry limited=1\n" );
    return 0;
}
"""

SERVER_QUEUE = """static void queue_msg( struct alpc_port *port, struct alpc_msg *msg )
{
    list_add_tail( &port->queue, &msg->entry );
    update_signal( port );
    if (alpc_telemetry_admit())
        fprintf( stderr, "wineserver: alpc queue kind=%d type=%u id=%u depth-signaled=%d sync-waiters=%d port-waiters=%d\\n",
                 port->kind, msg->type, msg->id, alpc_port_signaled( &port->obj, NULL ),
                 port->sync ? !list_empty( &port->sync->wait_queue ) : -1, !list_empty( &port->obj.wait_queue ) );
}"""

# handler -> (format suffix, arguments) printed after the final status.
SERVER_HANDLERS = {
    "alpc_connect_port": ('handle=%d', "reply->handle != 0"),
    "alpc_connect_result": ('state=%d msg_id=%u', "(int)reply->state, reply->msg_id"),
    "alpc_accept_connect_port": ('accept=%d msg_id=%u handle=%d', "(int)req->accept, req->msg_id, reply->handle != 0"),
    "alpc_receive_message": ('match=%u type=%u msg_id=%u', "req->match_id, reply->type, reply->msg_id"),
}


def _wrap_unix(text):
    pattern = re.compile(r"^NTSTATUS WINAPI (NtAlpc\w+)\(([^)]*)\)\n\{", re.M)
    found = pattern.findall(text)
    if not found:
        raise ValueError("No NtAlpc definitions in unix/alpc.c")
    wrappers = []
    for name, params in found:
        names = []
        for param in params.split(","):
            token = re.findall(r"[A-Za-z_]\w*", param)
            if not token:
                raise ValueError("Unparsed parameter in " + name)
            names.append(token[-1])
        if name == "NtAlpcConnectPort":
            target = "diagnostic_alpc_target( name, 0 )"
        elif name == "NtAlpcConnectPortEx":
            target = ("diagnostic_alpc_target( port_attr ? port_attr->ObjectName : NULL, "
                      "port_attr ? port_attr->RootDirectory : 0 )")
        else:
            target = '"none"'
        text = text.replace("NTSTATUS WINAPI %s(%s)\n{" % (name, params),
                            "static NTSTATUS alpc_impl_%s(%s)\n{" % (name, params), 1)
        wrappers.append(
            "NTSTATUS WINAPI %s(%s)\n{\n    NTSTATUS status = alpc_impl_%s( %s );\n"
            '    diagnostic_alpc_return( "%s", status, %s );\n    return status;\n}\n'
            % (name, params, name, ", ".join(names), name, target))
    return text + "\n" + "\n".join(wrappers), [name for name, _ in found]


def _wrap_server(text, handler, suffix, arguments):
    head = "DECL_HANDLER(%s)\n{" % handler
    if text.count(head) != 1:
        raise ValueError("Missing server handler " + handler)
    impl = "static void alpc_impl_%s( const struct %s_request *req, struct %s_reply *reply )\n{" % (
        handler, handler, handler)
    text = text.replace(head, impl, 1)
    skip_pending = " && status != STATUS_PENDING" if handler == "alpc_connect_result" else ""
    wrapper = (
        "\nDECL_HANDLER(%s)\n{\n    unsigned int status;\n    alpc_impl_%s( req, reply );\n"
        "    status = get_error();\n"
        "    if (alpc_telemetry_admit()%s)\n"
        '        fprintf( stderr, "wineserver: alpc %s pid %%04x status=%%08x %s\\n",\n'
        "                 current->process->id, status, %s );\n}\n"
        % (handler, handler, skip_pending, handler, suffix, arguments))
    return text + wrapper


ASSOCIATE_WRAPPER = r"""
DECL_HANDLER(associate_wait_completion_packet)
{
    unsigned int status;
    struct object *target;
    const char *kind = "unknown";
    int port = 0;
    alpc_impl_associate_wait_completion_packet( req, reply );
    status = get_error();
    if ((target = get_handle_obj( current->process, req->target, 0, NULL )))
    {
        if (target->ops->type == &alpc_port_type) { kind = "alpc-port"; port = 1; }
        else if (target->ops->type == &event_type) kind = "event";
        else kind = "other";
        release_object( target );
    }
    set_error( status );
    if (port || status)
        fprintf( stderr, "wineserver: wait-packet associate target=%s status=%08x already_signaled=%d\n",
                 kind, status, status ? 0 : reply->already_signaled );
}
"""


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned ALPC telemetry source")
    unix = source / "dlls/ntdll/unix/alpc.c"
    text = unix.read_text()
    if MARK in text:
        raise ValueError("ALPC telemetry already applied")
    anchor = "WINE_DEFAULT_DEBUG_CHANNEL(alpc);\n"
    if text.count(anchor) != 1:
        raise ValueError("Missing unix ALPC debug channel")
    text = text.replace(anchor, anchor + UNIX_HELPERS, 1)
    text, exports = _wrap_unix(text)
    unix.write_text(text)

    shutil.copy2(REPO / SOURCES[1], source / "dlls/kernelbase/package_kernelbase_failfast.h")
    debug = source / "dlls/kernelbase/debug.c"
    text = replace(debug.read_text(), "WINE_DECLARE_DEBUG_CHANNEL(winedbg);\n",
                   'WINE_DECLARE_DEBUG_CHANNEL(winedbg);\n#include "package_kernelbase_failfast.h"\n')
    text = replace(text, '    WARN( "(%p, %p, %lx)\\n", record, context, flags );\n',
                   '    WARN( "(%p, %p, %lx)\\n", record, context, flags );\n'
                   "    diagnostic_failfast( record, flags, __builtin_return_address(0) );\n")
    debug.write_text(text)

    server = source / "server/alpc.c"
    text = server.read_text()
    old_queue = ("static void queue_msg( struct alpc_port *port, struct alpc_msg *msg )\n{\n"
                 "    list_add_tail( &port->queue, &msg->entry );\n    update_signal( port );\n}")
    if text.count(old_queue) != 1:
        raise ValueError("Missing server queue_msg")
    text = text.replace(old_queue, SERVER_HELPERS + SERVER_QUEUE, 1)
    for handler, (suffix, arguments) in SERVER_HANDLERS.items():
        text = _wrap_server(text, handler, suffix, arguments)
    server.write_text(text)

    packets = source / "server/server_wait_completion_packet.c"
    text = packets.read_text()
    head = "DECL_HANDLER(associate_wait_completion_packet)\n{"
    if text.count(head) != 1:
        raise ValueError("Missing wait packet association handler")
    text = text.replace(head, "static void alpc_impl_associate_wait_completion_packet( "
                        "const struct associate_wait_completion_packet_request *req, "
                        "struct associate_wait_completion_packet_reply *reply )\n{", 1)
    packets.write_text(text + ASSOCIATE_WRAPPER)
    return {"files": {p: sha256(source / p) for p in PATHS},
            "unix_exports": exports,
            "server_handlers": sorted(SERVER_HANDLERS) + ["associate_wait_completion_packet"],
            "redaction": "fixed export names, statuses, ids and target classes only; no port names, data or pointers"}
