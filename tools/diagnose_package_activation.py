"""Collect bounded activation evidence without persisting raw application traces."""
import argparse
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
        fact = {"pid": int(pid, 16), "tid": int(tid, 16),
                "channel": channel, "function": function}
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
            missing_method = re.fullmatch(r'missing-method=([A-Za-z.]{1,64}) result=80004001', message)
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

    def verdict(self):
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
                    verdict = trace.verdict()
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
                    snapshots.tick(now, target_pid, target_result["state"] == "exited")
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
                            continue  # Still drain; never block the child on a full pipe.
                        stream = key.data
                        parts = (buffers[stream] + chunk).split(b"\n")
                        buffers[stream] = parts.pop()
                        for part in parts:
                            if discarding[stream] or len(part) > 16384:
                                discarding[stream] = False
                                trace.truncated = True
                                continue
                            line = part.decode("utf-8", errors="replace").rstrip("\r")
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
