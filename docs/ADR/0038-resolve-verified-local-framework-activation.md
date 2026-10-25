# ADR-0038: Resolve verified local framework activation

## Context

Cell006 observed the manifest-selected XboxPcAppCE process exit 0 after about
90 ms, with an error from combase factory lookup. It did not capture the
requested class or returned HRESULT. It did not prove a single-instance
redirect, a missing framework, a XAML failure, or a service that needs a
proxy.

The owner authorized exact public runtime class names, requested interface
GUIDs and returned HRESULTs, keeping other output redacted. The GamingApp
manifest declares four Microsoft framework dependencies. Their retained
copies are available locally; no download or proprietary runtime copy is
needed.

## Decision

Use a new isolated diagnostic source/build/install sibling. Preserve the
delivered package candidates, accepted renderer runtimes and cell004-006
evidence.

Resolve only manifest-declared package names and publishers, x64 architecture,
framework type and minimum versions. Check the existing pinned Microsoft
root policy, code-signing and Store EKUs, RFC3161 message imprint, signed
block-map digest and every installed block-map file. Copy the selected
packages to owned snapshots and verify the copied bytes again before
emitting graph and class-registration artifacts. Framework verification
does not grant GamingApp signed-context eligibility.

Historical framework timestamp certificates have expired now. Validate the
TSA chain at the token's stated signing time, then require the CMS signature,
exclusive timestamp EKU, identical verified content and signature-value
message imprint. The stated time is not trusted before those checks succeed.
Do not disable chain verification, certificate time checks or future-time
rejection. Offline revocation and archive-only digest limitations remain
explicit.

The private bounded graph contains the root application followed by its
declared frameworks in manifest traversal order. Server-bound package
identity must match the graph root, and its host-registration bit must be
present. Environment input never creates package identity or signed trust.
Malformed, oversized, mismatched or unreadable supplied graphs fail instead
of silently falling back. Plain executable children do not gain this graph.

The diagnostic Wine patch adds graph directories to loader search paths
before ordinary directories. It implements bounded current-package graph
enumeration and package-path lookup. Head/direct filters are supported;
other filters return an explicit unsupported error. Package ID parsing uses
the existing basic full-name parser, not a complete Windows deployment
database.

Generate class registration only from the authenticated manifests, with
absolute snapshot DLL paths and manifest ThreadingModel values. Import it
only into the execution owner's fresh cell prefix. Classes repeated within
one package fail as ambiguous; the first declared framework wins across
packages, and shadowed declarations remain in evidence. This is an explicit
diagnostic ordering policy, not proof of every Windows dynamic dependency
ranking rule. Existing Wine apartment handling is not replaced.

The new `pkgactivate` channel emits one completed record per factory or
instance call: class, IID, HRESULT and local registry-key/server category.
The host collector retains only bounded public type-name/GUID shapes and
only records attributed to the authoritative CE child PID. Unparsed shapes
are redacted explicitly. Registry-key presence is not proof of a successfully
loaded server. Existing raw child output and XGAMERUNTIME text are never
persisted.

## Consequences

Actual retained verified versions are VCLibs 14.0.33519.0, UWPDesktop
14.0.33728.0, UI.Xaml 8.2501.31001.0 and WindowsAppRuntime 2.5.1.0.
Their signed block maps cover 13, 27, 6 and 298 files respectively, in addition
to the application's 946. UI.Xaml declares 137 classes; WindowsAppRuntime
declares 1009, of which 129 are shadowed in this explicit graph order.

WindowsAppRuntime's signed manifest references
`Microsoft.Web.WebView2.Core.dll`, but the retained package contains no such
file. This absent server is recorded, not fetched, synthesized or called
verified payload. Its authenticated manifest registration may exist, but
activation must still fail if that missing server is requested.

Source regressions and compilation are not Xbox activation acceptance.
The execution owner must run a new cell007 with its own fresh prefix and
return the completed factory records. No sign-in, XAML, Store service,
claims generator call or successful application handoff follows from this
source change alone.

The new sibling compiled x64 and i386 ntdll, kernelbase and combase and
staged only those six PE replacements onto the frozen package predecessor.
The v5 helper compiled against its exact import libraries. A scheduler-owned
windowless slot then exercised the actual installed graph enumeration,
head/direct filters, package-path queries and DLL search sentinel. The plain
process and ordinary executable child had no graph. The packaged fixture
exited with its expected 17 and emitted a completed class/IID/HRESULT record.
Its fixture intentionally lacked COM initialization, so the returned
`800401f0` demonstrates return-status capture, not class-not-registered
resolution. Class registration import and genuine Xbox activation remain
for cell007's owner.

The fixture finished in 9.07 seconds. Its owned server stopped and waited
with exit 0; prefix open-file inspection returned no files. The collector
still marked the inherited-stream post-exit drain incomplete and did not
infer why EOF was missing. These headless fixture assertions are distinct
from capture completeness and Xbox product acceptance.
