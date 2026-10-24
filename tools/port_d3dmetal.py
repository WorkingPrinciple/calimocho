"""Port the public CW 26.3 D3DMetal boundary to pinned WineHQ 11.20 source.

This is a source transformation, not an Apple payload or ABI qualification.
Original LGPL notices are retained in copied source files and donor blocks.
"""

import hashlib
import re

from probe_wine_source import sha256


def replace_once(text, old, new):
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Port anchor occurs {count} times, expected one: {old[:100]!r}")
    return text.replace(old, new, 1)


def between(text, start, end):
    if text.count(start) != 1:
        raise ValueError(f"Ambiguous donor start: {start!r}")
    tail = text.split(start, 1)[1]
    if end not in tail:
        raise ValueError(f"Missing donor end: {end!r}")
    return start + tail.split(end, 1)[0]


def port_thread_teb_key(thread, server, virtual, unix_private):
    thread = replace_once(
        thread,
        "WINE_DECLARE_DEBUG_CHANNEL(seh);\nWINE_DECLARE_DEBUG_CHANNEL(threadname);\n",
        "WINE_DECLARE_DEBUG_CHANNEL(seh);\nWINE_DECLARE_DEBUG_CHANNEL(threadname);\n"
        "\npthread_key_t teb_key = 0;\n",
    )
    server = replace_once(
        server,
        "    if (data->teb)\n"
        "    {\n"
        "        init_teb_data( data );\n",
        "    if (data->teb)\n"
        "    {\n"
        "        pthread_setspecific( teb_key, data->teb );\n"
        "        init_teb_data( data );\n",
    )
    thread = replace_once(
        thread,
        "TEB * WINAPI NtCurrentTeb(void)\n"
        "{\n"
        "    struct thread_data *data = get_thread_data();\n"
        "    return data ? data->teb : NULL;\n"
        "}",
        "TEB * WINAPI NtCurrentTeb(void)\n"
        "{\n"
        "    return pthread_getspecific( teb_key );\n"
        "}",
    )
    virtual = replace_once(
        virtual,
        "    init_teb( data, ptr );\n    VIRTUAL_DEBUG_DUMP_VIEW( view );\n",
        "    init_teb( data, ptr );\n"
        "    pthread_key_create( &teb_key, NULL );\n"
        "    pthread_setspecific( teb_key, data->teb );\n"
        "    VIRTUAL_DEBUG_DUMP_VIEW( view );\n",
    )
    unix_private = replace_once(
        unix_private,
        "extern pthread_key_t thread_data_key;\n",
        "extern pthread_key_t thread_data_key;\nextern pthread_key_t teb_key;\n",
    )
    return thread, server, virtual, unix_private


def port(source, donor):
    """Stage all exact-anchor edits before writing any source."""
    driver = "dlls/winemac.drv/"
    ntdll = "dlls/ntdll/"
    changed = {}
    donor_files = {}

    def upstream(name):
        if name in changed:
            return changed[name]
        return (source / name).read_text()

    def donated(name):
        path = donor / name
        donor_files[name] = sha256(path)
        return path.read_text()

    def edit(name, old, new):
        changed[name] = replace_once(upstream(name), old, new)

    for name in ("d3dmetal.c", "d3dmetal_objc.m", "d3dmetal_objc.h"):
        changed[driver + name] = donated(driver + name)

    name = driver + "d3dmetal.c"
    edit(name, '#include "shellapi.h"\n', "")
    edit(name, "typedef LONG LSTATUS;", """typedef LONG LSTATUS;
typedef WineWindow *macdrv_window;
typedef WineContentView *macdrv_view;
typedef MTLDevice_id macdrv_metal_device;
typedef WineMetalView *macdrv_metal_view;
typedef CAMetalLayer *macdrv_metal_layer;""")
    edit(name, "client_surface = macdrv_client_surface_create(hwnd);",
         "client_surface = impl_from_client_surface(macdrv_CreateClientSurface(hwnd, 0, FALSE));")
    edit(name, "d3dm_data->pixel_format = data->pixel_format;",
         "d3dm_data->pixel_format = client_surface->client.format;")
    edit(name, "static LSTATUS WINAPI DECLSPEC_HOTPATCH RegCloseKey(",
         "static LSTATUS WINAPI DECLSPEC_HOTPATCH local_RegCloseKey(")
    edit(name, "return RegCloseKey(hkey);", "return local_RegCloseKey(hkey);")
    edit(name, "void OnMainThread(dispatch_block_t block);",
         "void OnMainThread(dispatch_block_t block);\n"
         "extern UINT64 regcreateopenkeyexa_callback, regqueryvalueexa_callback, regsetvalueexa_callback;")

    name = driver + "d3dmetal_objc.m"
    edit(name, '#include "macdrv_cocoa.h"',
         '#include "macdrv_cocoa.h"\n'
         'extern void *macdrv_get_view_d3dmetal_client_surface(WineContentView *view);')
    edit(name, "(macdrv_view)view.superview", "(WineContentView *)view.superview")

    name = driver + "Makefile.in"
    edit(name, "DELAYIMPORTS = ole32", "DELAYIMPORTS = advapi32 ole32")
    edit(name, "\tdisplay.c \\", "\td3dmetal.c \\\n\td3dmetal_objc.m \\\n\tdisplay.c \\")

    name = driver + "unixlib.h"
    callbacks = ("regcreateopenkeyexa", "regqueryvalueexa", "regsetvalueexa")
    fields = "".join(f"    UINT64 {callback}_callback;\n" for callback in callbacks)
    edit(name, "    UINT64 app_quit_request_callback;\n",
         "    UINT64 app_quit_request_callback;\n" + fields)
    donor_header = donated(name)
    structs = between(donor_header, "/* macdrv_regcreateopenkeyexa params */",
                      "static inline void *param_ptr")
    # These are pointers to the caller's LONG result, not 32-bit LONG values.
    structs = structs.replace("UINT32 result;", "UINT64 result;")
    edit(name, "static inline void *param_ptr", structs + "static inline void *param_ptr")

    name = driver + "dllmain.c"
    edit(name, '#include "winbase.h"\n',
         '#include "winbase.h"\n#include "winreg.h"\n')
    callback_functions = between(
        donated(name), "static NTSTATUS WINAPI macdrv_regcreateopenkeyexa",
        "static BOOL process_attach")
    callback_functions = callback_functions.replace(
        "static LSTATUS WINAPI DECLSPEC_HOTPATCH RegCloseKey(",
        "static LSTATUS WINAPI DECLSPEC_HOTPATCH local_RegCloseKey(")
    callback_functions = callback_functions.replace(
        "return RegCloseKey(hkey);", "return local_RegCloseKey(hkey);")
    edit(name, "static BOOL process_attach", callback_functions + "static BOOL process_attach")
    edit(name, "    params.app_quit_request_callback = (UINT_PTR)macdrv_app_quit_request;\n",
         "    params.app_quit_request_callback = (UINT_PTR)macdrv_app_quit_request;\n" +
         "".join(f"    params.{callback}_callback = (UINT_PTR)macdrv_{callback};\n"
                 for callback in callbacks))

    name = driver + "macdrv_main.c"
    edit(name, "UINT64 app_quit_request_callback = 0;\n",
         "UINT64 app_quit_request_callback = 0;\n" +
         "".join(f"UINT64 {callback}_callback = 0;\n" for callback in callbacks))
    edit(name, "    app_quit_request_callback = params->app_quit_request_callback;\n",
         "    app_quit_request_callback = params->app_quit_request_callback;\n" +
         "".join(f"    {callback}_callback = params->{callback}_callback;\n"
                 for callback in callbacks))
    edit(name, "        UINT64 app_quit_request_callback;\n",
         "        UINT64 app_quit_request_callback;\n" +
         "".join(f"        UINT64 {callback}_callback;\n" for callback in callbacks))
    edit(name, "    params.app_quit_request_callback = params32->app_quit_request_callback;\n",
         "    params.app_quit_request_callback = params32->app_quit_request_callback;\n" +
         "".join(f"    params.{callback}_callback = params32->{callback}_callback;\n"
                 for callback in callbacks))

    name = driver + "macdrv.h"
    edit(name, "    HANDLE              drag_event;",
         "    CFMutableArrayRef   d3dmetal_client_surfaces;\n"
         "    HANDLE              drag_event;")
    edit(name, "extern void macdrv_handle_event(const macdrv_event *event);",
         "extern void macdrv_handle_event(const macdrv_event *event);\n"
         "extern void macdrv_client_surface_presented(const macdrv_event *event);")

    name = driver + "macdrv_cocoa.h"
    edit(name, "    APP_QUIT_REQUESTED,\n",
         "    APP_QUIT_REQUESTED,\n    CLIENT_SURFACE_PRESENTED,\n")
    edit(name, "        }                                           app_quit_requested;\n",
         "        }                                           app_quit_requested;\n"
         "        struct {\n            void *client_surface;\n"
         "        }                                           client_surface_presented;\n")
    changed[name] = upstream(name) + (
        "\nextern void *macdrv_get_view_d3dmetal_client_surface(WineContentView *view);\n"
        "extern void macdrv_set_view_d3dmetal_client_surface(WineContentView *view, void *surface);\n")

    name = driver + "cocoa_window.m"
    edit(name, '#import "cocoa_window.h"', '#import "cocoa_window.h"\n#import "d3dmetal_objc.h"')
    edit(name, "    CGRect surfaceRect;",
         "    @public void *d3dmetal_client_surface;\n    @private\n    CGRect surfaceRect;")
    edit(name, "CAMetalLayer *layer = [CAMetalLayer layer];",
         "CAMetalLayer *layer = [WineMetalLayer layer];")
    accessors = between(donated(name), "void *macdrv_get_view_d3dmetal_client_surface",
                        "/***********************************************************************")
    accessors = accessors.replace("macdrv_view v", "WineContentView *v")
    changed[name] = upstream(name) + "\n" + accessors

    name = driver + "window.c"
    edit(name, "    CFDictionaryRemoveValue(win_datas, hwnd);\n",
         "    if (data->d3dmetal_client_surfaces) CFRelease(data->d3dmetal_client_surfaces);\n"
         "    CFDictionaryRemoveValue(win_datas, hwnd);\n")

    name = driver + "event.c"
    edit(name, '        "APP_QUIT_REQUESTED",\n',
         '        "APP_QUIT_REQUESTED",\n        "CLIENT_SURFACE_PRESENTED",\n')
    edit(name, "        event_mask |= event_mask_for_type(APP_QUIT_REQUESTED);\n",
         "        event_mask |= event_mask_for_type(APP_QUIT_REQUESTED);\n"
         "        event_mask |= event_mask_for_type(CLIENT_SURFACE_PRESENTED);\n")
    edit(name, "    case DISPLAYS_CHANGED:",
         "    case CLIENT_SURFACE_PRESENTED:\n"
         "        macdrv_client_surface_presented(event);\n        break;\n"
         "    case DISPLAYS_CHANGED:")

    name = ntdll + "unixlib.h"
    parameter_struct = between(donated(name), "struct pe_module_loaded_params",
                               "enum ntdll_unix_funcs")
    edit(name, "enum ntdll_unix_funcs", parameter_struct + "enum ntdll_unix_funcs")
    edit(name, "    unix_system_time_precise,\n",
         "    unix_system_time_precise,\n#if defined(__x86_64__)\n"
         "    unix_pe_module_loaded,\n#endif\n")

    name = ntdll + "loader.c"
    notification = between(donated(name),
                           "#if defined(__x86_64__)\n    /* CW HACK 22434 */",
                           "\n#if defined(__i386__) || defined(__x86_64__)")
    edit(name, "    update_load_config( *module );",
         notification + "\n    update_load_config( *module );")

    name = ntdll + "unix/loader.c"
    non_native = between(donated(name), "/* CW HACK 22434 */",
                         "static const unixlib_entry_t unix_call_funcs[]")
    edit(name, "static const unixlib_entry_t unix_call_funcs[]",
         non_native + "static const unixlib_entry_t unix_call_funcs[]")
    # Both Unix dispatch tables must keep the added enum entry in the same slot.
    original = upstream(name)
    if original.count("    system_time_precise,\n") != 2:
        raise ValueError("Expected both native and wow64 ntdll dispatch tables")
    changed[name] = original.replace(
        "    system_time_precise,\n",
        "    system_time_precise,\n#if defined(__x86_64__)\n    pe_module_loaded,\n#endif\n")
    # The wow64 entry is deliberately unsupported, matching the donor.
    edit(name, "    wow64_wine_spawnvp,\n    system_time_precise,\n"
         "#if defined(__x86_64__)\n    pe_module_loaded,",
         "    wow64_wine_spawnvp,\n    system_time_precise,\n"
         "#if defined(__x86_64__)\n    wow64_pe_module_loaded,")
    edit(name, "static NTSTATUS wow64_load_so_dll",
         "#if defined(__x86_64__)\n"
         "static NTSTATUS wow64_pe_module_loaded(void *args) { return STATUS_NOT_IMPLEMENTED; }\n"
         "#endif\n\nstatic NTSTATUS wow64_load_so_dll")

    name = ntdll + "unix/unix_private.h"
    abi_macros = between(donated(name), "/* CX Hack 23015 */", "/* LDT definitions */")
    edit(name, "/* LDT definitions */", abi_macros + "/* LDT definitions */")
    wrapper_count = 0
    for basename in ("sync.c", "server.c", "thread.c"):
        name = ntdll + "unix/" + basename
        wrappers = re.findall(
            r"#if defined\(__APPLE__\) && defined\(__x86_64__\)\n\n"
            r"NTSTATUS __attribute__\(\(ms_abi\)\) msthunk_.*?#endif",
            donated(name), re.DOTALL)
        if not wrappers:
            raise ValueError(f"No donor ABI wrappers in {name}")
        for wrapper in wrappers:
            functions = re.findall(r"GPT_ABI_WRAPPER\( (Nt\w+) \);", wrapper)
            if len(functions) != 1:
                raise ValueError(f"Ambiguous ABI wrapper in {name}")
            function = functions[0]
            edit(name, f"NTSTATUS WINAPI {function}(",
                 f"NTSTATUS WINAPI GPT_IMPORT({function})(")
            changed[name] = upstream(name) + "\n" + wrapper + "\n"
            wrapper_count += 1
    if wrapper_count != 9:
        raise ValueError(f"Expected nine donor ABI wrappers, found {wrapper_count}")

    for name, anchors in (
        (ntdll + "unix/thread.c", (
            "pthread_key_t teb_key = 0;",
            "pthread_setspecific( teb_key, teb );",
            "return pthread_getspecific( teb_key );",
        )),
        (ntdll + "unix/virtual.c", (
            "pthread_key_create( &teb_key, NULL );",
            "pthread_setspecific( teb_key, teb );",
        )),
        (ntdll + "unix/unix_private.h", ("extern pthread_key_t teb_key;",)),
    ):
        donor_source = donated(name)
        for anchor in anchors:
            if anchor not in donor_source:
                raise ValueError(f"Missing CW TEB-key donor anchor in {name}: {anchor}")

    thread, server, virtual, unix_private = port_thread_teb_key(
        upstream(ntdll + "unix/thread.c"),
        upstream(ntdll + "unix/server.c"),
        upstream(ntdll + "unix/virtual.c"),
        upstream(ntdll + "unix/unix_private.h"),
    )
    changed[ntdll + "unix/thread.c"] = thread
    changed[ntdll + "unix/server.c"] = server
    changed[ntdll + "unix/virtual.c"] = virtual
    changed[ntdll + "unix/unix_private.h"] = unix_private

    manifest = []
    for name, content in sorted(changed.items()):
        path = source / name
        manifest.append({
            "path": name,
            "upstream_sha256": sha256(path) if path.exists() else None,
            "ported_sha256": hashlib.sha256(content.encode()).hexdigest(),
        })
    for name, content in changed.items():
        (source / name).write_text(content)
    return {"donor_files": donor_files, "changed_files": manifest,
            "abi_wrappers": wrapper_count,
            "qualification": "experimental source port; no Apple ABI/runtime/game qualification"}
