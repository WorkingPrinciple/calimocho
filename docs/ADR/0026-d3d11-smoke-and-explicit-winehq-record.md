# ADR-0026: D3D11 smoke and an explicit WineHQ runtime record

## Status

Accepted for the coordinator-directed local DX11 and registry slice,
2026-10-24. No game, input, shared-registry or distribution authorization
is added.

## Context

The WineHQ port-09 and CW26.3 source baseline have matching owned D3D12
normal-window presentation/readback results. Both already reference the
installed GPTK D3D11 PE and Unix modules through read-only symlinks, but
that layout alone is not evidence of a working DX11 presentation path.

The coordinator requested the equivalent D3D11 probe and a separate
WineHQ registry record so the runtime adapter can bind either source
runtime explicitly. The existing baseline record must stay unchanged.

## Decision

Add an owned C probe in `tests/d3d11_present_probe.c`. Request a hardware
D3D11 feature-level 11_0 device, create a normal non-activating window
and two-buffer DXGI flip-discard swapchain, then clear the render target
to RGBA `(0.2,0.4,0.8,1.0)` for 120 successful Presents. Copy the final
cleared backbuffer to a staging texture before Present; Map READ supplies
synchronization, and the returned RowPitch locates the center pixel.
Require exact bytes `51,102,204,255` and print observed HRESULTs/count.
Keep the same 90-second process bound and targeted screenshot protocol.

Do not change Wine, introduce DXMT or revive the retired D3D11 shim.
Use the existing installed GPTK modules without copying or modifying them.

Emit `calimocho-wine11.20-gptk4b3` in the existing schema-version-1 engine
contract, separate from the CW baseline. Bind the actual install, launcher,
server, real Unix loader, native-GS helper, FreeType, Apple module links,
source identity, install manifest and observed smoke. Do not choose a
prefix in its launch environment or rely on injected environment variables.
Retain loader/helper hashes in profile assets/dependencies because hashing
only the Wine launcher would miss their changes.

Keep public placeholders separate from the executable local artifact.
Run the existing read-only Ode verifier and Calimocho exporter on the
actual local record. Do not edit a shared registry or app/backend source.

## Consequences

Both source runtimes pass the owned D3D11 120-frame and exact-pixel smoke.
The named-window captures are byte-identical and show the blue client area.
The local WineHQ record passes the existing verifier/exporter contracts.

This adds a measured D3DMetal DX11 route, not Xbox game compatibility,
shader/media coverage, a completed engine switch or distribution rights.
The shared desktop-negative conformance failure remains recorded.
Canonical acceptance stays in `dragos-core projects/ode-to-x/SPEC.md`.
