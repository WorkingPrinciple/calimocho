"""Add cell015 public activation names and real wait/thread metadata without behavior changes."""
from pathlib import Path
import shutil

from tools.build_launcher_overlay import REPO
from tools.port_uwp_activation import replace
from tools.probe_wine_source import sha256

PREVIOUS = REPO / "build/winehq-11.20/package-uwp-calltrace-01"
FILES = REPO / "patches/wine/files"
SOURCES = ("tools/port_activation_wait_diagnostics.py",
           "patches/wine/files/package_address_diagnostics.h",
           "patches/wine/files/package_ro_diagnostics.h",
           "patches/wine/files/package_thread_diagnostics.h")


def port(source):
    source = Path(source).resolve(strict=True)
    if not source.is_relative_to(REPO / "build") or any(source.parent.glob("*FROZEN*")):
        raise ValueError("Require owned unfrozen cell015 source")
    for relative in ("dlls/combase/roapi.c", "dlls/ntdll/unix/thread.c", "dlls/ntdll/unix/signal_x86_64.c"):
        shutil.copy2(PREVIOUS / "source" / relative, source / relative)
    shutil.copy2(FILES / "package_ro_diagnostics.h", source / "dlls/combase/package_ro_diagnostics.h")
    for name in ("package_address_diagnostics.h", "package_thread_diagnostics.h"):
        shutil.copy2(FILES / name, source / "dlls/ntdll/unix" / name)
    replace(source, "dlls/combase/roapi.c", "struct activatable_class_data\n{",
            '#include "package_ro_diagnostics.h"\n\nstruct activatable_class_data\n{')
    replace(source, "dlls/combase/roapi.c",
            "static HRESULT get_activation_factory(HSTRING classid, REFIID iid, void **class_factory)",
            "static HRESULT get_activation_factory(HSTRING classid, REFIID iid, void **class_factory, HMODULE *served)")
    replace(source, "dlls/combase/roapi.c", "    hr = pDllGetActivationFactory(classid, &factory);",
            '    *served = module;\n'
            '    diagnostic_ro("RoGetActivationFactory", "dispatch", classid, iid, S_OK, module);\n'
            "    hr = pDllGetActivationFactory(classid, &factory);")
    replace(source, "dlls/combase/roapi.c",
            '    HRESULT hr = get_activation_factory(classid, iid, class_factory);',
            '    HMODULE served = NULL;\n    HRESULT hr;\n'
            '    diagnostic_ro("RoGetActivationFactory", "enter", classid, iid, S_OK, NULL);\n'
            '    hr = get_activation_factory(classid, iid, class_factory, &served);\n'
            '    diagnostic_ro("RoGetActivationFactory", "exit", classid, iid, hr, served);')
    replace(source, "dlls/combase/roapi.c", "    hr = RoGetActivationFactory(classid, &IID_IActivationFactory, (void **)&factory);",
            '    diagnostic_ro("RoActivateInstance", "enter", classid, &IID_IInspectable, S_OK, NULL);\n'
            '    hr = RoGetActivationFactory(classid, &IID_IActivationFactory, (void **)&factory);')
    replace(source, "dlls/combase/roapi.c",
            '    trace_package_activation("RoActivateInstance", classid, &IID_IInspectable, hr);',
            '    diagnostic_ro("RoActivateInstance", "exit", classid, &IID_IInspectable, hr, NULL);\n'
            '    trace_package_activation("RoActivateInstance", classid, &IID_IInspectable, hr);')
    replace(source, "dlls/ntdll/unix/thread.c", "static NTSTATUS spawn_thread( struct thread_data *data )",
            '#include "package_address_diagnostics.h"\n#include "package_thread_diagnostics.h"\n\n'
            "static NTSTATUS spawn_thread( struct thread_data *data )")
    replace(source, "dlls/ntdll/unix/thread.c", "NTSTATUS WINAPI GPT_IMPORT(NtCreateThreadEx)(",
            "NTSTATUS WINAPI GPT_IMPORT(NtCreateThreadEx)(HANDLE *, ACCESS_MASK, OBJECT_ATTRIBUTES *, HANDLE,\n"
            "    PRTL_THREAD_START_ROUTINE, void *, ULONG, ULONG_PTR, SIZE_T, SIZE_T, PS_ATTRIBUTE_LIST *);\n\n"
            "static NTSTATUS diagnostic_original_create_thread(")
    thread = source / "dlls/ntdll/unix/thread.c"
    thread.write_text(thread.read_text() + """
NTSTATUS WINAPI GPT_IMPORT(NtCreateThreadEx)(HANDLE *handle, ACCESS_MASK access, OBJECT_ATTRIBUTES *attr,
    HANDLE process, PRTL_THREAD_START_ROUTINE start, void *param, ULONG flags, ULONG_PTR zero_bits,
    SIZE_T stack_commit, SIZE_T stack_reserve, PS_ATTRIBUTE_LIST *attr_list)
{
    NTSTATUS result;
    if (process == NtCurrentProcess()) diagnostic_thread("enter", start, NULL, STATUS_PENDING);
    result = diagnostic_original_create_thread(handle, access, attr, process, start, param, flags,
                                               zero_bits, stack_commit, stack_reserve, attr_list);
    if (process == NtCurrentProcess()) diagnostic_thread("exit", start, result ? NULL : *handle, result);
    return result;
}
""")
    signal = source / "dlls/ntdll/unix/signal_x86_64.c"
    signal.write_text(signal.read_text() + """
void *package_diagnostic_syscall_return(void)
{
    struct syscall_frame *frame = get_syscall_frame(get_thread_data());
    return frame ? (void *)frame->rip : NULL;
}
NTSTATUS package_diagnostic_stack_return(void **address)
{
    struct syscall_frame *frame = get_syscall_frame(get_thread_data());
    SIZE_T read;
    *address = NULL;
    if (!frame) return STATUS_UNSUCCESSFUL;
    return NtReadVirtualMemory(NtCurrentProcess(), (void *)frame->rsp, address, sizeof(*address), &read);
}
""")
    return {"files": {relative: sha256(source / relative) for relative in (
        "dlls/combase/roapi.c", "dlls/ntdll/unix/thread.c", "dlls/ntdll/unix/signal_x86_64.c",
        "dlls/ntdll/unix/sync.c")},
        "registration_api": "RoGetActivatableClassRegistration is an existing stub with no known ABI in this Wine source; no signature or success invented"}
