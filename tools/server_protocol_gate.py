"""Reject staged installs whose unrebuilt modules use renumbered server requests.

Wine numbers server requests by their order in server/protocol.def. Inserting a
request shifts every later number, and the server only checks the protocol
version against ntdll. Any other installed module that was not rebuilt keeps
the old numbers and would silently reach a different server handler.
"""
from pathlib import Path
import re
import subprocess


def request_numbers(source):
    text = (Path(source) / "include/wine/server_protocol.h").read_text()
    body = text[text.index("enum request\n"):text.index("REQ_NB_REQUESTS")]
    return {name: index for index, name in enumerate(re.findall(r"REQ_(\w+)", body))}


def module_of(relative):
    parts = Path(relative).parts
    if parts[:1] == ("build",) and len(parts) > 2 and parts[1] in ("dlls", "programs"):
        return parts[2]
    if parts[:2] == ("build", "server"):
        return "server"
    return None


def installed(install, module):
    return any((Path(install) / "lib/wine" / arch / name).exists()
               for arch in ("x86_64-windows", "x86_64-unix", "i386-windows")
               for name in (module, module + ".dll", module + ".exe", module + ".so",
                            module.rsplit(".", 1)[0] + ".so"))


def shifted_consumers(base_source, new_source, install, rebuilt):
    base, new = request_numbers(base_source), request_numbers(new_source)
    source = Path(new_source)
    listing = subprocess.run(["grep", "-rl", "--include=*.c", "SERVER_START_REQ", "dlls", "programs"],
                             cwd=source, capture_output=True, text=True, check=False)
    if listing.returncode not in (0, 1):
        raise RuntimeError("Cannot scan server request consumers")
    found = {}
    for relative in listing.stdout.split():
        module = Path(relative).parts[1]
        if module in rebuilt or not installed(install, module):
            continue
        used = set(re.findall(r"SERVER_START_REQ\(\s*(\w+)", (source / relative).read_text(errors="replace")))
        moved = sorted(name for name in used if name in base and base[name] != new.get(name))
        if moved:
            found.setdefault(module, set()).update(moved)
    return {module: sorted(names) for module, names in sorted(found.items())}


def require_consistent(base_source, new_source, install, built_paths):
    rebuilt = {module for module in map(module_of, built_paths) if module}
    found = shifted_consumers(base_source, new_source, install, rebuilt | {"ntdll"})
    if found:
        raise ValueError("Unrebuilt modules use renumbered server requests: " +
                         "; ".join("%s: %s" % (module, ", ".join(names)) for module, names in found.items()))
    return sorted(rebuilt)
