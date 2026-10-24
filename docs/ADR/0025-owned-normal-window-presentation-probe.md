# ADR-0025: An owned normal-window presentation discriminator

## Status

Accepted for the coordinator-directed REQ-74 presentation discriminator,
2026-10-24. No game or input authorization is added.

## Context

WineHQ port-09 and the source-built CW26.3 baseline both create a D3D12
device. Their identical Wine conformance test fails at a desktop-window
negative case before yielding a full passing summary. That shared failure
does not answer whether a normal application window can present correctly.

The coordinator requested one small owned PE probe, run on both runtimes
in fresh prefixes, with a 90-second deadline and a screenshot. The input
lease belongs to another lane. Displaying this bounded test window is
authorized; sending input or requesting focus is not.

## Decision

Keep the discriminator source in `tests/d3d12_present_probe.c`. Build it
with the installed MinGW x86_64 compiler and the standard D3D12/DXGI
import libraries. Do not modify either runtime or the installed renderer.

Create a normal non-activating 320 by 240 client window, a D3D12 device
and direct command queue, and a two-buffer flip-discard RGBA8 swapchain.
Clear each backbuffer to floating-point RGBA `(0.2, 0.4, 0.8, 1.0)` and
require 120 successful Presents. Use explicit resource transitions,
command-queue fences and bounded waits before allocator reuse.

Copy the final cleared texture to a readback buffer before its Present.
Respect the device-provided texture footprint and row pitch. After fence
completion, require the center pixel to equal RGBA `51,102,204,255`.
Print initialization, first/last Present and mapping HRESULTs, the actual
Present count and actual pixel. Fail on an API error, timeout, non-S_OK
Present or pixel mismatch.

At frame 60, hold the displayed image briefly for a targeted screenshot
of the named on-screen window. Do not capture the full desktop or send
input. Keep the original renderer hash, isolated runtime environment,
source/tool/probe/log hashes, capture identity and prefix-scoped cleanup
in the retained receipt.

## Consequences

Both runtimes complete the owned 120-frame test and exact pixel check.
Both named-window screenshots succeed and have identical PNG hashes.
This supplies independent display evidence in addition to GPU readback.

This is a small clear/presentation/readback smoke test, not shader,
media, game, resize, fullscreen or full-conformance qualification.
The existing desktop-negative-case failure remains unresolved. It does
not replace canonical acceptance in `dragos-core projects/ode-to-x/SPEC.md`.
