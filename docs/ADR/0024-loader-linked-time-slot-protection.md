# ADR-0024: Loader-linked time-slot protection for native GS

## Status

Accepted for the owner-directed isolated REQ-74 discriminator, 2026-10-24.
This adds no game, installation, security or distribution authorization.

## Context

The previous native-GS decision introduced a launch-injected localtime
helper. Review and an owned reproduction found a remaining libc-internal
ctime path, so this decision replaces that incomplete dependency design.

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
The old helper protects direct localtime calls, but libc's internal call
from ctime bypasses the external symbol binding and still corrupts the slot.

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
localtime_r and thread-local result storage. Interpose ctime separately,
using localtime_r and asctime_r with a thread-local 26-byte character buffer.
Keep the Windows PEB mirror: dropping a Windows ABI field without proving
that every PE consumer avoids it is not an established alternative.

Link the actual Unix Wine loader with a required `LC_LOAD_DYLIB` reference
to `@loader_path/libnative-gs-localtime.dylib`, using the linker's
needed-library flag. Require and verify that load command after linking.
No `DYLD_INSERT_LIBRARIES` runtime setting is required. Do not
modify Apple files or instructions, change security policy, sign payloads,
or set a global environment variable. Late-loaded ntdll and executable
interpose sections were ineffective in the retained experiments.

The bounded WineHQ build must produce and hash the helper, its source and
compiler, and record its required loader-relative dependency. Missing output,
compiler/link failure or missing load command is a build failure.
CW baseline builds do not gain this dependency.
Normal make installation does not include it: an isolated research install
must retain the helper explicitly beside the real Unix loader.

Keep optional Wine-owned callback and thread-start traces as a separate
source transformer. Record return values without evaluating calls twice.
Do not inspect or alter Apple's instructions.

## Consequences

Port-09 and the unchanged CW baseline both return D3D12 `S_OK` in fresh
prefixes. Port-09 also completes builtin startup and version/registry queries,
including startup with ntdll-channel timezone traces enabled.
The owned localtime/ctime probe fails without protection and passes with
the linked helper, including after relocation. A missing helper prevents
the probe from starting. Eleven audited libc time entrypoints preserve the
mirrored PEB on the observed host; this is not a claim about every libc API
or future operating-system version.

The identical Wine conformance executable has the same refcount failures
and missing-window-data swapchain error on both source-built runtimes.
WineHQ terminates; CW reaches exception handling and the bounded timeout.
The separate diagnostic identifies the fatal handle as GetDesktopWindow
in a negative test which expects `E_ACCESSDENIED`. This is not evidence of
a WineHQ-only regression or permission to claim full graphics parity,
game support or release readiness.
No shared registry or existing prefix was changed. Requirements remain in
the canonical `dragos-core projects/ode-to-x/SPEC.md`.
