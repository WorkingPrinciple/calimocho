# ADR-0037: Add an opt-in Wine-built AGS5.4 adapter

## Context

The DIRT5 owner traced the AMD-only startup path in the local executable.
It calls `agsInit`, ignores failure, then passes `AGSGPUInfo.driverVersion`
at offset `0x10` to `strstr`. Native AGS cannot reach an AMD driver under
GPTK and leaves that pointer null. The owner's prefix-local adapter reached
the title screen. That result belongs to that adapter, not to this module.

The owner approved folding the required behavior and the minidump API set
into a durable source-built Calimocho sibling. Canonical program requirements
remain in `dragos-core projects/ode-to-x/SPEC.md`. No proprietary executable
or native AGS binary is copied into the repository or engine.

## Decision

Implement exactly the four observed AGS5.4 imports as a Wine builtin:
`agsInit`, `agsDeInit`, `agsDriverExtensionsDX12_CreateDevice`, and
`agsDriverExtensionsDX12_DestroyDevice`. The ABI was checked against the
AMD declarations retained at Valve Wine commit
`913494390e634ebd136c760b01bbb5d35b19a177`, file
`dlls/amd_ags_x64/amd_ags.h`. The implementation uses small local declarations,
not Proton's Linux/Vulkan implementation.

Initialization reports interface version 5.4.1, non-null empty driver and
software strings, zero devices and no device array. It does not invent an
AMD driver version or hardware extensions. Device creation forwards the
exact adapter, interface ID and feature level to `d3d12!D3D12CreateDevice`
and reports zero extensions. Destruction releases one device reference.
Invalid arguments fail explicitly; failed device creation clears its output
and emits a Wine warning.

Use `tools/build_ags_overlay.py` to build with the existing source-built Wine
tools, CRT and import libraries in a new owned output. It writes no files
into the accepted source, build or install. It adds only the x64 AGS builtin
and ADR-0033's x64/i386 minidump forwarders to a new copy of the frozen
private-Metal base. Receipts bind source files, toolchain, link inputs,
commands, logs, outputs and the complete installed inventory.

Keep native AGS preferred in the builtin header. The generic candidate
registry retains the quiet base environment. A separate DIRT5/GPTK recipe
explicitly selects `amd_ags_x64=b`; it is not a new engine kind or a global
AGS replacement. It does not create a KnownDLLs entry or alter a game folder.
Other AGS versions and other games are unsupported by this four-export module.
The candidate registry discards inherited graphics, TLS and smoke acceptance.

## Consequences

The host C harness checks AGS5.4 record sizes and offsets, non-null empty
strings, zero devices/extensions, device forwarding, failure clearing,
release count and argument failures. A PE audit checks the Wine builtin
marker, exact four exports and direct D3D12 import.

The first isolated PE compile failed because it included `config.h` with
Wine's CRT headers and omitted `stdarg.h`. The corrected second output,
`metal-port-11d-ags54-02`, compiles and adds exactly the declared three DLLs.
The first output and diagnostics are retained.

An attempted `make -n -B` command to read an existing link recipe triggered
Makefile regeneration and failed the existing tool check for bison. No
runtime or accepted install was changed; subsequent recipe inspection read
the generated Makefile directly, and the standalone build does not run make.

Source and PE checks do not establish renderer/TLS regression acceptance or
the DIRT5 title-screen result for this actual builtin. Passive runtime
qualification needs the scheduler's bounded slot and existing non-overlap
policy. The DIRT5 owner owns actual game admission. The new sibling remains
unqualified until those observations are bound to its exact inventory.

## Reproduction

Use installed tools only and require a new build directory:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_ags54 tests.test_minidump_overlay
PYTHONDONTWRITEBYTECODE=1 python3 -m tools.build_ags_overlay \
  --output build/winehq-11.20/metal-port-11d-ags54-NEW
```

The generated `ags54-minidump.registry.local.UNQUALIFIED.json` is the generic
engine record. `dirt5-ags54.environment.json` is the explicit game-scoped
environment recipe, not a second engine. Preserve existing prefixes and
saves; do not merge this recipe into global defaults.
