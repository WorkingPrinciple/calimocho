# ADR-0041: Deliver process-bound UWP activation

## Context

ADR-0040 leaves UWP protocol routes explicitly unsupported in cell008. The
owner approved a separate cell009 source slice: a server-owned activation
record, genuine CoreApplication Activated delivery and a real Wine window
and dispatcher. No native cell008 scheme or handoff has been observed by
this source lane. Static GamingApp references identify CoreApplication,
Windows.UI.Xaml and WinUI2, not a Windows App SDK host.

The pinned CoreApplication supplies an activation factory but no application
lifecycle. Its CoreWindow static returns success with a null window. Passing
that null result to XAML would hide another missing implementation.
Separately, the verified main package declares its own in-process classes
that were absent from the earlier framework-only class import.

## Decision

Keep cell008 unchanged. Build cell009 as an isolated copy with exactly six
changed modules: wineserver, Unix and PE ntdll, twinapi.appcore, windows.ui
and the package-local Launcher. Canonical requirements remain in the parent
program's `projects/ode-to-x/SPEC.md`; this ADR does not accept a requirement
or create a second specification.

For a verified UWP protocol route, Launcher creates a suspended target with
its exact registered package identity and a bounded protocol record. The
server admits the target image, checks the same verified caller package,
records the real caller AppId and owns the record for that process only.
Plain children do not inherit it. Only the current process can query it.
The UWP command line contains the executable, not an invented URI switch.
A successful LaunchUriAsync result still means only that an admitted
process was resumed, not that XAML or UI works.

Implement the public ProtocolActivatedEventArgs and LaunchActivatedEventArgs
interfaces. The former returns the parsed URI and Protocol kind; a process
without a record gets Launch kind. Both report NotRunning as the previous
execution state. Unknown interfaces and unsupported methods fail explicitly.

CoreApplication creates the view, initializes it, creates a hidden HWND,
calls SetWindow and Load, then queues Activated before entering the view's
Run method. The dispatcher delivers Activated while Run pumps messages.
Waiting until a blocking Run returns would prevent normal app startup.
Handlers and event arguments have real COM ownership and bounded lifetimes.

CoreWindow returns the current view's actual window. Activate shows it;
Bounds, Visible and Dispatcher reflect the real HWND. Activation and size
events come from window messages. CoreDispatcher uses a bounded UI-thread
queue, real message pumping and asynchronous-action state, cancellation and
completion. Other event subscriptions and interfaces remain explicit missing
fingerprints, not successful placeholders. Display execution belongs only
in the scheduler-granted runtime slot.

Add main-package class registration as an opt-in to the existing verified
preparer. The authenticated snapshot contains442 such entries, with every
declared server present. Main-package classes take precedence over framework
duplicates. Earlier preparation defaults and frozen cells stay unchanged.
Other statically predicted Windows classes remain a trace-led backlog.

The collector admits core/window facts only from the directly observed CE
or a recorded protocol-child PID. Record fixed title/class categories, kind,
handler count, HRESULT and module basename, never raw URI, window content or
unfiltered output. Keep the original45-second helper and60-second collector
caps and explicit unknown child state when observation ends first.

## Consequences

The real source build and helper/owned-window-fixture compilation complete.
The staged inventory has exactly the six expected changes. These are source
and build facts, not native activation, XAML, window or Xbox acceptance.
The fixture and actual cell009 remain unexecuted in this source lane.
Cell008 must run first; Xbox0ab owns the actual cells and scheduler slots.

Retained failed attempts exposed a missing installed-header declaration,
stale generated server protocol, an ineffective directory make target,
WinRT namespace settings and GUID-definition ordering. A COM macro also
evaluated an increment expression twice; the reference increment is now
separate. The fixture link needed its own IID definitions. Failed outputs
and logs remain available rather than being rewritten as successful runs.

Restaging an unqualified candidate requires an explicit resume and preserves
its previous installed tree and receipts. Build, stage and freeze commands
refuse frozen siblings. A frozen receipt binds committed producer source,
all installed entries, individual registry assets, authenticated package and
framework inputs, both class imports, the server table, observer and fixture.
Integrity equality is not native qualification.

There is no host URI/default-browser fallback, remote UI or token substitution,
Store/licence implementation, new credential operation or broad API stubbing.
The first actual missing IID or method remains the next bounded fingerprint.
