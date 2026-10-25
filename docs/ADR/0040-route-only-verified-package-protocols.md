# ADR-0040: Route only verified package protocols

## Context

Actual Xbox cell007 activated Windows.Foundation.Uri successfully, then failed
the Windows.System.Launcher factory request for ILauncherStatics
`277151c3-9e3e-42f6-91a4-5dfdeb232451` with CLASSNOTREG. The pinned Wine
source has no Launcher implementation or IDL declaration. No Launcher method
or target URI was observed in007. Its absence is a local API gap, not evidence
of a remote-service call.

The owner approved a package-local implementation, no host URI handler,
default browser or CrossOver fallback. The verified GamingApp manifest
declares `msxboxl` on AppL/XboxPcApp.exe with UWP EntryPoint XboxPcApp.App.
Its `msgamelaunch` extension overrides the executable to XboxPcTray.exe and
uses a full-trust entrypoint. Ignoring that override would launch the wrong
image under the wrong activation model.

## Decision

Add an isolated Windows.System.Launcher DLL with the public ILauncherStatics
vtable, including the two preceding file methods. Use Wine's pinned boolean
asynchronous-operation machinery, preserving its upstream copyright and
licence. Unknown schemes complete false with no fallback. File launches and
non-null LauncherOptions return explicit E_NOTIMPL; options are not silently
ignored.

Resolve only protocol declarations in the verified owned package snapshot.
Bind every route to the declared Application Id, exact executable and
entrypoint, including extension-level overrides. Reject ambiguous schemes,
invalid names and escaping or symlinked payloads. Never derive an executable
from a caller's URI.

Extend the host startup registration file to a bounded32-entry exact-image
table, preserving the old single-record format. The server, not the parent
process, assigns the verified identity bit. Plain executable children still
do not inherit it. Launcher creates supported full-trust targets suspended
with an explicit package attribute, verifies the resulting server token and
resumes only the admitted image. A successful operation means a process
started, not that UI rendered or activation finished.

Full-trust protocol activation supplies one quoted URI argument, rejecting
quotes and control characters. The URI stays in process memory and is never
persisted by the collector. Record only a bounded scheme, Application Id,
child PID and result. The protocol table is private local activation metadata,
not a security sandbox against another process running as the same Mac user.

UWP protocol event delivery is not implemented by invoking a fictitious
command-line switch. AppL requires genuine CoreApplication Activated delivery
with ProtocolActivatedEventArgs. Cell008 reports that missing piece explicitly
as `uwp-protocol-activation` and E_NOTIMPL rather than claiming a launch.
The owner approved genuine process-bound UWP activation records as a subsequent
slice. Do not pretend a full-trust argv launch implements that contract.

Track both Windows.UI.Xaml.dll and Microsoft.UI.Xaml.dll by exact process
identity. A successful recorded protocol child suppresses the old two-second
direct-CE-exit drain cutoff, but never extends the original finite collector
budget. CE exit is not AppL exit. Missing child exit evidence remains unknown.

## Consequences

Cell007 and its frozen helper, collector, source and snapshot stay unchanged.
Cell008 is a new diagnostic sibling, not a game runtime or accepted Xbox app.
Source/build and synthetic fixture checks must remain distinct from genuine
CE execution. Synthetic test registrations are labelled as owned fixtures,
never cryptographically verified Microsoft packages.

The first isolated compile exposed missing package-aware include paths.
The next exposed Wine's Size macro and normalized-parameter constant.
Reusing the boolean async source also required its original inspectable
forwarding macros, and the UUID link archive lives under libs, not dlls.
All failed logs are retained. A generated unqualified registry initially
kept the predecessor entry despite computing a rebased copy; a direct path
check found it, and the corrected generator replaces the engine entry.
The wrong-path artifact is retained and is not an executable handoff.

The isolated DLL, server, diagnostic helper and windowless fixture now compile.
The fixture contains compile-time assertions for the public Launcher URI
vtable slots. The focused host suite passes52 checks, including route
overrides, deployed assets, redaction and child-aware capture. The retained
application and complete framework graph were cryptographically rechecked
with the pinned public2011 publisher and2010 timestamp roots. No new trust
anchor, credential or Keychain operation was needed.

The source freezer pins a real producer commit separately from upstream Wine,
all deployed files, individual assets, both explicit class imports, the new
multi-image registration table and a standalone collector. An unchanged
integrity result compares deployment with the build receipt; it is not
runtime qualification. Its receipt states that native execution is unobserved.
Resumed builds retain the previous candidate and refuse frozen outputs.

Native fixture and actual008 results remain unexecuted pending the scheduler's
exclusive lane and are recorded separately after execution. Compilation alone
does not prove activation, input, XAML or UI behavior. The approved009 event
delivery is separate: the pinned CoreApplication currently implements only an
activation factory, not ICoreApplication Run, views or Activated callbacks.
