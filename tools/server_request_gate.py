"""Reject client requests that add more data chunks than a Wine request can carry."""
import re
import sys
from pathlib import Path

MAX_DATA = 5
BLOCK = re.compile(r"SERVER_START_REQ\(\s*(\w+)\s*\)(.*?)SERVER_END_REQ", re.S)


def overflows(text):
    """Return (request, count) for blocks whose wine_server_add_data calls exceed __SERVER_MAX_DATA.
    Conditional calls are counted, so the result is an upper bound."""
    return [(match.group(1), count) for match in BLOCK.finditer(text)
            if (count := match.group(2).count("wine_server_add_data(")) > MAX_DATA]


def check(source, paths):
    source = Path(source)
    limit = re.search(r"#define __SERVER_MAX_DATA (\d+)", (source / "include/wine/server.h").read_text())
    if not limit or int(limit.group(1)) != MAX_DATA:
        raise ValueError("Unexpected __SERVER_MAX_DATA")
    found = {}
    for relative in paths:
        if relative.endswith(".c") and (source / relative).exists():
            hits = overflows((source / relative).read_text(errors="replace"))
            if hits:
                found[relative] = hits
    if found:
        raise ValueError("Server request data chunks exceed %d: %r" % (MAX_DATA, found))
    return {"max_data": MAX_DATA, "checked": sorted(p for p in paths if p.endswith(".c"))}


if __name__ == "__main__":
    root = Path(sys.argv[1])
    print(check(root, [str(p.relative_to(root)) for p in root.glob("dlls/**/*.c")] +
                      [str(p.relative_to(root)) for p in root.glob("programs/**/*.c")]))
