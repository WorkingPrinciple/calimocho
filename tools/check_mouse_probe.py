"""Check a raw-mouse probe log, not the provenance of injected events."""

import re


def check_log(text: str, exit_code: int, *, expected_clip: bool) -> dict[str, int]:
    """Reject setup, focus, empty-input and incomplete-run failures."""
    if exit_code or "ERROR " in text:
        raise ValueError("Probe failed or reported an error")
    ready = re.findall(
        r"^READY pid=([1-9]\d*) hwnd=([0-9a-fA-Fx]+) clip=([01]) "
        r"left=(-?\d+) top=(-?\d+) right=(-?\d+) bottom=(-?\d+) duration_ms=5000$",
        text, re.MULTILINE
    )
    if len(ready) != 1 or len(re.findall(r"^READY ", text, re.MULTILINE)) != 1:
        raise ValueError("Expected one ready record")
    _, _, clipped, left, top, right, bottom = ready[0]
    if bool(int(clipped)) != expected_clip or int(right) <= int(left) or int(bottom) <= int(top):
        raise ValueError("Wrong clip mode or invalid client rectangle")
    if len(re.findall(
        r"^CLEANUP clip_restored=1 raw_removed=1 cursor_show_calls=([1-9]|[12]\d|3[0-2])$",
        text, re.MULTILINE
    )) != 1:
        raise ValueError("Missing successful ordinary-exit cleanup")
    summaries = re.findall(
        r"^SUMMARY relative=(\d+) nonzero=(\d+) absolute=(\d+) moves=(\d+) "
        r"elapsed_ms=(\d+) aborted=(\d+) errors=(\d+)$", text, re.MULTILINE
    )
    if len(summaries) != 1:
        raise ValueError("Expected one complete summary")
    keys = ("relative", "nonzero", "absolute", "moves", "elapsed_ms", "aborted", "errors")
    result = dict(zip(keys, map(int, summaries[0])))
    raw = re.findall(r"^RAW flags=(\d+) dx=(-?\d+) dy=(-?\d+) foreground=([01])$",
                     text, re.MULTILINE)
    relative = [row for row in raw if not int(row[0]) & 1]
    nonzero = [row for row in relative if int(row[1]) or int(row[2])]
    if (result["aborted"] or result["errors"] or not 5000 <= result["elapsed_ms"] <= 6000
            or not nonzero or any(row[3] != "1" for row in raw)
            or result["relative"] != len(relative) or result["nonzero"] != len(nonzero)
            or result["absolute"] != len(raw) - len(relative)):
        raise ValueError("Missing bounded foreground relative-input evidence")
    return result
