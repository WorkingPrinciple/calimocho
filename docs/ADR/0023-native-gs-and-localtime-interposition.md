# ADR-0023: Native GS and localtime interposition for WineHQ

## Status

Accepted for the owner-directed isolated REQ-74 discriminator, 2026-10-24.
This adds no game, installation, security or distribution authorization.

## Context

The source-built CW26.3 baseline creates a D3D12 device with the installed
GPTK 4.0b3 payload. WineHQ 11.20 port-07 faults in the native pthread library
after a renderer thread enters at `dxgi.dll+0x1f00`. Wine-side traces show
no D3DMetal callback entry before that fault.

Public CW source preserves Darwin's native GS thread-data base. WineHQ
instead switches it to the Windows thread environment block (TEB) while
running Windows code. Native libraries entered directly from that code
then read Windows fields as native thread data.

Mirroring the Windows process pointer at native GS offset `0x60` introduces
a second conflict: Darwin localtime uses that same slot. CW documents the
conflict and patches localtime instructions. That instruction hook is not
appropriate for this isolated source port. An owned native regression
probe reproduces the slot corruption without Wine or Apple disassembly.

## Decision

Adapt the measured native-GS model into current WineHQ source rather than
replacing its old whole driver or signal implementation. Limit native GS
changes to Darwin x86_64. Resolve private syscall-frame and instrumentation
fields through the mirrored TEB pointer, preserve thread-start native GS,
and mirror TEB self, static TLS and process pointers. Synchronize static
TLS allocation, reallocation and teardown. Mirror preallocated expansion
TLS and reserve conflicting inline TLS indices for native-GS threads.
PE code uses the Darwin-only native-pointer marker because its cross
compiler does not define `__APPLE__`.

Build a small LGPL source-owned dylib which interposes localtime with
localtime_r and thread-local result storage. Load it at process startup
through the research process's explicit `DYLD_INSERT_LIBRARIES`. Do not
modify Apple files or instructions, change security policy, sign payloads,
or set a global environment variable. Late-loaded ntdll and executable
interpose sections were ineffective in the retained experiments.

The bounded WineHQ build must produce and hash the helper, its source and
compiler, and record the required environment. Missing output or compiler
failure is a build failure. CW baseline builds do not gain this dependency.
Normal make installation does not include it: an isolated research install
must retain the helper explicitly and bind its exact launch path.

Keep optional Wine-owned callback and thread-start traces as a separate
source transformer. Record return values without evaluating calls twice.
Do not inspect or alter Apple's instructions.

## Consequences

Port-08 and the unchanged CW baseline both return D3D12 `S_OK` in fresh
prefixes. Port-08 also completes builtin startup and version/registry queries.
The owned localtime probe fails without the helper and passes with it.

The Wine conformance executable progresses beyond device creation but
terminates during swapchain initialization after `my_get_win_data`
returns zero. That is a separate unresolved presentation boundary, not
permission to claim full graphics parity, game support or release readiness.
No shared registry or existing prefix was changed. Requirements remain in
the canonical `dragos-core projects/ode-to-x/SPEC.md`.
