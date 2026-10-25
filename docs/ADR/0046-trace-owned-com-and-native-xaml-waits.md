# ADR-0046: Trace owned COM calls and native XAML waits

## Context

Actual013 entered native FrameworkView.Initialize without a retained exit.
Both admitted target snapshots saw two threads before debugger attachment
and no window. Each captured only one module-relative frame per thread.
Neither those offsets nor the extra threads observed during attachment
identify a function, lock, event, or deadlock.

The owner approved a changed014 diagnostic with no input and the same
180-second cap. The next behavior change must follow actual interface
failure or wait evidence, not an assumed XAML requirement.

## Decision

Preserve sealed013 and build a new source sibling. Generate typed forwarding
wrappers from its exact generated Wine headers for all122 vtable slots on
CoreApplication's factory/statics/view, IStaticLifetime and its collection,
CoreWindow, and CoreDispatcher. The compiler checks their ABI. Each wrapper
calls its existing implementation without changing its arguments, output
or return value. Record every entry and exit from CoreApplication.Run until
it returns or the observation ends. QI records its exact IID and HRESULT;
reference-count returns are not described as HRESULTs. Do not log method
arguments, map keys, values or object pointers.

Stock x64 Wine relay formats string arguments and absolute return addresses.
Replace that formatting in this isolated diagnostic build. Enable thunks
only for combase, twinapi.appcore, windows.ui, coremessaging and selected
ntdll synchronization exports. Skip non-XAML static importers. At actual
relay entry, retain metadata only while native Initialize is active and
the return site falls inside the loaded native Windows.UI.Xaml image.
Keep the export name and image-relative offset, not arguments or results.
Disable stock relay DLL-entry formatting in this mode.

Retain a300-call ring per PID. Freeze that tail at actual NtWait entry.
Pair real NtWaitForSingleObject, NtWaitForMultipleObjects and
NtSignalAndWaitForSingleObject entry/exit around their existing implementations.
Read unnamed object type through NtQueryObject and event signal state
through NtQueryEvent. Retain the process-local handle, status, wait slot,
alertability and infinite-timeout flag. Never query or save object names.
Query failure means unknown. A wait entered without retained exit is not
automatically a deadlock or proof that its owner failed to signal.

The collector admits only fixed diagnostic grammar and the Launcher-bound
AppL PID. Keep up to65536 COM events plus the first32 HRESULT failures,
separately preserving the first E_NOINTERFACE and E_NOTIMPL. Mark overwritten
tail rows, source relay cap65536, and wait/PID storage limits. Keep at most
64 pending waits and32 recent completed waits. Source phase markers bound
wait/relay collection to Initialize. Continue parsing these fixed channels
past the ordinary8MiB stderr budget so the relevant tail is not silently
lost. The180-second cap and maximum line length remain unchanged.

Reuse the exact-image/token observers and safe20/60-second snapshots.
They remain measurements that perturb timing. The existing exact-window-only
screenshot rule remains: unknown mapping or no visible owned window means
no screenshot, not permission to capture a desktop.

## Consequences

The changed recipe can identify an actual missing owned interface/method,
or a real wait object observed during Initialize. It deliberately does not
implement a guessed interface, signal an event, change dispatch behavior,
or claim that a signaled/unsignaled state explains the stall.

Relay evidence covers only Wine's actual x64 relay thunks and direct native
XAML return sites. Norelay/syscall exports and native-to-native calls are
not covered by relay; the three actual wait wrappers provide separate
evidence. Logging, object queries and debugger snapshots perturb execution.
Reached limits remain explicit and prevent absence claims outside coverage.
Only the runtime owner executes the new private014 recipe once and cleans
that prefix. Source compilation and parser tests are not Xbox UI acceptance.
