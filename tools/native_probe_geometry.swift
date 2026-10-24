// Copyright 2026 Calimocho contributors
// SPDX-License-Identifier: LGPL-2.1-or-later
import AppKit
import CoreGraphics
import Foundation

let allowedTitles = Set(["Calimocho Vulkan Present Probe", "Calimocho D3D11 Present Probe",
                         "Calimocho D3D12 Present Probe"])
struct InvalidGeometry: Error {}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data(("ERROR native geometry: " + message + "\n").utf8))
    exit(1)
}

func foreground(_ pid: pid_t?) throws -> pid_t {
    guard let pid = pid, pid > 0 else { throw InvalidGeometry() }
    return pid
}

func numeric(_ value: Any?, integer: Bool = false, positive: Bool = false) -> NSNumber? {
    guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID(),
          number.doubleValue.isFinite,
          !integer || number.doubleValue.rounded(.towardZero) == number.doubleValue,
          !positive || number.doubleValue > 0 else { return nil }
    return number
}

func visibleWindows(_ raw: Any?) throws -> [[String: Any]] {
    guard let info = raw as? [[String: Any]], !info.isEmpty else { throw InvalidGeometry() }
    return try info.map { window -> [String: Any] in
        guard let number = numeric(window[kCGWindowNumber as String], integer: true, positive: true),
              let pid = numeric(window[kCGWindowOwnerPID as String], integer: true, positive: true),
              let layer = numeric(window[kCGWindowLayer as String], integer: true),
              let rect = window[kCGWindowBounds as String] as? [String: Any],
              let x = numeric(rect["X"]), let y = numeric(rect["Y"]),
              let width = numeric(rect["Width"], positive: true),
              let height = numeric(rect["Height"], positive: true)
        else { throw InvalidGeometry() }
        let title = window[kCGWindowName as String] as? String ?? ""
        return ["id": number, "pid": pid, "layer": layer,
                "bounds": ["X": x, "Y": y, "Width": width, "Height": height],
                "probe_title": allowedTitles.contains(title) ? title : ""]
    }
}

if CommandLine.arguments.dropFirst() == ["--self-test"] {
    let valid: [[String: Any]] = [[kCGWindowNumber as String: 1, kCGWindowOwnerPID as String: 1,
        kCGWindowLayer as String: 0, kCGWindowBounds as String:
            ["X": 0, "Y": 0, "Width": 20, "Height": 20]]]
    guard try visibleWindows(valid).count == 1, try foreground(1) == 1 else {
        fatalError("Valid geometry fixture rejected")
    }
    let invalid: [Any?] = [nil, "bad", [], [["bad": 1]],
        [[kCGWindowNumber as String: 1, kCGWindowOwnerPID as String: 1,
          kCGWindowLayer as String: 0, kCGWindowBounds as String: ["X": 0, "Y": 0, "Width": 0, "Height": 1]]]]
    for fixture in invalid {
        do {
            _ = try visibleWindows(fixture)
            fatalError("Invalid window fixture accepted")
        } catch is InvalidGeometry {}
    }
    for key in [kCGWindowNumber, kCGWindowOwnerPID, kCGWindowLayer, kCGWindowBounds] {
        var fixture = valid[0]
        fixture.removeValue(forKey: key as String)
        do {
            _ = try visibleWindows([fixture])
            fatalError("Missing required window field accepted")
        } catch is InvalidGeometry {}
    }
    for value: Any in [true, 1.5, Double.nan, "0"] {
        var fixture = valid[0]
        fixture[kCGWindowLayer as String] = value
        do {
            _ = try visibleWindows([fixture])
            fatalError("Malformed window layer accepted")
        } catch is InvalidGeometry {}
    }
    for pid: pid_t? in [nil, 0, -1] {
        do {
            _ = try foreground(pid)
            fatalError("Invalid foreground fixture accepted")
        } catch is InvalidGeometry {}
    }
    print("PASS fail-closed window/foreground fixtures")
    exit(0)
}
guard CommandLine.arguments.count == 1 else { fail("unexpected arguments") }
let windows: [[String: Any]]
let foregroundPID: pid_t
do {
    windows = try visibleWindows(CGWindowListCopyWindowInfo(
        [.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID))
    foregroundPID = try foreground(NSWorkspace.shared.frontmostApplication?.processIdentifier)
} catch is InvalidGeometry {
    fail("missing or malformed window inventory / unknown foreground")
}
var count: UInt32 = 0
guard CGGetActiveDisplayList(0, nil, &count) == .success, count > 0 else {
    fail("cannot enumerate displays")
}
var displays = [CGDirectDisplayID](repeating: 0, count: Int(count))
guard CGGetActiveDisplayList(count, &displays, &count) == .success else {
    fail("cannot read display identities")
}
let rectangles = displays.prefix(Int(count)).map { display -> [String: Any] in
    let rect = CGDisplayBounds(display)
    return ["id": display, "x": rect.minX, "y": rect.minY,
            "width": rect.width, "height": rect.height]
}
let data: [String: Any] = [
    "foreground_pid": foregroundPID,
    "displays": rectangles, "windows": windows,
    "observed_at": Date().timeIntervalSince1970
]
print(String(data: try JSONSerialization.data(withJSONObject: data, options: [.sortedKeys]),
             encoding: .utf8)!)
