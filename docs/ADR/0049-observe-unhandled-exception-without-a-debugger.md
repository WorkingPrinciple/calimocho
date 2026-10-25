# ADR-0049: Observe the unhandled exception without a debugger

## Context

Actual016 identified the waited process as winedbg.exe, Wine PID356,
parent256, alive at entry. The real wait was WaitAny(event88, process94).
This matches the inspected kernelbase debugger-launch implementation,
but016 did not retain the exception or prove its cause. The owner approved
changed017 exception diagnostics only. Canonical program requirements remain
in `dragos-core projects/ode-to-x/SPEC.md`.

In this exact Wine source, removing AeDebug.Debugger defaults to winedbg.
Auto=0 may display a yes/no dialog and does not reliably prevent launch.
UnhandledExceptionFilter explicitly bypasses debugger launch when the
process error mode includes SEM_NOGPFAULTERRORBOX.

## Decision

Use a new private017 prefix with a frozen registration setting AeDebug.Auto
to0. Record its import and readback. In this diagnostic source only,
CoreApplication.Run adds SEM_NOGPFAULTERRORBOX, preserving other error-mode
bits and restoring the previous mode on return. This prevents debugger
launch and its modal prompt without manufacturing an exception result.

Instrument the real ntdll unhandled-filter entry, forwarding its original
return unchanged. Retain the first32 records: code, flags, parameter count,
faulting image plus relative address, safe typed scalar parameters and
image-relative or redacted pointer parameters. Never dump C++ objects,
message strings or absolute addresses.

Retain the last50 admitted relay calls at the exception and separately
observe RoOriginateError, RoOriginateErrorW and RoOriginateLanguageException
HRESULTs. Same-thread origin records are candidates, not decoded proof of
the C++ exception's HRESULT. An unknown object layout remains unknown.
Observe AppL exit through the existing exact-target process handle.

## Consequences

The debugger wait should no longer hide the target's actual exception and
exit, but native acceptance requires the once-only runtime observation.
Unhandled-filter entry does not alone prove final termination: an application
filter may still handle it. Process exit/code are separate evidence.
The no-input180-second cap, safe samplers, exact-owned-window screenshot
rule and exclusive runtime owner remain unchanged. Sealed012-016 are not
modified or replayed. This is not a compatibility fix or UI acceptance.
