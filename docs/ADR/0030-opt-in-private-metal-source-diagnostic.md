# ADR-0030: Opt-in private Metal source diagnostic

## Context

The accepted port-11 runtime deliberately uses public Metal API only.
The runtime owner authenticated an NMS failure at `vkCreateDevice` for
physical-device feature flag 16. In the pinned Vulkan headers this is
`wideLines`. This establishes a requested-feature failure, not its remedy.
Pinned MoltenVK 1.4.2 sets that feature from `useMetalPrivateAPI`.
Its compile-time private-API default is zero.

Whiny commit `926c550`, REQ-A01/N13/H03/D08, assigns a source/build-only
diagnostic. This does not reopen the accepted REQ-78 runtime or authorize
runtime selection, native execution, a new registry, or a game launch.

## Decision

Add explicit `--metal-private-api` to the existing builder. It appends
`MVK_USE_METAL_PRIVATE_API=1` through the owned Xcode configuration.
The default build configuration remains unchanged and disables signing.
Resume refuses a different private-API configuration.

Use `--local-build-cache` to copy the existing owned, pinned source build
into a separate output directory without fetching dependencies. Verify
the successful source-build receipt, source/dependency commits, clean
tracked source, and artifact hashes. Record reused source-built static
dependency identities. Build MoltenVK with a fresh derived-data directory,
the existing four-job limit and 45-minute budget.

Add optional `--require-wide-lines` to the existing owned Vulkan probe.
Query the actual feature; refuse an unavailable feature, otherwise enable
it in `VkDeviceCreateInfo` before requesting the device. Default invocation
still enables no optional features. Retain the 120-Present and exact RGBA
readback criteria unchanged.

## Consequences

The private dylib and updated PE probe are compile-only artifacts.
Private Metal interfaces may change with macOS and are not App Store API.
Successful compilation is not proof of availability, correct wide-line
rasterization, or NMS compatibility. No runtime library is loaded here.
The existing public-API dylib, source/build outputs, registry and receipts
remain frozen. Native diagnostics and any later record/admission require
the runtime owner's separate exact grant.
