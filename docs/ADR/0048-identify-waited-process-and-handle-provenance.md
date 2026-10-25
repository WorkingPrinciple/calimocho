# ADR-0048: Identify the waited process and handle provenance

## Context

Actual cell015 identified an event and a process in the pending native
Initialize multiple wait. The event was unsignaled at entry. Process identity,
creation provenance and WaitAll versus WaitAny were not retained. The evidence
does not establish a missing broker, a signal-or-exit pattern or a deadlock.
The owner approved changed cell016 diagnostics, not a guessed behavior fix.
Canonical program requirements remain in `dragos-core projects/ode-to-x/SPEC.md`.

## Decision

Build a separate source-only diagnostic sibling, preserving sealed015.
At the real wait, query the process handle for basic information, image
basename and exit status. Retain actual wait type. Failed queries remain
unknown, not a dead or nonexistent process.

Record actual event creation/open, process open/create, handle duplication
and close, and LPC/ALPC connection entry/result. Preserve every original
argument, ABI bridge and result. Observe from CoreApplication.Run; objects
created before it or inherited from another process have unavailable origin.
Numeric-handle matches are chronological candidates, not an automatically
proven lineage. Retain at most4096 events and32 candidates per waited slot.

Use saved syscall and read-only user-stack return-slot sites, module-relative
only. These are not complete creator stacks. Expand sanitized relay imports
only for native XAML, combase and twinapi.appcore callers. OpenProcess,
CreateProcess and RPC API relay callsites complement the syscall records.
Norelay and internal calls are not inferred from missing relay rows.

Observe the actual rpcrt4 client transport connection attempt and its result,
with at most1024 events. Endpoint and binding strings are excluded. RPC
internal callers do not establish a full caller chain to XAML or combase.
Only exact known-public DBWIN event basenames may be retained. Unclassified
names are named-redacted; unnamed objects are distinguished.

Keep the fresh private prefix, no input,180-second cap, safe20/60-second
samplers and exact-owned-window-only screenshot rule. Runtime owner0ab alone
executes once and cleans the prefix. Source compilation does not execute Wine.

## Consequences

The next actual observation can identify the waited process and expose
creation/IPC attempts without manufacturing an event, process or service.
Missing creation records remain a coverage gap. Handle reuse, access-denied
queries, source caps, collector overwrite and debugger perturbation stay
explicit. No UI, sign-in, game or engine-compatibility acceptance follows
from this diagnostic source change.
