# ADR-0047: Observe activation providers and wait/thread facts

## Context

Actual014 entered native Initialize and recorded no owned E_NOINTERFACE
or E_NOTIMPL. The last three direct native XAML relays were combase
WindowsCreateStringReference, RoGetActivationFactory and
CoCreateFreeThreadedMarshaler. StaticCollection.GetIids completed.
A real nonalertable infinite two-handle wait was entered without a retained
exit. Successful object-type queries were classified as unknown.

The classifier compared Wine's16-bit WCHAR strings to Unix host wide string
literals, whose wchar_t is32 bits. This is a diagnostic defect, not evidence
that Wine cannot identify the objects. Preserve sealed014 and correct the
source for the separately owner-approved015 observation.

## Decision

Compare queried UTF-16 code units to fixed ASCII type names. A host-compiled
regression explicitly uses32-bit wchar_t and16-bit WCHAR. Query event signal
state, semaphore current/maximum count and thread basic/start information
through their actual NtQuery APIs. Failed queries remain unknown. Resolve
a waited thread's start image only if its PID matches this process.
Never query object names.

Record every AppL RoGetActivationFactory and RoActivateInstance entry and
exit independently of Initialize. Type names use a bounded public identifier
grammar; no arbitrary strings or arguments are retained. Record the requested
IID and actual HRESULT on exit. At the actual DllGetActivationFactory dispatch,
record the serving image's validated basename. Successful factory exit carries
the same selected image. RoActivateInstance keeps its original nested factory
call, which supplies its provider evidence. Entry and dispatch are not success.

RoGetActivatableClassRegistration is an existing stub in this pinned Wine;
neither its implementation nor a prototype exists in the source headers.
Do not guess its private ABI to decode arguments or replace its behavior.
Retain a fixed fingerprint if that exact stub failure is observed. Its
class/IID/provider details remain an explicit unavailable coverage surface.

Wrap actual in-process NtCreateThreadEx entry/return, preserving its existing
implementation and ABI bridge. During Initialize, record its start image,
query result and real returned thread ID. Resolve the saved syscall return
and a read-only user-stack return-slot candidate to image-relative offsets.
They are not a recovered full call chain or a proven high-level creator.
Remote-process thread creation is outside this in-process measurement.

At20/60-second snapshots, query each exact target thread's exit status and
start address, then keep its existing top-frame sample. An alive thread is
not automatically running application code. OS blocked-state enums are
not supplied by this Wine snapshot API. Separately attach the collector's
actual wait entries that have no retained exit at snapshot collection.

Events and semaphores have no intrinsic expected-signaler owner. Retain
unknown unless separate observed behavior establishes one. A thread handle
signals when that exact thread terminates; this is a real condition, not
an inferred thread that should signal an event. Do not signal anything,
alter apartment/dispatcher behavior, or invent interface success.

## Consequences

The source-built combase is a seventh changed module in the new isolated
recipe. Preserve all native input, mappings, package identity and180-second
no-input policy. Keep all sealed predecessors immutable.

Bound public activation records at4096 and thread records at1024 retained
events with explicit overwrite counts. Existing COM/relay/wait bounds,
target-PID filtering, safe debugger attach/continue/detach and exact-window-only
screenshot policy remain. Logging and queries perturb timing.

Actual015 is required before claiming any activation provider, object state,
thread creation or signaler outcome. The private registration stub, unavailable
mapping and unobservable signaler remain explicit limitations, not false
completion or justification for guessed behavior.
