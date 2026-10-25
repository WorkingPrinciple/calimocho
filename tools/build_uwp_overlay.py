"""Build a new cell009 process-record sibling, never execute Wine."""
import argparse
import json
import os
from pathlib import Path
import shutil

from tools.build_gameinput_overlay import WINE, compile_flags
from tools.build_launcher_overlay import REPO
from tools.port_uwp_activation import port
from tools.port_uwp_activation import replace
from tools.probe_wine_source import run_step, sha256

BASE = REPO / "build/winehq-11.20/package-launcher-01"


def build(root, resume=False, call_diagnostics=False, activation_wait_diagnostics=False, handle_provenance=False, exception_diagnostics=False, failfast_diagnostics=False, status_diagnostics=False, claims_site_b=False, claims_thread_token=False, claims_packaged_thread=False, onecore_transform=False, coremessaging_prerequisites=False, alpc_transport=False, restricted_token=False, alpc_identity=False, token_identity=False, token_security=False, alpc_impersonation=False, registrar_service=False, coremsg_dispatch=False, appcontainer_object_path=False):
    root = Path(root).resolve()
    if not root.is_relative_to(REPO / "build") or root == BASE:
        raise ValueError("Require a new owned009 sibling")
    if any(root.glob("*FROZEN*")):
        raise ValueError("Refuse to rebuild a frozen009 sibling")
    if activation_wait_diagnostics and not call_diagnostics:
        raise ValueError("Activation/wait diagnostics require call diagnostics")
    if handle_provenance and not activation_wait_diagnostics:
        raise ValueError("Handle provenance requires activation/wait diagnostics")
    if exception_diagnostics and not handle_provenance:
        raise ValueError("Exception diagnostics require handle provenance")
    if failfast_diagnostics and not exception_diagnostics:
        raise ValueError("Fail-fast diagnostics require exception diagnostics")
    if status_diagnostics and not failfast_diagnostics:
        raise ValueError("Status diagnostics require fail-fast diagnostics")
    if claims_site_b and not status_diagnostics:
        raise ValueError("Claims Site B requires retained status diagnostics")
    if claims_thread_token and (not status_diagnostics or claims_site_b):
        raise ValueError("Thread-token claims require status diagnostics and exclude the r6 mode")
    if claims_packaged_thread and (not status_diagnostics or claims_site_b or claims_thread_token):
        raise ValueError("Packaged thread claims require status diagnostics and exclude older claims modes")
    if onecore_transform and not claims_packaged_thread:
        raise ValueError("OneCore query requires retained023 claims and diagnostics")
    if coremessaging_prerequisites and not onecore_transform:
        raise ValueError("CoreMessaging prerequisites require retained024 query and diagnostics")
    if alpc_transport and (not coremessaging_prerequisites or resume):
        raise ValueError("ALPC transport requires a fresh CoreMessaging source sibling")
    if restricted_token and not alpc_transport:
        raise ValueError("Restricted-token source requires the fresh ALPC candidate")
    if alpc_identity and not restricted_token:
        raise ValueError("ALPC identity requires restricted-token source")
    if token_identity and not alpc_identity:
        raise ValueError("Token identity requires the fresh ALPC identity candidate")
    if token_security and not token_identity:
        raise ValueError("Token security requires the fresh token identity candidate")
    if alpc_impersonation and not token_security:
        raise ValueError("ALPC impersonation requires the fresh token security candidate")
    if registrar_service and not alpc_impersonation:
        raise ValueError("Registrar service requires the fresh ALPC impersonation candidate")
    if coremsg_dispatch and not (registrar_service and onecore_transform):
        raise ValueError("CoreMessaging dispatch requires the fresh registrar and OneCore candidate")
    if appcontainer_object_path and (not coremsg_dispatch or resume):
        raise ValueError("Named-object-path research requires a fresh CoreMessaging dispatch sibling")
    frozen = BASE / "cell008-receipt.json"
    if sha256(frozen) != "ac5b627263c409b804e3f812160c6dd0ba8d39cec52910255725939de12915bc":
        raise ValueError("Frozen008 receipt changed")
    if resume:
        if not (root / "build-receipt.json").is_file():
            raise ValueError("Resume requires this builder's receipt")
        previous = json.loads((root / "build-receipt.json").read_text())
        if "steps" in previous and bool(previous.get("call_diagnostics")) != call_diagnostics:
            raise ValueError("Resume must preserve the diagnostic build mode")
        if "steps" in previous and bool(previous.get("activation_wait_diagnostics")) != activation_wait_diagnostics:
            raise ValueError("Resume must preserve the activation/wait diagnostic mode")
        if "steps" in previous and bool(previous.get("handle_provenance")) != handle_provenance:
            raise ValueError("Resume must preserve the handle-provenance mode")
        if "steps" in previous and bool(previous.get("exception_diagnostics")) != exception_diagnostics:
            raise ValueError("Resume must preserve the exception-diagnostic mode")
        if "steps" in previous and bool(previous.get("failfast_diagnostics")) != failfast_diagnostics:
            raise ValueError("Resume must preserve the fail-fast diagnostic mode")
        if "steps" in previous and bool(previous.get("status_diagnostics")) != status_diagnostics:
            raise ValueError("Resume must preserve the status diagnostic mode")
        if "steps" in previous and bool(previous.get("claims_site_b")) != claims_site_b:
            raise ValueError("Resume must preserve the claims Site B mode")
        if "steps" in previous and bool(previous.get("claims_thread_token")) != claims_thread_token:
            raise ValueError("Resume must preserve the claims thread-token mode")
        if "steps" in previous and bool(previous.get("claims_packaged_thread")) != claims_packaged_thread:
            raise ValueError("Resume must preserve the packaged thread-token mode")
        if "steps" in previous and bool(previous.get("onecore_transform")) != onecore_transform:
            raise ValueError("Resume must preserve the OneCore query mode")
        if "steps" in previous and bool(previous.get("coremessaging_prerequisites")) != coremessaging_prerequisites:
            raise ValueError("Resume must preserve the CoreMessaging prerequisite mode")
    else:
        root.mkdir(exist_ok=False)
        shutil.copytree(BASE / "source", root / "source", symlinks=True)
        port(root / "source")
    module = root / "source/dlls/twinapi.appcore"
    for original, destination in (("core_application_activated.c", "core_application.c"),
                                  ("package_activation.idl", "package_activation.idl")):
        shutil.copy2(REPO / "patches/wine/files" / original, module / destination)
    makefile = module / "Makefile.in"
    text = makefile.read_text()
    if "\tpackage_activation.idl" not in text:
        makefile.write_text(text.replace("\tcore_application.c \\", "\tcore_application.c \\\n\tpackage_activation.idl \\"))
    text = makefile.read_text()
    makefile.write_text(text.replace("IMPORTS   = combase advapi32", "IMPORTS   = combase advapi32 ntdll"))
    ui = root / "source/dlls/windows.ui"
    shutil.copy2(REPO / "patches/wine/files/corewindow_host.c", ui / "corewindow_host.c")
    ui_make = ui / "Makefile.in"
    if "\tcorewindow_host.c" not in ui_make.read_text():
        replace(root / "source", "dlls/windows.ui/Makefile.in", "\tcorewindow.c \\",
                "\tcorewindow.c \\\n\tcorewindow_host.c \\")
        replace(root / "source", "dlls/windows.ui/corewindow.c", '#include "private.h"',
                '#include "private.h"\nextern HRESULT WINAPI wine_get_core_window(ICoreWindow **out);')
        replace(root / "source", "dlls/windows.ui/corewindow.c", "*windows = NULL;\n    return S_OK;",
                "return wine_get_core_window(windows);")
        spec = ui / "windows.ui.spec"
        spec.write_text(spec.read_text() + "\n@ stdcall __wine_create_core_window(ptr)\n")
    record = root / "build-receipt.json"
    if not record.exists():
        record.write_text(json.dumps({"status": "source-port-incomplete", "runtime_executed": False}) + "\n")
    diagnostic_port = None
    if call_diagnostics:
        from tools.port_call_diagnostics import port as diagnostic_port_source
        diagnostic_port = diagnostic_port_source(root / "source")
    activation_port = None
    if activation_wait_diagnostics:
        from tools.port_activation_wait_diagnostics import port as activation_port_source
        activation_port = activation_port_source(root / "source")
    handle_port = None
    if handle_provenance:
        from tools.port_handle_provenance import port as handle_port_source
        handle_port = handle_port_source(root / "source")
    exception_port = None
    if exception_diagnostics:
        from tools.port_exception_diagnostics import port as exception_port_source
        exception_port = exception_port_source(root / "source")
    failfast_port = None
    if failfast_diagnostics:
        from tools.port_failfast_diagnostics import port as failfast_port_source
        failfast_port = failfast_port_source(root / "source")
    status_port = None
    if status_diagnostics:
        from tools.port_status_diagnostics import port as status_port_source
        status_port = status_port_source(root / "source")
    claims_port = None
    if resume and coremessaging_prerequisites:
        # Revalidate the unchanged claims seam before reapplying our additive source entry.
        make = root / "source/dlls/ntdll/Makefile.in"
        text = make.read_text()
        extra = "\tcoremessaging_ntdll_stubs.c \\\n"
        if text.count(extra) == 1:
            make.write_text(text.replace(extra, ""))
        elif extra in text:
            raise ValueError("Repeated CoreMessaging stub source entry")
    if claims_site_b:
        from tools.port_claims_site_b import port as claims_port_source
        claims_port = claims_port_source(root / "source")
    thread_token_port = None
    if claims_thread_token or claims_packaged_thread:
        from tools.port_claims_thread_token import port as thread_token_source
        thread_token_port = thread_token_source(root / "source", packaged=claims_packaged_thread)
    onecore_port = None
    if onecore_transform:
        from tools.port_onecore_transform import port as onecore_source
        onecore_port = onecore_source(root / "source")
    coremessaging_port = None
    if coremessaging_prerequisites:
        from tools.port_coremessaging_prerequisites import port as coremessaging_source
        coremessaging_port = coremessaging_source(root / "source")
    alpc_port = None
    if alpc_transport:
        from tools.port_alpc_transport import port as alpc_source
        alpc_port = alpc_source(root / "source")
    restricted_port = None
    if restricted_token:
        from tools.port_restricted_token import port as restricted_source
        restricted_port = restricted_source(root / "source")
    identity_port = None
    if alpc_identity:
        from tools.port_alpc_identity import port as identity_source
        identity_port = identity_source(root / "source")
    token_identity_port = None
    if token_identity:
        from tools.port_token_identity import port as token_identity_source
        token_identity_port = token_identity_source(root / "source")
    token_security_port = None
    if token_security:
        from tools.port_token_security import port as token_security_source
        token_security_port = token_security_source(root / "source")
    impersonation_port = None
    if alpc_impersonation:
        from tools.port_alpc_impersonation import port as impersonation_source
        impersonation_port = impersonation_source(root / "source")
        from tools.port_alpc_connect_attrs import port as connect_attrs_source
        connect_attrs_port = connect_attrs_source(root / "source")
        from tools.port_alpc_sync_request import port as sync_request_source
        sync_request_port = sync_request_source(root / "source")
        from tools.port_alpc_work_on_behalf import port as work_on_behalf_source
        work_on_behalf_port = work_on_behalf_source(root / "source")
        from tools.port_alpc_release_reply import port as release_reply_source
        release_reply_port = release_reply_source(root / "source")
    registrar_port = None
    if registrar_service:
        from tools.port_registrar_service import port as registrar_source
        registrar_port = registrar_source(root / "source")
        from tools.port_sechost_services import port as sechost_source
        sechost_port = sechost_source(root / "source")
    dispatch_port = None
    if coremsg_dispatch:
        from tools.port_coremsg_dispatch import port as dispatch_source
        dispatch_port = dispatch_source(root / "source")
        from tools.port_theme_color_preference import port as theme_source
        theme_port = theme_source(root / "source")
    object_path_port = None
    if appcontainer_object_path:
        from tools.port_appcontainer_object_path import port as object_path_source
        object_path_port = object_path_source(root / "source")
    from tools.port_server_request_limits import port as request_limits_source
    request_limits_port = request_limits_source(root / "source")
    telemetry_port = None
    if coremsg_dispatch:
        # Last: wraps the final ALPC, wait-packet and kernelbase fail-fast sources.
        from tools.port_alpc_telemetry import port as telemetry_source
        telemetry_port = telemetry_source(root / "source")
    attempt = 1
    while (root / ("attempt-%02d" % attempt)).exists():
        attempt += 1
    logs = root / ("attempt-%02d" % attempt)
    logs.mkdir()
    if record.exists():
        shutil.copy2(record, logs / "previous-receipt.json")
    directory = root / "build"
    directory.mkdir(exist_ok=True)
    baseline = json.loads((WINE / "receipt.json").read_text())
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("WINE", "DYLD_", "CX_", "MVK_", "PKG_CONFIG"))
           and key not in ("CPATH", "LIBRARY_PATH", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS")}
    env.update(baseline["environment"])
    env["PATH"] = "/opt/homebrew/opt/bison/bin:" + env["PATH"]
    env["ac_cv_lib_soname_MoltenVK"] = "@rpath/libMoltenVK.dylib"
    env["ac_cv_lib_soname_gnutls"] = "@rpath/libgnutls.30.dylib"
    receipt = {"status": "incomplete", "runtime_executed": False, "steps": [],
               "predecessor_receipt_sha256": sha256(frozen)}
    if diagnostic_port is not None:
        receipt["call_diagnostics"] = diagnostic_port
    if activation_port is not None:
        receipt["activation_wait_diagnostics"] = activation_port
        # The activation port adds includes to sync.c after the call port.
        for relative in receipt["call_diagnostics"]["files"]:
            receipt["call_diagnostics"]["files"][relative] = sha256(root / "source" / relative)
    if handle_port is not None:
        receipt["handle_provenance"] = handle_port
        for group in ("call_diagnostics", "activation_wait_diagnostics"):
            for relative in receipt[group]["files"]:
                receipt[group]["files"][relative] = sha256(root / "source" / relative)
    if exception_port is not None:
        receipt["exception_diagnostics"] = exception_port
        for group in ("call_diagnostics", "activation_wait_diagnostics", "handle_provenance"):
            for relative in receipt[group]["files"]:
                receipt[group]["files"][relative] = sha256(root / "source" / relative)
    if failfast_port is not None:
        receipt["failfast_diagnostics"] = failfast_port
        for group in ("call_diagnostics", "activation_wait_diagnostics", "handle_provenance", "exception_diagnostics"):
            for relative in receipt[group]["files"]:
                receipt[group]["files"][relative] = sha256(root / "source" / relative)
    if status_port is not None:
        receipt["status_diagnostics"] = status_port
        for group in ("call_diagnostics", "activation_wait_diagnostics", "handle_provenance", "exception_diagnostics", "failfast_diagnostics"):
            for relative in receipt[group]["files"]:
                receipt[group]["files"][relative] = sha256(root / "source" / relative)
    if claims_port is not None:
        receipt["claims_site_b"] = claims_port
    if thread_token_port is not None:
        receipt["claims_packaged_thread" if claims_packaged_thread else "claims_thread_token"] = thread_token_port
    if onecore_port is not None:
        receipt["onecore_transform"] = onecore_port
    if coremessaging_port is not None:
        receipt["coremessaging_prerequisites"] = coremessaging_port
        for group in ("call_diagnostics", "activation_wait_diagnostics", "handle_provenance",
                      "exception_diagnostics", "failfast_diagnostics", "status_diagnostics",
                      "claims_packaged_thread", "onecore_transform"):
            for relative in receipt[group]["files"]:
                receipt[group]["files"][relative] = sha256(root / "source" / relative)
    if alpc_port is not None:
        receipt["alpc_transport"] = alpc_port
        for group in ("call_diagnostics", "activation_wait_diagnostics", "handle_provenance",
                      "exception_diagnostics", "failfast_diagnostics", "status_diagnostics",
                      "claims_packaged_thread", "onecore_transform", "coremessaging_prerequisites"):
            for relative in receipt[group]["files"]:
                receipt[group]["files"][relative] = sha256(root / "source" / relative)
    if restricted_port is not None:
        receipt["restricted_token"] = restricted_port
        for group in ("handle_provenance", "claims_packaged_thread", "coremessaging_prerequisites"):
            for relative in receipt[group]["files"]:
                receipt[group]["files"][relative] = sha256(root / "source" / relative)
    if identity_port is not None:
        receipt["alpc_identity"] = identity_port
    if token_identity_port is not None:
        receipt["token_identity"] = token_identity_port
    if token_security_port is not None:
        receipt["token_security"] = token_security_port
    if impersonation_port is not None:
        receipt["alpc_impersonation"] = impersonation_port
        receipt["alpc_connect_attrs"] = connect_attrs_port
        receipt["alpc_sync_request"] = sync_request_port
        receipt["alpc_work_on_behalf"] = work_on_behalf_port
        receipt["alpc_release_reply"] = release_reply_port
    if registrar_port is not None:
        receipt["registrar_service"] = registrar_port
        receipt["sechost_services"] = sechost_port
    if dispatch_port is not None:
        receipt["coremsg_dispatch"] = dispatch_port
        receipt["theme_color_preference"] = theme_port
    if object_path_port is not None:
        receipt["appcontainer_object_path"] = object_path_port
        receipt["runtime_admission_blocked"] = (
            "XB-58: current-native non-AppContainer absolute-path output remains unresolved; "
            "this research build is not a frozen runtime candidate")
    receipt["server_request_limits"] = request_limits_port
    if telemetry_port is not None:
        receipt["alpc_telemetry"] = telemetry_port

    def run(name, command, budget=300, cwd=directory):
        step = run_step(command, cwd, env, logs / (name + ".log"), budget)
        receipt["steps"].append(step)
        record.write_text(json.dumps(receipt, indent=2) + "\n")
        if step["exit_code"] or step["timed_out"]:
            raise RuntimeError("Build failed: " + str(logs / (name + ".log")))

    args = [str(root / "source/configure")] + baseline["steps"][0]["command"][1:]
    args = [arg for arg in args if not arg.startswith("--prefix=")] + ["--prefix=" + str(root / "install")]
    if coremessaging_prerequisites:
        run("syscalls", ["/usr/bin/perl", "tools/make_specfiles"], cwd=root / "source")
        for relative in ("dlls/ntdll/ntsyscalls.h", "dlls/ntdll/ntdll.spec"):
            receipt["coremessaging_prerequisites"]["files"][relative] = sha256(root / "source" / relative)
    run("protocol", ["/usr/bin/perl", "tools/make_requests"], cwd=root / "source")
    if coremessaging_prerequisites:
        for relative in ("include/wine/server_protocol.h", "server/request_handlers.h", "server/request_trace.h"):
            receipt["coremessaging_prerequisites"]["files"][relative] = sha256(root / "source" / relative)
    run("configure", args)
    targets = ["/usr/bin/make", "-j4", "server/wineserver",
                       "dlls/ntdll/ntdll.so", "dlls/ntdll/x86_64-windows/ntdll.dll",
                       "dlls/twinapi.appcore/x86_64-windows/twinapi.appcore.dll",
                       "dlls/windows.ui/x86_64-windows/windows.ui.dll"]
    if activation_wait_diagnostics:
        targets.append("dlls/combase/x86_64-windows/combase.dll")
    if handle_provenance:
        targets.append("dlls/rpcrt4/x86_64-windows/rpcrt4.dll")
    if onecore_transform:
        targets.append("dlls/user32/x86_64-windows/user32.dll")
    if coremessaging_prerequisites:
        targets.append("dlls/ucrtbase/x86_64-windows/ucrtbase.dll")
    if registrar_service:
        targets.append("programs/services/x86_64-windows/services.exe")
        targets.append("dlls/sechost/x86_64-windows/sechost.dll")
    if coremsg_dispatch:
        targets += ["dlls/win32u/win32u.so", "dlls/win32u/x86_64-windows/win32u.dll",
                    "dlls/apisetschema/x86_64-windows/apisetschema.dll",
                    "dlls/kernelbase/x86_64-windows/kernelbase.dll",
                    "dlls/uxtheme/x86_64-windows/uxtheme.dll"]
    run("server-ntdll", targets, budget=600)
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler:
        raise RuntimeError("Require existing MinGW compiler")
    launcher = root / "source/dlls/windows.system.launcher"
    include = root / "launcher-include"
    include.mkdir(exist_ok=True)
    for name in ("launcher", "async_private"):
        run(name + "-header", [str(WINE / "build/tools/widl/widl"), "-h",
                              "-o", str(include / (name + ".h")),
                              "-I", str(root / "source/include"), str(launcher / (name + ".idl"))])
    objects = []
    for name in ("main", "async"):
        obj = root / (name + ".o")
        run("launcher-" + name, [compiler, "-c", "-I" + str(root / "source/include"),
                                *compile_flags(include), "-I" + str(launcher),
                                "-D_UCRT", "-fno-strict-aliasing", "-ffunction-sections",
                                "-mlong-double-64", "-mcx16", "-mcmodel=small",
                                str(launcher / (name + ".c")), "-o", str(obj)])
        objects.append(str(obj))
    libraries = [directory / relative for relative in (
        "libs/winecrt0/x86_64-windows/libwinecrt0.a", "libs/compiler-rt/x86_64-windows/libcompiler-rt.a",
        "dlls/ucrtbase/x86_64-windows/libucrtbase.a", "dlls/kernel32/x86_64-windows/libkernel32.a",
        "dlls/ntdll/x86_64-windows/libntdll.a", "dlls/combase/x86_64-windows/libcombase.a",
        "libs/uuid/x86_64-windows/libuuid.a")]
    # UUIDs are generated only by targets that need them; use the exact frozen base archive.
    libraries[-1] = WINE / "build/libs/uuid/x86_64-windows/libuuid.a"
    run("launcher-link", [str(WINE / "build/tools/winegcc/winegcc"), "--wine-objdir", str(directory),
                          "--cc-cmd=" + compiler, "-b", "x86_64-w64-mingw32", "-shared",
                          "-Wl,--wine-builtin", str(launcher / "windows.system.launcher.spec"),
                          *objects, *map(str, libraries), "-o", str(root / "windows.system.launcher.dll")])
    receipt["status"] = "built-not-staged-not-executed"
    if alpc_port is not None:
        for relative in receipt["alpc_transport"]["files"]:
            receipt["alpc_transport"]["files"][relative] = sha256(root / "source" / relative)
    if restricted_port is not None:
        for relative in receipt["restricted_token"]["files"]:
            receipt["restricted_token"]["files"][relative] = sha256(root / "source" / relative)
    if identity_port is not None:
        for group in ("alpc_identity", "alpc_transport", "restricted_token",
                      "handle_provenance", "claims_packaged_thread", "coremessaging_prerequisites"):
            for relative in receipt[group]["files"]:
                receipt[group]["files"][relative] = sha256(root / "source" / relative)
    if token_identity_port is not None:
        for group in ("token_identity", "alpc_identity", "alpc_transport", "restricted_token",
                      "handle_provenance", "claims_packaged_thread", "coremessaging_prerequisites"):
            for relative in receipt[group]["files"]:
                receipt[group]["files"][relative] = sha256(root / "source" / relative)
    if token_security_port is not None:
        for group in ("token_security", "token_identity", "alpc_identity", "alpc_transport", "restricted_token",
                      "handle_provenance", "claims_packaged_thread", "coremessaging_prerequisites"):
            for relative in receipt[group]["files"]:
                receipt[group]["files"][relative] = sha256(root / "source" / relative)
    if impersonation_port is not None:
        for group in ("alpc_impersonation", "token_security", "token_identity", "alpc_identity",
                      "alpc_transport", "restricted_token", "handle_provenance",
                      "claims_packaged_thread", "coremessaging_prerequisites"):
            for relative in receipt[group]["files"]:
                receipt[group]["files"][relative] = sha256(root / "source" / relative)
    receipt["source_inputs"] = {
        str(path.relative_to(REPO)): sha256(path) for path in (
            REPO / "tools/port_uwp_activation.py", REPO / "tools/build_uwp_overlay.py",
            REPO / "patches/wine/files/core_application_activated.c",
            REPO / "patches/wine/files/corewindow_host.c",
            REPO / "patches/wine/files/package_activation.idl",
            REPO / "patches/wine/files/package_activation_record.h")}
    if call_diagnostics:
        for relative in ("tools/port_call_diagnostics.py",
                         "patches/wine/files/package_call_diagnostics.h",
                         "patches/wine/files/package_relay_diagnostics.h",
                         "patches/wine/files/package_wait_diagnostics.h",
                         "patches/wine/files/package_address_diagnostics.h",
                         "patches/wine/contracts/istaticlifetime-diagnostics.json",
                         "patches/wine/files/whiny_diagnostics_17b0e613_942a_422d_904c_f90dc71a7dae.h",
                         "patches/wine/files/istaticlifetime-relay-filter.txt"):
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if activation_wait_diagnostics:
        from tools.port_activation_wait_diagnostics import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if handle_provenance:
        from tools.port_handle_provenance import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if exception_diagnostics:
        from tools.port_exception_diagnostics import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if failfast_diagnostics:
        from tools.port_failfast_diagnostics import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if status_diagnostics:
        from tools.port_status_diagnostics import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if claims_site_b:
        from tools.port_claims_site_b import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if claims_thread_token:
        from tools.port_claims_thread_token import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if claims_packaged_thread:
        from tools.port_claims_thread_token import PACKAGED_SOURCES
        for relative in PACKAGED_SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if onecore_transform:
        from tools.port_onecore_transform import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if coremessaging_prerequisites:
        from tools.port_coremessaging_prerequisites import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if alpc_transport:
        from tools.port_alpc_transport import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if restricted_token:
        from tools.port_restricted_token import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if alpc_identity:
        from tools.port_alpc_identity import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if token_identity:
        from tools.port_token_identity import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if token_security:
        from tools.port_token_security import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if alpc_impersonation:
        from tools.port_alpc_impersonation import SOURCES
        from tools.port_alpc_connect_attrs import SOURCES as CONNECT_SOURCES
        from tools.port_alpc_sync_request import SOURCES as SYNC_SOURCES
        from tools.port_alpc_work_on_behalf import SOURCES as WORK_SOURCES
        from tools.port_alpc_release_reply import SOURCES as RELEASE_SOURCES
        for relative in SOURCES + CONNECT_SOURCES + SYNC_SOURCES + WORK_SOURCES + RELEASE_SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if registrar_service:
        from tools.port_registrar_service import SOURCES
        from tools.port_sechost_services import SOURCES as SECHOST_SOURCES
        for relative in SOURCES + SECHOST_SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if coremsg_dispatch:
        from tools.port_coremsg_dispatch import SOURCES
        from tools.port_theme_color_preference import SOURCES as THEME_SOURCES
        for relative in SOURCES + THEME_SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    if appcontainer_object_path:
        from tools.port_appcontainer_object_path import SOURCES
        for relative in SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    from tools.port_server_request_limits import SOURCES
    for relative in SOURCES:
        receipt["source_inputs"][relative] = sha256(REPO / relative)
        for group, value in list(receipt.items()):
            if isinstance(value, dict) and "files" in value:
                for relative in value["files"]:
                    value["files"][relative] = sha256(root / "source" / relative)
    if coremsg_dispatch:
        from tools.port_alpc_telemetry import SOURCES as TELEMETRY_SOURCES
        for relative in TELEMETRY_SOURCES:
            receipt["source_inputs"][relative] = sha256(REPO / relative)
    receipt["built_files"] = {str(path.relative_to(root)): sha256(path) for path in (
        directory / "server/wineserver", directory / "dlls/ntdll/ntdll.so",
        directory / "dlls/ntdll/x86_64-windows/ntdll.dll",
        directory / "dlls/twinapi.appcore/x86_64-windows/twinapi.appcore.dll",
        directory / "dlls/windows.ui/x86_64-windows/windows.ui.dll",
        root / "windows.system.launcher.dll")}
    if activation_wait_diagnostics:
        relative = "build/dlls/combase/x86_64-windows/combase.dll"
        receipt["built_files"][relative] = sha256(root / relative)
    if handle_provenance:
        relative = "build/dlls/rpcrt4/x86_64-windows/rpcrt4.dll"
        receipt["built_files"][relative] = sha256(root / relative)
    if onecore_transform:
        relative = "build/dlls/user32/x86_64-windows/user32.dll"
        receipt["built_files"][relative] = sha256(root / relative)
    if coremessaging_prerequisites:
        relative = "build/dlls/ucrtbase/x86_64-windows/ucrtbase.dll"
        receipt["built_files"][relative] = sha256(root / relative)
    if registrar_service:
        for relative in ("build/programs/services/x86_64-windows/services.exe",
                         "build/dlls/sechost/x86_64-windows/sechost.dll"):
            receipt["built_files"][relative] = sha256(root / relative)
    if coremsg_dispatch:
        for relative in ("build/dlls/win32u/win32u.so", "build/dlls/win32u/x86_64-windows/win32u.dll",
                         "build/dlls/apisetschema/x86_64-windows/apisetschema.dll",
                         "build/dlls/kernelbase/x86_64-windows/kernelbase.dll",
                         "build/dlls/uxtheme/x86_64-windows/uxtheme.dll"):
            receipt["built_files"][relative] = sha256(root / relative)
    from tools.check_ntdll_syscall_exports import check as check_syscall_exports
    receipt["ntdll_syscall_exports"] = check_syscall_exports(
        directory / "dlls/ntdll/x86_64-windows/ntdll.dll", root / "source/dlls/ntdll/ntsyscalls.h")
    receipt["source_inputs"]["tools/check_ntdll_syscall_exports.py"] = sha256(REPO / "tools/check_ntdll_syscall_exports.py")
    record.write_text(json.dumps(receipt, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--call-diagnostics", action="store_true")
    parser.add_argument("--activation-wait-diagnostics", action="store_true")
    parser.add_argument("--handle-provenance", action="store_true")
    parser.add_argument("--exception-diagnostics", action="store_true")
    parser.add_argument("--failfast-diagnostics", action="store_true")
    parser.add_argument("--status-diagnostics", action="store_true")
    parser.add_argument("--claims-site-b", action="store_true")
    parser.add_argument("--claims-thread-token", action="store_true")
    parser.add_argument("--claims-packaged-thread", action="store_true")
    parser.add_argument("--onecore-transform", action="store_true")
    parser.add_argument("--coremessaging-prerequisites", action="store_true")
    parser.add_argument("--alpc-transport", action="store_true")
    parser.add_argument("--restricted-token", action="store_true")
    parser.add_argument("--alpc-identity", action="store_true")
    parser.add_argument("--token-identity", action="store_true")
    parser.add_argument("--token-security", action="store_true")
    parser.add_argument("--alpc-impersonation", action="store_true")
    parser.add_argument("--registrar-service", action="store_true")
    parser.add_argument("--coremsg-dispatch", action="store_true")
    parser.add_argument("--appcontainer-object-path", action="store_true",
                        help="XB-58 research only; native non-AppContainer contract remains unresolved")
    args = parser.parse_args()
    print(build(args.root, args.resume, args.call_diagnostics, args.activation_wait_diagnostics, args.handle_provenance, args.exception_diagnostics, args.failfast_diagnostics, args.status_diagnostics, args.claims_site_b, args.claims_thread_token, args.claims_packaged_thread, args.onecore_transform, args.coremessaging_prerequisites, args.alpc_transport, args.restricted_token, args.alpc_identity, args.token_identity, args.token_security, args.alpc_impersonation, args.registrar_service, args.coremsg_dispatch, args.appcontainer_object_path))
