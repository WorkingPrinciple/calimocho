# ADR-0028: An owned relative-mouse discriminator

## Status

Accepted for source and synthetic checks only, 2026-10-24.
Native execution requires a coordinator-scheduled exclusive input lease.
No production runtime correction is selected.

## Context

The owner reports that Fallout 4 camera movement does not work on port-10.
The earlier Apple GPTK runtime reportedly allowed movement, with some
choppiness. This is not yet a controlled runtime comparison. The existing
input-free graphics probes cannot establish relative mouse delivery.

The CW26.3 source donor and frozen WineHQ 11.20 input paths have differences,
but not a demonstrated missing CW event-tap implementation:

| Surface | Observed source difference |
| --- | --- |
| Cocoa clipping | Identical confinement, event-tap, warp and association implementations apart from includes and removal of the macOS 10.13 availability check |
| Cocoa motion | Same absolute/interior versus relative/boundary selection and fractional delta accumulation; display-reconfiguration reset moved to a display callback |
| Cocoa event queue | Same adjacent compatible mouse-motion coalescing |
| Mac driver input | WineHQ adds `MOUSEEVENTF_MOVE_NOCOALESCE`; window Z-order handling moves to the server instead of the driver's explicit request |
| Capture | WineHQ receives the previous and already top-level window from the caller |
| Clip reset | CW returns without changing host clipping on reset; WineHQ clears host clipping on reset |
| win32u clipping | WineHQ tries automatic fullscreen clipping for an empty region even when the thread was not previously clipping |
| win32u raw registration | Same registration implementation; message-time bookkeeping changes |
| win32u motion | WineHQ adds motion accumulation and optional raw-frame transport; macdrv's no-coalesce flag forces immediate dispatch |
| Server raw input | WineHQ supports raw-frame arrays and suppresses empty mouse packets; without the raw-input flag it still derives relative deltas from cursor displacement |

Both donors default to confinement clipping when the Cocoa method is
available. The alternative event tap is not necessarily the active path.
Actual settings and foreground/clip state of the two game runs remain unknown.
These differences are candidates to discriminate, not identified causes.

Source comparison uses `build/cw26.3-candidate-04/sources/wine` and
`build/winehq-11.20/metal-port-08/source`. The latter supplies the unchanged
port-10 core. Source identities are already bound in the runtime records.

## Decision

Add `tests/raw_mouse_probe.c`, built using the installed MinGW compiler.
Require an explicit `--run` argument before taking foreground focus, hiding
the cursor and clipping it to the client rectangle. Register foreground mouse
raw input (usage page 1, usage 2). For five seconds, print raw packet flags,
relative deltas, foreground state, legacy mouse coordinates and screen cursor
coordinates. `--unclipped` supplies a separate unclipped control.
Record the original cursor flags and require no pre-existing raw registrations
in this owned process before registering. Record the original clip rectangle
before changing it.

Fail on API errors, missing nonzero relative packets or focus loss. Restore
the previous clip rectangle and balance every cursor-hide call, and remove
registration on ordinary cleanup, including focus loss, the five-second
deadline, wait failures and partial initialization. Before a stage succeeds,
its cleanup flag stays unset; a failed clip call does not authorize changing
the prior rectangle. Each successful cursor-hide call has exactly one matching
show call. The original zero raw registrations are restored by removing this
process's registration. The cleanup record reports API failures as failures.
A forced termination, crash or OS stall cannot guarantee this cleanup.
Those cases require the coordinator to verify host cursor visibility and
confinement explicitly before returning the lease. Do not call a deadline-killed
run successful or start another run while host state remains uncertain.
The probe does not inject Windows input and does not establish DirectInput
or game-specific behavior.

`tools/check_mouse_probe.py` checks complete foreground relative-input logs
against the process exit code and the requested clipped/unclipped mode.
Its synthetic tests reject empty deltas,
absolute-only input, mismatched counts, lost focus, errors, duplicate runs
and incomplete timing. Log acceptance alone cannot authenticate event origin.

### Scheduled native discriminator

The coordinator must first release the UI/owner input lease. No game may
be receiving input during the test. Do not run concurrently with Fallout 4.

1. Build and hash one PE, then use it unchanged on port-10 and the isolated
   source-built CW26.3 baseline. Use separate new prefixes and each exact
   recorded environment. Keep frozen installs and registry records untouched.
2. Initialize each fresh prefix separately with a finite startup deadline.
   Start the probe with a 15-second process deadline and retain stdout/stderr
   and its exit code. Wait for `READY` before injecting anything.
3. Bind the unique named probe window to its actual native process ID and
   on-screen window ID. The printed Windows process ID is not a macOS PID.
   Check the native frontmost process and window identity before every event.
   Abort if identity or focus changes.
4. With existing macOS event-post authorization only, send process-targeted
   `CGEvent` mouse-move events to that native process. Do not broadcast
   events, click, grant permissions or alter settings. Use a fixed bounded
   sequence with explicit nonzero X/Y deltas and locations inside the probe
   client bounds, and retain timestamps, deltas and target identity.
   Position and delta must agree for the interior-motion part. Include a
   boundary-motion part to exercise relative motion rather than only interior
   absolute-position conversion.
5. Check the complete five-second log with
   `check_log(text, exit_code, expected_clip=True)` (or `False` for the
   unclipped control). Record raw flags,
   nonzero relative packet counts, legacy movement and clipping/focus
   transitions. Exact raw deltas need not equal injected values because
   Cocoa can coalesce events and apply Retina scaling.
6. The smallest matrix is two clipped runs: port-10 and CW26.3, one unchanged
   PE and one identical event sequence. Repeat those two runs with
   `--unclipped` only if the clipped comparison differs. Terminate
   only the exact probe process if its deadline expires. Perform prefix-scoped
   Wine cleanup, verify clip/cursor restoration and release the lease.

Process-targeted synthetic events may not reproduce physical mouse event-tap
delivery. Failure on both runtimes is inconclusive, not evidence that both
physical input paths are broken. If needed, the coordinator can schedule the
same short physical-movement sequence on each runtime under the lease.

## Consequences

The source probe and its receipt checks can be prepared without disturbing
the owner. No native/input execution, port-11 engine record or mouse fix is
implied by compilation. A production patch requires a reproduced failing
boundary first, then the same input probe plus D3D11/D3D12 regressions.
Canonical acceptance remains in `dragos-core projects/ode-to-x/SPEC.md`.
