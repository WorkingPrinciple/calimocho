"""Instrument actual process/event/duplicate/IPC creation, retaining no arbitrary names."""
from pathlib import Path
import shutil

from tools.build_launcher_overlay import REPO
from tools.port_uwp_activation import replace
from tools.probe_wine_source import sha256

PREVIOUS = REPO / "build/winehq-11.20/package-uwp-activation-waits-01"
FILES = REPO / "patches/wine/files"
SOURCES = ("tools/port_handle_provenance.py", "patches/wine/files/package_handle_diagnostics.h",
           "patches/wine/files/package_rpc_diagnostics.h")


def wrap(source, relative, symbol, signature, arguments, before, after):
    path = source / relative
    text = path.read_text()
    public = "GPT_IMPORT(" + symbol + ")" if "NTSTATUS WINAPI GPT_IMPORT(" + symbol + ")(" in text else symbol
    old = "NTSTATUS WINAPI " + public + "("
    if text.count(old) != 1:
        raise ValueError("Missing actual handle seam " + symbol)
    declaration = "NTSTATUS WINAPI " + public + "(" + signature + ");\n"
    text = text.replace(old, declaration + "static NTSTATUS diagnostic_original_" + symbol + "(", 1)
    text += "\nNTSTATUS WINAPI " + public + "(" + signature + ")\n{\n    NTSTATUS result;\n"
    text += "    if (TRACE_ON(pkghandle))\n    {\n" + before + "\n    }\n"
    text += "    result = diagnostic_original_" + symbol + "(" + arguments + ");\n"
    text += "    if (TRACE_ON(pkghandle))\n    {\n" + after + "\n    }\n    return result;\n}\n"
    path.write_text(text)


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require owned unfrozen016 source")
    predecessor = PREVIOUS / "cell015-receipt.json"
    if sha256(predecessor) != "58eccd9ec5d9aba954eb80251efadb8d8117b2f49aba6088604e981b5b50a122":
        raise ValueError("Require sealed015 predecessor")
    baseline = {}
    for relative in ("dlls/ntdll/unix/process.c", "dlls/ntdll/unix/server.c", "dlls/ntdll/unix/alpc.c",
                     "dlls/rpcrt4/rpc_transport.c"):
        baseline[relative] = sha256(PREVIOUS / "source" / relative)
        shutil.copy2(PREVIOUS / "source" / relative, source / relative)
    shutil.copy2(FILES / "package_handle_diagnostics.h", source / "dlls/ntdll/unix/package_handle_diagnostics.h")
    shutil.copy2(FILES / "package_rpc_diagnostics.h", source / "dlls/rpcrt4/package_rpc_diagnostics.h")
    for relative, marker in (
        ("dlls/ntdll/unix/process.c", "WINE_DEFAULT_DEBUG_CHANNEL(process);"),
        ("dlls/ntdll/unix/server.c", "WINE_DEFAULT_DEBUG_CHANNEL(server);"),
        ("dlls/ntdll/unix/alpc.c", "WINE_DEFAULT_DEBUG_CHANNEL(alpc);"),
    ):
        replace(source, relative, marker, marker + '\n#include "package_address_diagnostics.h"\n#include "package_handle_diagnostics.h"')
    replace(source, "dlls/ntdll/unix/sync.c", '#include "package_wait_diagnostics.h"',
            '#include "package_wait_diagnostics.h"\n#include "package_handle_diagnostics.h"')
    current = "HandleToULong(NtCurrentTeb()->ClientId.UniqueProcess)"

    def event(symbol, signature, arguments):
        wrap(source, "dlls/ntdll/unix/sync.c", symbol, signature, arguments,
             f'    diagnostic_handle("{symbol}", "enter", STATUS_PENDING, NULL, NULL, {current}, 0, attr ? attr->ObjectName : NULL);',
             f'    diagnostic_handle("{symbol}", "exit", result, result ? NULL : *handle, NULL, {current}, 0, attr ? attr->ObjectName : NULL);')
    event("NtCreateEvent", "HANDLE *handle, ACCESS_MASK access, const OBJECT_ATTRIBUTES *attr, EVENT_TYPE type, BOOLEAN state",
          "handle, access, attr, type, state")
    event("NtOpenEvent", "HANDLE *handle, ACCESS_MASK access, const OBJECT_ATTRIBUTES *attr", "handle, access, attr")
    wrap(source, "dlls/ntdll/unix/process.c", "NtOpenProcess",
         "HANDLE *handle, ACCESS_MASK access, const OBJECT_ATTRIBUTES *attr, const CLIENT_ID *id",
         "handle, access, attr, id",
         f'    diagnostic_handle("NtOpenProcess", "enter", STATUS_PENDING, NULL, NULL, {current}, id ? HandleToULong(id->UniqueProcess) : 0, NULL);',
         f'    diagnostic_handle("NtOpenProcess", "exit", result, result ? NULL : *handle, NULL, {current}, id ? HandleToULong(id->UniqueProcess) : 0, NULL);')
    wrap(source, "dlls/ntdll/unix/server.c", "NtDuplicateObject",
         "HANDLE source_process, HANDLE source, HANDLE dest_process, HANDLE *dest, ACCESS_MASK access, ULONG attributes, ULONG options",
         "source_process, source, dest_process, dest, access, attributes, options",
         '    diagnostic_handle("NtDuplicateObject", "enter", STATUS_PENDING, NULL, source, diagnostic_process_id(dest_process), diagnostic_process_id(source_process), NULL);',
         '    diagnostic_handle("NtDuplicateObject", "exit", result, result || !dest ? NULL : *dest, source, diagnostic_process_id(dest_process), diagnostic_process_id(source_process), NULL);')
    wrap(source, "dlls/ntdll/unix/server.c", "NtClose", "HANDLE handle", "handle",
         f'    diagnostic_handle("NtClose", "enter", STATUS_PENDING, handle, NULL, {current}, 0, NULL);',
         f'    diagnostic_handle("NtClose", "exit", result, handle, NULL, {current}, 0, NULL);')
    wrap(source, "dlls/ntdll/unix/process.c", "NtCreateUserProcess",
         "HANDLE *process_handle_ptr, HANDLE *thread_handle_ptr, ACCESS_MASK process_access, ACCESS_MASK thread_access, "
         "OBJECT_ATTRIBUTES *process_attr, OBJECT_ATTRIBUTES *thread_attr, ULONG process_flags, ULONG thread_flags, "
         "RTL_USER_PROCESS_PARAMETERS *params, PS_CREATE_INFO *info, PS_ATTRIBUTE_LIST *ps_attr",
         "process_handle_ptr, thread_handle_ptr, process_access, thread_access, process_attr, thread_attr, process_flags, thread_flags, params, info, ps_attr",
         f'    diagnostic_handle("NtCreateUserProcess", "enter", STATUS_PENDING, NULL, NULL, {current}, 0, NULL);',
         f'    diagnostic_handle("NtCreateUserProcess", "exit", result, result ? NULL : *process_handle_ptr, NULL, {current}, result ? 0 : diagnostic_process_id(*process_handle_ptr), NULL);')
    for relative, symbol, signature, args, output, name in (
        ("dlls/ntdll/unix/sync.c", "NtConnectPort",
         "HANDLE *handle, UNICODE_STRING *name, SECURITY_QUALITY_OF_SERVICE *qos, LPC_SECTION_WRITE *write, "
         "LPC_SECTION_READ *read, ULONG *max_len, void *info, ULONG *info_len",
         "handle, name, qos, write, read, max_len, info, info_len", "handle", "name"),
        ("dlls/ntdll/unix/sync.c", "NtSecureConnectPort",
         "HANDLE *handle, UNICODE_STRING *name, SECURITY_QUALITY_OF_SERVICE *qos, LPC_SECTION_WRITE *write, "
         "PSID sid, LPC_SECTION_READ *read, ULONG *max_len, void *info, ULONG *info_len",
         "handle, name, qos, write, sid, read, max_len, info, info_len", "handle", "name"),
        ("dlls/ntdll/unix/alpc.c", "NtAlpcConnectPort",
         "HANDLE *port_handle, UNICODE_STRING *port_name, OBJECT_ATTRIBUTES *obj_attr, ALPC_PORT_ATTRIBUTES *port_attr, "
         "DWORD flags, PSID required_server_sid, ALPC_PORT_MESSAGE *connect_msg, SIZE_T *connect_msg_size, "
         "ALPC_MESSAGE_ATTRIBUTES *send_msg_attr, ALPC_MESSAGE_ATTRIBUTES *recv_msg_attr, LARGE_INTEGER *timeout",
         "port_handle, port_name, obj_attr, port_attr, flags, required_server_sid, connect_msg, connect_msg_size, send_msg_attr, recv_msg_attr, timeout",
         "port_handle", "port_name"),
    ):
        wrap(source, relative, symbol, signature, args,
             f'    diagnostic_handle("{symbol}", "enter", STATUS_PENDING, NULL, NULL, {current}, 0, {name});',
             f'    diagnostic_handle("{symbol}", "exit", result, result || !{output} ? NULL : *{output}, NULL, {current}, 0, {name});')
    replace(source, "dlls/rpcrt4/rpc_transport.c", "WINE_DEFAULT_DEBUG_CHANNEL(rpc);",
            'WINE_DEFAULT_DEBUG_CHANNEL(rpc);\n#include "package_rpc_diagnostics.h"')
    replace(source, "dlls/rpcrt4/rpc_transport.c",
            '  TRACE("(Connection == ^%p)\\n", Connection);\n\n  assert(!Connection->server);\n  return Connection->ops->open_connection_client(Connection);',
            '  RPC_STATUS result;\n  const void *caller = __builtin_return_address(0);\n'
            '  diagnostic_rpc("enter", RPC_S_OK, caller);\n'
            '  assert(!Connection->server);\n  result = Connection->ops->open_connection_client(Connection);\n'
            '  diagnostic_rpc("exit", result, caller);\n  return result;')
    # Include process/RPC API callsites from only the three admitted modules.
    relay = source / "dlls/ntdll/package_relay_diagnostics.h"
    text = relay.read_text()
    text = text.replace('    if (!name) return FALSE;',
                        '    if (!name) return FALSE;\n'
                        '    if (!_stricmp(module, "rpcrt4")) return TRUE;\n'
                        '    if (!_stricmp(module, "kernelbase") || !_stricmp(module, "kernel32"))\n'
                        '        return !strcmp(name, "OpenProcess") || !strcmp(name, "CreateProcessA")\n'
                        '            || !strcmp(name, "CreateProcessW") || !strcmp(name, "CreateProcessInternalW");')
    start = text.index("    if (!InterlockedCompareExchange(&diagnostic_initialize")
    end = text.index("    if (!diagnostic_selected", start)
    text = text[:start] + '''    void *base = NULL;
    IMAGE_EXPORT_DIRECTORY *exports;
    ULONG size;
    const char *image, *admitted;
    if (!__wine_pkg_diagnostic_active() || !name || !RtlPcToFileHeader((void *)caller, &base)) return;
    exports = RtlImageDirectoryEntryToData(base, TRUE, IMAGE_DIRECTORY_ENTRY_EXPORT, &size);
    if (!exports) return;
    image = (const char *)base + exports->Name;
    if (!_stricmp(image, "Windows.UI.Xaml.dll")) admitted = "Windows.UI.Xaml.dll";
    else if (!_stricmp(image, "combase.dll")) admitted = "combase.dll";
    else if (!_stricmp(image, "twinapi.appcore.dll")) admitted = "twinapi.appcore.dll";
    else return;
''' + text[end:]
    text = text.replace('caller=Windows.UI.Xaml.dll offset=%Ix\\n",\n'
                        '                        data->dllname, name, caller - diagnostic_xaml);',
                        'caller=%s offset=%Ix\\n",\n'
                        '                        data->dllname, name, admitted, caller - (ULONG_PTR)base);')
    relay.write_text(text)
    replace(source, "dlls/ntdll/relay.c",
            'if (TRACE_ON(pkgrelay) && user && wcsicmp(user, L"windows.ui.xaml.dll"))',
            'if (TRACE_ON(pkgrelay) && user && wcsicmp(user, L"windows.ui.xaml.dll")\n'
            '        && wcsicmp(user, L"combase.dll") && wcsicmp(user, L"twinapi.appcore.dll"))')
    return {"predecessor_receipt_sha256": sha256(predecessor), "baseline_files": baseline,
            "files": {relative: sha256(source / relative) for relative in (
        "dlls/ntdll/unix/process.c", "dlls/ntdll/unix/server.c", "dlls/ntdll/unix/sync.c",
        "dlls/ntdll/unix/alpc.c", "dlls/rpcrt4/rpc_transport.c", "dlls/ntdll/relay.c",
        "dlls/ntdll/package_relay_diagnostics.h", "dlls/ntdll/unix/package_handle_diagnostics.h",
        "dlls/rpcrt4/package_rpc_diagnostics.h")}}
