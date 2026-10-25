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

    def __init__(self):
        self.metadata = {}
        self.loads = []
        self.errors = 0
        self.process_events = 0
        self.truncated = False

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
            if module in ("windows.ui.xaml.dll", "xboxpcappce.exe", "xboxpcapp.exe"):
                event = {"pid": int(pid, 16), "module": module, "kind": kind}
                if event not in self.loads and len(self.loads) < 128:
                    self.loads.append(event)
        if re.match(r"^[0-9a-f]+:[0-9a-f]+:err:", line, re.IGNORECASE):
            self.errors += 1
        if re.match(r"^[0-9a-f]+:[0-9a-f]+:trace:process:", line, re.IGNORECASE):
            self.process_events += 1

    def verdict(self):
        pid_text = self.metadata.get("child_pid", "")
        pid = int(pid_text) if pid_text.isdecimal() else None
        loaded = any(e["pid"] == pid and e["module"] == "windows.ui.xaml.dll"
                     for e in self.loads)
        return {
            "created": pid is not None and pid > 0,
            "resumed": pid is not None and self.metadata.get("resume_status") == "00000000",
            "xaml": "loaded-in-child" if loaded else (
                "unknown-truncated" if self.truncated else "not-observed"),
            "metadata": self.metadata,
            "module_loads": self.loads,
            "error_events": self.errors,
            "process_trace_events": self.process_events,
            "raw_trace_persisted": False,
            "trace_truncated": self.truncated,
        }


def collect(argv, environment, cwd, seconds=60):
    """Drain both streams; retain only allowlisted metadata and module-load facts."""
    trace = ActivationTrace()
    started = time.monotonic()
    buffers = {"stdout": b"", "stderr": b""}
    discarding = {"stdout": False, "stderr": False}
    seen = 0
    timed_out = False
    with subprocess.Popen(argv, env=environment, cwd=cwd, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            try:
                while selector.get_map():
                    now = time.monotonic()
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
                      elapsed_seconds=time.monotonic() - started, bytes_drained=seen)
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
    return 0 if result["created"] and result["resumed"] and result["helper_exit"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
