# ADR-0029: Source-built Vulkan in a separate candidate

## Status

Accepted for coordinator-assigned REQ-78, 2026-10-24.
Canonical claim and acceptance: `dragos-core` commit
`28533b096cd836db448dc265e79d779053a83777`.
Native passive execution requires scheduling and foreground/resource checks.
No game, mouse input or distribution admission is added.

## Context

The frozen port-10 configuration does not define `SONAME_LIBVULKAN` or
`SONAME_LIBMOLTENVK`. WineHQ's `win32u/vulkan.c` loads the configured
`SONAME_LIBVULKAN` with `dlopen`; the donor's `CX_LIBVULKAN` environment
override is not implemented in this upstream loader. A Wine Vulkan module
file alone is not evidence that the native backend can load.

No Man's Sky requires Vulkan. The coordinator assigned a separate backend
prerequisite before any title launch. This is not a mouse correction.
The repository requires source-built dependencies, so downloading an official
prebuilt MoltenVK release would still violate the chosen source policy.

## Decision

Use the official MoltenVK v1.4.2 source commit
`db66022459ffb663aa2b50f6b018bc2e124f5edf`, under Apache-2.0.
Pin its seven `ExternalRevisions` Git dependencies in `versions.json` and
verify each against the actual release's manifest before building.
The reported historical abbreviated revision did not resolve in the official
repository; no equivalence to a commercial recipe is inferred.

`tools/build_moltenvk.py` builds in a new worktree-owned directory, using
installed Xcode tools, a 45-minute total budget and four build jobs.
Use x86_64 only, no code signing, no system install and no prebuilt library.
Keep source identities, commands, compiler output, build configuration,
architecture, linkage and library hashes in local receipts.
The upstream pre-generated SPIRV-Tools templates supply generated headers,
not a prebuilt runtime library.

`tools/build_vulkan_overlay.py` copies the qualified port-10 source/build
and install into a separate port-11 directory. Reconfigure through upstream's
supported MoltenVK detection and build the win32u, winevulkan, vulkan-1 and
winemac modules, including their normal make prerequisites. Overlay only
those four PE modules for both PE architectures and three Unix modules.
Keep the original loader, native-GS helper, TLS modules and renderer links.
Select `@rpath/libMoltenVK.dylib` with an explicit owned LC_RPATH on win32u.
Do not add hidden `CX_LIBVULKAN` behavior.

The source-built MoltenVK version supports
`MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1`, which is also its default.
Bind this explicit setting in the new recipe. Do not present it as a
validated game-specific fix.

### Actual graphics discriminator

`tests/vulkan_present_probe.c` creates a non-activating owned window and
uses Vulkan 1.0 plus surface, Win32 surface and swapchain extensions.
Select a graphics queue with surface presentation support. Request no optional
device features, including `wideLines`. Clear a UNORM swapchain to
`(0.2, 0.4, 0.8, 1.0)`, present 120 frames, copy the final image into coherent
host-visible memory and require center RGBA `51,102,204,255`.
Handle BGRA and RGBA formats explicitly. Print actual Vulkan results,
device identity, frame count and readback.

Run only after source/artifact pins and passive scheduling are handed off.
Use a fresh owned prefix and a 90-second probe deadline. Never activate
the window or send input. Win32 `HWND_BOTTOM` is not proof of ordering below
native applications. A read-only CoreGraphics geometry helper enumerates
current display bounds and visible window frames. Select a free 400 by 340
region before spawn; pass its position through validated per-launch
`CALIMOCHO_PROBE_X` and `CALIMOCHO_PROBE_Y` values. The D3D probes support the
same placement without changing their rendering or readback assertions.
Bind the live native probe window to its authenticated process group and
check its actual frame for non-overlap and unchanged foreground application.
No free region, missing native identity or conflicting frame means stop,
not permission to move other apps or change native window levels.
The coordinator also permits an explicit short UI-input pause: only the
exact independently confirmed Ode PID/window-ID pair may then be excluded
from obstacles. Require that same foreground PID and exact window in every
fresh inventory. Another window of the same PID is not exempt. All foreign
windows remain obstacles. Bind the allowance and its scope in the receipt;
it is not unrestricted native non-overlap.
Respect competing graphics workloads. Retain prefix-scoped cleanup, before/after Apple payload
hashes and frozen port-10 hashes. Then rerun the existing owned D3D11, D3D12
and positive/expired-certificate HTTPS probes without weakening their checks.

One independent source-bound review returned REVISE. It identified the
native-ordering assumption, a local runner that did not propagate recorded
probe/cleanup failures, an unavailable expired-certificate case and a resumed
architecture-log path error. Corrections add fresh geometry/actual-frame
guards, fail-closed command/payload/residual checks, explicit negative TLS
selection and validation of the current architecture log. Original review
history is retained. Source checks are not native admission.

Emit a new exact local registry and sanitized public evidence only after
actual observations. Optional `provider: {id: "calimocho", contract_version: 1}`
is a producer declaration, not an admission or trust decision.
The coordinator must independently admit exact record/evidence identities.
Never rewrite the frozen port-10 registry.

## Consequences

Compilation supplies a candidate, not Vulkan presentation or No Man's Sky
acceptance. Failure remains visible in receipts; no prebuilt fallback is
permitted. A successful small clear/presentation/readback probe would not
establish shader, extension, title, input or performance compatibility.
This local dependency path is not a relocatable release package.
Canonical requirements remain in `dragos-core projects/ode-to-x/SPEC.md`.
