# ADR-0045: Observe bounded target state without input

## Context

Actual012 obtains the formerly missing IStaticLifetime factory successfully.
The separate native map fixture passes. Actual AppL nevertheless reaches
the180-second observation bound without a completed GetCollection trace,
new activation failure, lifecycle callback or window fact. This does not
locate a blocked method or prove that the target is running normally.

The coordinator relayed owner approval for a changed013 diagnostic, not
an unchanged replay or longer timeout: sample the admitted target at about
20 and60 seconds, record method entry/completion and inspect only an
exact target window if one exists.

## Decision

Build a fresh source sibling and preserve sealed012. Add fixed method
entry/completion fingerprints for GetCollection, inner PropertySet activation
and map query, Lookup/Insert, CoreApplication.Run, FrameworkView creation,
Initialize, SetWindow, Load, Run and Activated. Record no class keys or
object values. Cap progress at256 rows per process and mark the limit.
Entry is not success; only an exit carries a result.

The collector schedules two target-state helpers relative to the recorded
AppL handoff, while retaining the separate exact-process exit observer
and original180-second cap. Each state helper rechecks the exact executable
and admitted AppId/token before any target observation or debug attachment.

First count target threads and enumerate only target-owned top-level HWNDs.
Retain HWND, fixed known class or redacted class, visible flag and dimensions.
Do not read arbitrary titles or send window messages. The HWND is needed
for the observer owner's exact host-window mapping.

For stacks, use Wine's real debugger attachment and local-module StackWalk64,
not fabricated frame names. Create a debug object and disable kill-on-exit
before attaching. Continue debug events and explicitly detach. Allow at most
5 seconds to reach the attach breakpoint and10 seconds for the helper
overall. If the helper exceeds its bound, terminate only that helper;
its debug object has kill-on-exit disabled. The owner still performs final
exact-prefix cleanup.

Retain at most64 target threads,16 frames per thread and512 modules.
Frames contain only validated module basenames and module-relative offsets.
Unmapped PCs are redacted, not saved as absolute addresses. Symbol search
uses an explicitly empty local path, ignores CodeView symbol records and
does not request a symbol-server download. Attach, context, unwind coverage,
format, truncation and detach limitations remain visible.

Debugger attachment briefly pauses threads and introduces a debugger
break-in thread. Record thread count before attachment separately; do not
interpret the resulting stack sample as an unperturbed execution trace.
The helper never assigns package identity, runs a target command, changes
a window, or follows an unknown PID based on its name.

If a genuine CalimochoCoreWindow is visible, the existing no-input host
observer owner maps that exact Wine HWND to a Mac window and captures one
private window-only screenshot with SHA-256. An unavailable exact mapping,
window or permission is an explicit limitation, not permission for a
desktop capture or guessed window.

## Consequences

The new fingerprints can distinguish a method entered without completion
from a method never observed. Target thread/window samples can provide
additional evidence about that interval. Neither an alive PID nor a
sampled waiting frame proves UI readiness or a root-cause deadlock.

The collector retains only a fixed helper grammar. Unexpected debugger
output is rejected with a format-error marker, not persisted verbatim.
Only helper processes created by this collector may be terminated by it;
the actual target remains owned by the exact-prefix runtime observer.
Native013 evidence is required before claiming any new runtime outcome.
