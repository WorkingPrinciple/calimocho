"""Collect bounded activation evidence without persisting raw application traces."""
import argparse
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import subprocess
import tempfile
import time


class CallDiagnostics:
    """Fixed metadata only; preserve a bounded relay tail at actual wait entry."""
    IID = r"(?:none|\{[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\})"
    OBJECTS = r"(?:CoreFactory|CoreApplication|CoreApplicationView|StaticLifetime|StaticCollection|CoreWindow|CoreDispatcher)"
    WAIT = r"(?:NtWaitForSingleObject|NtWaitForMultipleObjects|NtSignalAndWaitForSingleObject)"
    COMMON = frozenset("QueryInterface AddRef Release GetIids GetRuntimeClassName GetTrustLevel".split())
    METHODS = {
        "CoreFactory": frozenset(("ActivateInstance",)),
        "CoreApplication": frozenset("get_Id add_Suspending remove_Suspending add_Resuming remove_Resuming get_Properties GetCurrentView Run RunWithActivationFactories".split()),
        "CoreApplicationView": frozenset("get_CoreWindow add_Activated remove_Activated get_IsMain get_IsHosted".split()),
        "StaticLifetime": frozenset(("Reserved", "GetCollection", "AddCallback", "RemoveCallback",
                                     "Slot8", "Slot9", "Slot10", "Slot13", "Slot14", "Slot15", "Slot16", "Slot17", "Slot18")),
        "StaticCollection": frozenset("Lookup get_Size HasKey GetView Insert Remove Clear".split()),
        "CoreDispatcher": frozenset("get_HasThreadAccess ProcessEvents RunAsync RunIdleAsync".split()),
        "CoreWindow": frozenset("get_AutomationHostProvider get_Bounds get_CustomProperties get_Dispatcher get_FlowDirection put_FlowDirection get_IsInputEnabled put_IsInputEnabled get_PointerCursor put_PointerCursor get_PointerPosition get_Visible Activate Close GetAsyncKeyState GetKeyState ReleasePointerCapture SetPointerCapture".split())
        | frozenset(prefix + event for prefix in ("add_", "remove_") for event in (
            "Activated AutomationProviderRequested CharacterReceived Closed InputEnabled KeyDown KeyUp "
            "PointerCaptureLost PointerEntered PointerExited PointerMoved PointerPressed PointerReleased "
            "TouchHitTesting PointerWheelChanged SizeChanged VisibilityChanged").split()),
    }

    def __init__(self):
        self.interfaces = deque(maxlen=65536)
        self.first_failures = []
        self.interface_count = self.sequence = 0
        self.counts, self.relays, self.first_no_interface, self.first_not_implemented = {}, {}, {}, {}
        self.active = set()
        self.pending = {}
        self.completed = deque(maxlen=32)
        self.source_limited = set()
        self.storage_limited = False
        self.phases = deque(maxlen=32)
        self.activations = deque(maxlen=4096)
        self.thread_events = deque(maxlen=1024)
        self.activation_count = self.thread_count = 0
        self.registration_abi_unavailable = set()
        self.running = set()
        self.handles = deque(maxlen=4096)
        self.rpc = deque(maxlen=1024)
        self.handle_count = self.rpc_count = 0
        self.exceptions = []
        self.origins = deque(maxlen=128)
        self.exception_limited = set()
        self.exception_policy_pids = set()
        self.error_context_scope = set()
        self.error_context = deque(maxlen=512)
        self.error_context_count = 0
        self.failfasts = []
        self.error_context_limited = set()
        self.fixmes = []
        self.fixme_count = 0
        self.status_returns = deque(maxlen=128)
        self.status_return_count = 0
        self.status_return_limited = set()

    def observe_fixme(self, pid, tid, channel, function):
        if pid not in self.running:
            return
        self.sequence += 1
        self.fixme_count += 1
        if (len(channel) > 64 or len(function) > 128
                or not re.fullmatch(r"[A-Za-z0-9_]+", channel)
                or not re.fullmatch(r"[A-Za-z0-9_]+", function)):
            return
        if len(self.fixmes) < 128:
            self.fixmes.append({"pid": pid, "tid": tid, "sequence": self.sequence,
                                "channel": channel, "function": function, "arguments": "redacted",
                                "basis": "actual FIXME emission, not proof of STATUS_NOT_IMPLEMENTED"})

    def observe(self, pid, tid, channel, function, message):
        if channel == "pkgcore" and function == "application_run" and message == "exception-policy no-gpfault-dialog=1":
            self.exception_policy_pids.add(pid)
            return
        if channel not in ("pkgiface", "pkgrelay", "pkgwait", "pkgro", "pkgthread", "pkghandle", "pkgrpc", "pkgexception", "pkgstatus"):
            return
        if pid not in self.counts:
            if len(self.counts) >= 8:
                self.storage_limited = True
                return
            self.counts[pid] = {"interfaces": 0, "relays": 0, "activations": 0, "threads": 0}
            self.relays[pid] = deque(maxlen=300)
        self.sequence += 1
        fact = {"pid": pid, "tid": tid, "sequence": self.sequence}
        if channel == "pkgstatus" and function == "diagnostic_status_return" and pid in self.running:
            if message == "status-return limited=1":
                self.status_return_limited.add(pid)
                return
            match = re.fullmatch(
                r"status-return module=([A-Za-z0-9_.-]{1,127}) export=([A-Za-z_][A-Za-z0-9_]{0,127}) "
                r"result=(c0000002|d0000002) caller=([A-Za-z0-9_.-]{1,127}) offset=([0-9a-f]{1,8})", message)
            if match:
                fact.update(module=match[1], export=match[2], result="0x" + match[3],
                            caller_module=match[4], caller_offset=match[5], source="actual-relay-return",
                            basis="matching low32 return bits; relay metadata does not prove semantic return type")
                self.status_returns.append(fact)
                self.status_return_count += 1
        elif channel == "pkgexception" and function == "diagnostic_exception" and pid in self.running:
            if message == "exception limited=1":
                self.exception_limited.add(pid)
                return
            match = re.fullmatch(
                r"exception stage=unhandled-filter id=([0-9]{1,2}) code=([0-9a-f]{8}) flags=([0-9a-f]{8}) "
                r"count=([0-9]{1,10}) module=([A-Za-z0-9_.-]{1,127}) offset=([0-9a-f]{1,16}) hresult=unknown", message)
            parameter = re.fullmatch(
                r"parameter id=([0-9]{1,2}) slot=([0-9]{1,2}) kind=(scalar|cpp-magic) value=([0-9a-f]{8})", message)
            address = re.fullmatch(
                r"parameter id=([0-9]{1,2}) slot=([0-9]{1,2}) kind=address module=([A-Za-z0-9_.-]{1,127}) offset=([0-9a-f]{1,16})", message)
            if match and len(self.exceptions) < 256:
                fact.update(id=int(match[1]), stage="unhandled-filter-entry", code="0x" + match[2],
                            flags="0x" + match[3], parameter_count=int(match[4]),
                            module=match[5], offset=match[6], hresult=None, parameters=[],
                            relay_tail=[dict(row) for row in list(self.relays[pid])[-50:]],
                            origin_candidates=[dict(row) for row in self.origins if row["pid"] == pid and row["tid"] == tid],
                            basis="actual unhandled-filter entry, not necessarily final termination")
                self.exceptions.append(fact)
            elif parameter or address:
                item = parameter or address
                row = next((row for row in reversed(self.exceptions)
                            if row["pid"] == pid and row["tid"] == tid and row["id"] == int(item[1])), None)
                if row and int(item[2]) < 15 and len(row["parameters"]) < 15:
                    value = {"slot": int(item[2]), "kind": item[3] if parameter else "address"}
                    if parameter:
                        value["value"] = "0x" + item[4]
                    else:
                        value.update(module=item[3], offset=item[4])
                    row["parameters"].append(value)
        elif channel == "pkgro" and function == "diagnostic_error_context" and pid in self.error_context_scope:
            if message in ("error-context limited=failfast", "error-context limited=operations"):
                self.error_context_limited.add(pid)
                return
            match = re.fullmatch(
                r"error-context operation=(RoFailFastWithErrorContextInternal2|RoOriginateError|RoOriginateErrorW|"
                r"RoOriginateLanguageException|GetRestrictedErrorInfo|SetRestrictedErrorInfo) "
                r"kind=(argument|return) hresult=([0-9a-f]{8}) module=([A-Za-z0-9_.-]{1,127}) offset=([0-9a-f]{1,16})",
                message)
            if not match or int(match[5], 16) > 0xffffffff:
                return
            is_return = match[1] in ("GetRestrictedErrorInfo", "SetRestrictedErrorInfo")
            if (match[2] == "return") != is_return:
                return
            fact.update(operation=match[1], hresult_kind=match[2], hresult="0x" + match[3],
                        caller_module=match[4], caller_offset=match[5],
                        basis="actual HRESULT argument" if not is_return else "actual existing stub return; no error object decoded")
            if match[1] == "RoFailFastWithErrorContextInternal2":
                if len(self.failfasts) < 32:
                    fact.update(relay_tail=[dict(row) for row in list(self.relays[pid])[-30:]],
                                interface_tail=[dict(row) for row in
                                                [row for row in self.interfaces if row["pid"] == pid][-30:]])
                    self.failfasts.append(fact)
                else:
                    self.error_context_limited.add(pid)
            else:
                self.error_context.append(fact)
                self.error_context_count += 1
        elif channel == "pkgro" and function in ("RoOriginateError", "RoOriginateErrorW", "RoOriginateLanguageException"):
            match = re.fullmatch(r"origin operation=(RoOriginateError|RoOriginateErrorW|RoOriginateLanguageException) hresult=([0-9a-f]{8})", message)
            if match and function == match[1]:
                fact.update(operation=match[1], hresult="0x" + match[2])
                self.origins.append(fact)
        elif channel == "pkghandle" and function == "diagnostic_handle" and pid in self.running:
            match = re.fullmatch(
                r"handle operation=(NtCreateEvent|NtOpenEvent|NtOpenProcess|NtDuplicateObject|NtClose|NtCreateUserProcess|NtConnectPort|NtSecureConnectPort|NtAlpcConnectPort) "
                r"phase=(enter|exit) result=([0-9a-f]{8}) handle=([0-9a-f]{1,8}) source=([0-9a-f]{1,8}) "
                r"owner=([0-9]{1,10}) peer=([0-9]{1,10}) name=(unnamed|named-redacted|DBWIN_BUFFER_READY|DBWIN_DATA_READY) "
                r"query=([0-9a-f]{8}) module=([A-Za-z0-9_.-]{1,127}) offset=([0-9a-f]{1,16}) "
                r"syscall=([A-Za-z0-9_.-]{1,127}) site=([0-9a-f]{1,16})", message)
            if match:
                fact.update(operation=match[1], phase=match[2], handle="0x" + match[4],
                            source_handle="0x" + match[5], owner_pid=int(match[6]), peer_pid=int(match[7]),
                            name=match[8], caller_query_status="0x" + match[9],
                            caller_module=match[10], caller_offset=match[11],
                            syscall_return_module=match[12], syscall_return_offset=match[13],
                            caller_basis="user-stack-return-slot-not-a-full-stack")
                if match[2] == "exit":
                    fact["result"] = "0x" + match[3]
                self.handles.append(fact)
                self.handle_count += 1
        elif channel == "pkgrpc" and function == "diagnostic_rpc" and pid in self.running:
            match = re.fullmatch(
                r"rpc operation=OpenClientConnection phase=(enter|exit) result=([0-9a-f]{8}) "
                r"module=([A-Za-z0-9_.-]{1,127}) offset=([0-9a-f]{1,16}) endpoint=redacted", message)
            if match:
                fact.update(operation="OpenClientConnection", phase=match[1], caller_module=match[3],
                            caller_offset=match[4], endpoint="redacted")
                if match[1] == "exit":
                    fact["result"] = "0x" + match[2]
                self.rpc.append(fact)
                self.rpc_count += 1
        elif channel == "pkgro" and function == "diagnostic_ro":
            match = re.fullmatch(
                r"activation operation=(RoGetActivationFactory|RoActivateInstance) phase=(enter|dispatch|exit) "
                r"class=([A-Za-z_][A-Za-z0-9_.]{0,511}|invalid-redacted) iid=(" + self.IID +
                r") result=([0-9a-f]{8}) module=([A-Za-z0-9_.-]{1,127})", message)
            if match and match[4] != "none":
                fact.update(operation=match[1], phase=match[2], runtime_class=match[3],
                            iid=match[4], serving_module=match[6])
                if match[2] == "exit":
                    fact["hresult"] = "0x" + match[5]
                self.activations.append(fact)
                self.activation_count += 1
                self.counts[pid]["activations"] += 1
        elif channel == "pkgthread" and function == "diagnostic_thread" and pid in self.active:
            creator = re.fullmatch(
                r"creator phase=(enter|exit) query=([0-9a-f]{8}) module=([A-Za-z0-9_.-]{1,127}) "
                r"offset=([0-9a-f]{1,16}) basis=user-stack-return-slot", message)
            match = re.fullmatch(
                r"thread phase=(enter|exit) result=([0-9a-f]{8}) query=([0-9a-f]{8}) "
                r"tid=([0-9]{1,10}) pid=([0-9]{1,10}) start=([A-Za-z0-9_.-]{1,127}) "
                r"offset=([0-9a-f]{1,16}) syscall=([A-Za-z0-9_.-]{1,127}) site=([0-9a-f]{1,16})", message)
            if match:
                fact.update(phase=match[1], result="0x" + match[2], query_status="0x" + match[3],
                            new_tid=int(match[4]), new_pid=int(match[5]), start_module=match[6],
                            start_offset=match[7], syscall_return_module=match[8], syscall_return_offset=match[9])
                self.thread_events.append(fact)
                self.thread_count += 1
                self.counts[pid]["threads"] += 1
            elif creator:
                fact.update(operation="creator-return-slot", phase=creator[1], query_status="0x" + creator[2],
                            module=creator[3], offset=creator[4], basis="user-stack-return-slot-not-a-full-stack")
                self.thread_events.append(fact)
                self.thread_count += 1
                self.counts[pid]["threads"] += 1
        elif channel == "pkgiface" and function == "diagnostic_interface":
            match = re.fullmatch(
                r"interface object=(" + self.OBJECTS + r") method=([A-Za-z_][A-Za-z0-9_]{0,63}) "
                r"phase=(enter|exit) iid=(" + self.IID + r") kind=(HRESULT|ULONG) result=([0-9a-f]{8})",
                message)
            if not match or (match[2] == "QueryInterface") != (match[4] != "none"):
                return
            if match[2] not in self.COMMON | self.METHODS[match[1]]:
                return
            if (match[5] == "ULONG") != (match[2] in ("AddRef", "Release")):
                return
            fact.update(object=match[1], method=match[2], phase=match[3], iid=match[4])
            if (match[1], match[2]) == ("CoreApplication", "Run"):
                if match[3] == "enter":
                    self.running.add(pid)
                else:
                    self.running.discard(pid)
                    self.error_context_scope.discard(pid)
            if match[3] == "exit":
                fact["hresult" if match[5] == "HRESULT" else "refcount"] = "0x" + match[6]
                if match[5] == "HRESULT" and int(match[6], 16) & 0x80000000:
                    if len(self.first_failures) < 32:
                        self.first_failures.append(dict(fact))
                    if match[6] == "80004002":
                        self.first_no_interface.setdefault(pid, dict(fact))
                    if match[6] == "d0000002":
                        self.status_returns.append(dict(fact, source="owned-COM-HRESULT", result="0xd0000002"))
                        self.status_return_count += 1
                    if match[6] == "80004001":
                        self.first_not_implemented.setdefault(pid, dict(fact))
            self.interface_count += 1
            self.counts[pid]["interfaces"] += 1
            self.interfaces.append(fact)
        elif channel == "pkgrelay":
            phase = re.fullmatch(r"phase initialize=(1 xaml=([01])|0)", message)
            if function == "__wine_pkg_diagnostic_phase" and phase:
                fact.update(initialize=phase[1] != "0")
                if phase[1] != "0":
                    self.active.add(pid)
                    self.error_context_scope.add(pid)
                    fact["xaml_range_known"] = phase[2] == "1"
                else:
                    self.active.discard(pid)
                self.phases.append(fact)
                return
            if pid not in self.active and pid not in self.running:
                return
            if function == "diagnostic_relay" and message == "relay limited=1":
                self.source_limited.add(pid)
                return
            match = re.fullmatch(
                r"relay module=(combase|twinapi\.appcore|windows\.ui|coremessaging|ntdll|kernelbase|kernel32|rpcrt4) "
                r"export=([A-Za-z_][A-Za-z0-9_]{0,127}) caller=(Windows\.UI\.Xaml\.dll|combase\.dll|twinapi\.appcore\.dll) offset=([0-9a-f]{1,8})",
                message, re.IGNORECASE)
            if function == "diagnostic_relay" and match:
                fact.update(module=match[1].lower(), export=match[2], caller_module=match[3],
                            caller_offset=match[4])
                self.relays[pid].append(fact)
                self.counts[pid]["relays"] += 1
        elif channel == "pkgwait" and pid in self.active:
            entry = re.fullmatch(r"wait method=(" + self.WAIT + r") phase=enter id=([0-9]{1,10}) "
                                 r"count=([0-9]{1,10}) alertable=([01]) infinite=([01])(?: waittype=([0-9]{1,10}))?", message)
            exited = re.fullmatch(r"wait method=(" + self.WAIT + r") phase=exit id=([0-9]{1,10}) result=([0-9a-f]{8})", message)
            obj = re.fullmatch(r"object id=([0-9]{1,10}) slot=([0-9]{1,2}) handle=([0-9a-f]{1,8}) "
                              r"type=(unknown|event|mutant|thread|process|semaphore|timer|alpc|port) query=([0-9a-f]{8})", message)
            event = re.fullmatch(r"event id=([0-9]{1,10}) slot=([0-9]{1,2}) query=([0-9a-f]{8}) signaled=([01])", message)
            semaphore = re.fullmatch(r"semaphore id=([0-9]{1,10}) slot=([0-9]{1,2}) query=([0-9a-f]{8}) count=([0-9]{1,10}) maximum=([0-9]{1,10})", message)
            thread = re.fullmatch(
                r"thread id=([0-9]{1,10}) slot=([0-9]{1,2}) query=([0-9a-f]{8}) pid=([0-9]{1,10}) "
                r"tid=([0-9]{1,10}) exit=([0-9a-f]{8}) start-query=([0-9a-f]{8}) "
                r"module=([A-Za-z0-9_.-]{1,127}) offset=([0-9a-f]{1,16})", message)
            process = re.fullmatch(
                r"process id=([0-9]{1,10}) slot=([0-9]{1,2}) query=([0-9a-f]{8}) pid=([0-9]{1,10}) "
                r"parent=([0-9]{1,10}) exit=([0-9a-f]{8}) image-query=([0-9a-f]{8}) image=([A-Za-z0-9_.-]{1,127})", message)
            if entry and function == entry[1]:
                key = (pid, tid, entry[2])
                if len(self.pending) >= 64:
                    self.storage_limited = True
                    return
                fact.update(method=entry[1], id=int(entry[2]), count=int(entry[3]),
                            alertable=entry[4] == "1", infinite=entry[5] == "1",
                            objects=[], events=[], semaphores=[], threads=[], processes=[],
                            wait_type={"0": "all", "1": "any"}.get(entry[6], "unknown"),
                            expected_signaler="unknown-not-an-intrinsic-event-or-semaphore-owner",
                            relay_tail=[dict(row) for row in self.relays[pid]],
                            relay_source_limited=pid in self.source_limited)
                self.pending[key] = fact
            elif exited and function == exited[1]:
                row = self.pending.pop((pid, tid, exited[2]), None)
                if row and row["method"] == exited[1]:
                    row.update(exit_sequence=self.sequence, result="0x" + exited[3])
                    self.completed.append(row)
            elif obj and function == "diagnostic_wait":
                row = self.pending.get((pid, tid, obj[1]))
                if row and len(row["objects"]) < 64:
                    row["objects"].append({"slot": int(obj[2]), "handle": "0x" + obj[3],
                                           "type": obj[4], "query_status": "0x" + obj[5]})
                    candidates = [dict(event) for event in self.handles if event["pid"] == pid
                                  and event["owner_pid"] == pid and int(event["handle"], 16) == int(obj[3], 16)
                                  and event["sequence"] < row["sequence"]]
                    row.setdefault("handle_provenance_candidates", []).append({
                        "slot": int(obj[2]), "events": candidates[-32:],
                        "tail_limited": len(candidates) > 32 or self.handle_count > self.handles.maxlen,
                        "basis": "numeric-handle chronological candidates; pre-Run creation and inheritance unavailable",
                    })
            elif event and function == "diagnostic_wait":
                row = self.pending.get((pid, tid, event[1]))
                if row and len(row["events"]) < 64:
                    row["events"].append({"slot": int(event[2]), "query_status": "0x" + event[3],
                                          "signaled": event[4] == "1" if event[3] == "00000000" else None})
            elif semaphore and function == "diagnostic_wait":
                row = self.pending.get((pid, tid, semaphore[1]))
                if row and len(row["semaphores"]) < 64:
                    row["semaphores"].append({"slot": int(semaphore[2]), "query_status": "0x" + semaphore[3],
                                              "count": int(semaphore[4]) if semaphore[3] == "00000000" else None,
                                              "maximum": int(semaphore[5]) if semaphore[3] == "00000000" else None})
            elif thread and function == "diagnostic_wait":
                row = self.pending.get((pid, tid, thread[1]))
                if row and len(row["threads"]) < 64:
                    row["threads"].append({"slot": int(thread[2]), "query_status": "0x" + thread[3],
                                          "pid": int(thread[4]), "tid": int(thread[5]), "exit_status": "0x" + thread[6],
                                          "start_query_status": "0x" + thread[7], "start_module": thread[8],
                                          "start_offset": thread[9], "signal_condition": "this-thread-terminates"})
            elif process and function == "diagnostic_wait":
                row = self.pending.get((pid, tid, process[1]))
                if row and len(row["processes"]) < 64:
                    ok = process[3] == "00000000"
                    row["processes"].append({
                        "slot": int(process[2]), "query_status": "0x" + process[3],
                        "pid": int(process[4]) if ok else None, "parent_pid": int(process[5]) if ok else None,
                        "exit_status": "0x" + process[6] if ok else None,
                        "alive_at_entry": process[6] == "00000103" if ok else None,
                        "image_query_status": "0x" + process[7], "image": process[8],
                        "signal_condition": "this-process-terminates",
                    })

    def result(self, target_pids):
        select = lambda rows: [row for row in rows if row["pid"] in target_pids]
        return {
            "interface_events": select(self.interfaces), "first_interface_failures": select(self.first_failures),
            "first_e_nointerface": select(self.first_no_interface.values()),
            "first_e_notimpl": select(self.first_not_implemented.values()),
            "interface_events_seen": sum(self.counts.get(pid, {}).get("interfaces", 0) for pid in target_pids),
            "interface_tail_overwritten": max(0, self.interface_count - self.interfaces.maxlen),
            "initialize_phases": select(self.phases),
            "relay_tail": [row for pid in sorted(target_pids) for row in self.relays.get(pid, ())],
            "relay_calls_seen": sum(self.counts.get(pid, {}).get("relays", 0) for pid in target_pids),
            "relay_source_limited": bool(target_pids & self.source_limited),
            "waits_without_retained_exit": select(self.pending.values()),
            "recent_completed_waits": select(self.completed), "wait_storage_limited": self.storage_limited,
            "activation_calls": select(self.activations),
            "activation_calls_seen": sum(self.counts.get(pid, {}).get("activations", 0) for pid in target_pids),
            "activation_tail_overwritten": max(0, self.activation_count - self.activations.maxlen),
            "thread_creation": select(self.thread_events),
            "thread_tail_overwritten": max(0, self.thread_count - self.thread_events.maxlen),
            "registration_abi_unavailable": sorted(target_pids & self.registration_abi_unavailable),
            "handle_provenance": select(self.handles),
            "handle_tail_overwritten": max(0, self.handle_count - self.handles.maxlen),
            "rpc_connection_attempts": select(self.rpc),
            "rpc_tail_overwritten": max(0, self.rpc_count - self.rpc.maxlen),
            "unhandled_filter_exceptions": select(self.exceptions),
            "exception_source_limited": bool(target_pids & self.exception_limited),
            "winrt_error_origins": select(self.origins),
            "failfast_error_context": select(self.failfasts),
            "restricted_error_context": select(self.error_context),
            "error_context_source_limited": bool(target_pids & self.error_context_limited),
            "error_context_tail_overwritten": max(0, self.error_context_count - self.error_context.maxlen),
            "run_fixme_fingerprints": select(self.fixmes),
            "run_fixme_fingerprints_seen": self.fixme_count,
            "run_fixme_fingerprints_not_retained": max(0, self.fixme_count - len(self.fixmes)),
            "not_implemented_returns": select(self.status_returns),
            "status_return_tail_overwritten": max(0, self.status_return_count - self.status_returns.maxlen),
            "status_return_source_limited": bool(target_pids & self.status_return_limited),
            "no_gpfault_dialog_policy_observed": sorted(target_pids & self.exception_policy_pids),
            "basis": "instrumented calls, not a deadlock or unsignalled-event cause determination",
        }


class ActivationTrace:
    KEYS = frozenset((
        "image", "command", "cwd", "create_utc", "create_status", "child_pid",
        "token_status", "full_name", "family_name", "app_id", "verified_gamingapp",
        "resume_status", "still_running", "termination_requested_utc",
        "exit_observed_utc", "exit_code", "elapsed_ms", "exit_utc",
        "parent_winedebug", "child_winedebug", "wait_result",
    ))
    LOAD = re.compile(
        r'^([0-9a-f]+):[0-9a-f]+:trace:loaddll:build_module Loaded L"([^"]+)"'
        r' at [0-9a-fx]+: (native|builtin)', re.IGNORECASE)
    EVENT = re.compile(
        r"^([0-9a-f]+):([0-9a-f]+):(err|trace|fixme):([A-Za-z0-9_]+):"
        r"([A-Za-z0-9_]+) (.*)", re.IGNORECASE)

    @staticmethod
    def module_path_key(path):
        return re.sub(r"\\+", r"\\", path.replace("/", "\\")).lower()

    def __init__(self, module_paths=None):
        self.metadata = {}
        self.loads = []
        self.errors = 0
        self.process_events = 0
        self.truncated = False
        self.error_fingerprints = []
        self.handoff_facts = []
        self.sync_facts = []
        self.activation_facts = []
        self.activation_results = []
        self.protocol_results = []
        self.window_facts = []
        self.activation_delivery = []
        self.progress = []
        self.calls = CallDiagnostics()
        self.module_paths = {self.module_path_key(key): value
                             for key, value in (module_paths or {}).items()}

    def append_fact(self, target, fact):
        if len(target) < 128:
            target.append(fact)
        else:
            self.truncated = True

    def stdout(self, line):
        prefix = "calimocho-activation "
        if not line.startswith(prefix):
            return
        key, separator, value = line[len(prefix):].partition(" ")
        if key not in self.KEYS or not separator:
            return
        if key in self.metadata:
            raise ValueError(f"Duplicate activation metadata: {key}")
        self.metadata[key] = value

    def stderr(self, line):
        match = self.LOAD.match(line)
        if match:
            pid, path, kind = match.groups()
            module = path.replace("/", "\\").rsplit("\\", 1)[-1].lower()
            if module in ("windows.ui.xaml.dll", "microsoft.ui.xaml.dll", "xboxpcappce.exe", "xboxpcapp.exe", "wintypes.dll"):
                event = {"pid": int(pid, 16), "module": module, "kind": kind}
                if module in ("windows.ui.xaml.dll", "microsoft.ui.xaml.dll"):
                    known = self.module_paths.get(self.module_path_key(path))
                    event.update(path=known["path"] if known else "unrecognized-redacted",
                                 source=known["source"] if known else "unrecognized-redacted")
                if event not in self.loads and len(self.loads) < 128:
                    self.loads.append(event)
        if re.match(r"^[0-9a-f]+:[0-9a-f]+:err:", line, re.IGNORECASE):
            self.errors += 1
        if re.match(r"^[0-9a-f]+:[0-9a-f]+:trace:process:", line, re.IGNORECASE):
            self.process_events += 1
        event = self.EVENT.match(line)
        if not event:
            return
        pid, tid, level, channel, function, message = event.groups()
        if level == "fixme":
            self.calls.observe_fixme(int(pid, 16), int(tid, 16), channel, function)
        self.calls.observe(int(pid, 16), int(tid, 16), channel, function, message)
        fact = {"pid": int(pid, 16), "tid": int(tid, 16),
                "channel": channel, "function": function}
        if "RoGetActivatableClassRegistration" in message and "unimplemented" in message.lower():
            self.calls.registration_abi_unavailable.add(int(pid, 16))
        if channel in ("pkgcore", "pkgwindow"):
            if channel == "pkgcore" and function == "progress":
                progress = re.fullmatch(
                    r'progress method=(StaticLifetime\.(?:GetCollection|PropertySet|MapQuery|Lookup|Insert)'
                    r'|CoreApplication\.Run|FrameworkView\.(?:CreateView|Initialize|SetWindow|Load|Run)|Activated)'
                    r' phase=(enter|exit) result=([0-9a-f]{8})', message)
                if progress:
                    fact.update(method=progress[1], phase=progress[2])
                    if progress[2] == "exit":
                        fact["hresult"] = "0x" + progress[3]
                    if len(self.progress) < 256:
                        self.progress.append(fact)
                    else:
                        self.truncated = True
                elif message == "progress limited=1":
                    self.truncated = True
                return
            missing_iid = re.fullmatch(
                r'missing-iid=(\{[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\}) result=80004002',
                message, re.IGNORECASE)
            missing_method = re.fullmatch(r'missing-method=([A-Za-z0-9.]{1,64}) result=80004001', message)
            methods = {
                "Suspending", "RemoveSuspending", "Resuming", "RemoveResuming", "Properties",
                "RunWithActivationFactories", "CoreWindow.GetForCurrentThread", "CreateCoreWindow",
                "SplashScreen", "AutomationHostProvider", "CustomProperties", "FlowDirection",
                "PointerCursor", "PutPointerCursor", "GetAsyncKeyState", "GetKeyState",
                "ReleasePointerCapture", "SetPointerCapture", "RunIdleAsync", "AsyncInfo.Id",
                "StaticLifetime.Reserved",
            }
            events = {"AutomationProviderRequested", "CharacterReceived", "Closed", "InputEnabled",
                      "KeyDown", "KeyUp", "PointerCaptureLost", "PointerEntered", "PointerExited",
                      "PointerMoved", "PointerPressed", "PointerReleased", "TouchHitTesting",
                      "PointerWheelChanged", "VisibilityChanged"}
            methods |= events | {"Remove" + name for name in events}
            methods |= {"StaticLifetime.Slot%d" % slot for slot in (8, 9, 10, 13, 14, 15, 16, 17, 18)}
            if missing_iid:
                fact.update(missing_iid=missing_iid[1].lower(), hresult="0x80004002")
                self.append_fact(self.activation_results, fact)
            elif missing_method and missing_method[1] in methods:
                fact.update(missing_method=missing_method[1], hresult="0x80004001")
                self.append_fact(self.activation_results, fact)
            else:
                window = re.fullmatch(
                    r'window category=package-view class=CalimochoCoreWindow '
                    r'(created=1 visible=0|visible=1|destroyed=1)', message)
                delivery = re.fullmatch(r'activated kind=([04]) handlers=([0-9]{1,2}) result=([0-9a-f]{8})', message)
                collection = re.fullmatch(r'static-lifetime collection-result=([0-9a-f]{8})', message)
                if collection and channel == "pkgcore" and function == "lifetime_collection_get":
                    fact.update(operation="StaticLifetime.GetCollection", hresult="0x" + collection[1])
                    self.append_fact(self.activation_results, fact)
                elif window:
                    fact.update(category="package-view", window_class="CalimochoCoreWindow", state=window[1])
                    self.append_fact(self.window_facts, fact)
                elif delivery:
                    fact.update(kind=int(delivery[1]), handlers=int(delivery[2]), hresult="0x" + delivery[3])
                    self.append_fact(self.activation_delivery, fact)
            return
        if channel == "pkglaunch" and function == "activate_route":
            route = re.fullmatch(
                r'route scheme=L"([a-z][a-z0-9+.-]{0,62})" '
                r'app=L"([A-Za-z][A-Za-z0-9.]{0,63})" pid=([0-9]+) '
                r'result=([0-9a-f]{8}) missing=(none|uwp-protocol-activation)',
                message)
            if route:
                scheme, app, child, status, missing = route.groups()
                fact.update(scheme=scheme, app_id=app, child_pid=int(child),
                            hresult="0x" + status, missing=missing)
                self.append_fact(self.protocol_results, fact)
            return
        if channel == "pkglaunch":
            missing = re.fullmatch(
                r'missing-iid=(\{[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\}) result=(80004002)',
                message, re.IGNORECASE)
            unsupported = re.fullmatch(
                r'unsupported method=(LaunchUriWithOptionsAsync|LaunchFileAsync) result=(80004001)', message)
            if missing:
                fact.update(missing_iid=missing[1].lower(), hresult="0x" + missing[2])
                self.append_fact(self.activation_results, fact)
            elif unsupported:
                fact.update(missing_method=unsupported[1], hresult="0x" + unsupported[2])
                self.append_fact(self.activation_results, fact)
            return
        if channel == "pkgactivate" and function == "trace_package_activation":
            completed = re.fullmatch(
                r'operation=(RoGetActivationFactory|RoActivateInstance) '
                r'class=L"([A-Za-z_][A-Za-z0-9_.]{0,511})" '
                r'iid=(\{[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\}) '
                r'hr=([0-9a-f]{8}) registration=([01]) '
                r'server=(absent|unknown|in-process-dll|out-of-process-server)',
                message, re.IGNORECASE)
            if completed:
                operation, runtime_class, iid, hr, present, server = completed.groups()
                fact.update(operation=operation, runtime_class=runtime_class, iid=iid.lower(),
                            hresult="0x" + hr.lower(), registration_present=present == "1",
                            server_type=server)
            else:
                fact["message_class"] = "activation-result-format-redacted"
            self.append_fact(self.activation_results, fact)
            return
        if level == "err":
            message_class = "other-redacted"
            for marker, category in (
                ("not found", "module-not-found"), ("failed to load", "load-failed"),
                ("not supported", "unsupported"), ("not implemented", "unimplemented"),
                ("failed", "operation-failed"),
            ):
                if marker in message.lower():
                    message_class = category
                    break
            fact["message_class"] = message_class
            # Only explicitly labelled numeric statuses are retained; never message text.
            fact["statuses"] = re.findall(
                r"\b(?:status|hr|hresult|error|err)\s*[=:]?\s*(0x[0-9a-f]{1,8}|[0-9a-f]{8})\b",
                message, flags=re.IGNORECASE)[:8]
            self.append_fact(self.error_fingerprints, fact)
        elif channel == "process":
            if function == "NtCreateUserProcess":
                created = re.search(r"\bpid ([0-9a-f]+) tid ([0-9a-f]+) handles ", message)
                if created:
                    fact["child_pid"] = int(created[1], 16)
                    fact["child_tid"] = int(created[2], 16)
                    fact["operation"] = "native-process-created"
                else:
                    fact["operation"] = "native-process-create-attempt"
            elif function in ("CreateProcessInternalW", "CreateProcessW", "CreateProcessAsUserW"):
                created = re.search(r"started process pid ([0-9a-f]+) tid ([0-9a-f]+)", message)
                fact["operation"] = "win32-process-created" if created else "win32-process-call"
                if created:
                    fact["child_pid"] = int(created[1], 16)
            elif function in ("NtTerminateProcess", "RtlExitUserProcess", "ExitProcess"):
                fact["operation"] = "process-exit-call"
                code = re.search(r"(?:status|code)\s*[=:]?\s*(0x[0-9a-f]+|[0-9a-f]{8})", message)
                if code:
                    fact["exit_status"] = code[1]
            else:
                return
            for basename in ("XboxPcAppCE.exe", "XboxPcApp.exe"):
                if re.search(r"(?:^|[\\\" ])" + re.escape(basename) + r'(?:[" ]|$)', message, re.I):
                    fact["image"] = basename
            self.append_fact(self.handoff_facts, fact)
        elif channel == "sync" and function in (
                "NtCreateMutant", "NtOpenMutant", "NtCreateEvent", "NtOpenEvent"):
            if "name (null)" in message:
                fact["name_class"] = "unnamed"
            elif "\\BaseNamedObjects\\" in message:
                fact["name_class"] = "base-named-object"
            elif "Global\\" in message:
                fact["name_class"] = "global"
            elif "Local\\" in message:
                fact["name_class"] = "local"
            else:
                fact["name_class"] = "other-redacted"
            # Entry traces do not establish success or ERROR_ALREADY_EXISTS.
            fact["outcome"] = "not-observed"
            self.append_fact(self.sync_facts, fact)
        elif function in ("RoGetActivationFactory", "RoActivateInstance"):
            fact["activation_class"] = "app-lifecycle" if (
                "Microsoft.Windows.AppLifecycle." in message or
                "Windows.ApplicationModel.AppInstance" in message) else "other-redacted"
            self.append_fact(self.activation_facts, fact)

    def verdict(self, include_calls=True):
        pid_text = self.metadata.get("child_pid", "")
        pid = int(pid_text) if pid_text.isdecimal() else None
        loaded = any(e["pid"] == pid and e["module"] in ("windows.ui.xaml.dll", "microsoft.ui.xaml.dll")
                     for e in self.loads)
        routes = [fact for fact in self.protocol_results if fact["pid"] == pid]
        target_pids = {fact["child_pid"] for fact in routes
                       if fact["hresult"] == "0x00000000" and fact["child_pid"] > 0}
        target_loads = [fact for fact in self.loads if fact["pid"] in target_pids]
        target_exits = [fact for fact in self.handoff_facts
                        if fact["pid"] in target_pids and fact["operation"] == "process-exit-call"]
        return {
            "created": pid is not None and pid > 0,
            "resumed": pid is not None and self.metadata.get("resume_status") == "00000000",
            "xaml": "loaded-in-child" if loaded else (
                "unknown-truncated" if self.truncated else "not-observed"),
            "metadata": self.metadata,
            "module_loads": self.loads,
            "error_events": self.errors,
            "process_trace_events": self.process_events,
            "error_fingerprints": self.error_fingerprints,
            "handoff_facts": self.handoff_facts,
            "sync_facts": self.sync_facts,
            "activation_facts": self.activation_facts,
            "activation_results": [fact for fact in self.activation_results if fact["pid"] == pid],
            "protocol_target_activation_results": [fact for fact in self.activation_results if fact["pid"] in target_pids],
            "activation_delivery": [fact for fact in self.activation_delivery if fact["pid"] == pid or fact["pid"] in target_pids],
            "window_facts": [fact for fact in self.window_facts if fact["pid"] == pid or fact["pid"] in target_pids],
            "method_progress": [fact for fact in self.progress if fact["pid"] == pid or fact["pid"] in target_pids],
            "call_diagnostics": self.calls.result(target_pids) if include_calls else None,
            "protocol_results": routes,
            "protocol_target_loads": target_loads,
            "protocol_target_exit_calls": target_exits,
            "protocol_target_state": "exit-call-observed" if target_exits else (
                "unknown" if target_pids else "not-started"),
            "raw_trace_persisted": False,
            "trace_truncated": self.truncated,
        }


STATE_ROW = re.compile(
    r"state (?:pid=[0-9]{1,10} verified=1"
    r"|hwnd=[0-9a-f]{1,16} class=(?:CalimochoCoreWindow|other-redacted) visible=[01] width=[0-9]{1,8} height=[0-9]{1,8}"
    r"|tid=[0-9]{1,10} frame=[0-9]{1,2} module=[A-Za-z0-9_.-]{1,127} offset=[0-9a-f]{1,16}"
    r"|tid=[0-9]{1,10} (?:frames=[0-9]{1,2}|(?:context-error|unwind-end)=[0-9]{1,10})"
    r"|threads=[0-9]{1,10} captured=[0-9]{1,2}"
    r"|threads-before-attach=[0-9]{1,10}"
    r"|tid=[0-9]{1,10} alive=[01] wait=unknown"
    r"|tid=[0-9]{1,10} live-error=[0-9]{1,10}"
    r"|tid=[0-9]{1,10} start-error=[0-9]{1,10}"
    r"|tid=[0-9]{1,10} start module=[A-Za-z0-9_.-]{1,127} offset=[0-9a-f]{1,16}"
    r"|module-load-errors=[0-9]{1,3}"
    r"|kill-on-exit=0|attached=1"
    r"|debug-events=[0-9]{1,10} continued=[0-9]{1,10}"
    r"|windows=[0-9]{1,2}"
    r"|(?:modules|threads|windows)-truncated=1"
    r"|(?:window|enum|modules|symbols|threads|open|debug-policy|debug-connect|attach|continue|detach)-error=[0-9]{1,10}"
    r"|(?:identity-mismatch|target-not-active)=1"
    r"|detached=1 stacks=[01] target-exited=[01])")


def state_rows(output):
    """Retain only fixed helper grammar, never raw debugger text or absolute addresses."""
    if len(output) > 256 * 1024:
        return {"rows": [], "format_error": True, "truncated": True}
    rows = []
    invalid = False
    for row in output.decode("ascii", errors="replace").splitlines():
        if STATE_ROW.fullmatch(row):
            rows.append(row)
        else:
            invalid = True
    return {"rows": rows, "format_error": invalid, "truncated": False,
            "debugger_detached": any(row.startswith("state detached=1 ") for row in rows)}


class StateSnapshots:
    def __init__(self, configuration, environment, cwd):
        self.configuration, self.environment, self.cwd = configuration, environment, cwd
        self.started = None
        self.next = 0
        self.process = self.output = None
        self.results = []

    def finish(self, reason=None):
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.kill()  # Only this helper; debugger kill-on-exit is explicitly disabled.
        else:
            reason = None
        self.process.wait(timeout=5)
        self.output.seek(0)
        result = state_rows(self.output.read(256 * 1024 + 1))
        result.update(self.active, helper_exit=self.process.returncode,
                      bounded=reason is not None, reason=reason)
        self.results.append(result)
        self.output.close()
        self.process = self.output = None

    def tick(self, now, pid, target_exited=False):
        if self.configuration is None or pid is None:
            return
        if self.started is None:
            self.started = now
        if self.process is not None:
            if self.process.poll() is not None:
                self.finish()
            elif now - self.launched >= 10:
                self.finish("snapshot-bound")
        if self.process is not None or target_exited or self.next >= 2:
            return
        offset = (20, 60)[self.next]
        if now - self.started < offset:
            return
        self.next += 1
        self.output = tempfile.TemporaryFile()
        self.active = {"pid": pid, "scheduled_seconds": offset, "elapsed_seconds": now - self.started}
        self.launched = now
        try:
            self.process = subprocess.Popen(
                self.configuration["argv"] + [str(pid), self.configuration["image"], self.configuration["app_id"]],
                env=self.environment, cwd=self.cwd, stdin=subprocess.DEVNULL,
                stdout=self.output, stderr=subprocess.DEVNULL)
        except OSError:
            self.output.close()
            self.output = None
            raise


def collect(argv, environment, cwd, seconds=60, post_exit_seconds=2,
            module_paths=None, target_observer=None, state_observer=None):
    """Drain both streams; retain only allowlisted metadata and module-load facts."""
    trace = ActivationTrace(module_paths)
    started = time.monotonic()
    buffers = {"stdout": b"", "stderr": b""}
    discarding = {"stdout": False, "stderr": False}
    seen = 0
    timed_out = False
    drain_limited = False
    exit_seen_at = None
    exit_basis = None
    observer = None
    target_pid = None
    target_result = {"state": "not-started"}
    target_exit_at = None
    snapshots = StateSnapshots(state_observer, environment, cwd)
    with subprocess.Popen(argv, env=environment, cwd=cwd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            try:
                while selector.get_map() or (observer is not None and target_result["state"] == "observing"):
                    now = time.monotonic()
                    verdict = trace.verdict(include_calls=False)
                    if target_observer and target_pid is None:
                        routes = [fact for fact in verdict["protocol_results"]
                                  if fact["child_pid"] > 0 and fact["hresult"] == "0x00000000"
                                  and fact["app_id"] == target_observer["app_id"]]
                        if routes:
                            target_pid = routes[0]["child_pid"]
                            remaining = max(1, min(180, math.ceil(seconds - (now - started))))
                            observer = subprocess.Popen(
                                target_observer["argv"] + [str(target_pid), target_observer["image"],
                                                           target_observer["app_id"], str(remaining)],
                                env=environment, cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                            target_result = {"pid": target_pid, "state": "observing"}
                    if observer is not None and observer.poll() is not None and target_result["state"] == "observing":
                        output = observer.communicate(timeout=1)[0]
                        match = re.fullmatch(
                            rb"calimocho-target pid=([0-9]+) state=exited code=([0-9]+)\r?\n", output)
                        if observer.returncode == 0 and match and int(match[1]) == target_pid:
                            target_result = {"pid": target_pid, "state": "exited",
                                             "exit_code": int(match[2]), "basis": "exact-image-token-process-handle"}
                            target_exit_at = now
                        else:
                            target_result = {"pid": target_pid, "state": "unknown",
                                             "observer_exit": observer.returncode}
                            failure = re.fullmatch(
                                rb"calimocho-target pid=([0-9]+) state="
                                rb"(open-failed|identity-mismatch|bound-reached|wait-failed)(?: error=([0-9]+))?\r?\n",
                                output)
                            if failure and int(failure[1]) == target_pid:
                                target_result["reason"] = failure[2].decode("ascii")
                                if failure[3]:
                                    target_result["error"] = int(failure[3])
                    previous_snapshots = len(snapshots.results)
                    snapshots.tick(now, target_pid, target_result["state"] == "exited")
                    for snapshot in snapshots.results[previous_snapshots:]:
                        snapshot["waits_without_retained_exit_at_collection"] = [
                            {"pid": row["pid"], "tid": row["tid"], "method": row["method"], "id": row["id"]}
                            for row in trace.calls.pending.values() if row["pid"] == target_pid]
                    if exit_seen_at is None:
                        if process.poll() is not None:
                            exit_seen_at, exit_basis = now, "helper-process-exit"
                        elif "elapsed_ms" in trace.metadata and "exit_observed_utc" in trace.metadata:
                            exit_seen_at, exit_basis = now, "child-exit-record"
                    # A direct CE exit is not an AppL exit. Keep draining within the
                    # original finite budget when our exact Launcher recorded a child.
                    handoff = any(fact["child_pid"] > 0 and fact["hresult"] == "0x00000000"
                                  for fact in verdict["protocol_results"])
                    if target_exit_at is not None and now - target_exit_at >= post_exit_seconds:
                        drain_limited = True
                        trace.truncated = True
                        exit_basis = "protocol-target-handle-exit"
                        break
                    if exit_seen_at is not None and not handoff and now - exit_seen_at >= post_exit_seconds:
                        drain_limited = True
                        trace.truncated = True
                        break
                    if now - started >= seconds:
                        timed_out = True
                        trace.truncated = True
                        if process.poll() is None:
                            process.kill()
                        break
                    ready = selector.select(timeout=0.1) if selector.get_map() else ()
                    if not selector.get_map():
                        time.sleep(0.05)
                    for key, _ in ready:
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            if buffers[key.data] or discarding[key.data]:
                                trace.truncated = True
                            continue
                        seen += len(chunk)
                        if seen > 8 * 1024 * 1024 and key.data == "stderr":
                            trace.truncated = True
                        stream = key.data
                        parts = (buffers[stream] + chunk).split(b"\n")
                        buffers[stream] = parts.pop()
                        for part in parts:
                            if discarding[stream] or len(part) > 16384:
                                discarding[stream] = False
                                trace.truncated = True
                                continue
                            line = part.decode("utf-8", errors="replace").rstrip("\r")
                            if seen > 8 * 1024 * 1024 and stream == "stderr" and not re.match(
                                    r"^[0-9a-f]+:[0-9a-f]+:(?:fixme:[A-Za-z0-9_]+:|trace:(?:pkgiface|pkgrelay|pkgwait|pkgcore|pkgwindow|pkglaunch|pkgro|pkgthread|pkghandle|pkgrpc|pkgexception|pkgstatus):)",
                                    line, re.IGNORECASE):
                                continue
                            getattr(trace, stream)(line)
                        if len(buffers[stream]) > 16384:
                            buffers[stream] = b""
                            discarding[stream] = True
                            trace.truncated = True
            finally:
                snapshots.finish("collector-ended")
                if observer is not None:
                    if observer.poll() is None:
                        observer.kill()  # Only this invocation's observer, never the target.
                    observer.wait(timeout=5)
                    if observer.stdout:
                        observer.stdout.close()
                    if target_result["state"] == "observing":
                        target_result = {"pid": target_pid, "state": "unknown", "reason": "observation-bound"}
                if process.poll() is None:
                    process.kill()  # This collector's helper only, never a name-based kill.
                process.wait(timeout=5)
        result = trace.verdict()
        if state_observer:
            result["state_snapshots"] = snapshots.results
            result["state_snapshots_expected"] = [20, 60]
        if target_observer:
            result["protocol_target_observation"] = target_result
            if target_result["state"] == "exited":
                result["protocol_target_state"] = "exited"
        result.update(helper_exit=process.returncode, collector_timeout=timed_out,
                      elapsed_seconds=time.monotonic() - started, bytes_drained=seen,
                      post_exit_drain_limited=drain_limited, post_exit_basis=exit_basis,
                      capture_end="post-exit-drain-limit" if drain_limited else (
                          "collector-timeout" if timed_out else "stream-eof"))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text())
    if args.output.exists():
        raise FileExistsError("Refuse to overwrite activation evidence")
    for field, digest in (
        ("helper", "helper_sha256"), ("registry", "registry_sha256"),
        ("diagnostic_collector", "diagnostic_collector_sha256"),
    ):
        if hashlib.sha256(Path(receipt[field]).read_bytes()).hexdigest() != receipt[digest]:
            raise ValueError(f"Receipt hash mismatch: {field}")
    for field in ("graph", "framework_registration", "protocol_table", "server_registration_table"):
        if field in receipt:
            if hashlib.sha256(Path(receipt[field]).read_bytes()).hexdigest() != receipt[field + "_sha256"]:
                raise ValueError(f"Receipt hash mismatch: {field}")
    if "target_observer" in receipt:
        observer = receipt["target_observer"]
        if hashlib.sha256(Path(observer["path"]).read_bytes()).hexdigest() != observer["sha256"]:
            raise ValueError("Receipt hash mismatch: target observer")
    if "state_observer" in receipt:
        observer = receipt["state_observer"]
        if hashlib.sha256(Path(observer["path"]).read_bytes()).hexdigest() != observer["sha256"]:
            raise ValueError("Receipt hash mismatch: state observer")
        if observer["image"] != receipt["target_observer"]["image"] or observer["app_id"] != receipt["target_observer"]["app_id"]:
            raise ValueError("State observer must bind the same exact admitted AppL target")
    install = Path(receipt["install"])
    for relative, digest in (
        ("bin/wine", "wine_sha256"), ("bin/wineserver", "wineserver_sha256"),
        ("lib/wine/x86_64-windows/ntdll.dll", "ntdll_sha256"),
    ):
        if hashlib.sha256((install / relative).read_bytes()).hexdigest() != receipt[digest]:
            raise ValueError(f"Deployed engine hash mismatch: {relative}")
    if Path(receipt["diagnostic_collector"]).resolve() != Path(__file__).resolve():
        raise ValueError("Receipt names a different diagnostic collector")
    environment = dict(os.environ)
    environment.pop("CALIMOCHO_PACKAGE_REGISTRATION", None)
    environment.update(receipt["environment"])
    # Setup and server registration remain explicit Xbox-owner steps, not hidden actions.
    seconds = receipt.get("collector_limit_seconds", 60)
    if not isinstance(seconds, int) or isinstance(seconds, bool) or not 1 <= seconds <= 180:
        raise ValueError("Collector observation bound must be an integer from1 to180 seconds")
    result = collect(receipt["activation_argv"], environment, receipt["cwd"], seconds=seconds,
                     module_paths=receipt.get("xaml_module_paths"),
                     target_observer=receipt.get("target_observer"),
                     state_observer=receipt.get("state_observer"))
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps(result, indent=2))
    return 0 if (result["created"] and result["resumed"] and result["helper_exit"] == 0
                 and not result["trace_truncated"] and not result["collector_timeout"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
