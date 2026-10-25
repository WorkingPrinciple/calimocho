"""Collect bounded activation evidence without persisting raw application traces."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
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

    def __init__(self):
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
            if module in ("windows.ui.xaml.dll", "microsoft.ui.xaml.dll", "xboxpcappce.exe", "xboxpcapp.exe"):
                event = {"pid": int(pid, 16), "module": module, "kind": kind}
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
            "protocol_results": routes,
            "protocol_target_loads": target_loads,
            "protocol_target_exit_calls": target_exits,
            "protocol_target_state": "exit-call-observed" if target_exits else (
                "unknown" if target_pids else "not-started"),
            "raw_trace_persisted": False,
            "trace_truncated": self.truncated,
        }


def collect(argv, environment, cwd, seconds=60, post_exit_seconds=2):
    """Drain both streams; retain only allowlisted metadata and module-load facts."""
    trace = ActivationTrace()
    started = time.monotonic()
    buffers = {"stdout": b"", "stderr": b""}
    discarding = {"stdout": False, "stderr": False}
    seen = 0
    timed_out = False
    drain_limited = False
    exit_seen_at = None
    exit_basis = None
    with subprocess.Popen(argv, env=environment, cwd=cwd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            try:
                while selector.get_map():
                    now = time.monotonic()
                    if exit_seen_at is None:
                        if process.poll() is not None:
                            exit_seen_at, exit_basis = now, "helper-process-exit"
                        elif "elapsed_ms" in trace.metadata and "exit_observed_utc" in trace.metadata:
                            exit_seen_at, exit_basis = now, "child-exit-record"
                    # A direct CE exit is not an AppL exit. Keep draining within the
                    # original finite budget when our exact Launcher recorded a child.
                    handoff = any(fact["child_pid"] > 0 and fact["hresult"] == "0x00000000"
                                  for fact in trace.verdict()["protocol_results"])
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
                    for key, _ in selector.select(timeout=0.1):
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
                if process.poll() is None:
                    process.kill()  # This collector's helper only, never a name-based kill.
                process.wait(timeout=5)
        result = trace.verdict()
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
    result = collect(receipt["activation_argv"], environment, receipt["cwd"])
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps(result, indent=2))
    return 0 if (result["created"] and result["resumed"] and result["helper_exit"] == 0
                 and not result["trace_truncated"] and not result["collector_timeout"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
