"""Add genuine server wait packets and explicit unsupported native dependencies."""
import hashlib
from pathlib import Path
import re
import shutil

from tools.build_launcher_overlay import REPO
from tools.probe_wine_source import sha256

SOURCES = (
    "tools/port_coremessaging_prerequisites.py",
    "patches/wine/files/coremessaging_ntdll_stubs.c",
    "patches/wine/files/ntdll_wait_completion_packet.c",
    "patches/wine/files/server_wait_completion_packet.c",
    "versions.json",
)

PROTOTYPES = """
NTSYSAPI NTSTATUS WINAPI NtCreateWaitCompletionPacket(HANDLE*,ACCESS_MASK,OBJECT_ATTRIBUTES*);
NTSYSAPI NTSTATUS WINAPI NtAssociateWaitCompletionPacket(HANDLE,HANDLE,HANDLE,void*,void*,NTSTATUS,ULONG_PTR,BOOLEAN*);
NTSYSAPI NTSTATUS WINAPI NtCancelWaitCompletionPacket(HANDLE,BOOLEAN);
NTSYSAPI NTSTATUS WINAPI RtlGetAppContainerNamedObjectPath(HANDLE,PSID,BOOLEAN,UNICODE_STRING*);
NTSYSAPI NTSTATUS WINAPI RtlGetThreadWorkOnBehalfTicket(ULONGLONG*,ULONG);
NTSYSAPI NTSTATUS WINAPI RtlSetThreadWorkOnBehalfTicket(ULONGLONG*);
NTSYSAPI NTSTATUS WINAPI NtAlpcConnectPortEx(HANDLE*,OBJECT_ATTRIBUTES*,OBJECT_ATTRIBUTES*,ALPC_PORT_ATTRIBUTES*,ULONG,PSECURITY_DESCRIPTOR,ALPC_PORT_MESSAGE*,SIZE_T*,ALPC_MESSAGE_ATTRIBUTES*,ALPC_MESSAGE_ATTRIBUTES*,LARGE_INTEGER*);
NTSYSAPI NTSTATUS WINAPI NtAlpcQueryInformation(HANDLE,ULONG,void*,ULONG,ULONG*);
"""

EXPORTS = """
@ stdcall -syscall NtCreateWaitCompletionPacket(ptr long ptr)
@ stdcall -syscall NtAssociateWaitCompletionPacket(ptr ptr ptr ptr ptr long long ptr)
@ stdcall -syscall NtCancelWaitCompletionPacket(ptr long)
@ stdcall RtlGetAppContainerNamedObjectPath(ptr ptr long ptr)
@ stdcall RtlGetThreadWorkOnBehalfTicket(ptr long)
@ stdcall RtlSetThreadWorkOnBehalfTicket(ptr)
@ stdcall NtAlpcConnectPortEx(ptr ptr ptr ptr long ptr ptr ptr ptr ptr ptr)
@ stdcall NtAlpcQueryInformation(ptr long ptr long ptr)
"""

PROTOCOL = """
/* Server-owned, one-shot wait completion packets. */
@REQ(create_wait_completion_packet)
    unsigned int access;
    VARARG(objattr,object_attributes);
@REPLY
    obj_handle_t handle;
@END

@REQ(associate_wait_completion_packet)
    obj_handle_t packet;
    obj_handle_t completion;
    obj_handle_t target;
    apc_param_t ckey;
    apc_param_t cvalue;
    apc_param_t information;
    unsigned int status;
@REPLY
    int already_signaled;
@END

@REQ(cancel_wait_completion_packet)
    obj_handle_t packet;
    int remove_signaled;
@END
"""

ORDINAL_GUARDS = """
# Reserved unsupported native CoreMessaging ordinal imports, not native function names.
86 stub -noname __wine_unsupported_coremessaging_ordinal_86
87 stub -noname __wine_unsupported_coremessaging_ordinal_87
88 stub -noname __wine_unsupported_coremessaging_ordinal_88
"""


def guard_combase_ordinals(path):
    text = path.read_text()
    original = text
    if original.startswith(ORDINAL_GUARDS + "\n"):
        original = original[len(ORDINAL_GUARDS) + 1:]
    elif original.endswith(ORDINAL_GUARDS):
        original = original[:-len(ORDINAL_GUARDS)]
    original = re.sub(r"^\d+ ", "@ ", original, flags=re.M)
    if hashlib.sha256(original.encode()).hexdigest() != (
            "4f7580702a341f8003b48c87fa65904f476d0c8d9102d9edd64e8b7855ac47b0"):
        raise ValueError("Unexpected combase baseline export allocation")
    rows = []
    ordinal = 0
    for line in original.splitlines(keepends=True):
        if line.startswith("@ "):
            ordinal += 1
            # Preserve every other ordinal; only the three colliding named APIs move.
            assigned = ordinal + 270 if ordinal in (86, 87, 88) else ordinal
            line = str(assigned) + line[1:]
        rows.append(line)
    generated = "".join(rows) + ORDINAL_GUARDS
    if text not in (original, ORDINAL_GUARDS + "\n" + original, generated):
        raise ValueError("Unexpected guarded combase export allocation")
    if text != generated:
        path.write_text(generated)


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned CoreMessaging prerequisite source")
    changed = set()

    def change(relative, old, new):
        path = source / relative
        text = path.read_text()
        if new in text:
            if text.count(new) != 1:
                raise ValueError("Repeated CoreMessaging seam: " + relative)
        elif text.count(old) == 1:
            path.write_text(text.replace(old, new))
        else:
            raise ValueError("Unexpected CoreMessaging seam: " + relative)
        changed.add(relative)

    guard_combase_ordinals(source / "dlls/combase/combase.spec")
    changed.add("dlls/combase/combase.spec")
    change("include/winternl.h", "NTSYSAPI NTSTATUS  WINAPI NtAlpcAcceptConnectPort",
           PROTOTYPES + "\nNTSYSAPI NTSTATUS  WINAPI NtAlpcAcceptConnectPort")
    change("dlls/ntdll/ntdll.spec", "@ stdcall -syscall NtAllocateReserveObject",
           EXPORTS + "\n@ stdcall -syscall NtAllocateReserveObject")
    change("dlls/ntdll/Makefile.in", "\tcrypt.c \\", "\tcrypt.c \\\n\tcoremessaging_ntdll_stubs.c \\")
    change("dlls/ucrtbase/ucrtbase.spec", "@ stdcall -arch=!i386,!arm64ec __C_specific_handler(ptr long ptr ptr)",
           "@ stdcall -arch=x86_64 __C_specific_handler_noexcept(ptr long ptr ptr) ntdll.__C_specific_handler\n"
           "@ stdcall -arch=!i386,!arm64ec __C_specific_handler(ptr long ptr ptr)")
    change("dlls/ntdll/unix/sync.c", "#include \"unix_private.h\"",
           "#include \"unix_private.h\"\n#include \"ntdll_wait_completion_packet.c\"")
    change("server/object.h", "    struct thread_wait *wait;\n};",
           "    struct thread_wait *wait;\n    int (*wake_callback)(struct wait_queue_entry *);\n};")
    change("server/thread.c", "        entry->wait = wait;\n",
           "        entry->wait = wait;\n        entry->wake_callback = NULL;\n")
    change("server/thread.c", "if (!(ret = wake_thread( get_wait_queue_thread( entry )))) continue;",
           "if (!(ret = entry->wake_callback ? entry->wake_callback(entry) :\n"
           "                    wake_thread( get_wait_queue_thread( entry )))) continue;")
    change("server/protocol.def", "/* Create I/O completion port */",
           PROTOCOL + "\n/* Create I/O completion port */")
    change("server/completion.c", "struct comp_msg\n{",
           "struct wait_packet;\nstruct comp_msg;\nstatic void wait_packet_dequeued(struct comp_msg *);\n"
           "static void cancel_completion_packets(struct completion *);\n\nstruct comp_msg\n{")
    change("server/completion.c", "    struct   list queue_entry;\n",
           "    struct   list queue_entry;\n    struct wait_packet *packet;\n")
    change("server/completion.c", "    unsigned int        concurrent;\n};",
           "    unsigned int        concurrent;\n    struct list         packets;\n};")
    change("server/completion.c", "    wait->msg = msg;\n",
           "    wait_packet_dequeued(msg);\n    wait->msg = msg;\n")
    change("server/completion.c", "    list_init( &completion->wait_queue );\n",
           "    list_init( &completion->wait_queue );\n    list_init( &completion->packets );\n")
    change("server/completion.c", "    if (completion->obj.handle_count != 1) return 1;\n",
           "    if (completion->obj.handle_count != 1) return 1;\n\n    cancel_completion_packets(completion);\n")
    change("server/completion.c", "    msg->ckey = ckey;\n",
           "    msg->packet = NULL;\n    msg->ckey = ckey;\n")
    change("server/completion.c", "/* create a completion */",
           '#include "server_wait_completion_packet.c"\n\n/* create a completion */')
    change("server/completion.c", "        free( msg );\n        reply->wait_handle = 0;\n",
           "        wait_packet_dequeued(msg);\n        free( msg );\n        reply->wait_handle = 0;\n")
    for relative, original in (
        ("dlls/ntdll/coremessaging_ntdll_stubs.c", "coremessaging_ntdll_stubs.c"),
        ("dlls/ntdll/unix/ntdll_wait_completion_packet.c", "ntdll_wait_completion_packet.c"),
        ("server/server_wait_completion_packet.c", "server_wait_completion_packet.c"),
    ):
        shutil.copy2(REPO / "patches/wine/files" / original, source / relative)
        changed.add(relative)
    return {"files": {relative: sha256(source / relative) for relative in sorted(changed)},
            "scope": "server-owned event/timer/semaphore/process/thread wait packets; five explicit unsupported exports; combase ordinal 86-88 failure guards",
            "ordinal_guards": {
                "module": "combase.dll", "ordinals": [86, 87, 88],
                "behavior": "Wine unimplemented-export exception, never a status-shaped success",
                "native_function_names": None,
            },
            "limitations": "Other waitable types and in-process-sync-only targets fail explicitly; user32 dispatcher and private API-set gaps remain unsupported; no native execution"}
