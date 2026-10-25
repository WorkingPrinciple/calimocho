"""Integrate qualified CoreMessaging IOCP and dispatch forms into current Wine."""
from pathlib import Path
import hashlib
import subprocess

from tools.build_launcher_overlay import REPO
from tools.port_alpc_transport import replace
from tools.probe_wine_source import sha256

SOURCES = ("tools/port_coremsg_dispatch.py", "patches/wine/files/win32u_coremsg.c",
           "patches/wine/files/user32_coremsg.c")
EVIDENCE_COMMIT = "3ee99fb8caee9af215021f407d6710c9f0d25b4c"


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require unfrozen owned CoreMessaging dispatch source")
    if (source / "dlls/win32u/coremsg.c").exists():
        raise ValueError("Require fresh CoreMessaging dispatch source")
    changed = {}

    def update(path, old, new):
        text = changed.get(path, (source / path).read_text())
        changed[path] = replace(text, old, new)

    evidence = {}
    for path in ("dlls/win32u/input.c", "dlls/user32/misc.c"):
        data = subprocess.check_output(["git", "--no-replace-objects", "show", EVIDENCE_COMMIT + ":" + path],
                                       cwd="/Users/dragoshont/xodus-runs/wine-v20-src")
        evidence[path] = hashlib.sha256(data).hexdigest()
    update("dlls/win32u/ntuser_private.h", "    HANDLE                        idle_event;",
           "    HANDLE                        coremsg_iocp;\n    HWND                          coremsg_hwnd[2];\n"
           "    HANDLE                        idle_event;")
    update("dlls/win32u/win32u_private.h", "extern LRESULT send_message( HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam );",
           """extern LRESULT send_message( HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam );
enum { COREMSG_ERROR = -1, COREMSG_EMPTY, COREMSG_DELIVERED, COREMSG_MARKER, COREMSG_LINKED, COREMSG_NOWAKE };
extern int coremsg_dispatch_packet(void);
extern BOOL coremsg_marker( HANDLE, ULONG );
extern HANDLE coremsg_initialize( HWND, DWORD * );
extern BOOL coremsg_drain( HWND );
extern DWORD coremsg_queue_readonly( UINT );""")
    update("include/ntuser.h", "    NtUserCallTwoParam_GetVirtualScreenRect,",
           "    NtUserCallTwoParam_GetVirtualScreenRect,\n"
           "    NtUserCallTwoParam_CoreMessagingInitialize,\n"
           "    NtUserCallTwoParam_CoreMessagingDrain,\n"
           "    NtUserCallTwoParam_CoreMessagingQueueReadonly,")
    update("dlls/win32u/sysparams.c", "    case NtUserCallTwoParam_GetDialogProc:",
           """    case NtUserCallTwoParam_CoreMessagingInitialize:
        return (ULONG_PTR)coremsg_initialize( UlongToHandle(arg1), (DWORD *)arg2 );
    case NtUserCallTwoParam_CoreMessagingDrain:
        return coremsg_drain( UlongToHandle(arg1) );
    case NtUserCallTwoParam_CoreMessagingQueueReadonly:
        return coremsg_queue_readonly( arg1 );
    case NtUserCallTwoParam_GetDialogProc:""")
    update("dlls/win32u/sysparams.c", "    if (thread_info->idle_event) NtClose( thread_info->idle_event );",
           "    if (thread_info->idle_event) NtClose( thread_info->idle_event );\n"
           "    if (thread_info->coremsg_iocp) NtClose( thread_info->coremsg_iocp );")
    for ordinal, name, args in ((2541, "GetQueueStatusReadonly", "long"),
                                (2669, "InitThreadCoreMessagingIocp2", "long ptr"),
                                (2670, "DrainThreadCoreMessagingCompletions2", "long")):
        update("dlls/user32/user32.spec", f"{ordinal} stub -noname {name}  # NtUser{name}",
               f"{ordinal} stdcall -noname {name}({args})")
    changed["dlls/user32/user32.spec"] += (
        "\n@ stdcall GetQueueStatusForCoreMessaging(long)\n"
        "@ stdcall ScheduleCoreMessagingDispatch(long long long long ptr)\n")
    # Wine hashes apiset names without the final version, so l1-1-3 also resolves l1-1-1.
    update("dlls/apisetschema/apisetschema.spec",
           "apiset ext-ms-win-rtcore-minuser-private-ext-l1-1-3 =\n",
           "apiset ext-ms-win-rtcore-minuser-private-ext-l1-1-3 = user32.dll\n")
    input_path = "dlls/win32u/input.c"
    changed[input_path] = (source / input_path).read_text() + '\n#include "coremsg.c"\n'
    misc_path = "dlls/user32/misc.c"
    changed[misc_path] = (source / misc_path).read_text() + '\n#include "coremsg.c"\n'
    message_path = "dlls/win32u/message.c"
    text = (source / message_path).read_text()
    start = text.index("DWORD WINAPI NtUserMsgWaitForMultipleObjectsEx(")
    end = text.index("\n/***********************************************************************", start)
    changed[message_path] = text[:start] + """DWORD WINAPI NtUserMsgWaitForMultipleObjectsEx( DWORD count, const HANDLE *handles,
                                                DWORD timeout, DWORD mask, DWORD flags )
{
    HANDLE wait_handles[MAXIMUM_WAIT_OBJECTS];
    HANDLE iocp = get_user_thread_info()->coremsg_iocp;
    ULONGLONG start = NtGetTickCount();
    DWORD i, extra = 0, result, remaining = timeout;

    if (count > MAXIMUM_WAIT_OBJECTS - 1 ||
        (iocp && ((flags & MWMO_WAITALL) || count > MAXIMUM_WAIT_OBJECTS - 2)))
    {
        RtlSetLastWin32Error( iocp ? ERROR_NOT_SUPPORTED : ERROR_INVALID_PARAMETER );
        return WAIT_FAILED;
    }
    for (i = 0; i < count; i++) wait_handles[i] = normalize_std_handle( handles[i] );
    if (iocp) wait_handles[count + extra++] = iocp;
    wait_handles[count + extra] = get_server_queue_handle();
    for (;;)
    {
        result = wait_objects( count + extra + 1, wait_handles, remaining,
                               (flags & MWMO_INPUTAVAILABLE) ? mask : 0, mask, flags );
        if (!extra || result != count) break;
        switch (coremsg_dispatch_packet())
        {
        case COREMSG_ERROR: return WAIT_FAILED;
        case COREMSG_LINKED:
            return coremsg_marker( iocp, 0x80000000 ) ? count : WAIT_FAILED;
        case COREMSG_DELIVERED:
        case COREMSG_MARKER: return count;
        default:
            if (timeout != INFINITE)
            {
                ULONGLONG elapsed = NtGetTickCount() - start;
                if (elapsed >= timeout) return WAIT_TIMEOUT;
                remaining = timeout - elapsed;
            }
            break;
        }
    }
    if (extra && result == count + 1) return count;
    return result;
}
""" + text[end:]
    for path, text in changed.items():
        (source / path).write_text(text)
    for destination, original in (("dlls/win32u/coremsg.c", SOURCES[1]), ("dlls/user32/coremsg.c", SOURCES[2])):
        (source / destination).write_bytes((REPO / original).read_bytes())
        changed[destination] = ""
    return {"files": {p: sha256(source / p) for p in changed}, "registrar_qualified": False,
            "evidence_commit": EVIDENCE_COMMIT, "evidence_files": evidence,
            "unsupported": "Schedule operation2; wait-all with CoreMessaging IOCP"}
