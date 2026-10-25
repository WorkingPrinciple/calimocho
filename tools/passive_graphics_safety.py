"""Fail-closed validation of read-only display/window inventories."""

import math
import time


def intersects(a, b):
    return (a[0] < b[0] + b[2] and b[0] < a[0] + a[2]
            and a[1] < b[1] + b[3] and b[1] < a[1] + a[3])


def bounds(window):
    frame = window["bounds"]
    return tuple(frame[key] for key in ("X", "Y", "Width", "Height"))


def obstacles(snapshot, paused_ode_window=None, ignored_window=None):
    """Exclude only the explicitly paused, exact foreground Ode window."""
    if paused_ode_window is not None:
        pid, window_id = paused_ode_window
        if (type(pid) is not int or type(window_id) is not int or min(pid, window_id) <= 0
                or snapshot["foreground_pid"] != pid
                or sum(w["pid"] == pid and w["id"] == window_id
                       for w in snapshot["windows"]) != 1):
            raise ValueError("Paused Ode window identity/foreground no longer matches")
    if ignored_window is not None:
        pid, window_id = ignored_window
        matches = [w for w in snapshot["windows"] if (w["pid"], w["id"]) == (pid, window_id)]
        if (type(pid) is not int or type(window_id) is not int or min(pid, window_id) <= 0
                or len(matches) != 1 or matches[0]["layer"] != 20):
            raise ValueError("Explicit ignored window identity/layer no longer matches")
    return [window for window in snapshot["windows"] if window["layer"] >= 0
            and (ignored_window is None or (window["pid"], window["id"]) != ignored_window)
            and (paused_ode_window is None
                 or (window["pid"], window["id"]) != paused_ode_window)]


def free_position(snapshot, paused_ode_window=None, ignored_window=None):
    frames = [bounds(window) for window in obstacles(snapshot, paused_ode_window, ignored_window)]
    for display in snapshot["displays"]:
        for y in range(int(display["y"]) + 50, int(display["y"] + display["height"]) - 360, 40):
            for x in range(int(display["x"]) + 40, int(display["x"] + display["width"]) - 420, 40):
                if not any(intersects((x, y, 400, 340), frame) for frame in frames):
                    return x, y
    raise ValueError("No free 400x340 display region outside foreign windows")


def validate_geometry(snapshot, now=None):
    now = time.time() if now is None else now

    def number(value, positive=False, integer=False):
        if (type(value) not in (int, float) or not math.isfinite(value)
                or (positive and value <= 0) or (integer and int(value) != value)):
            raise ValueError("Unknown or malformed native geometry value")

    if not isinstance(snapshot, dict):
        raise ValueError("Missing native geometry inventory")
    number(snapshot.get("foreground_pid"), positive=True, integer=True)
    number(snapshot.get("observed_at"))
    if not 0 <= now - snapshot["observed_at"] <= 5:
        raise ValueError("Native geometry is stale")
    for key in ("displays", "windows"):
        if not isinstance(snapshot.get(key), list) or not snapshot[key]:
            raise ValueError(f"Missing {key} inventory")
    for display in snapshot["displays"]:
        if not isinstance(display, dict):
            raise ValueError("Malformed display")
        number(display.get("id"), positive=True, integer=True)
        for field in ("x", "y", "width", "height"):
            number(display.get(field), positive=field in ("width", "height"))
    ids = set()
    for window in snapshot["windows"]:
        if not isinstance(window, dict):
            raise ValueError("Malformed native window")
        for field in ("id", "pid", "layer"):
            number(window.get(field), positive=field != "layer", integer=True)
        number(window.get("alpha"))
        if not 0 <= window["alpha"] <= 1 or window.get("on_screen") is not True:
            raise ValueError("Unknown native window visibility")
        if window["id"] in ids:
            raise ValueError("Duplicate native window identity")
        ids.add(window["id"])
        if not isinstance(window.get("bounds"), dict):
            raise ValueError("Missing native window frame")
        for field in ("X", "Y", "Width", "Height"):
            number(window["bounds"].get(field), positive=field in ("Width", "Height"))
        if not isinstance(window.get("probe_title"), str):
            raise ValueError("Missing probe window identity field")
    return snapshot
