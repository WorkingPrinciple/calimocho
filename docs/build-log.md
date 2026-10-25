# calimocho — build log

Live notes from the build investigation. Will become structured docs once
the recipe is reliable.

## 2026-10-25: observed native factory matrix and supported-only011 recipe

Xbox0ab executed the owned810-class headless matrix against the retained
original16302bfe native XAML DLL. All810 unique rows and the summary completed
with exit0, no timeout and owned cleanup complete. There were558 genuine
DllGetActivationFactory plus IActivationFactory QueryInterface positives,
including FrameworkViewSource at index549. The remaining252 were not positive
under these probe conditions, not universally unsupported Windows classes.
Matrix mode called no ActivateInstance, Run, registration or window APIs.

The actual observation and fixed-field output were read and hash-checked:
`a6d66a55991c8afc2098dae0e0ca0c862872008b6fa9a4ef41f969fdc2f0c22b`
and `8d8cf60816703e6d169e2b6569ef0d2c8675ad83884d61079eb52c96ea678ca2`.
They live under `xbox-calimocho-xaml-factory-20261025-001/evidence` in
`xodus-runs`. The consumer reports original DLL identity unchanged before
and after,5.587 seconds elapsed, no input and no application activation.

ADR-0043's generator now derives011 from that complete observation. It imports
only558 supported classes mapped by the observed export to the actual XAML
DLL. The per-class decisions explicitly label the cross-build26300.9711 to
retained16302bfe evidence. Other DLLs are not redirected; Wine009
CoreApplication and CoreWindow remain unchanged. The new recipe reuses the
exact009 engine and010 native override, collector and180-second exit observer.
Its receipt hash is
`7c61c26de2fcbaf1814e09b1e2b91afd925f49c5f1827ae73b33fe44ac78a83c`.
All3915 deployed entries and individual registry assets were rechecked.
The receipt is with Xbox0ab;011 instance, activation and UI are unobserved.

## 2026-10-25: native XAML loader discriminator after actual009 handoff

Actual010 subsequently loaded native Windows.UI.Xaml.dll from the expected
prefix system32 path in AppL PID256. The Application factory returned S_OK.
The next requests for Windows.UI.Xaml.FrameworkViewSource returned CLASSNOTREG
for both its factory and RoActivateInstance, with registration absent.
The exact-image, admitted-token process observer recorded AppL exit3 through
a signaled process handle, separately from CE exit0. No activation callback
or window was observed.

The redacted010 evidence was read and hash-checked as
`53e6a14d60abb9ce0e65ce7e3a1b8efaf7f25a2a7888f6d77abf8f5698124415`
at `xbox-calimocho-packaged-20261025-010/evidence/activation-redacted.json`
under `xodus-runs`. Collection took4.084 seconds, not the180-second cap.
Its final two-second post-target-exit drain cutoff is explicitly truncated;
this does not invalidate the separately observed target exit.
An owned exact native factory probe now compiles without execution or
registration mutation. The next mapping must use actual native registration
and matching retained DLL evidence, not invent a replacement interface.

The actual009 redacted evidence was read and hash-checked as
`5b11eb94534ba745c2394e1a55f7105a51504674f4292d029d98fa6c853eb58b`
at `xbox-calimocho-packaged-20261025-009/evidence/activation-redacted.json`
under `xodus-runs`. Launcher started the observed `msxboxl` AppL target
PID256 with S_OK and native XboxPcApp.exe loaded. Its first captured factory
failure was Windows.UI.Xaml.Application, IID
`06499997-f7b4-45fe-b763-7577d1d3cb4a`, CLASS_E_CLASSNOTAVAILABLE with a
registered class. The loader explicitly reported builtin Windows.UI.Xaml.dll.
CE exit0 after124 milliseconds was not AppL exit. The60-second capture was
truncated, with no activation delivery or window facts.

ADR-0042 records the approved recipe-only correction. The retained002/003
override adds only `windows.ui.xaml=n`; their identical one-class imports
set only the Application DllPath. Both imports were read/hash-checked,
as was the retained original native DLL input16302bfe. No binary was copied,
rewritten or executed by this source lane. The next receipt keeps the exact
frozen009 engine, adds explicit per-prefix loader selection and uses a new
bounded AppL handle observer. Unknown module paths remain redacted.

## 2026-10-25: cell009 process-bound UWP and real CoreWindow candidate

Xbox0ab subsequently ran frozen008. Its redacted evidence was read and
SHA-256 checked as
`b7d167683392abaa26bc6da85b9fe5851af7335fa587caef574b7c2975ab6496`
at `xbox-calimocho-packaged-20261025-008/evidence/activation-redacted.json`
under the owner's `xodus-runs` directory. Actual CE activated both Uri and
Launcher successfully. The observed route was `msxboxl` to
`Microsoft.Xbox.AppL`, with child PID0 and E_NOTIMPL for
`uwp-protocol-activation`. The target did not start. This confirms the
factory fix and the next missing surface, not UWP or UI success.
CE exited0 after94 milliseconds. Capture ended at the post-exit drain limit,
with truncation explicitly true and XAML unknown. No full-trust/Tray route
or raw URI was observed. Xbox0ab reported owned-server cleanup complete and
is preparing frozen009 for the next authorized run.

ADR-0041 records the approved continuation after cell008's explicit UWP gap.
The new source carries a server-owned, process-only protocol record with the
real caller AppId and target identity. CoreApplication creates its view and
real hidden HWND, calls SetWindow and Load, queues Activated and enters Run.
The dispatcher delivers a genuine protocol or launch event during message
pumping. Activate shows the window; bounds, visibility, activation and size
events use that HWND. Unsupported queries report their first missing surface.

The isolated `package-uwp-01` source build completes and stages exactly six
changed files relative to frozen008: wineserver, Unix/PE ntdll, twinapi.appcore,
windows.ui and Launcher. The v7 bounded observer and owned HWND lifecycle
fixture compile without running either. A resumed stage retains its previous
unqualified installed tree and receipts. Frozen-output guards prevent a later
build or stage from changing the handoff.

A fresh retained snapshot passes the existing pinned-root signature,
timestamp, blockmap and four-framework checks. Its combined class import
includes442 authenticated main-package entries, with all server DLLs present.
This is an opt-in; older preparation and frozen007/008 remain unchanged.
The new collector tracks both public XAML basenames and limits window/event
facts to CE or an actual recorded handoff PID, retaining no URI or content.

Initial builds failed on missing installed-header registration, generated
server protocol, a no-op directory target, WinRT namespace settings and GUID
definitions. Those attempts remain retained. A separate reference increment
fix avoids a COM macro's repeated evaluation. The final build also includes
real asynchronous-action IDs and closed-state errors rather than fake values.

Native fixture execution, actual CE routing, process-bound event delivery,
window display and Xbox UI remain unobserved by this source lane. No game,
prefix or foreign process was started or changed for this build. Xbox0ab owns
the scheduled008/009 cell execution; source/build success is not UI evidence.

## 2026-10-25: truthful no-device GameInput sibling

ADR-0039 records the owner's Witcher input/haptics evidence and the exact
GameInput API gap. The new source implements separate typed v0/v1/v2
interfaces, initialization, empty reading/device results, managed callback
tokens, QPC timestamps and an empty dispatcher. It does not advertise a
physical device, guess a COM class ID or expand the AGS5.4 module to AGS6.

The isolated `metal-port-11e-gameinput-04` build replaces only the x64
GameInput DLL on a copy of frozen 11d. The retained receipt binds compiler,
Wine build tools, link archives, interface IDL, source and full inventory.
The expanded headless probe and all three source vtables compile with
warnings treated as errors. Host checks inspect the actual four PE exports,
native preference and single-file deployed difference.

The scheduler then granted a bounded windowless slot. Actual baseline
Create returned E_NOTIMPL, Initialize was absent and the probe exited1.
Actual candidate Create returned S_OK, Initialize was present and every
probe assertion passed, with zero callbacks and exit0. Baseline8.87 seconds
and candidate12.94 seconds stayed inside the slot. Only fresh owned prefixes
were initialized; no game or foreign Wine family was touched.

The first harness falsely required server-stop0 after natural process exit.
It retained the baseline observation and stopped before candidate execution.
The corrected harness ran only the candidate, without replaying baseline.
Both prefixes had stop1, wait0 and lsof1/empty. The slot was released directly
after cleanup. This is GameInput contract evidence, not Witcher acceptance.

The Witcher recipe embeds `gameinput=b;amd_ags_x64=n` after generic defaults,
retaining the owner's native AGS shim without installing or modifying it.
The full deployed audit and committed producer evidence are frozen separately
from the old unqualified registry. Frozen 11d and Xbox cell007 remain unchanged.

## 2026-10-25: opt-in Wine-built AGS5.4 sibling

ADR-0037 records the DIRT5 owner's source-bound native-AGS null-string path
and the minimal four-export builtin. Its API version is 5.4.1; driver and
software strings are empty, devices and extensions are zero. Standard D3D12
creation is forwarded unchanged, and device destruction releases one reference.
Native AGS remains preferred without the separate DIRT5/GPTK builtin override.

The source harness initially failed with the module absent, then passed.
The first real Wine PE compile exposed incompatible `config.h`/CRT headers
and a missing `stdarg.h`; those were corrected in the second isolated output.
`metal-port-11d-ags54-02` adds only the x64 AGS builtin and the two minidump
forwarders to a new copy of the frozen private-Metal base. Its registry is
explicitly unqualified and retains no inherited graphics/TLS acceptance.
The scheduler granted a windowless slot. The installed AGS/minidump probe
passed actual initialization, D3D12 device creation, destruction with zero
remaining references and both exact dbghelp forwarders. HTTPS returned200;
expired HTTPS produced expected12157/12037 rejection with validation enabled.
All three prefix servers were stopped/waited and open-file/process-group checks
were clean. Foreground, renderer payloads and baseline remained unchanged.

The first chain had completed AGS01 before a competing Forza server blocked
TLS02. Its retained receipt corrected an initial overly broad pre-spawn-refusal
report. After the scheduler cleared the lane, only TLS02/03 ran, not another
AGS replay. Graphics remains blocked by the non-overlap guard; no Dock
transparency exception, desktop control or DIRT5 title-screen claim was made.

The owner subsequently allowed ignoring exact Dock PID716/window33 for one
bounded 11d qualification. That opt-in exception is implemented and tested,
including wrong identity/layer and a second blocking window. Fresh native
geometry still had no free400x340 area because ordinary windows occupied the
remaining main-display space. The exception was not broadened and no graphics
probe was started. The scheduler received the current geometry blocker.

## 2026-10-25: bounded cell005 activation diagnostics

The Xbox owner's cell004 result was a zero helper exit without observed CE
or handoff telemetry. No XAML or sign-in success was inferred.
ADR-0036 adds actual creation parameters, suspended-child token metadata,
PID, resume/wait status, exit code and UTC times to a new v3 helper.
Its child-only process/loader trace is drained by a bounded redacting host
collector. Raw child output and XGAMERUNTIME traces are not persisted.

The helper compiled against the exact package candidate's import libraries.
Fresh headless fixture08 and fixture09 each passed all four cases. The
registered diagnostic observed creation/resume, authoritative token metadata,
21 process events, child exit 17 and matching exit/observation UTC. Different
images had no verified eligibility; guest spoofing remained rejected.
Both fixture servers were stopped and waited. No Xbox or game ran here.

The delivered cell004 engine, registry, helper and snapshot remain unchanged.
Cell005 uses a new helper and receipt with a fresh owned prefix; actual CE,
XAML and handoff outcomes await the Xbox owner's run.

The returned cell005 result now establishes CE PID240 creation/resume with
verified metadata, native CE loading and exit0 after about89ms. No XAML load
was observed. Capture stayed open until60s with only8756bytes, so missing
EOF, not the byte bound, made the result incomplete. Collector rc0 was a bug;
the next revision returns nonzero for incomplete capture, bounds post-exit
draining and preserves structured error/handoff facts without raw traces.

## 2026-10-25: explicit local package identity and installed verification

ADR-0035 records the opt-in package-identity delta. The isolated
`build/winehq-11.20/package-identity-01` builds wineserver, both ntdll PEs,
the ntdll Unix library and both kernelbase PEs together. Protocol version
965 prevents accidental use with the unchanged accepted server.
Patch 0006 applies to the exact port11 integration source; it does not
apply patch 0005. The included generated r5 header is unchanged.

The first configure attempt omitted private headers from `include/Makefile.in`.
The first compile attempts exposed misplaced server definitions, a missing
`stdarg.h` include and the generated table's intentional win64-only ABI.
Those were corrected without changing generated code. Both architectures
compile; i386 claims remain unsupported. No accepted engine was modified.

The first live fixture reached the plain-process checks but its activation
helper called Wine's unbounded `swprintf` with the C bounded signature.
Replacing that helper call with bounded-by-input string construction fixed
the fixture. The retained third run has explicit child success markers and
passes plain/registered identity, package ID allocation, sentinel/length
checks, token duplicate/close, a plain child without inherited registration,
and unsupported packaged claims with an unchanged sentinel.
Both fixture subprocesses exit zero. Its candidate-only server was stopped.
No Xbox or game was launched.

Twenty-seven focused source tests pass, including the installed block-map
tamper checks, wrong root, missing Store usage, unknown critical extension,
tampered timestamp imprint, wrong TSA chain and signer validation at genTime.
The crypto command error-path tests use mocks; the actual retained GamingApp
is the separate real-signature check.

The real package's code-signing leaf expired on October 17. Authenticated
RFC3161 verification establishes October 14 at epoch `1792002659`, so the
signing chain is checked at that time rather than disabling expiry checks.
Its signed AXBM matches. The first installed-content run failed because
`[Content_Types].xml` is absent. Signed AXCT:
`4c05e708e85fb6f685a2396e13047813fef21604e447a8006d3fa4c49d86a3e2`.
The owner then narrowed the installed-file policy: AXPC, AXCD and AXCT are
archive-only and explicitly unverified. The genuine package passes the
remaining policy, including signed AXCI, all 946 block-map files, no unlisted
executables, the matching publisher/family and full-trust manifest.
Revocation is not checked offline. The manifest is version 2609.1001.20.0,
not the VM observer's 2610.1001.20.0, and selects XboxPcAppCE.exe.

The final sibling adds a host-only startup registration record. It must
match identity and image path before the token receives verified eligibility.
Guest-supplied verified flags are rejected. The final native fixtures
`fixture-06-results.json` and `fixture-07-results.json` pass ordinary package
identity, synthetic host registration, a different image without eligibility
and guest spoof rejection (`c000000d`). The actual predicate and unchanged
generated table also pass the source-compiled context harness. No native
Xbox process ran in this session.

Local immutable evidence includes `staging-receipt.json`,
`fixture-03-results.json`, the later fixture receipts, and
`activation-cell004/verification.json` in that
candidate directory. This is not graphics/TLS qualification, S2 admission,
verified Store activation or Xbox compatibility.

## 2026-10-25: generated claims observer diagnostic

ADR-0034 records the corrected input and diagnostic-only boundary. An
isolated source/build/install at `claims-observer-r2-01` compiled the
unchanged generated source `88f34892` into x86_64 ntdll.
Actual ntdll SHA-256:
`6ec7ff267f173ed7dba1c27b3b920f2b3bfb98b9d8a873cfcedcd426b85f3c81`.
Every installed file and link matches the frozen private base except that
one PE. Wine and wineserver hashes remain unchanged.

The initial parity link failed because the copied ntdll import library
did not contain the new export. Explicitly rebuilding the candidate
import-library target corrected the link. The parity PE imports the
candidate export but has not been executed on the local ntdll.

The unqualified diagnostic registry SHA-256 is
`92d63416e3e83b93cf83be73452a9ed02deff312ba0818544cac7bcac0e9d913`.
Build receipt SHA-256:
`d710254c90f8366849a5dae1e44b6ca72254ccceba94a29736f84153319b69d5`.
The fresh cell003 binding capsule SHA-256 is
`e47c52849f059e5fd463e5c5515f717c53acfe9f2ffc03a1fc096b2d812c400d`.
These artifacts were sent directly to the Xbox owner and coordinator.
The capsule includes exact environment and app argv, not fresh-prefix
setup; the Xbox owner must adapt its existing owned launcher.

The sole operator subsequently supplied the actual Windows native and
generated parity receipts. Their hashes were authenticated:
collect `f409406904b22e8b1cd9ea82c2fcd61efdfe8fc2b8ec10994a2d14426ffd9946`,
exit confirmation
`632c323aa1876fccfa3402ed9a76b9ac81c808add1f62decaea3cf15be343f57`.
Native parity was 3/3 and generated parity 4/4 with no failures or guest
stderr. The first run omitted exit codes because of a batch bug; the
second recorded both zero exits with identical stdout hashes.
The authenticated supplement retains these limits without changing the
already handed-off build or registry hashes. This does not establish local
runtime parity or real claims support. No local Wine or Xbox launch was
performed.

## 2026-10-25: DIRT 5 minidump forwarding sibling

ADR-0033 records the loader failure and the source-built forwarding module.
The isolated `metal-port-11c-minidump-01` install copies the frozen private
performance install and adds only x86_64 and i386 minidump forwarders.
The builder compared every original file and symbolic link with the base
before and after copying. The frozen base remained unchanged.

Actual built x86_64 DLL SHA-256:
`c8df444b8c81f601f1a5bd0f5a8cb7060de245adbfdd5d7b7dd9e049ebd57a77`.
Actual built i386 DLL SHA-256:
`0d083b0c0e6852019a7aa95b60dff3765deaa2d5f8acc321de35c245dfdfd438`.
PE export inspection confirms both named forwards to dbghelp. The output
receipt retains source/tool/command hashes and the frozen performance
environment. No package-claims patch is included.

Status: built, not runtime-qualified or admitted. The coordinator granted
one exclusive five-cell interval. Its first Vulkan cell refused before
Wine spawn because no 400x340 region was free of foreign windows. The
main-display Dock window and second-display ChatGPT window covered both
displays. No guard exception or replay was used. The lane was returned.

Retained build receipt SHA-256:
`c36b4b732e9483e37b5ad15a50d5aa8eed943f0fac68deed513ec3e6bada8dc5`.
Retained preflight refusal SHA-256:
`f10dd60fd8dddcf132f29f298dc14f7b9c83d410f4a554eb49d513d86acf5212`.
No native test, new prefix, game launch or ready registry was produced.

## 2026-10-25: limited package claims source export

Owner-selected source-only work under ADR-0032 adds an opt-in patch against
WineHQ `7298a818b79446bae153b8d5aa27235ab3703bf9`:
`patches/wine/0005-query-package-claims-errors.patch`.
It clears optional attributes, validates the actual borrowed token and
propagates real token-query failures. Missing token security attributes
remain unsupported, never fabricated no-package or Store identity.

`tests/test_package_claims.py` exercises the actual patch function using a
mock query. This is not a runtime build, genuine local token observation,
package compatibility or Xbox acceptance. Selected source, accepted
installs, prefixes and registries remain unchanged.

## 2026-10-24: reactivated isolated source builds (REQ-69)

The owner reactivated source work under ADR-0022 and canonical COR-36.
No result below is a runtime/game qualification.

1. Verified official WineHQ 11.20 commit
   `7298a818b79446bae153b8d5aa27235ab3703bf9`, Git tree
   `c616492cbb57e71339abf5d67179d3073de9d1a2`. Normal x86_64 configure
   failed because x86_64 FreeType was absent. Native Homebrew FreeType
   is arm64, so it cannot fill that dependency.
2. One explicitly fontless server-only diagnostic compiled
   `server/wineserver`, SHA-256
   `fe00f03fc0c7548d715f33b6a2dcce337c0cd9281ac8e666599157fa630db5c6`.
   This cannot render a game and is not a candidate. No more features
   were disabled to manufacture a usable-engine result.
3. REQ-70 recommended a coherent CodeWeavers 26.3 graphics integration
   baseline before a measured forward port to current WineHQ.
   Rehashed archive:
   `ac99c8ca4b3848f3e81784135f023df266b61c2345726ea55a50b3e030dd6872`.
   Its Wine VERSION is 11.0. Its bundled FreeType configure/build failed
   because `subprojects/dlg` was missing. The failed tree is retained.
4. Built the complete official FreeType 2.13.3 release, archive SHA-256
   `0550350666d427c74daeb85d5ac7bb353acba5f76956395995311a9c6f063289`,
   with Apple clang targeting x86_64. Isolated `libfreetype.6.dylib`:
   `0232db652042c84271e1f07d463e9c93ffb5a758fdb32042a328d4eacf872d05`.
   Linkage is its local prefix plus system zlib/libSystem, no Intel
   Homebrew requirement. No global package was installed.
5. CW normal font-enabled configure succeeded. Initial macOS component
   compile failed at `win32u/vulkan.c:3009`: CW's Vulkan override used
   undefined `SONAME_LIBVULKAN` when configure found no Vulkan loader.
   Guarded that absent macro and kept explicit failure logging. This
   supplies no Vulkan implementation. First patch retry failed because
   the unified-diff hunk count was wrong; corrected it and retained
   that failed output too.
6. Fresh `build/cw26.3-candidate-03` configured and compiled the loader,
   server and macdrv in 28.879 seconds, with the donor's 192-byte
   callback and 120-byte legacy-window assertions enabled. Patch:
   `eaae968780854d6e2880408a3d94ab315a58ae91293216124ef10098d48e2c9c`.
   Pristine source-tree digest:
   `ca90321a6161104f0a1000579de0c214c3b820e51be4be1323b9cfee6da59b70`.
   Patched source-tree digest:
   `aa252d0c679a589c8a88f018229981c6452908fae159f18f75f794fc14292a67`.

| Component | Architecture | SHA-256 |
|---|---|---|
| loader/wine | x86_64 Mach-O | `9004950d1f1ae32471f89abe318eb6e451343e8af8cc46101de556570cdd3931` |
| server/wineserver | x86_64 Mach-O | `5c325eee6ae11dcd6fc23777db2f707434d1152da72484f70404d3081b209068` |
| winemac.so | x86_64 Mach-O | `dfc7982c3ce692ec9c4fe49e9ac54b5561a005e22ab6144623819bed4e295f03` |

All commands, logs, per-file identities and observed linkage remain in
local build receipts. The newer runner also resolves actual Xcode tools
with `xcrun`: `/usr/bin/clang` and `/usr/bin/make` are the same dispatch
shim on this host, so hashing only those paths does not identify the
actual compiler and make. Installed MinGW, bison, flex and SDK are recorded.

WineHQ 11.20's official tag was rechecked against WineHQ on this date:
`b117f32aada84ede119f6c5e7ec385f16315d6f6` remains the highest 11.x tag.
Its macdrv changed opaque types to typed Objective-C pointers, changed
client-surface construction and removed the old window pixel-format field.
The measured port must include callback transport, surface lifetime,
Cocoa layer presentation, PE-region notifications and calling-convention
adapters. Copying three D3DMetal source files is not sufficient.

The interrupted candidate-04 full `make -j4` log ends with `Wine build
complete.` The process ended before the runner could update its receipt,
which still reports the configure step as the latest recorded step. Its
completed artifacts were independently identified locally:

| Component | Architecture | SHA-256 |
|---|---|---|
| loader/wine | x86_64 Mach-O | `6b56c74fe6e3737dd2788bda6ce90af60600e77a5203de764c7501f263489c86` |
| wineserver | x86_64 Mach-O | `232b612bfd3d3bc4ca286dbc8950f4bc6695420e2ca02bca7cff6fe23f7930c0` |
| winemac.so | x86_64 Mach-O | `9b04588f045ee29939484a8bf5c9cdb810dd496d95ca737275b094e2ace47669` |
| ntdll.so | x86_64 Mach-O | `47f8c3083225d97dd0fd4a6bfea83d9c0853aa339b77a9f29ecd72ce95fa32e0` |
| win32u.so | x86_64 Mach-O | `84a74bbc49c9634b42a79dc380fd014aa06140ac03a8ed3419b10636bf805827` |
| ntdll.dll | x86_64 PE | `b97a66687729651747746842a9d59175250ba328ee9a0461e95c92507d294476` |
| kernel32.dll | x86_64 PE | `0cd806ea70a4e0d9853c638fb8ef050357bc349cc6acc786a8f629eed729b371` |
| winemac.drv | x86_64 PE | `c34597b9bdf58195ec6d80df82c6ac70a33d92d9198c20f6653a89b03b0d0acf` |
| wineboot.exe | x86_64 PE | `7bf584797d9376e5ab0198f01bcee3c7cef163fcd64b97652f473bf926eedc88` |

This is a full source compile, not an installed or executed runtime.
No Apple payload was copied and no Wine executable was launched.

The first measured WineHQ 11.20 forward-port applies the CW bridge and its
coupled seams to a fresh source snapshot. Three early compile attempts
exposed and corrected ObjC header contamination, missing WinReg declarations,
and private `RegCloseKey` name conflicts. The next bounded candidate compiled
the x86_64 loader/server/macdrv/ntdll/win32u plus x86_64 ntdll, kernel32 and
winemac PE modules. Receipt:
`build/winehq-11.20/metal-port-05/receipt.json`.
The patched source tree SHA-256 is
`72ee65e26bfa957b8217c5c20bc66542b591d19b82be750bfeba011505293960`;
the port transformer SHA-256 is
`24566527dcba1a46b5cad2763695c622f40e9f6bb36a97c15c6344e155356c27`.
The receipt binds the 19 edited upstream files and nine x86_64 ms-ABI
wrappers to public CW donor-file digests. The copied D3DMetal code remains
guarded to x86_64, matching the inspected Apple bridge architecture.

Public DXMT source was checked as a separate potential DX11 route. Its README
describes Direct3D 10/11 translation; the LGPL-2.1-or-later license is
present in its main branch. The observed upstream main revision is
`a148782d431249405acdb1531dbb0c7e737bbece`; the Sikarugir mirror main
revision is `50102f994b406f58f56d5d09f2ad20f9b90390a2`. Neither DXMT revision
was built. It is not a DX12 option and is not a qualified candidate.

The latest-Wine full build in `build/winehq-11.20/metal-port-06/` completed
configure and `make -j4` with exit code 0. The initial post-build verifier
then failed because it expected an i386 `wineboot.exe`; this configured
build produces `wineboot.exe` only for x86_64. The verifier's manifest now
requires the observed x86_64 `wineboot.exe`, both architecture variants of
`cmd.exe`, and the selected x86_64/i386 runtime modules. All 14 expected
nonempty files were independently found and hashed in the unchanged build
tree. This is complete source compilation, not a runtime startup/self-check.

| Component | Architecture | SHA-256 |
|---|---|---|
| loader/wine | x86_64 Mach-O | `5e6e04322ae5c42bf704ff74f9c45263d76410e8ee80ab709aedaae89df7e54b` |
| wineserver | x86_64 Mach-O | `704425b1692335692475758236af3192b5e268e8cd92a066997233f757b3461f` |
| winemac.so | x86_64 Mach-O | `9809f7533bcc162a76fa883ee948c80e158a6215d99b5ad8aeabde2be5cc884a` |
| ntdll.so | x86_64 Mach-O | `e4f5eb509d705dac64006fb53c89dba654359a58b976617c34ac733aa5805249` |
| win32u.so | x86_64 Mach-O | `316d5741f2a3d663a138b4ba1c50e0bffbfc5f0f07d62598267ac4c02f688698` |
| ntdll.dll | x86_64 PE | `2e7463c162fae037844166247df9367c6e27bb4f9a12e07f15c6f85be736b857` |
| kernel32.dll | x86_64 PE | `2bffa00abf00463c674ccda57cf48d8124bbdbf9778e89707ea6566c2395ae2e` |
| winemac.drv | x86_64 PE | `eb4c1e0362395c5302dd528fe31eb8d167d8bb98aecf27eedff7564ad85406fc` |
| cmd.exe | x86_64 PE | `69bcf5b6b41bfcccc96ed11c821750e82d84dc04a4c4cfd6aa8044696b8c6178` |
| ntdll.dll | i386 PE | `f456dd8356a09b3036fc4f23b64e2b232544d6878dec076a0913cc1bd348b5eb` |
| kernel32.dll | i386 PE | `99b166fd89c662d450f476b2e11ab73393f8555e600e951ada42693d9c325829` |
| winemac.drv | i386 PE | `b9c15f48cd0560e70a3d70a7c340bc10555fe31c328fb2b58dd854d965d74d9c` |
| cmd.exe | i386 PE | `785dd3c4ca50bf97207b2a81d68111f111cfb0369e95286d9f42182d3f9d471a` |
| wineboot.exe | x86_64 PE | `d7fcd1d7c7e6ccab4bc913c87d3a3c85e90109a2a6a337653aa60ae815aa1314` |

The local receipt retains source, transformation, toolchain, command, log,
linkage and artifact identities. DX11 and DX12 may have separate runtime
records. The 11.20 port does not depend on DX11 parity or on the retired
D3D11 override shim.

An isolated built-in startup self-check then used a fresh prefix at
`build/winehq-11.20/metal-port-06/startup-self-check/prefix`. The build-tree
Wine frontend ran the built x86_64 `wineboot.exe --init` with a 180-second
timeout. The only injected Wine variables selected this build's prefix,
loader, server and DLL directory; `HOME` and temporary files were redirected
under the same private build output. No D3DMetal or `DYLD_*` variable and no
Apple payload were supplied. `wineboot` created `system.reg` with
`#arch=win64`, but did not exit before timeout. The subsequent `cmd /c ver`
and registry query were therefore not run.

The first diagnostic was `Wine cannot find the FreeType font library`.
Configure had found `libfreetype.6.dylib`, but this run did not provide a
runtime search path for the isolated FreeType prefix. Source inspection
confirmed that `win32u` calls `dlopen(SONAME_LIBFREETYPE, RTLD_NOW)` and the
build defines that soname as the bare name `libfreetype.6.dylib`.

A second attempt used a new prefix at
`build/winehq-11.20/metal-port-06/startup-self-check-02/prefix`. Before
launch, `lipo -archs` confirmed the isolated pinned FreeType library was
x86_64. The environment matched the first attempt, with
`DYLD_FALLBACK_LIBRARY_PATH` set to the FreeType prefix's `lib` directory
followed by `/usr/lib`. The FreeType diagnostic did not recur, but
`wineboot --init` again timed out after 180 seconds. The first error in the
new log reports that Wine was built without Vulkan support; subsequent
errors report COM/RpcSs startup failures and setupapi `copy error 1812`
copying `wineusb.inf`. The command did create `system.reg` with
`#arch=win64`. Since initialization timed out, `cmd /c ver` and the
registry query were not run.

The timed-out wineboot process was terminated within its tracked process
group. The exact build wineserver was then invoked with `-k` and the new
`WINEPREFIX`; it exited 0. The local receipt reports no residual PIDs.
The partial prefix and logs remain in the ignored build tree for diagnosis:

| Evidence | Result |
|---|---|
| wineboot | timed out after 180 seconds; process exit `-15` after targeted termination |
| wineserver `-k` | exit 0 |
| residual tracked processes | none |
| wineboot stderr SHA-256 | `d5745579d420b864904a6f4371221b5e115873d274a0510607ba15071d42fc47` |
| wineboot stdout SHA-256 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| local self-check receipt SHA-256 | `5f03516fc381bf87831f1a58dd91c142a7f8ead5cbad09e93b0444d2a271c133` |

This is a failed startup self-check, not a usable-runtime result. No game
was launched and no existing prefix or save was touched.

For the second attempt, process-group termination and prefix-scoped
`wineserver -k` also completed successfully, with no residual build
processes. Its stderr SHA-256 is
`66e2b150203304b3f6dc6f181ba3b9434ad5f9f5857e5f4fb5d169992c1ab184`;
the ignored local receipt SHA-256 is
`01d02ff3c35168cfee8de47d2b5b46dd164be0ce4360fcf275a9ed2eecc198d5`.
The local receipt records the exact environment, executable and FreeType
hashes, command result, prefix files, and cleanup result. This retry
confirms the missing FreeType lookup diagnostic is addressed by the
explicit isolated search path, but does not establish successful startup.

A preliminary third harness attempt started `wineboot` in a separate new
prefix but was interrupted by a harness polling error before its configured
300-second deadline; it is not counted as a startup result. The wineserver
was stopped for that prefix, and its partial prefix and logs remain in the
ignored build tree. The receipt marks this as `harness-aborted`.

The next fresh-prefix attempt used
`build/winehq-11.20/metal-port-06/startup-self-check-04/prefix` and the same
isolated x86_64 FreeType search path, with
`WINEDLLOVERRIDES=mscoree,mshtml=` to suppress Mono/Gecko installer
overrides. `wineboot --init` exited 0 in 7.645 seconds. The `ps` snapshot
at 60 seconds for its tracked process group was empty because initialization
had already exited. The follow-up `cmd /c ver` and built-in registry query
also exited 0, reporting `Microsoft Windows 10.0.19045` and registry
`CurrentVersion` `6.3`. `system.reg` contains `#arch=win64`. The Wineboot
log still contains Vulkan-unavailable, COM/RpcSs, setupapi, and
winegstreamer diagnostics; these did not prevent this built-in check from
completing and do not establish graphics or game support. Prefix-scoped
`wineserver -k` exited 0 and no residual build processes remained.

| Evidence | Result |
|---|---|
| FreeType architecture | x86_64 |
| wineboot | exit 0 in 7.645 seconds |
| `cmd /c ver` | exit 0; `Microsoft Windows 10.0.19045` |
| registry query | exit 0; `CurrentVersion` is `6.3` |
| process group at 60 seconds | empty |
| `wineserver -k` | exit 0 |
| residual build processes | none |
| Wineboot stderr SHA-256 | `ee83e022a47470ca1e490e098026e8a85f09eb7f7641feea917fb0010b2d3950` |
| `cmd /c ver` stdout SHA-256 | `07496cbba7bef678e6732b1552fda0cc41494da42c30c49400c7a502499a9b3e` |
| registry stdout SHA-256 | `c7f9e2e888b34b5b7f94623f12c1f3e8fae23a88466ec7d12298032e2346a8b7` |
| local self-check receipt SHA-256 | `6ee189bcd1b7f57ea6ae27f6d55776c31026294537ae42c72c268961312b98be` |

The passing receipt records the exact FreeType path/hash and environment.
The runtime recipe uses the selected registry record's
`DYLD_FALLBACK_LIBRARY_PATH`; the exporter preserves that value and does
not take it from the ambient shell environment. A regression test covers
this boundary. This is startup evidence only, not a graphics or game
qualification.

Known unresolved features include GnuTLS/schannel, Vulkan/MoltenVK and
GStreamer. Wine was executed only for the isolated startup check above.
At the time of that self-check, no Apple payload had been executed or copied.
The later read-only GPTK PE probe is recorded below. No existing runtime,
prefix, save or account was modified. Current-Wine integration, Apple ABI
compatibility, isolated runtime startup and actual Xbox DX12 gameplay remain
open.

## 2026-10-24: GPTK D3D12 device probe (REQ-69)

The first graphics attempt loaded Wine's `d3d12.dll` and `dxgi.dll` from
`C:\windows\system32`; it did not exercise the installed GPTK PE files.
`WINEDLLPATH` supplies Wine's Unix/builtin search paths. In this Wine source,
`WINEDLLDIR0` is consulted by the builtin fallback search, not the native
load-order search. Both attempts and their logs remain in the ignored build
tree.

A third fresh prefix,
`build/winehq-11.20/metal-port-06/startup-gfx-03/prefix`, used a private
application directory containing copies of only the Wine-built test
executables and symlinks to the installed GPTK `d3d12.dll`, `dxgi.dll`, and
`d3d12core.dll`.
The Apple files were not copied or modified. The Wine loader mapped the
`d3d12.dll` and `dxgi.dll` files from those app-local links; its `loaddll`
trace labels them `builtin`, consistent with the Wine-built PE metadata in
the GPTK files. Their mapped paths and hashes match the installed redist.
`d3d12core.dll` was not observed loading. Wine also loaded
`libd3dshared.dylib` and reported support for non-native code regions.
The environment used `WINEARCH=win64`, the isolated FreeType fallback,
`WINEDLLPATH` for the candidate's builtin modules,
`WINEDLLOVERRIDES=mscoree,mshtml=;d3d12,dxgi,d3d12core=n,b`, and
`CX_APPLEGPTK_LIBD3DSHARED_PATH` pointing at the installed bridge. The
ignored local receipt records the complete environment.

The isolated first call to `D3D12CreateDevice` returned `0x80004005`
(`E_FAIL`). Wine's conformance executable exited 0, but executed only 3
tests and skipped 9 device-dependent tests because device creation failed;
this is not a graphics pass. The 192-byte `macdrv_functions_t` assertion
was present in the compiled object, but the runtime callback path was not
independently exercised. No game was launched.

| Evidence | Result |
|---|---|
| Wine source commit / patched tree SHA-256 | `7298a818b79446bae153b8d5aa27235ab3703bf9` / `72ee65e26bfa957b8217c5c20bc66542b591d19b82be750bfeba011505293960` |
| Wineboot | exit 0 in 5.648 seconds |
| Wineboot stderr SHA-256 | `482de9ac74aeebabb5041c3c76a504bd102c4bd4726765d32c0e5892984c0579` |
| First `D3D12CreateDevice` call | `0x80004005` (`E_FAIL`); probe exit 1 |
| Direct probe stdout / stderr SHA-256 | `f978a10864383f32b30a7f703874dd07846a5a65e5e0721d0b2b282944e65aec` / `00f2077bf9a12ab51d2016444425eb32adb6eacd2e04debb8e13c1fa773b43eb` |
| GPTK `d3d12.dll` SHA-256 | `02aa673497ff8694b41f976e194a920468e54897f3546ed1cd4c1b3a97179735` |
| GPTK `dxgi.dll` SHA-256 | `124015390b8527033bcd6e65af6376fde8fb3923450b63a9dbe0bbef05e63f10` |
| GPTK `d3d12core.dll` SHA-256 | `1034f5989c8c69496add15f79c04e56ae47cdf2a861098e8b4323bc8835b9e29` |
| `libd3dshared.dylib` SHA-256 / signature | `e985a9e0b9807856018ee63ac40de3b3baaca7c33568f672d80d89934fbc41f1`; verification passed |
| 192-byte callback ABI object SHA-256 | `d7d793f4424c2a4fc9f6d45a8a6aa958c9dcbe8c161ceeb60d5e09935241c1f8` |
| D3D12 conformance | exit 0; 3 executed, 9 skipped, 0 assertion failures; device-dependent coverage not reached |
| Test stdout / stderr SHA-256 | `71386958820b0080d02aabc7670b1e2c73d3c90e5d6068af818d66441f976ced` / `044dab1be79e2835bbbc51c77bc0e4d350336edcff218b7e2fab4ed0caf76985` |
| Prefix-scoped `wineserver -k` / residual processes | exit 0 / none |
| GPTK payload hashes before and after | unchanged |
| Local receipt SHA-256 | `9eb9479cdf279efeabf3c61a8a0458d69616277c75aa19c2c1c7fe5b43b60613` |
| Local receipt | `build/winehq-11.20/metal-port-06/startup-gfx-03/receipt.json` (ignored) |

The receipt records the isolated environment, exact command results, output
hashes and prefix. The E_FAIL is the current blocker; this result does not
establish whether the limitation is Wine's renderer integration, adapter
creation, or game compatibility.

### startup-gfx-04: redist-first builtin search

A fourth fresh prefix used the installed GPTK `redist/lib/wine` first in
`WINEDLLPATH`, the requested builtin overrides for D3D12/DXGI, and
`CX_APPLEGPTK_LIBD3DSHARED_PATH`. Wineboot exited 0 in 5.657 seconds. The
probe still loaded Wine's `C:\windows\system32\d3d12.dll` and `dxgi.dll` as
builtins, with no GPTK Unix-module load evidence. The installed GPTK
`x86_64-unix/{d3d12,d3d12core,dxgi}.so` paths are symlinks to the same
`libd3dshared.dylib`; their presence in `WINEDLLPATH` does not by itself
prove those Unix modules were selected.

This is explained by the Wine 11.20 loader source: builtin lookup checks
`WINEBUILDDIR/dlls/<module>/x86_64-windows` before iterating the directories
from `WINEDLLPATH`. The candidate build contains its own `d3d12.dll`,
`d3d12core.dll`, and `dxgi.dll` in those builtin directories. Redist-first
`WINEDLLPATH` therefore did not select the GPTK PE/Unix pair. The trace
instead shows Wine's builtin `vulkan-1.dll` and `winevulkan.dll` loading,
followed by `vkd3d` reporting `Unhandled VkResult -3`. `libd3dshared.dylib`
also loaded, but the D3D12 probe did not establish entry into GPTK's D3D12
path.

`D3D12CreateDevice` returned `0x80004005` (`E_FAIL`). The conformance
executable exited 0 with 3 tests executed and 9 skipped because device
creation failed; this is not a pass. The 192-byte macdrv callback ABI
assertion is compiled but was not exercised by this runtime path. The fresh
prefix was shut down with its prefix-scoped `wineserver -k`; no residual
build processes remained. GPTK files were not copied or modified, and their
hashes were unchanged. No game was launched.

| Evidence | Result |
|---|---|
| Attempt / local receipt | `startup-gfx-04`; `build/winehq-11.20/metal-port-06/startup-gfx-04/receipt.json` (ignored) |
| Wine source commit / patched tree SHA-256 | `7298a818b79446bae153b8d5aa27235ab3703bf9` / `72ee65e26bfa957b8217c5c20bc66542b591d19b82be750bfeba011505293960` |
| Wineboot | exit 0 in 5.657 seconds |
| Wineboot stderr SHA-256 | `47adc10aa5829a54c38854708a450fd45ae8a248b7da5cb7b461e6386720e193` |
| First `D3D12CreateDevice` call | `0x80004005` (`E_FAIL`); probe exit 1 |
| Direct probe stdout / stderr SHA-256 | `f978a10864383f32b30a7f703874dd07846a5a65e5e0721d0b2b282944e65aec` / `22b9437f149bc639bd133c48a9a27fd6138d88052c55244e534d409b5e31cfc7` |
| GPTK `d3d12.dll` / `dxgi.dll` / `d3d12core.dll` SHA-256 | `02aa673497ff8694b41f976e194a920468e54897f3546ed1cd4c1b3a97179735` / `124015390b8527033bcd6e65af6376fde8fb3923450b63a9dbe0bbef05e63f10` / `1034f5989c8c69496add15f79c04e56ae47cdf2a861098e8b4323bc8835b9e29` |
| `libd3dshared.dylib` SHA-256 / signature | `e985a9e0b9807856018ee63ac40de3b3baaca7c33568f672d80d89934fbc41f1`; verification passed |
| D3D12 conformance | exit 0; 3 executed, 9 skipped, 0 assertion failures; device-dependent coverage not reached |
| Test stdout / stderr SHA-256 | `71386958820b0080d02aabc7670b1e2c73d3c90e5d6068af818d66441f976ced` / `8ca2582f9e1488f4a649661534bbbf8691d90620035a4a87e7d50309994108c1` |
| Prefix-scoped `wineserver -k` / residual processes | exit 0 / none |
| GPTK payload hashes before and after | unchanged |
| Local receipt SHA-256 | `abf97d88ce46bb620b6c939038d0e76bf53117703ddb5da2219449d9781c1604` |

This attempt identifies a loader/build-layout blocker, not a GPTK
compatibility verdict. The next discriminator must select matching GPTK PE
and Unix modules without modifying the installed payload; do not repeat
redist-first `WINEDLLPATH` alone.

### startup-gfx-05: isolated installed-module layout

The WineHQ 11.20 build was installed with `make -j4 install` into a fresh
research-owned prefix. The install's five x86_64 Wine PE modules
(`d3d10.dll`, `d3d11.dll`, `d3d12.dll`, `d3d12core.dll`, and `dxgi.dll`)
were moved into `install/research-wine-originals/` and retained. Their
installed paths and the corresponding x86_64 Unix-module paths were then
symlinked to the installed GPTK redist. `install/lib/external` was also
symlinked to the redist's `lib/external`. No GPTK file was copied, modified,
or re-signed. The probe environment had no `WINEBUILDDIR` or `WINEDLLPATH`,
so this run used the installed `bin/wine` without the build-tree module
precedence seen in startup-gfx-04.

The fresh prefix initialized successfully, and Wine's load trace reported
the D3D12, DXGI, and D3D12Core PE modules as builtins. The direct D3D12
probe then faulted on a null read at `00007FF8183B31E3`, started WineDbg,
and timed out after 60 seconds before reporting a `D3D12CreateDevice`
HRESULT. The D3D12 conformance command exited 5 without a test summary.
There was no `vulkan-1.dll` or `vkd3d` evidence in either graphics-command
log; WineVulkan appeared during wineboot only. The logs did not establish
that GPTK's Unix modules or `libd3dshared.dylib` loaded, so this is not a
D3DMetal-path or compatibility pass. The observed page fault is the first
graphics error; its origin is not established by this probe.

| Evidence | Result |
|---|---|
| Attempt / local receipt | `startup-gfx-05`; `build/winehq-11.20/metal-port-06/startup-gfx-05/receipt.json` (ignored) |
| Wine source commit / patched tree SHA-256 | `7298a818b79446bae153b8d5aa27235ab3703bf9` / `72ee65e26bfa957b8217c5c20bc66542b591d19b82be750bfeba011505293960` |
| Installed Wine version | `wine-11.20` |
| Wineboot | exit 0 in 10.677 seconds |
| Wineboot stderr SHA-256 | `0a99d77fbee9734e18272bd924b870195b2b439ba7a2cae8c7ad48f117045bf5` |
| First D3D12 probe | timed out at 60 seconds after null-read page fault; no HRESULT |
| Probe stdout / stderr SHA-256 | `264825d7b30134af2d05da580c485ecca4550a323166e446cd944e2f49157007` / `ac1d4d66272c5fc2b18934c36e747a3b9af34b5f1c603f69f36313b76f037dd0` |
| D3D12 conformance | exit 5; no stdout or test summary |
| Test stdout / stderr SHA-256 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` / `1e7de8dafb5beb5e89c2925c520cac6367de0cd49f17a2b78a3d1e46ab26f6bd` |
| Prefix-scoped `wineserver -k` / residual isolated Wine processes | exit 0 / none |
| GPTK payload hashes before and after | unchanged; all module, bridge, and framework hashes are in the ignored receipt |
| Local receipt SHA-256 | `6fe481b93f01579d55618c6727aa77a1c9fd344dfda40143d400bc844856b0f1` |

This layout removed build-tree precedence and avoided Vulkan/vkd3d in the
graphics probe, but neither a D3D12 device result nor GPTK Unix-module load
was established. Preserve the crash logs and do not treat conformance exit
5 as a test pass.

### startup-gfx-06: symbolized WineHQ fault and GPTK control

Both graphics runs used the same probe executable and tracing channels,
with separate fresh prefixes and no game. The first GPTK-control attempt
omitted the `mscoree,mshtml=` override. Wineboot reached `mscoree.dll` and
`appwiz.cpl` before timing out. This is consistent with the Wine Mono/Gecko
setup path, but the attempt did not reach graphics and is not used as the
control result. The corrected control added the suppression override and
completed startup.

The WineHQ 11.20 installed-layout run reached the same D3D12 probe but
faulted before returning an HRESULT. `atos` maps the faulting instruction
to `pthread_setname_np + 51` in `libsystem_pthread.dylib`. The exception
was a null read, with `RDI=0x5`. `RDX` and `R14` point inside
`libd3dshared.dylib`, but do not identify a caller or symbol. WineDbg
attached and printed only that it had attached; no call stack was captured.
The 192-byte `macdrv_functions_t` compile-time assertion passed in the
build, but runtime callback-table use before the fault is not established.

The corrected GPTK 4.0b3 control returned `S_OK` from
`D3D12CreateDevice` using the same probe. The loaded GPTK D3D12 PE hash
matches the installed redist. The runtime `d3d12.so` symlink resolves to
the mapped `libd3dshared.dylib`, and `D3DMetal.framework` is mapped. The
graphics probe log contains no Vulkan or vkd3d traces. Wineboot separately
loaded and unloaded `winevulkan.dll`; those setup messages are not evidence
that the graphics probe used Vulkan. This validates the probe's control
path, but device creation alone does not demonstrate rendered output or
game compatibility. The contrast isolates a WineHQ 11.20 integration
failure; it does not identify the caller of `pthread_setname_np` or prove
the exact root cause.

| Evidence | Result |
|---|---|
| Attempts / local receipts | `startup-gfx-06` and `startup-gfx-06-control-02`; ignored receipts under `build/winehq-11.20/metal-port-06/` |
| Wine source commit / patched tree SHA-256 | `7298a818b79446bae153b8d5aa27235ab3703bf9` / `72ee65e26bfa957b8217c5c20bc66542b591d19b82be750bfeba011505293960` |
| Shared probe SHA-256 | `60267fbfbfd1db1deee301f296036d40cf5d4fd93c5b821583b04023fcbcb363` |
| WineHQ run A | Wineboot and AeDebug setup succeeded; probe timed out after the fault with no HRESULT |
| A fault symbol / registers | `libsystem_pthread.dylib: pthread_setname_np + 51`; null read, `RDI=0x5`; `RDX`/`R14` map inside `libd3dshared.dylib` |
| A probe stdout / stderr SHA-256 | `7240c2ac19c18dae3215461f0e4d3fdf1ebbef87b1a229454e9bdd7350dcfa7b` / `94de99dd84ca119de99ab65cfc1e1e0a3166df9e4a63a545b96c4673b116a5d3` |
| GPTK control B | Wineboot exit 0 in 4.644 seconds; probe exit 0 in 43.796 seconds; first `D3D12CreateDevice` HRESULT `0x00000000` (`S_OK`) |
| B probe stdout / stderr SHA-256 | `7aa18ce0f09191e261141580ffc54afc5efecee4f1410440e27306df5bb8521f` / `02b628e22176898f5685303021c991c5af27b849095bb349aa04e0d2a3953afd` |
| GPTK `d3d12.dll` / `d3d12core.dll` / `dxgi.dll` SHA-256 | `02aa673497ff8694b41f976e194a920468e54897f3546ed1cd4c1b3a97179735` / `1034f5989c8c69496add15f79c04e56ae47cdf2a861098e8b4323bc8835b9e29` / `124015390b8527033bcd6e65af6376fde8fb3923450b63a9dbe0bbef05e63f10` |
| `libd3dshared.dylib` / D3DMetal binary SHA-256 | `e985a9e0b9807856018ee63ac40de3b3baaca7c33568f672d80d89934fbc41f1` / `b16aab78127dcf6dbbaba4cfaf8120b96c90ee7b31a48be8599847932a4931e1` |
| GPTK payloads before and after / cleanup | Hashes unchanged; prefix-scoped `wineserver -k` and `-w` succeeded for B; no residual process matched either fresh prefix |
| Probe interpretation | The GPTK control proves D3D12 device creation on the control runtime, not a draw/readback or game pass |
| Local receipt SHA-256 (A / B) | `5c10bb30bb520d56eda4013e386bf6a7f645973c75ccc2dc885692255435e330` / `e35da8a1344fda6661092097805b570b52223e6ed9b7196528d679ffc09e81b3` |

No Apple payload was copied or changed. No game was launched.

## 2026-05-31 — Session 1: discovery + planning

### What we learned
- Whisky ships **Wine 7.7 + GPTK 1.1** (April 2023). Archived May 2025.
- Whisky's WhiskyWine CDN (`data.getwhisky.app`) is **dead (HTTP 404)**.
  Mirror via Wayback at `https://web.archive.org/web/20250824114303if_/https://data.getwhisky.app/Wine/Libraries.tar.gz`.
- Steam's current client uses **CEF/Chromium 128+** — needs syscalls only
  Wine 9+ provides. `steamwebhelper.exe` crashes on Whisky's Wine 7.7 with
  `LdrInitializeThunk ... status 80000003`.
- GPTK 3.0-3 (Apple, March 2026) still bundles **Wine 7.7**. Apple has
  never updated Wine. So GPTK 3 alone doesn't fix Steam.
- gcenx publishes upstream **Wine 11.9 staging** as a standalone tarball
  for macOS — works at the binary level but lacks CodeWeavers' macdrv
  patches → Steam UI renders as a **black window** (no chrome drawn).
- CodeWeavers publishes their full LGPL-compliant Wine source at
  `media.codeweavers.com/pub/crossover/source/crossover-sources-26.1.0.tar.gz`
  (142 MB). Confirmed Wine 11.0 + ~38 macdrv files with CW-specific patches.

### Path chosen
Build CodeWeavers-patched Wine 11 from source, overlay GPTK 3 D3DMetal
libraries, drop into Whisky's `Libraries/` folder.

### Next
- Toolchain: brew install bison@2.7 flex mingw-w64 gnutls freetype sdl2
  gstreamer pkg-config
- `./configure --enable-win64 --disable-tests --without-x` etc. for Apple
  Silicon
- Build, copy `wine64`, `wineserver`, `lib/wine/x86_64-{unix,windows}/`
  into Whisky's tree
- Overlay GPTK 3's `lib/external/{D3DMetal.framework, libd3dshared.dylib}`
- Verify Steam UI renders, then test SN2 launch

### Open risks
- The CW source includes vkd3d, dxvk, gstreamer, moltenvk — may need to
  build all of them or use system equivalents
- GPTK 3 D3DMetal was built against Wine 7's d3d12 stub ABI; Wine 11
  refactored this — may need a Wine 7-compatible d3d12.dll shim
- ANGLE / swiftshader interaction inside CEF is what makes Steam render
  on CrossOver; the patches that handle this may be in dlls/win32u or
  user32 rather than macdrv

## To be continued...

## 2026-05-31 / 2026-06-01 — Session 2: Phase 1 engine, end to end

### Outcome

Phase 1 acceptance closed. A1.1, A1.2, A1.3, A1.5 PASS. A1.4 deferred
(Steam install is Phase 2/3 scope — requires the wizard's "Install
Steam" step which doesn't exist yet). A1.6 = this entry.

Engine artifact: `out/engine/` — x86_64 Mach-O Wine 11.0, ad-hoc
signed, runs under Rosetta 2 on Apple Silicon. ~140 MB.

### Scripts written

- `scripts/fetch-sources.sh`        — sha256-pinned curl of CodeWeavers Wine 11 tarball
- `scripts/prep-build-deps.sh`      — Rosetta 2 + x86_64 Homebrew + brew deps
- `scripts/patch-sources.sh`        — applies `patches/wine/*.patch`
- `scripts/fixup-config-h.sh`       — post-configure patches to `include/config.h`
- `scripts/build-wine.sh`           — configure + make + install + stage to `out/engine`
- `scripts/overlay-gptk.sh`         — copies Apple GPTK D3DMetal into out/engine/lib/external
- `scripts/sign-engine.sh`          — adhoc sign every Mach-O with Wine entitlements
- `scripts/verify-no-copied-binaries.sh` — A1.5 enforcement (AGENTS rule #1)
- `scripts/test-engine.sh`          — runs A1.1, A1.2, A1.3, A1.5 in sequence

### Patches kept (in `patches/wine/`)

- `0003-rename-wineloader-id.patch` — see ADR-0009. Replaces
  `com.codeweavers.CrossOver.wineloader` bundle id with
  `app.calimocho.wineloader`. Required for AGENTS rule #3
  (don't impersonate CodeWeavers' code-signing identity).

### Patches dropped

- `0001-winemac-metallayer-arm64.patch` — only needed for native arm64
  build; ADR-0010 pivoted to x86_64.
- `0002-d3dmetal-arm64-stub.patch` — same reason.

### Errors encountered and fixed (chronological)

1. **`make: bison: invalid directive: %code`** — Apple's system bison
   is 2.3 (2008). Wine's `parser.y` needs bison ≥ 3. Fix: prepend
   `/opt/homebrew/opt/bison/bin` to PATH (later replaced by
   `/usr/local/opt/bison/bin` once we pivoted to x86_64).

2. **`include/config.h` missing `HAVE_SYS_STAT_H` etc.** — Autoconf
   2.72's autoheader stopped emitting `#define` stubs for the C99
   standard headers. CodeWeavers' `dlls/ntdll/unix/msync.c` wraps
   `#include <sys/stat.h>` in `#ifdef HAVE_SYS_STAT_H`, so
   `struct stat` becomes undefined. Same script also force-defines
   `SONAME_LIBVULKAN="libMoltenVK.dylib"` because
   `dlls/win32u/vulkan.c` references it unconditionally even with
   `--without-vulkan`. Fix: `scripts/fixup-config-h.sh`, run after
   configure.

3. **Native arm64 Wine: `WineMetalLayer` undeclared on arm64** —
   declared in `d3dmetal_objc.h` under `#if defined(__x86_64__)`.
   Patched with arm64 guard. Eventually superseded by ADR-0010.

4. **Native arm64 Wine: linker missing
   `_macdrv_client_surface_presented`** — defined in `d3dmetal.c`
   under the same `#if __x86_64__`. Patched arm64 stub. Eventually
   superseded by ADR-0010.

5. **Native arm64 Wine: every spawned wine subprocess killed by
   `AppleSystemPolicy`** — kernel log: `ASP: Security policy would
   not allow process: .../lib/wine/aarch64-unix/wine`. Hours of
   investigation: ruled out signature, entitlements, hardened runtime,
   bundle identifier, path, quarantine xattrs. Survey of Whisky's
   bundled Wine 11.9-staging, CrossOver, GPTK, gcenx confirmed **no
   shipping Wine-on-Mac stack is native arm64**. ADR-0010 pivots to
   x86_64 + Rosetta 2 (what every working stack does).

6. **x86_64 build: configure errors `libgnutls 64-bit dev files not
   found`** — arm64 Homebrew at `/opt/homebrew` is arm64-only;
   x86_64 build can't link against it. Fix: install x86_64 Homebrew
   at `/usr/local/` (under Rosetta), install the same brew formulae
   in the x86_64 keg. `scripts/prep-build-deps.sh` does this.

7. **x86_64 build: configure error `FreeType 64-bit dev files not
   found`** — Wine probes some headers (`ft2build.h`, sdl2) by
   direct compile rather than pkg-config. Fix: set
   `CPPFLAGS=-I/usr/local/include
   -I/usr/local/opt/freetype/include/freetype2 …` and
   `LDFLAGS=-L/usr/local/lib` for the configure run.

8. **A1.3 runtime: "Wine cannot find the FreeType font library"** —
   Wine `dlopen`s libfreetype by SONAME (`libfreetype.6.dylib`) at
   runtime; default dyld search path doesn't include `/usr/local/lib`
   from Rosetta processes. Fix: set
   `DYLD_FALLBACK_LIBRARY_PATH=/usr/local/lib:/usr/lib` when invoking
   `bin/wine`. Long-term Phase 2: bundle libfreetype + friends into
   `out/engine/lib/external/`.

9. **A1.2 first run: "Wine Mono Installer" dialog blocks
   non-interactively** — Wine prompts on first init of a new prefix
   to download Mono and Gecko. Calimocho's scope doesn't include
   .NET-based Windows apps. Fix: set
   `WINEDLLOVERRIDES=mscoree,mshtml=` so Wine skips both prompts.
   Baked into `scripts/test-engine.sh`.

10. **A1.2 spurious "exit=0 in 6s, system.reg missing"** — a leftover
    `wineserver` from an interrupted prior run was answering the new
    wineboot request without doing real work. Fix: `scripts/test-engine.sh`
    now kills stale wineservers before A1.2 and waits up to 60s for
    `system.reg` to appear after wineboot returns (Rosetta filesystem
    latency).

### Configure flags (final, x86_64)

```bash
./configure
  --prefix=$BUILD_DIR/_install
  --enable-archs=x86_64,i386
  --without-x --disable-tests --with-mingw --with-gnutls
  --without-gstreamer --without-cms --without-coreaudio
  --without-fontconfig --without-pcap --without-vulkan
  --without-vkd3d --without-opencl
```

Run via `arch -x86_64`. Environment: brew bison/flex first in PATH,
`/usr/local/bin` (x86 brew) before `/usr/bin`, `PKG_CONFIG_*` pointing
at `/usr/local/lib/pkgconfig`, `CPPFLAGS`/`LDFLAGS` set for the
header probes.

### Build durations (10-core M1 Max)

| Build | Wall time | Notes |
|---|---|---|
| native arm64 (rejected, ADR-0010) | ~6 min | the build that the OS won't let you run |
| x86_64 under Rosetta | ~20 min | what we ship |
| x86_64 incremental (cached) | <1 min | for iteration |

### What was NOT done in Phase 1 (per scope)

- No GUI / no Calimocho.app (Phase 2)
- No DMG (Phase 4)
- No CI (Phase 5)
- No bundled libfreetype/libgnutls/etc. (Phase 2 — currently relies on
  the x86_64 brew at /usr/local; will be embedded under
  `out/engine/lib/external/` for distribution)
- A1.4 Steam login deferred — requires the Phase 2 first-run wizard's
  "Install Steam" flow; will be retested when that exists. Engine is
  ready to run Steam once a prefix has Steam installed in it.

### Files committed (Phase 1)

- `docs/ADR/0009-rename-wineloader-id.md`
- `docs/ADR/0010-host-arch-x86_64-rosetta.md`
- `docs/ADR/0001-bundle-codeweavers-wine.md` (cross-link to 0010)
- `docs/ARCHITECTURE.md` (Layer 2 x86_64 note + Rosetta failure mode)
- `docs/SPECS.md` (A1 preconditions + x86_64 file layout)
- `docs/PHASES.md` (Phase 1 status table → DONE)
- `patches/wine/0003-rename-wineloader-id.patch`
- `scripts/wine-entitlements.plist`
- `scripts/*.sh` (the 9 scripts listed above)

## 2026-06-01 — CW HACK 22434 discovered: CEF GPU crash root cause

Adversarial investigation against installed CrossOver 26.5 to determine
whether the Steam black-screen issue was (a) a missing config in our
build or (b) held-back patches in the LGPL release.

Result: **(a) — a missing env var, not held-back patches.**

- `strings(1)` on CrossOver's `ntdll.so` revealed `CX_APPLEGPTK_LIBD3DSHARED_PATH`
- Same string appears in our compiled `ntdll.so` (proves the patch is in the LGPL release)
- Wine source `dlls/ntdll/unix/loader.c:1303-1352` (CW HACK 22434) +
  `dlls/ntdll/unix/unix_private.h:600-624` (CX Hack 23015) read this env var to
  hook D3DMetal's ms_abi callbacks
- Without the env var, asm trampolines unconditionally use sysv calling convention
  → register corruption when D3DMetal calls back into wine
  → CEF GPU subprocess STATUS_BREAKPOINT (0xC0000005)
  → 6+ crashes → CEF disables GPU → black window

Fix: `export CX_APPLEGPTK_LIBD3DSHARED_PATH=$ENGINE/lib/external/libd3dshared.dylib`
in `bin/calimocho-wine`. Documented in [ADR-0013](ADR/0013-cw-hack-22434-d3dshared-env.md).

Also discovered three operational gaps:
1. `scripts/sign-engine.sh` had never been run after the Wine 11 full-features
   rebuild — every Mach-O in the engine was unsigned, blocking dylib loads
   under macOS hardened runtime
2. `cp` of `libd3dshared.dylib` from `/Applications/Game Porting Toolkit.app/`
   propagates `com.apple.quarantine` xattr; needs `xattr -c` after copy or
   `cp -X` to skip xattrs
3. `bin/calimocho-wine` in the repo and `out/engine/bin/calimocho-wine` are
   separate files — must be sync'd after every edit (build-app.sh handles this
   via rsync but ad-hoc edits don't)

Verification:
- Before fix: 6+ `exit_code=-2147483645` per launch, `variations_crash_streak=6`
- After fix: 0 crashes, GPU subprocess stays alive, GPU not disabled by CEF

Remaining (NOT this ADR's scope): ANGLE's D3D11 init still fails
(`Renderer11.cpp:1108 Error querying driver version from DXGI Adapter`)
causing fallback to GLES 2.0, which is below CEF compositor minimum, so the
window paints but renders black. Investigating whether DXVK overrides are
actually applying or if wined3d's DXGI shim needs additional config.

## 2026-06-01 (cont'd) — Adversarial investigation vs Porting Kit + CrossOver

After the CW HACK fix eliminated GPU subprocess crashes, ANGLE still
failed `Renderer11::populateRenderer11DeviceCaps` with the DXVK route
and CEF fell back to GLES 2.0 → window painted but rendered black.

Tested four configurations against the same Wine 11 build:

| Config | GPU crashes | ANGLE D3D11 | Window |
|---|---|---|---|
| DXVK (`d3d11,dxgi=n`), no registry tweaks | 0 | NVIDIA 8800 GTX (wrong) | black |
| Builtin (`d3d11,dxgi=b`) + DXVK DLLs removed | 9 | n/a (crashed) | black |
| DXVK + PK registry config (`csmt=1, renderer=gl`) | 6 | NVIDIA 8800 GTX | black |
| DXVK + PK registry + `renderer=vulkan` | **0** | **Apple M1 Max (correct)** | black |

The `Wine\Direct3D\renderer=vulkan` registry setting flips wined3d's
backend from OpenGL ES (which Apple deprecated and never updated past
GL 4.1 on M-series) to Vulkan (MoltenVK → Metal). With `renderer=vulkan`
ANGLE correctly reports the M1 Max as the D3D11 adapter and GPU process
stays alive across the full Steam boot.

**Remaining issue**: window is now in the macOS accessibility tree at
the right size (705x440), GPU subprocess survives, ANGLE reports a
working D3D11 device — but the macOS window stays solid black. This is
a separate winemac.drv ↔ wined3d swap-chain composition issue, not the
original GPU crash. The render target gets written but never composited
to the NSWindow's Metal layer.

Findings on PK/CX comparison:
- PK ships **gcenx's wine-private wined3d-based d3d11.dll** in the
  bottle (sourced from an upstream local build tree),
  NOT real DXVK. It's the same wined3d code as our Wine 11 builtin.
- PK wraps wine with `wineskinlauncher` (Wineskin) which sets
  `MVK_ALLOW_METAL_FENCES=1`, `MVK_CONFIG_VK_SEMAPHORE_SUPPORT_STYLE=
  ..._SINGLE_QUEUE`, plus `D3DMETALPATH` to a bundled D3DMetal copy.
- CX deletes WINEDLLOVERRIDES entirely (defaults to builtin) and uses
  the CW HACK 22434 path with its proprietary wine-11.0-8720 commits
  ahead of upstream.
- Neither sets anything we haven't now tried. The remaining gap is in
  Wine 11 vs Wine 10's winemac.drv composition path, not in registry
  or env config.

**Honest assessment**: Without weeks of clean-room reverse engineering
on either CX's 8,720 unpublished commits OR a fix from upstream
WineHQ for the winemac.drv regression, calimocho cannot match
CrossOver/PK rendering on this hardware. Phase 2 SHOULD ship without
working Steam UI rendering and mark A1.4/A2.4 as KNOWN BLOCKER pending
upstream Wine 11+ winemac.drv fixes.

## 2026-06-01 (audit 4) — D3DMetal integration audit; design lands in ADR-0015

Senior-engineer-style audit before writing any shim code, motivated
by the concern that earlier scope estimates were anchored on
assumptions, not data.

Tools used: `nm -gU`, `otool -l`, Python `struct` for PE parsing,
`capstone` for x86_64 disassembly (installed via Homebrew + venv),
manual grep of wine 11 source.

### Surprising finding

CodeWeavers' LGPL release of wine 11 already ships
`dlls/winemac.drv/d3dmetal.c` (436 lines) plus
`d3dmetal_objc.{h,m}`. These provide a `DECLSPEC_EXPORT` callback
table (`macdrv_functions`, 192 bytes, 24 entries) that
`D3DMetal.framework` calls back into via `GetMacDRVFunctions()` in
`libd3dshared.dylib`. Three out of four pieces of the integration
chain are therefore already built into every calimocho engine
bundle today.

The missing piece is the **PE side** of `d3d11.dll`: a thin shim
that funnels Microsoft D3D11 entry points (CEF's input) into
D3DMetal's matching exports. ADR-0015 details the design.

### Confidence findings

- Apple's compiled `d3d11.dll` has **only 3 exports**. PE export
  table read directly via Python.
- `.text` is **662 bytes** total. Disassembled via capstone; every
  export is a near-identical ~30-byte dispatcher matching wine's
  `__wine_unix_call(handle, code, args)` pattern.
- D3DMetal's `D3D11CreateDevice` prologue spills XMM6-XMM15 and
  reads R9 → **compiled with `__attribute__((ms_abi))`** → calls
  from a PE shim work directly without per-method vtable thunks.
- Our `winemac.so` already exports `_macdrv_functions` —
  `nm -gU` confirms.
- Our `libd3dshared.dylib` exports `GetMacDRVFunctions()` —
  `nm -g` confirms.

### Scope, with confidence

| Component | Lines | New / modified |
|---|---|---|
| d3d11 PE shim | ~150 | new file |
| d3d11 ELF unix lib | ~120 | new file |
| d3d11 private header | ~80 | new file |
| d3d11 Makefile.in | 4 | modified |
| d3d11_main.c | 2 | modified |
| dxgi same trio | ~250 | new + modified |

Total: ~600 lines of new C, plus 6 lines of modifications. Packaged
as two patches in `patches/wine/`.

### Packaging decision

Patches (vs vendored fork submodule): patches win at this scope.
Three patches don't justify a 500 MB submodule. Documented in
ADR-0015.

### Testing strategy

Three tiers planned (Tier 1 unit on D3D11CreateDevice round-trip,
Tier 2 swap chain Present(), Tier 3 visual NCC on Steam UI).
Defined in ADR-0015 §Testing strategy.

## 2026-06-01 — ADR-0015 implementation: shim built, Tier 1 PASSES

Following the audit (ADR-0015), implemented the D3DMetal-forwarding
shim per design:

- `patches/wine/files/d3d11/d3d11_d3dmetal.c` (PE side, 158 lines)
- `patches/wine/files/d3d11/d3d11_d3dmetal_unix.c` (ELF unixlib, 369 lines)
- `patches/wine/files/d3d11/d3d11_d3dmetal_private.h` (shared types, 89 lines)
- `patches/wine/0004-d3d11-d3dmetal-shim.patch` (wine source integration, 65 lines)
- `tests/d3d11_shim/test_d3dmetal_shim.c` (Tier 1 unit test, 83 lines)
- Updated `scripts/patch-sources.sh` to sync `patches/wine/files/` into wine tree

**Tier 1 unit test PASSES:** standalone test EXE successfully:
- Loaded our shim
- dlopen'd `D3DMetal.framework`
- Called `D3D11CreateDevice` and got `S_OK` back
- Received valid `ID3D11Device*` with feature_level 0xb000 (FL 11.0)
- AddRef/Release vtable methods round-trip correctly

This proves the architectural design works: PE ms_abi shim → wine
unixlib dispatcher → ELF sysv_abi → ms_abi-typed function pointer →
D3DMetal.framework → real M1 Max D3D11 device.

**Steam-specific integration is INCOMPLETE.** Standalone test passes
but Steam still crashes the GPU subprocess 9 times. The
file-based shim log (`~/Library/Logs/Calimocho/d3d11-shim.log`,
opt-in via `CALIMOCHO_D3D11_DEBUG=1`) stays empty during Steam
launches, indicating Steam's CEF subprocess never reaches our
`D3D11CreateDevice` interceptor. Hypothesis: CEF spawns its GPU
helper via a path that bypasses the `WINEDLLOVERRIDES` we set, OR
CEF crashes earlier in its loader before reaching d3d11.dll. Needs
further investigation:

1. Trace which `d3d11.dll` Steam actually loads (`WINEDEBUG=+module`
   in a freshly-killed bottle)
2. Check whether CEF's separate prefetch_2 GPU helper process
   reaches the shim init
3. Consider per-app override `AppDefaults\\steamwebhelper.exe`
4. Run Tier 2 test (HWND + swap chain + Present) to bisect
   "shim works in isolation" vs "shim fails when given a real
   Win32 window"

This is now a Steam/CEF integration debugging problem, not a shim
design problem. The shim itself is sound.

## 2026-06-01 (cont'd) — Phase 3 session 1: shim reach confirmed, dxgi gap identified

Continuing on branch `phase3-cef-integration`. Two root causes
found and one fixed; the remaining one documented in ADR-0016.

### Why the shim log was empty during Steam runs

`bin/calimocho-wine` defaulted `WINEDLLOVERRIDES` to
`d3d11,dxgi=n` (native = DXVK), explicitly disabling our builtin
shim. The comment in the file documented prior experiments that
predated the shim and were never revisited. Tier-1 unit test
passed in isolation only because tests were run by hand with
`=b` set in the environment.

Fix: flipped default to `d3d11,dxgi=b` in `bin/calimocho-wine`
and synced to `out/engine/bin/calimocho-wine`. Users who want
DXVK again can `WINEDLLOVERRIDES=...d3d11,dxgi=n calimocho-wine`.

### Second issue: Wine 11 builtin loader requires the file to exist in the prefix

Even with `=b`, Wine 11 refused to load `d3d11.dll` if the bottle's
`drive_c/windows/system32/d3d11.dll` was missing (or moved aside).
Error: `Library d3d11.dll ... not found, status c0000135`. Wine's
builtin loader still does the prefix-side filesystem probe before
falling back to the engine's `lib/wine/x86_64-windows/`.

Fix: copy `d3d11.dll` + `dxgi.dll` from
`out/engine/lib/wine/{x86_64,i386}-windows/` into
bottle's `system32`/`syswow64` when preparing the prefix.

After both fixes, Tier-1 test PASSES via `bin/calimocho-wine`
(rc=0, hr=S_OK, FL 11.0 device, shim log populated).

### Steam launch with the fix: ENTER but no RETURN

Shim log under Steam load (CEF GPU subprocess):

```text
init: ready (CreateDevice=0x215355ea8, ...)
create_device: ENTER adapter=0x2b95e0 driver_type=0 flags=0x0
                levels_count=5 sdk_version=7
(no RETURN line)
```

ENTER count: 1. RETURN count: 0. **D3DMetal is reached but never
returns.** Adapter pointer is non-NULL (CEF's ANGLE enumerated it
via `IDXGIFactory1::EnumAdapters1` first) and driver_type=UNKNOWN
(per Microsoft docs, required when adapter != NULL).

Tier-1 worked because it passes `adapter=NULL, driver_type=HARDWARE`
— D3DMetal allocates its own adapter internally. With a wined3d-
backed adapter pointer handed in from wine's builtin `dxgi.dll`,
D3DMetal can't dereference it (different vtable / different
private layout) and faults.

CEF's next log lines confirm the user-visible symptom one layer up:

```text
EGL Driver message (Critical) eglInitialize: No available renderers
eglInitialize D3D11 failed with error EGL_NOT_INITIALIZED
EGL Driver message (Error) eglCreateContext: Requested GLES version
                                              (3.0) > max (2,0)
```

CEF falls back to GLES 2.0 → compositor disabled → black window.

### Decision

Documented in ADR-0016: implement the dxgi.dll D3DMetal shim that
ADR-0015's audit table planned (~250 lines, "dxgi same trio") but
the first pass skipped. The d3d11 shim alone is insufficient; the
adapter pointer must originate from D3DMetal end-to-end.

### Files changed this session

- `bin/calimocho-wine`: default override flipped to `=b`
- `out/engine/bin/calimocho-wine`: synced
- `docs/ADR/0016-dxgi-shim-required-for-cef.md`: new
- `docs/build-log.md`: this entry

## 2026-06-01 (cont'd) — Phase 3 session 2: four-experiment falsification round

Ran four diagnostic experiments before committing to ADR-0016's
direction. Each either falsifies a hypothesis or narrows the cause.

### Experiment B: env propagation

Added env probe + `dlopen(..., RTLD_NOLOAD)` for libd3dshared at
shim init. In Steam's CEF GPU subprocess (pid 58358):

```text
init: pid=58358 ppid=1 CX_APPLEGPTK_LIBD3DSHARED_PATH=...libd3dshared.dylib
init: libd3dshared already-loaded probe handle=0x77a380
```

Env propagates. libd3dshared is loaded. **CW HACK 22434 wiring is
intact in the subprocess.** Falsified.

### Experiment A: FORCE_NULL_ADAPTER

Shim override that substitutes `(NULL, HARDWARE)` for the caller's
`(adapter, driver_type)`. With it set, D3DMetal CreateDevice
returns hr=S_OK FL 11.1 device in 391ms.

But Steam still goes black with a NEW error one layer up:

```text
SwapChain11.cpp:636 Could not create additional swap chains, HRESULT: 0x887A0004
eglCreateWindowSurface failed with error EGL_BAD_ALLOC
```

DXGI swap chain creation against a D3DMetal device fails because
wine's builtin `dxgi.dll` doesn't recognize it. The whole
**D3D11+DXGI stack must be coherent**.

### Experiment: Apple's complete drop-in (deep dive per request)

Replaced our half-shim with Apple's GPTK `d3d11.dll` + `dxgi.dll`
+ `d3d11.so` + `dxgi.so` + Apple's `libd3dshared.dylib` +
Apple-signed `D3DMetal.framework`.

Key layout discovery: Apple's `d3d11.so`, `dxgi.so`, `d3d10.so`,
`d3d12.so` are all **symlinks to one file**:
`lib/external/libd3dshared.dylib`. First attempt copied them as
regular files; `@loader_path` then pointed at the wrong directory
and D3DMetal couldn't resolve. After redoing with symlinks:

- 0 "Failed to dlopen D3DMetal" assertions (was 3 per launch)
- D3DMetal loads cleanly from `@rpath/D3DMetal.framework/D3DMetal`
- Steam still black, with new error:

```text
ERROR:gpu_process_host.cc(1002) GPU process exited unexpectedly:
                                 exit_code=-1073741819
```

`0xC0000005` = STATUS_ACCESS_VIOLATION. Apple's libd3dshared was
built against CodeWeavers' Wine 7.7 ntdll trampoline layout. Our
Wine 11 has the equivalent functions (env var is set, trampolines
present) but the ABI offsets/layouts have drifted enough that the
ms_abi callbacks corrupt memory rather than landing where
libd3dshared expects.

**Apple drop-in not viable** without a matching CodeWeavers Wine 7.7
runtime — which would mean shipping a 3-year-old Wine and giving up
all the CEF/Steam fixes Wine 11 has. Not an acceptable trade.

### Verdict

ADR-0016 stands: build our own dxgi.dll D3DMetal shim symmetric to
the d3d11 shim. It's the only path that:

1. Routes adapter pointers through D3DMetal end-to-end
2. Stays on our own Wine 11 ntdll trampolines (CW HACK 22434 wired
   to our binary, not Apple's)
3. Is maintainable across CodeWeavers source rebases without
   pulling 3-year-old binaries

### Engine reset

Restored our calimocho-shim baseline (`d3d11.dll`+`dxgi.dll` PE +
`d3d11.so` ELF). Removed experimental symlinks and Apple PE
copies. Re-signed. Bottle's `system32`/`syswow64` still have our
shim DLLs copied from the engine.

### Files changed this session 2

- `patches/wine/files/d3d11/d3d11_d3dmetal_unix.c`: added env
  probe (Experiment B) and FORCE_NULL_ADAPTER override
  (Experiment A) for production use as diagnostic levers
- `docs/ADR/0016-dxgi-shim-required-for-cef.md`: extended with
  four-experiment evidence chain

## 2026-06-01 (cont'd) — Phase 3 session 3: Tests D + E + PK reality check

### Test D — Steam CEF with GPU disabled

Hypothesis: Steam CEF has a CPU/SwiftShader fallback that
bypasses our D3D11 path entirely.

Three flag variants attempted: `-cef-disable-d3d11`,
`-cef-disable-gpu`, `-cef-force-d3d9`, `-cef-force-software`,
also `WINEDLLOVERRIDES=d3d11,dxgi=` to disable both.

Bootstrap log shows Steam **received** the flags
(`Steam Client launched with: ... -cef-disable-d3d11 -cef-disable-gpu`)
but webhelper still spawns `--type=gpu-process` and CEF still
tries D3D11. None of those flags actually proxy through to
steamwebhelper's CEF command line.

Disabling DLLs entirely produces 6+ GPU process crashes
(`exit_code=-2147483645`); CEF has no usable SwiftShader fallback
in Steam's build. **Test D: no escape via flags.**

### Test E — SN2 shipping exe directly, bypassing Steam UI

Hypothesis: SN2 talks D3D11 directly (not through CEF). If our
shim works for direct D3D11 callers (Tier-1 passes), SN2 might
play even if Steam UI is black.

Launched
`Subnautica2/Binaries/Win64/Subnautica2-Win64-Shipping.exe`
directly from CrossOver's existing SN2 install via our
calimocho-wine. MoltenVK created `WineMetalView` swap chain
images at 705×440. Shim log:

```text
create_device: ENTER adapter=0x2fa2b0 driver_type=0
                levels_count=5 sdk_version=7
create_device: about to call D3DMetal CreateDevice@0x2159bfea8
                adapter=0x2fa2b0 driver=0
(no RETURN line)
```

**Same failure mode as Steam.** D3DMetal hangs on the non-NULL
wined3d-backed adapter pointer. SN2 in `Subnautica2.exe` launcher
exits silently. **Test E: SN2 alone doesn't escape the shim
problem.** Strong reinforcement of ADR-0016 — adapter coherence
is required end-to-end for both CEF and UE5.

### PK reality check — measured 2026-06-01

User pointed out two PK Steambuild apps are installed locally.
We measured both — and this changes the strategic picture.

**Steambuild 32 64bit DXVK.app:**

```text
Wine version:          10.0 Sikarugir  (gcenx-built, not Wine 11)
bottle d3d11.dll:      3.9 MB, strings: "DXVK adapter", "DxvkCommandList"
                       = DXVK 2.x PE binaries (MIT FOSS, not D3DMetal)
bottle dxgi.dll:       237 KB, DXVK companion
DLL override:          *d3d11=native,builtin  (DXVK wins)
Info.plist envs:       D3DMETAL=0 D3DMETAL_FORCE=0 MOLTENVKCX=1
                       VK_ICD_FILENAMES=/opt/homebrew/opt/molten-vk/.../MoltenVK_icd.json
                       VKD3D_CONFIG=force_static_cbv VKD3D_FEATURE_LEVEL=12_2
Registry [Software\Wine\Direct3D]:
                       csmt=1, renderer="gl", VideoMemorySize=65536
lib/external/:         (no D3DMetal.framework, no libd3dshared.dylib)
```

**Steambuild 32 64bit Direct3D.app:**

Similar but `D3DMETAL_FORCE=1`. Two PK variants representing the
two routes: DXVK (FOSS, default) and D3DMetal (proprietary, alt).

**Live test:** Launched the DXVK variant. Steam UI rendered
correctly. User confirmed: their login active, SN2 already
appears installed. No GPU process crashes. No black window.

### What this corrects

ADR-0015's audit (session 1) claimed "most of the integration
chain is already in CodeWeavers' source" and chose D3DMetal-
forwarding as the obvious path. The premise was unmeasured: I
assumed every working macOS Wine stack used D3DMetal, because
CrossOver's `d3d11.so` ships under that name and Apple's GPTK
ships D3DMetal too.

The measured reality:

- **PK uses DXVK 2.x, not D3DMetal.** Wine 10, not Wine 11.
- **No CW HACK 22434 env var.** No libd3dshared. No D3DMetal load.
- **It just works** on this exact hardware running today's
  macOS and today's Steam.
- The only entrants we know that *require* D3DMetal are
  CrossOver (proprietary) and PK's "Direct3D" variant (which is
  optional). Whisky used Wine 7 + D3DMetal and is too old. GPTK
  is Wine 7 + D3DMetal and CEF needs Wine 9+, so GPTK alone
  doesn't work for Steam either.

So calimocho's whole D3DMetal direction was built on a wrong
premise about what "the FOSS Mac Wine ecosystem" actually does.
The right answer is **DXVK + Wine 10 + MoltenVK**, not
**Wine 11 + D3DMetal shim**.

### Decision

ADR-0018 (proposed) documents the pivot: drop D3DMetal shim work,
adopt PK-style stack. Open question gating acceptance: does PK +
SN2 recipe (vcrun2022 + UE4SS proxy + Sentry hack + AVX + Win11)
actually run SN2 in-game, or does PK get stuck at the same wall
beyond Steam UI?

**Next test (continuing this session):** symlink CrossOver's
existing SN2 install into PK's bottle (no 15 GB redownload),
run PK winetricks vcrun2022, launch SN2 via PK Steam, observe.

### Files changed this session 3

- `docs/ADR/0018-pivot-to-dxvk-wine10-foss-stack-proposal.md`: new (Proposed status)
- `docs/build-log.md`: this entry

## 2026-06-01 (cont'd) — Phase 3 session 4: PK SN2 tests close the question

### Symlinked CrossOver's SN2 install into PK bottles

15 GB SN2 install lives at
`~/Library/Application Support/CrossOver/Bottles/Steam/.../Subnautica2`.
PK bottles symlink it in to avoid redownload. Test only; both PK
bottles restored to original state at session end.

### Test E.1 — SN2 via PK DXVK variant (vkd3d-proton + MoltenVK)

Launched Steam UI → Library → SN2 Play. SN2 launched
(vcrun runtime present), reached RHI init, then:

```text
LogRHI: Using Default RHI: D3D12
LogRHI: Using Highest Feature Level of D3D12: SM6
LogD3D12RHI: D3D12CreateDevice failed with code 0x80070057  (E_INVALIDARG)
LogD3D12RHI: Failed to choose a D3D12 Adapter
LogD3D12RHI: Adapter was not found
LogRHI: RHI D3D12 is not supported on your system
Message dialog: "DirectX 12 is not supported on your system."
HandleUnsupportedRHI.D3D12 -> RequestExitWithStatus(1)
```

Then UE5 CrashReportClient popped up. Confirmed via screenshot
that **regular Win32 desktop windows render correctly under
PK** — the black-window class is D3D11/CEF-specific, not a
Wine-level rendering bug.

### Test E.2 — `-dx11` override

UE5 normally accepts `-dx11` to force the D3D11 RHI. SN2 shipping
build crashed instead with:

```text
Fatal error: Unable to launch with RHI 'D3D11' since the project
is not configured to support it.
```

**SN2's UE5 build was packaged without the D3D11 RHI module**.
There is no client-side workaround; SN2 is D3D12-only on Windows.

### Test E.3 — SN2 via PK Direct3D variant (Apple D3DMetal d3d12)

PK ships a second app ("Steambuild 32 64bit Direct3D") that sets
`D3DMETAL_FORCE=1`. This routes D3D12 through Apple's
D3DMetal.framework instead of vkd3d-proton. Bypassed Steam's vcrun
prompt by launching `Subnautica2-Win64-Shipping.exe` directly via
the bottle's wine64.

```text
LogD3D12RHI: D3D12CreateDevice failed with code 0x80004005  (E_FAIL)
LogD3D12RHI: DirectX Agility SDK runtime not found
LogD3D12RHI: Failed to choose a D3D12 Adapter
LogRHI: RHI D3D12 is not supported on your system
```

Different error code (E_FAIL vs E_INVALIDARG) confirms the
D3DMetal path was taken, but D3DMetal's d3d12 implementation
also can't produce an adapter that satisfies UE5/SM6.

### Verdict: SN2 on M1 Max via any FOSS-or-FOSS-adjacent stack

| Stack | Steam UI | SN2 in-game |
|---|---|---|
| CrossOver 26 (proprietary `d3d12.so`) | works | works (with recipe) |
| PK DXVK + vkd3d-proton + MoltenVK | works | D3D12 0x80070057 |
| PK Direct3D + Apple D3DMetal | works | D3D12 0x80004005 |
| calimocho any tested config | black | not reached |

**No FOSS-only path on M1 Max produces a D3D12 adapter that UE5
SM6 accepts today.** CrossOver does something proprietary in their
`d3d12.so` that nobody in the public FOSS ecosystem has reproduced.

### What this splits the project into

**P1 — Steam UI (achievable today via DXVK pivot):**

PK proves Wine 10 + DXVK 2.x + MoltenVK + `renderer=gl` renders
Steam UI on this hardware. Calimocho can adopt this for the
engine layer. ADR-0018 (Proposed) is the pivot blueprint for
this layer; it would close SPECS A1.4 / A2.4 / Issue #4 for the
Steam-browsing experience.

**P2 — SN2 in-game (upstream-blocked, ADR-0017 known-blocker):**

D3D12 on Apple Silicon for UE5 SM6 games is not solved outside
CrossOver. Not narrowly leadable per ADR-0017 — this is upstream
vkd3d-proton + MoltenVK work, beyond a Phase 3 calimocho task.

### Honesty per AGENTS rule #4

A calimocho that closes P1 but not P2 ships "you can see your
Steam library, but you can't play the game" — which the README
decision table can honestly state ("for SN2 itself, buy
CrossOver"). That is the ADR-0017 known-blocker form of honesty.
Whether to ship P1 alone is a separate strategic call (in
discussion).

### Files changed this session 4

- `docs/build-log.md`: this entry
- (No code or other doc changes; PK bottles restored to original
  state, no calimocho-side state touched)

## 2026-10-24: Wine 11.20 TEB TLS port-07

### Source and build

- Added the CodeWeavers TEB thread-local-storage seam to the Wine 11.20
  source port. This initializes `teb_key`, sets it for the first and
  subsequent threads, and makes `NtCurrentTeb()` use
  `pthread_getspecific()`.
- The cloned configured build compiled `dlls/ntdll/ntdll.so`
  incrementally. The x86_64 Mach-O SHA-256 is
  `f743ac4549c2e23a02fb77d2a33ca8fd682f0fc344e6e4a1d661667ee3624111`.
- The focused port tests passed: 5 tests. `git diff --check` passed.
- A full `make install` retriggered the broader build. Its parallel attempt
  stalled at `tools/install` PID 23146. The serial retry stalled at PID
  24673. Only the exact `make` parents were stopped. Both U-state children
  were left untouched. The candidate install used for the startup attempt
  was the existing isolated clone with only its `ntdll.so` replaced; the
  port-06 copy was preserved under `research-wine-originals`.

### Startup and control result

- A fresh port-07 prefix did not initialize. `wineboot --init` PID 25090
  entered U state with empty stdout and stderr. One prefix-scoped
  `wineserver -k` attempt, PID 25226, also entered U state. The D3D12 probe
  was not launched, so there is no port-07 HRESULT, callback result, or
  runtime qualification.
- A fresh GPTK control using the selected `apple-gptk-4.0b3` engine record
  also stopped before prefix creation. Its `wine.real` process, PID 25644,
  entered U state with empty stdout and stderr. The D3D12 probe was not
  launched. The earlier `startup-gfx-06-control-02` receipt did reach
  `D3D12CreateDevice` with `S_OK`, but this fresh control could not repeat
  that result.
- The coordinator independently verified that a newly compiled trivial
  x86_64 executable also entered U state. The current blocker is host
  Rosetta/OAH translation, not evidence against the TEB port. No further
  x86_64 binaries were launched after that diagnosis. The coordinator reported
  `oahd` PID 798 had been running for 12 days. Recovery requires an owner
  reboot or a privileged `launchctl` action; neither was performed.
- U-state processes left untouched: PID 14902 (`wineserver -k` from the
  earlier LLDB run), PID 19500 (`conftest`), PIDs 23146 and 24673
  (`tools/install`), PID 25090 (port-07 `wineboot`), PID 25226
  (port-07 `wineserver -k` client), PID 25644 (GPTK control `wine.real`),
  and PID 25832 (coordinator's x86_64 translation check).
- GPTK payload hashes still match the prior verified control baseline.
  Apple payloads were not copied or modified, and no game was launched.

Port-07 has a successful incremental compile and passing source-port tests,
but remains runtime-unverified. Resume the fresh install and graphics probe
after the host translation service is available.

## 2026-10-24: Post-reboot CW baseline and Wine 11.20 graphics discriminator

The owner rebooted. The parent verified that newly compiled x86_64 programs
run again. This slice used fresh research prefixes and did not launch a game.
REQ-69 baseline evidence and REQ-74 forward-port evidence remain separate.

### Source-built CW26.3 baseline (REQ-69)

The retained CW26.3 source tree matched its recorded SHA-256 before use.
Completing `make -j4` and an isolated `make install` both returned zero.
The source archive remains pinned to
`ac99c8ca4b3848f3e81784135f023df266b61c2345726ea55a50b3e030dd6872`.
Its source-built FreeType dependency is version 2.13.3.

The research install retains Wine's original graphics modules in
`research-wine-originals`. D3D10/11/12, D3D12Core and DXGI PE/Unix modules
are symlinks to the owner's installed GPTK 4.0b3 redist. `lib/external` is
also a symlink. No Apple file was copied, modified, signed or de-quarantined.

In `gfx-cw-baseline-02`, Wine builtin startup, prefix-local AeDebug setup,
and the D3D12 create-device probe all returned zero. The probe printed
`D3D12CreateDevice first HRESULT=0x00000000`. The bridge and D3DMetal
framework appeared in loader diagnostics; the probe had no Vulkan/vkd3d
selection. Prefix-scoped `wineserver -k` and `-w` returned zero, with no
tracked process groups or prefix file handles remaining.

The first baseline harness attempt incorrectly expected a Unix `wineboot`
wrapper. CW installs the PE entrypoint instead. That attempt did not create
a prefix. The second used `wine wineboot --init` in a new prefix. Its
passing result does not erase the retained failed harness logs.

The [sanitized baseline registry](evidence/calimocho-cw26.3-gptk4b3.registry.json)
uses the existing Ode schema and engine name `calimocho-cw26.3-gptk4b3`.
It binds loader/server hashes, source and FreeType pins, the tested
environment, renderer links, smoke command/log hashes and an install manifest.
Its placeholders must not be passed directly to a launcher. The matching
local registry is
`build/winehq-11.20/metal-port-07-reboot-01/calimocho-cw26.3-gptk4b3.registry.local.json`.
Read-only Ode `engines.verify` and this repository's runtime exporter
validated the local artifact. No shared engine registry was edited.

Wine service children retain the original `wineboot` stderr descriptor
after that command exits. Log hashes were therefore finalized after
prefix-scoped shutdown. Receipts retain the earlier command-exit hashes
separately, rather than presenting those changing logs as immutable.

### Fresh WineHQ 11.20 port-07 (REQ-74)

A fresh source copy at WineHQ commit
`7298a818b79446bae153b8d5aa27235ab3703bf9` received the public CW integration
and TEB TLS change from `f8c56fa`. Configure, full `make -j4`, and isolated
installation all returned zero. No configured build tree was cloned for
this post-reboot build.

The port includes PE-region registration, nine native/Windows ABI wrappers,
client-surface integration, next-drawable dispatch, registry callback
transport, and the TEB TLS seam. The 192-byte callback-table compile-time
assertion passed compilation. That is not proof that runtime callback
registration completed before the fault.

Builtin startup and prefix-local AeDebug setup returned zero. The
create-device probe still faulted before returning an HRESULT. SEH recorded
`RIP=0x7ff81aa731e3` and `RDI=5`. The native image map places that instruction
at `libsystem_pthread.dylib+0x31e3`, matching the earlier
`pthread_setname_np` fault signature. The exact same probe on a fresh
installed GPTK control returned `S_OK` with exit zero.

AeDebug launched `winedbg --auto`, which printed only
`WineDbg attached to pid 0204`; it did not produce backtrace frames before
the 180-second probe deadline. The Wine D3D12 conformance executable exited
5 after an access violation, with no test summary. Neither is a passing
graphics result.

One additional fresh-prefix reproduction used a bounded, native stack-only
sample of our own probe process. It reproduced the same fault. Sampling
succeeded but did not recover a trustworthy crashed-thread caller chain:
the unwinder repeated `ntdll.so!__wine_syscall_dispatcher+405`. This is not
evidence of actual recursion. No Apple instructions were disassembled, and
LLDB was not repeated.

Both candidate prefixes shut down through their exact `wineserver -k/-w`.
Transient child zombies seen before the runner returned were reaped after
it exited; no tracked groups or prefix file handles remained. Apple payload
hashes matched before and after every graphics attempt. Probe diagnostics
contained no Vulkan/vkd3d selection.

The next seam to investigate is the native-thread start/syscall-frame and
Darwin GS/TEB transition in `signal_start_thread` and
`__wine_syscall_dispatcher`, not another callback-table expansion. CW and
WineHQ use different thread-data arrangements there. Instrument Wine-owned
entry arguments and context first; this is a hypothesis, not a diagnosed
root cause or permission to copy the old signal implementation wholesale.

Local source/build/install/graphics receipts are retained under
`build/winehq-11.20/metal-port-07-reboot-01`. The build receipt SHA-256 is
`ba56be6bbad7dbe2f801c7376bb1d2045fa924f158325bf23bf17d77a5dfb38b`.
The native stack sample SHA-256 is
`fd4cb9ab8d18451288179ec32d6d286980513333a0046c0276047badc28bca52`.
The final `gfx-candidate-01/receipt.json` SHA-256 is
`e200f03faf546061ec75efe1877043dd5fed8a45a263e578b0e12c1682c9ec1e`.
The final `gfx-candidate-02/receipt.json` SHA-256 is
`76119cdc1456ad774f2b96d8cb5f907dacd45802f22e79c26bdd1675d7795735`.
The `gfx-control-01/receipt.json` SHA-256 is
`e63cf3e9bdfc52518c088426f0044425537d6a8cb126a791478c867ed8865913`.

The deterministic Python suite passed all 37 tests. This slice establishes
source-built CW builtin startup and D3D12 device creation, not window
presentation, DX11 parity, Xbox gameplay, release readiness or distribution
rights. WineHQ graphics parity remains unresolved.

## WineHQ port-08: native GS and builtin/device parity (REQ-74)

The owner requested Wine-side boundary tracing and then a coherent
Darwin x86_64 native-GS port. See
the native-GS decision, now continued in
[ADR-0024](ADR/0024-loader-linked-time-slot-protection.md).
The canonical requirements remain in `dragos-core projects/ode-to-x/SPEC.md`.

### Discriminator and source change

`tools/trace_d3dmetal.py` instruments all 24 `my_*` callbacks with entry
and return-value traces. It also traces the safe C thread-start boundary,
`init_syscall_frame`, before assembly hands off to the Windows entrypoint.
The first instrumented reproduction entered no renderer callback before
the existing pthread fault. Thread `0210` reached its handoff at
`dxgi.dll+0x1f00`, with argument `0x7fce04015a00`, TEB `0x100027000` and
native thread-data base `0x40446a0e0`.

Port-08 adapts the public CW native-GS model into the pinned WineHQ
`7298a818b79446bae153b8d5aa27235ab3703bf9` source. It retains native GS in
Darwin signal, syscall, Unix-call and thread-start paths. Private Wine
frame fields are reached through mirrored TEB self. Static TLS updates,
expansion-slot allocation and inline-slot reservation preserve the native
thread-data slots. Other platforms retain their original assembly paths.

Native GS alone exposed a second source-documented conflict: localtime
uses the same native slot as the mirrored Windows process pointer.
Temporary Wine-only diagnostics narrowed the lost process parameters to
the timezone query. Those diagnostics were removed from the final build.
The owned native regression in `tests/native_gs_localtime_probe.c` confirms
the conflict: without the helper it reports
`mirrored_peb_changed=1` and exits 1; with the final helper it reports
`mirrored_peb_changed=0` and exits 0.

`tools/native_gs_localtime.c` uses standard launch-loaded symbol
interposition to call localtime_r with thread-local result storage.
No Apple instructions or files are patched. The WineHQ build tool now
compiles and hashes this helper, binds its source/compiler and records
the required process-local `DYLD_INSERT_LIBRARIES`. Compiler failures or
missing helper artifacts fail the build. CW baseline builds are unchanged.

The failed native-GS-only attempts and late/executable interpose attempts
remain under `metal-port-07-reboot-01/gfx-candidate-04` through `11`.
One attempt also put the real loader in the wrong `bin/wine` location.
The launcher belongs there; the actual loader is under
`lib/wine/x86_64-unix/wine`. That layout error was corrected, not treated
as runtime evidence. Attempt 12 first returned `S_OK` with the
launch-loaded helper, before the clean final rebuild.

### Clean source and runtime observations

The final `metal-port-08/source` was regenerated from a new archive of the
exact pristine WineHQ commit, then transformed and instrumented.
The known-good post-reboot build configuration was reused for an
incremental `make -j4` of the changed Unix modules, loader and both PE
ntdll architectures. Source-byte checks bind that build input to the
clean source receipt. A separate copy-on-write research install retains
the unchanged original port-07 install and CW baseline. There are no
temporary kernelbase diagnostics in this final install.

Fresh prefixes produced these results:

| Check | WineHQ port-08 | Unchanged CW26.3 baseline |
| --- | --- | --- |
| wineboot and prefix-local AeDebug | Exit 0 | Exit 0 |
| cmd /c ver | Exit 0, Windows 10.0.19045 | Exit 0 |
| CurrentVersion registry query | Exit 0, REG_SZ 6.3 | Exit 0 |
| Same D3D12 device probe | Exit 0, HRESULT 0x00000000 | Exit 0, HRESULT 0x00000000 |
| Prefix-scoped server shutdown | Exit 0 | Exit 0 |

Both probes loaded the installed GPTK bridge/framework, with no
Vulkan/vkd3d selection. Apple payload hashes matched before and after.
There were no tracked process groups or prefix file handles after cleanup.
The baseline had no native-GS helper injected.

The Wine D3D12 conformance executable progressed beyond device creation
but exited 1 without a passing summary. Its first test failure was
`d3d12.c:893: Got unexpected refcount 3`. Its fatal boundary was
`my_get_win_data(hwnd=0x10020)` returning zero, followed by
`No macdrv window data` and `Failed to initialize swapchain`.
This is not the earlier pthread fault, nor evidence of presentation parity.
The next presentation discriminator is Wine window/client-surface lifetime
and driver selection at that callback, not another export or GS rewrite.

### Evidence and limits

The [sanitized smoke evidence](evidence/winehq-port08-native-gs-smoke.json)
binds source tools, compiler/helper/runtime hashes, final log hashes,
regression results, both HRESULTs and the conformance failure.
Its SHA-256 is
`b5d1d0e5b06b930d2f1768cbda08131b46d56210e065648f5f684c41d8993627`.
Local source/build/install manifests, raw logs and the actual environment
are under `build/winehq-11.20/metal-port-08`; `handoff.local.json` binds
their paths. The install manifest covers 3913 entries.

All 43 deterministic Python tests pass. The localtime regression also
completed its observed red/green cycle against the final helper.
This completes the assigned builtin/device discriminator, not full
REQ-74 acceptance, presentation, Xbox gameplay, an Exodus engine switch,
distribution clearance or release readiness. No game, shared registry,
existing prefix/save, signing policy or global environment was changed.

## Port-09: protect ctime and link the helper (REQ-74)

Review of `09fea4a` identified a libc-internal call which the original
localtime-only helper did not intercept. The extended native regression
reproduced it: with the old helper, ctime succeeds but changes the mirrored
PEB bytes. This is a real correction to port-08, not just packaging.
The earlier environment-injection recipe and evidence remain historical.
[ADR-0024](ADR/0024-loader-linked-time-slot-protection.md) replaces that
dependency design.

### Bounded libc audit and correction

The public Apple Libc reference is commit
`71bbe350ab79eef58113991d817ccc6165061a64`.
In [localtime.c](https://raw.githubusercontent.com/apple-oss-distributions/Libc/71bbe350ab79eef58113991d817ccc6165061a64/stdtime/FreeBSD/localtime.c),
ctime calls localtime internally at line 2213. Gmtime uses a distinct
`__LIBC_PTHREAD_KEY_GMTIME`, not the localtime key. Mktime calls time1 and
localsub with caller-owned storage, not public localtime.
[Strftime](https://raw.githubusercontent.com/apple-oss-distributions/Libc/71bbe350ab79eef58113991d817ccc6165061a64/stdtime/FreeBSD/strftime.c)
formats caller-owned calendar fields; its `%s` path calls mktime.
These are public reference sources, not a claim that they are the exact
private sources of every system library on this host.

The helper now interposes ctime separately, using localtime_r and asctime_r
with a thread-local character buffer. It retains localtime interposition.
The Windows PEB mirror is retained: there is no established proof that
all Windows PE consumers can safely lose that ABI field.

The owned native probe audits localtime, ctime, gmtime, localtime_r,
gmtime_r, ctime_r, asctime, asctime_r, mktime, timegm and strftime
(`%c %s %Z %z`). It checks both the mirrored data and the pointer slot.
All eleven preserve both on the observed macOS 27.0.1 / Darwin 27.0.0 host
with the linked helper. Localtime and ctime reproduce corruption without
protection; ctime still reproduces it with the old helper. This does not
qualify every private libc entrypoint or future operating-system version.

### Required loader dependency, no injection environment

The bounded builder compiles the helper into
`build/loader/libnative-gs-localtime.dylib`, then relinks only the actual
Wine loader with the linker's needed-library flag. It verifies a required
`LC_LOAD_DYLIB` naming `@loader_path/libnative-gs-localtime.dylib`.
Its source, compiler, binary, dependency path and observed load commands
are bound in the receipt. Helper compilation, loader link, missing output
and missing load command all have explicit failing tests.

The separate port-09 research install contains the corrected helper
beside `lib/wine/x86_64-unix/wine`. No Apple payload or ntdll/macdrv source
was changed for this follow-up. No DYLD_INSERT_LIBRARIES entry is present
in the observed runtime environment. Relocated native probes pass with
the adjacent helper, while the actual Wine loader copied without it fails
at process load before main. No security setting was changed.

Fresh-prefix port-09 startup, version/registry queries and the original
device probe all exit zero; D3D12CreateDevice returns `0x00000000`.
A further fresh-prefix run enables the correct `+ntdll` debug channel and
records timezone year_start/year_end and DST ctime traces while still
returning `S_OK`. An earlier `+system` run passed but did not enable those
traces; it is not used as evidence that the ctime TRACE path executed.

### Same conformance executable, same desktop negative-case boundary

The original, unmodified conformance executable SHA-256 is
`e70d5839afee5cad229b21893fde69bbf6ecc8b9c98238ec64d85a8575c497de`.
The exact same bytes and arguments ran on port-09 and the unchanged
source-built CW26.3 baseline in fresh prefixes. Both device probes
returned `S_OK`. Both conformance runs print identical first twelve
stdout lines, including the refcount failures at lines 893 and 1172.
Both then print `No macdrv window data` and
`Failed to initialize swapchain`.

Port-09 exits 1. CW proceeds into exception handling, records access
violations and a stack overflow, and reaches the 180-second deadline.
It is a timeout, not a passing exit. Prefix-scoped server shutdown
completes on both. A transient baseline zombie is absent after the runner
returns; final checks find no owned groups or prefix file handles.

Source ordering points to the desktop-window negative test, not a normal
application window. A separate diagnostic rebuild adds exactly one trace
after GetDesktopWindow in test_desktop_window, with no assertion or
behavior changes. It prints desktop HWND `0x10020` immediately before the
renderer asserts for that same handle. The test expects `E_ACCESSDENIED`.
Earlier normal-window callbacks return nonzero data. This rules out
treating the observed NULL as a forward-port-only window-lifetime failure.
It does not turn either conformance run into a pass.

The diagnostic source and executable are retained separately. Original
source bytes were restored. A rebuild changed the PE timestamp/checksum,
so the exact frozen original executable was restored from the retained
run artifact and its original hash verified.

### Evidence and remaining scope

The [sanitized follow-up evidence](evidence/winehq-port09-time-and-conformance.json)
binds the source audit, helper regression, loader linkage, runtime bytes,
original pair, separate desktop diagnostic and final cleanup.
Its SHA-256 is
`d41620d4df221cb09bb2e8c4f0a81c545dd019c7cc2f86c83e16488c87f4d6c3`.
Raw receipts, logs, install manifest and actual launch paths remain under
`build/winehq-11.20/metal-port-09`; `handoff.local.json` contains the
non-injected runtime environment and required adjacent dependency.

The deterministic suite passes 46 tests, including native red/green,
relocation and missing-dependency checks. Apple payload hashes are
unchanged and probe diagnostics contain no Vulkan/vkd3d selection.
There is no passing full-conformance summary, independently observed
presentation, game launch, engine-switch qualification or REQ-74 closure.
The shared desktop-negative-case behavior must remain distinct from any
future ordinary-window presentation probe.

## Owned normal-window D3D12 presentation parity (REQ-74)

The coordinator requested a separate normal-window discriminator after
the shared desktop-negative-case conformance failure. This changes no
Wine or renderer source. See
[ADR-0025](ADR/0025-owned-normal-window-presentation-probe.md).

`tests/d3d12_present_probe.c` is an owned C PE probe. It creates a normal
320 by 240 overlapped window without activation, a D3D12 device/direct
queue and a two-buffer RGBA8 flip-discard swapchain. Each frame clears
to `(0.2,0.4,0.8,1.0)`, with explicit resource transitions and fences.
It copies the final cleared backbuffer through CopyTextureRegion into
a readback buffer, uses the returned footprint/row pitch, and checks
the center pixel after GPU completion. It prints actual HRESULTs,
successful Present count and actual pixel values. Failure is nonzero.

The installed MinGW GCC 16.2.0 compiles it with warnings as errors:

```bash
x86_64-w64-mingw32-gcc -std=c11 -Wall -Wextra -Werror -O2 \
  tests/d3d12_present_probe.c -o /owned/output/d3d12-present-probe.exe \
  -ld3d12 -ldxgi -ldxguid -lole32 -luuid -lgdi32
```

The exact same final PE bytes ran in fresh prefixes with 90-second
probe deadlines:

| Observation | WineHQ 11.20 port-09 | CW26.3 source baseline |
| --- | --- | --- |
| Device, queue, swapchain HRESULTs | 0x00000000 | 0x00000000 |
| First and last Present HRESULTs | 0x00000000 | 0x00000000 |
| Successful Present count | 120 of 120 | 120 of 120 |
| Readback center RGBA | 51,102,204,255 | 51,102,204,255 |
| Exact expected pixel | Match | Match |
| Probe exit | 0 | 0 |
| Probe elapsed seconds | 7.163 | 47.346 |
| Targeted on-screen PNG capture | Exit 0 | Exit 0 |

Elapsed time includes launch/teardown and diagnostic output; it is not
a frame-rate or performance comparison. Neither exceeded its deadline.

At the 60-Present marker, an owned CoreGraphics helper finds only the
named on-screen probe window. Screencapture records that window, not the
full desktop. Both 24373-byte PNGs have SHA-256
`ed06bfba1a3fe99b634ab016400a8ffcf4d2749b57b16ebae8c2115a7bf876e4`.
The inspected PNG shows the probe title and solid blue client area,
not a black window. GPU readback and observed display are separate
evidence; an exact pixel check alone would not prove screen presentation.
No mouse, keyboard or focus request was sent; the other lane keeps its
input lease.

The final PE SHA-256 is
`a3c229641de95940e9c11a38b4d8f4e886be0295be25f436293c4d3dfc19efdb`.
The source SHA-256 is
`9c5b5181f5d2b869a0f2ab7155e550e6d15dd4d986ef8875d4f939b64d3485d3`.
An initial passing probe run is also retained. The final run adds explicit
first/last Present HRESULT output and reports its result after the final
fence check; the hashes above bind that final committed source.

The [sanitized presentation evidence](evidence/req74-d3d12-present-parity.json)
has SHA-256
`4921396e766bdd9cb20be40834d50c59517367f4cd0209bcf04115f88df22449`.
It binds compiler, source/PE, runtime, log and screenshot bytes, exact
thresholds and cleanup. Local receipts, PNGs, capture-helper source/binary
and `handoff.local.json` remain under
`build/winehq-11.20/present-parity-01`. No image was uploaded.

Builtin startup/version/registry checks and exact prefix server shutdown
also pass for both runs. Apple payload hashes are unchanged, no
Vulkan/vkd3d selection appears, and final checks find no owned process
groups or prefix handles. No injection environment was needed.

All 47 deterministic tests pass, including a warning-free PE64 build
of this owned probe. This establishes bounded normal-window
clear/presentation/readback parity, not a full conformance pass,
gameplay, shader/media coverage, engine switching or canonical REQ-74
closure. No game, shared registry, existing prefix/save or security
policy was changed.

## 2026-10-24: Owned D3D11 presentation parity and WineHQ registry

The coordinator requested the D3D11 equivalent of the owned D3D12 probe
and a separate bindable WineHQ record while game-route/lease work remains
elsewhere. [ADR-0026](ADR/0026-d3d11-smoke-and-explicit-winehq-record.md)
records this bounded extension.

`tests/d3d11_present_probe.c` creates a hardware feature-level 11_0 device,
normal non-activating window and two-buffer DXGI flip-discard swapchain.
It clears an RGBA8 render target to `(0.2,0.4,0.8,1.0)` and requires
120 successful Presents. Before the final Present, CopyResource captures
the cleared backbuffer into a staging texture. Map READ synchronizes the
readback; its RowPitch locates the center pixel. There is no software
fallback, DXMT integration or retired custom shim.

The same warning-free MinGW PE runs on both unchanged source installs,
through their existing GPTK D3D11 PE/Unix symlinks and fresh prefixes:

| Observation | WineHQ port-09 | CW26.3 baseline |
| --- | --- | --- |
| D3D11 device, swapchain, staging Map HRESULT | 0x00000000 | 0x00000000 |
| Feature level | 11_0 | 11_0 |
| Successful Presents | 120 of 120 | 120 of 120 |
| First/last Present HRESULT | 0x00000000 | 0x00000000 |
| Exact staging pixel RGBA | 51,102,204,255 | 51,102,204,255 |
| Probe exit | 0 | 0 |
| Elapsed seconds, 90-second deadline | 6.923 | 47.409 |
| Targeted on-screen PNG capture | Exit 0 | Exit 0 |

Elapsed times include diagnostics and startup; they are not a performance
comparison. Both PNGs are byte-identical, and inspection shows the solid
blue client area. Their SHA-256 is
`111135097e904a284f093739afd412ca51c7827e5202e2fbbef9d27dc022087d`.
The exact PE SHA-256 is
`06d5a74f6cb1c9eb5965d7913be102c900ef4ae9d3bdaa19425e352ff5f13c04`.
The [D3D11 evidence](evidence/req74-d3d11-present-parity.json) binds
source, compiler, runtime, logs, capture, readback and cleanup.
Raw receipts and images stay local under
`build/winehq-11.20/d3d11-parity-01`.

Wineboot/version/AeDebug and prefix-specific shutdown all exit zero.
There are no residual owned process groups or prefix handles.
Apple payload before/after hashes match and no Vulkan/vkd3d selection
is observed. No input or focus request was sent.

The new [sanitized WineHQ registry](evidence/calimocho-wine11.20-gptk4b3.registry.json)
is named `calimocho-wine11.20-gptk4b3`. Its executable local counterpart is
`build/winehq-11.20/metal-port-09/calimocho-wine11.20-gptk4b3.registry.local.json`.
The record binds the pinned WineHQ commit, donor archive, source receipt,
FreeType, launcher/server, actual Unix loader, ntdll/macdrv, native-GS time
helper and GPTK symlink map. The helper remains a required
`LC_LOAD_DYLIB @loader_path/libnative-gs-localtime.dylib`, not an injected
environment variable. A freshly frozen and rehashed 3912-file install
manifest matches. The existing read-only Ode verifier and Calimocho recipe
exporter accept the local record. No shared registry was changed.

All 49 deterministic tests pass, including warning-free PE64 builds for
both presentation probes and the public WineHQ identity/threshold checks.
This is bounded DX11/DX12 smoke and a bindable local record, not game
rendering, full conformance, engine-switch or distribution acceptance.

## 2026-10-24: Port-10 source-built schannel overlay

The coordinator identified missing schannel support in game-owned logs.
An owned PE independently reproduces it on unchanged port-09: WinHTTP
SendRequest returns `0x80090305` (`SEC_E_SECPKG_NOT_FOUND`), alongside
`SECUR32_initSchannelSP no schannel support`. The same final PE succeeds
on port-10. This establishes a missing runtime capability, not causality
for a particular game's activation error.

[ADR-0027](ADR/0027-isolated-schannel-dependency.md) records the bounded
dependency and overlay decision. `versions.json` now pins official GMP
6.3.0, nettle 4.0, libtasn1 4.21.0 and GnuTLS 3.8.13 archives with SHA-256
checksums independently published in the Homebrew formula API. Only
official source was downloaded, never a Homebrew binary. Every archive
hash was verified before extraction.

`tools/build_tls.py` builds shared x86_64 libraries with installed tools
under `build/dependencies/tls-x86_64-01/prefix`. The retained source trees
contain their licences. GnuTLS uses included unistring without p11-kit or
optional IDN support. Its complete five-dylib closure references only that
owned prefix and macOS system libraries, not Homebrew or `/usr/local`.
It is a local-only dependency layout, not a relocatable distribution.

`tools/build_cw_candidate.py --tls PREFIX` makes schannel explicit and
rejects a missing library, wrong architecture or absent/wrong SONAME.
Configure emits `SONAME_LIBGNUTLS "@rpath/libgnutls.30.dylib"`. The Unix
TLS modules carry an LC_RPATH for the isolated TLS lib directory.
The runtime recipe adds that directory alongside FreeType. A separate
positive HTTPS run removes TLS from DYLD_FALLBACK_LIBRARY_PATH and still
returns 200, proving the new selection does not rely only on fallback.

The coordinator then prioritized an immediate targeted overlay instead
of a full rebuild. A fresh pinned-source tree had already configured;
only its secur32, bcrypt and crypt32 module targets were completed.
`--tls-only` now exposes that narrow repeatable build mode and explicitly
builds the ucrtbase import archives first. For example:

```bash
python3 tools/build_cw_candidate.py \
  --archive "$CW_SOURCE_ARCHIVE" --winehq-source build/winehq-11.20/source \
  --output "$NEW_OWNED_BUILD" \
  --freetype build/dependencies/freetype-2.13.3-x86_64-02/prefix \
  --tls build/dependencies/tls-x86_64-01/prefix --tls-only
```

Use the existing installed modern bison on PATH, not macOS's old bison.
This command compiles only; it does not install or launch a runtime.
The observed research overlay copies the qualified port-09 install and
replaces exactly eight files: secur32/bcrypt/crypt32 PE modules for both
architectures and secur32/crypt32 Unix modules. Current WineHQ has no
`bcrypt.so`. The full 3912-file manifest proves every other file identical
to port-09, including its real loader, native-GS helper, ntdll/macdrv and
GPTK symlinks. The old install was also rehashed unchanged.

The owned `tests/winhttp_https_probe.c` is built with MinGW warnings as
errors and makes a synchronous WinHTTP request, with bounded network
timeouts and ordinary certificate checks. The normal request requires
200; `--expired-certificate` selects only the fixed negative endpoint.
It never ignores certificate errors or changes trust:

| Observation | Result |
| --- | --- |
| port-09 Microsoft HTTPS, same final PE | Missing schannel, exit 1 |
| port-10 Microsoft HTTPS | Status 200, exit 0 |
| port-10 expired.badssl.com | TLS completes; certificate-date error 12037 |
| Negative public API result | Generic secure-channel error 12157, raw PE exit 1 |
| port-10 HTTPS without TLS fallback directory | Status 200, exit 0 |
| D3D12 presentation/readback | 120 Presents; RGBA 51,102,204,255; exit 0 |
| D3D11 presentation/readback | 120 Presents; RGBA 51,102,204,255; exit 0 |

The negative run did not deliver the date-invalid callback expected by
the strict probe. Its raw exit remains 1, not relabeled as a positive
success. The WinHTTP trace explicitly says `cert verify failed: 12037`
after `InitializeSecurityContext ret 0`, establishing certificate expiry
rather than a generic connection failure. Native curl independently
rejects the same certificate with exit 60. No validation was bypassed.

The two exact previously qualified graphics PEs run in fresh prefixes,
each with a 90-second deadline. D3D12 takes 7.130 seconds and D3D11 takes
7.006 seconds; these are not performance comparisons. All printed
HRESULTs are zero, exact readback matches, and targeted captures show the
blue client area. Their PNG hashes match the corresponding earlier
D3D12 and D3D11 captures. No input or focus request was sent.

The [sanitized port-10 record](evidence/calimocho-wine11.20-gptk4b3-tls.registry.json)
is `calimocho-wine11.20-gptk4b3-tls`. Its usable local copy is
`build/winehq-11.20/metal-port-10-03/calimocho-wine11.20-gptk4b3-tls.registry.local.json`.
It binds the original core, source/overlay receipts, eight module changes,
all TLS dylibs, FreeType, renderer links, fresh-prefix HTTPS receipt,
negative observation and both graphics reruns. The existing read-only
Ode verifier and Calimocho exporter accept it. The local record was sent
to the coordinator before documentation, as requested.
HTTP/schannel diagnostic channels remain test-only, not enabled in the
runtime recipe. Another fresh HTTPS 200 receipt binds the final exact
runtime environment without HTTP tracing.

The [TLS/graphics evidence](evidence/req74-port10-schannel-and-graphics.json)
retains exact sources, commands, artifact/log/receipt/capture hashes and
honest failed/stopped approaches. Initial configure rejected old bison.
A bare-SONAME full build was abandoned for explicit RPATH selection.
Full builds were then stopped for the targeted approach. The shell
wrapper stop left separate-session make children alive; their exact owned
PIDs/groups were authenticated by working directory and stopped explicitly.
A concurrent initial narrow target hit an incomplete import archive;
explicit prerequisites and the narrow retry succeeded. No abandoned
full build is called complete. Logs stay local.

Initial dependency configure warnings for ignored optional flags are
retained in the evidence; the repeatable tool removes those flags.
Required GnuTLS selection options were recognized. The CW baseline is
unchanged because a second rebuild was not cheap.

Apple before/after hashes match. All owned run groups and prefix handles
are gone. No game, account, shared registry, existing prefix/save, global
install, signing or trust-policy change was made in this lane. Game
retests and canonical acceptance remain coordinator-owned.

All 57 deterministic tests pass, including pinned-archive rejection,
explicit TLS-prefix/SONAME guards, narrow-build target selection,
warning-free owned PE compilation and registry closure/observation checks.

## 2026-10-24: Relative mouse discriminator prepared, native run held

The owner reports Fallout 4 camera movement missing on port-10, with
movement previously working but choppy on the Apple GPTK engine.
This remains a reported comparison, not an isolated runtime regression.
The Ode coordinator restricted this follow-up to source and synthetic
checks while the UI/owner holds the desktop input lease.

[ADR-0028](ADR/0028-owned-relative-mouse-discriminator.md) records the
CW26.3 versus frozen WineHQ input-path differences and the scheduled
discriminator. The event-tap and confinement implementations are
substantially identical. Real differences include host clipping on reset,
fullscreen clipping transitions, server Z-order handling and WineHQ's
motion accumulation/raw-frame transport. None is yet proven causal.

Added `tests/raw_mouse_probe.c`: a foreground five-second raw mouse
registration, clipping and hidden-cursor probe, with an unclipped control,
relative/absolute packet flags, legacy coordinates, focus-loss abort and
ordinary-exit cleanup. Added `tools/check_mouse_probe.py` and synthetic
receipt tests. Receipt validity does not authenticate the source of events.

Nine focused tests cover the new probe's warning-free PE64 compilation
and synthetic receipt checks, existing D3D11/D3D12 probe compilation,
and frozen registry evidence invariants. No PE or native input probe was
executed. No runtime, existing prefix, frozen record or game was changed.
There is no port-11 candidate or fix claim. Reproduction under an exclusive
input lease is the next gate before selecting any production patch.

An independent read-only source review returned REVISE for one Medium:
the checker did not bind the expected clipped/unclipped mode. The checker
now requires that mode and validates it against the structured ready record;
a focused synthetic test rejects both mismatch directions. This correction
has not received a second independent review. Neither source checks nor a
source review grant native input admission. Crash or forced termination
cannot guarantee clip/cursor cleanup and requires host-state verification
before returning the input lease.

## 2026-10-24: REQ-78 source-built Vulkan candidate, native gate pending

The coordinator committed the separate Vulkan prerequisite and assigned
Calimocho in canonical `dragos-core` commit
`28533b096cd836db448dc265e79d779053a83777`.
[ADR-0029](ADR/0029-source-built-vulkan-candidate.md) records the supported
upstream configure/loader seam and isolated source-build decision.
This port-11 candidate is not a mouse fix.

Official MoltenVK v1.4.2 commit
`db66022459ffb663aa2b50f6b018bc2e124f5edf` and all seven release-manifest
Git dependencies were fetched at exact commits and built with installed
Xcode tools. No prebuilt dependency was used. The resulting dylib is
x86_64 only, SHA-256
`533494b0eef1871d79e6b1d9d5faa59c8417232f7d6ecf00c2850ac40247c6cf`.
Its install ID is `@rpath/libMoltenVK.dylib`; its other imports are system
libraries/frameworks. The Apache-2.0 licence is retained in the source.

The first dependency packaging attempt failed because the owned job-limit
wrapper passed `-jobs 4` to `xcodebuild -create-xcframework`. The corrected
wrapper exempts packaging and resumes the exact sources within the original
45-minute budget. The failed-attempt receipt retains the error and recorded
log hashes. The first wrapper revision reused log names on resume, so the
initial dependency log bytes were overwritten; those historical hashes are
not presented as currently re-verifiable log files. The repeatable builder
now uses separate resumed log names.

An isolated copy of the port-10 source/build/install reconfigures successfully
with `SONAME_LIBVULKAN` set to `@rpath/libMoltenVK.dylib`.
Narrow win32u, winevulkan, vulkan-1 and winemac compilation succeeds.
An initial overlay filename error was corrected without rerunning configure:
the PE module is `winemac.drv`, not `winemac.drv.drv`, and its Unix module
is `winemac.so`. A complete comparison finds exactly the eleven declared
Vulkan files changed across 3,913 install entries. The original port-10
registry still hashes to `13bc00b7f8e1496cd2b02822d75bc00b2b366b37692ff3701db083b45e56c1c4`.

The owned Vulkan probe cross-compiles warning-free. An independent source
review returned REVISE for native ordering, runner failure propagation,
negative TLS selection and resumed architecture-log selection.
Those corrections are implemented; parent review additionally required
fail-closed missing/malformed CoreGraphics inventories and unknown foreground.
Fresh geometry validation and negative fixtures cover that boundary.
The parent independently ran the fifteen focused checks and closed the
specific source-review and geometry fail-open findings. The original REVISE
remains part of the history, not a blanket product PASS. All 73 deterministic
repository checks subsequently pass, including compilation, synthetic
geometry/receipt failures and original TLS registry invariants.

The parent admitted one bounded passive Vulkan run after the UI boundary
cleared. Its fresh geometry preflight refused before Wine or prefix creation:
neither display had a free 400 by 340 region. The read-only inventory is
retained locally and a short shared UI pause was requested. No window was
moved and no native ordering or overlap check was bypassed.

The coordinator then allowed overlap with only the exact foreground Ode
PID/window pair during an explicit UI-input pause. The new negative fixtures
require this exact identity and still reject other windows of the same
process or any foreign process. The UI owner confirmed the pair and paused.
A fresh preflight still found no region: a foreign layer-20 window covered
the main display, while foreign windows occupied the second display.
Execution stopped without Wine, prefix creation or another retry, and
quiescence was returned to the UI owner. This is a desktop-resource blocker,
not a Vulkan failure or success.

A subsequent read-only discriminator bound the full-main window to the system
Dock executable, but reported alpha 1 and on-screen status. A relative
above-Ode query also included it. These metadata do not prove its pixel
coverage, so no Dock exception or native-ordering workaround was added.
The helper now requires explicit valid alpha and on-screen fields rather
than assuming visibility metadata. All 73 checks still pass. The coordinator
then stopped geometry investigation because S3 acquired the runtime/input
lease for a separate Subnautica 2 run. Calimocho remains quiescent until that
lease is released and a concrete workspace boundary is resolved.

At this checkpoint no Wine or graphics probe has run on the candidate.
Actual execution still requires a supported current geometry boundary.
No usable port-11 record, Vulkan/NMS success, mouse correction, release or
distribution admission is claimed. Existing prefixes, Apple payloads and
the frozen port-10 install remain untouched.

### REQ-78 qualification after owner unlock and native allocation

The first post-game preflight still refused while two foreground windows
covered both displays. The owner later confirmed the Mac was unlocked.
A single newly admitted unchanged geometry check found a free region.
After the separate Apple TV benchmark interval released the CPU/GPU lane,
the coordinator allocated one sequential passive qualification sequence.
All actual launches rechecked fresh geometry rather than reusing coordinates.
No Dock, layer or overlap exemption was used.

The source-built MoltenVK candidate enumerated Apple M5 Max, created an
instance, graphics/presentation device, native surface and swapchain,
completed 120 successful `vkQueuePresentKHR` calls, and read back exact
RGBA `51,102,204,255`. The D3D12 and D3D11 regression probes each completed
120 Presents with the same exact pixel. These are swapchain/backing-content
checks, not a claim about captured compositor pixels or game compatibility.

Positive WinHTTP HTTPS returned HTTP 200 with certificate validation enabled.
The expired-certificate probe exited 1 as expected for this negative test:
Wine reported certificate diagnostic 12037, while the Windows API still
returned generic 12157 with zero secure-failure flags. Rejection is established;
the strict Windows error-mapping limitation from port-10 is not fixed.

Every setup and prefix-scoped shutdown command exited 0 without timeout.
All three graphics windows bound to the owned process group and passed
actual native-frame non-overlap checks. Foreground stayed unchanged across
all five runs. No residual process groups or prefix handles remained;
Apple payload and full port-10 install hashes stayed unchanged.

The emitter produced the new exact local record named
`calimocho-wine11.20-gptk4b3-tls-vulkan`, SHA-256
`a5d37d2909f56abe75f9b6096cf39b4d75c91a7f6aac75154488d4c35b5ff28a`.
The existing schema-1 exporter validated its exact paths, hashes and contract.
The optional provider declaration is not backend trust or admission.
The coordinator and S2 received the local path and whole-file hash.
[Sanitized qualification evidence](evidence/req78-vulkan-qualification.json)
retains exact receipt identities and limitations. No NMS or other game
was launched by this qualification slice, and no mouse correction is claimed.

## 2026-10-24: Private Metal opt-in, source/build only

Whiny assigned the bounded source/build diagnostic in commit `926c550`,
REQ-A01/N13/H03/D08. The parent authenticated the NMS feature-16 failure
from run `73fb0798-b917-45db-b80b-b1fa57afe68c`; this child did not replay it.
[ADR-0030](ADR/0030-opt-in-private-metal-source-diagnostic.md) records the
explicit opt-in and the separate native/admission hold.

The offline invocation was:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/build_moltenvk.py \
  --output build/dependencies/moltenvk-1.4.2-x86_64-private-01 \
  --metal-private-api \
  --local-build-cache build/dependencies/moltenvk-1.4.2-x86_64-01
```

The builder copied the existing pinned local source and source-built static
dependencies into the new exclusively owned root, verified clean tracked
source and all eight Git identities, and skipped dependency fetching.
The build exited 0 with Xcode 27.1 (`27A9275`) and Apple clang 21.0.0.
The existing nested four-job limit and 45-minute budget remained in force.
The actual MoltenVK compiler response files contain
`-DMVK_USE_METAL_PRIVATE_API=1`; the public default is unchanged.
Owned configuration SHA-256:
`bee29f198b8240c79ecfe77218da8a2dcdbc68571cc1c3142826d9954ab6b820`.

The new x86_64 dylib SHA-256 is
`4b4bc6fe5fd68f8e2fda12b6a153e69f838d78f72623d062ebcb42374833a385`.
Its receipt SHA-256 is
`65a5ff586bafe0d06a0b4627382d416f6fcf6e564f821ad0cb9fe815cfe8c58a`.
Its install ID is `@rpath/libMoltenVK.dylib`, with no LC_RPATH and only
system/framework imports. Read-only `codesign -dv` reported that it is
unsigned, as expected with signing disabled. No signing identity or
Keychain access was used. No dylib was loaded.

The existing Vulkan probe now accepts optional `--require-wide-lines`.
It queries actual feature support, fails if absent, and requests the feature
at device creation when present. Its default still enables no optional
features. The exact 120-Present and RGBA criteria remain unchanged.
The updated PE compiled warning-free, SHA-256
`dce67d9b539350bdcb6c2eec12d892cff35747cebde385efaebcdf3d593bb916`.
An initial link attempt used Wine's whole import-library directory and
accidentally shadowed the compiler's CRT imports. It failed with unresolved
CRT symbols. Linking the exact `libvulkan-1.a` archive instead succeeded:

```bash
x86_64-w64-mingw32-gcc -std=c11 -Wall -Wextra -Werror -O2 \
  -Ibuild/dependencies/moltenvk-1.4.2-x86_64-private-01/source/External/Vulkan-Headers/include \
  tests/vulkan_present_probe.c \
  build/winehq-11.20/metal-port-11/install/lib/wine/x86_64-windows/libvulkan-1.a \
  -lgdi32 \
  -o build/dependencies/moltenvk-1.4.2-x86_64-private-01/vulkan-present-probe.exe
```

Nine focused builder/probe checks pass, including actual compiler macro and
dependency-artifact hash checks. Both frozen install manifests still match
all 3,913 entries each. The public MoltenVK `533494...` and exact `a5d37...`
registry bytes remain unchanged. No engine registry, install overlay,
selection, prefix, native probe, capture, input, game or publication occurred.

A future separately authorized native diagnostic must bind the private
dylib to an isolated loader route first, then invoke this PE with
`--require-wide-lines` and `MVK_CONFIG_USE_METAL_PRIVATE_API=1` under the
existing fresh-prefix, passive-window, 90-second and cleanup guards.
The frozen public route is not that loader binding. Feature support and
device creation must be observed, not inferred from this compile result.
Even a passing clear/readback probe would not exercise wide-line rasterization
or establish NMS compatibility.

### Port-11b private-Metal native qualification

The separately authorized `69e07d0` diagnostic03 continuation completed all
five cells with fresh prefixes and prefix-scoped cleanup. Earlier geometry
refusals remain preserved. A missing diagnostic parent directory stopped the
first03 invocation before runtime spawn; creating that owned directory fixed
the preparation error without changing the probe, runtime or safety guards.

The actual Vulkan native PID 89328 loaded the colocated private MoltenVK
`4b4bc6...` through the unchanged win32u loader route. Its tagged dyld line
is retained in the receipt. The probe reported wideLines supported, required
and enabled as 1, successful device creation, 120 successful Presents and
exact RGBA 51,102,204,255. D3D12 and D3D11 each reached 120 Presents and the
same exact pixel. HTTPS returned 200 with certificate validation enabled.
The expired certificate was rejected with API error 12157 and Wine's
date-invalid diagnostic 12037. Strict Windows error mapping remains unproven.

The native command span was 98.34 seconds. All cells retained unchanged
foreground, Apple payloads, port10 and private dylib hashes, no residual
owned process groups and no open prefix files. No activation, input, capture
or game launch occurred. The public `a5d37...` record remains unchanged.

The existing emitter and recipe exporter accepted one separate local record:
`calimocho-wine11.20-gptk4b3-tls-vulkan-private.registry.local.json`,
SHA-256 `fbb6b9cbe1fc6cf35ffcb9378c60344b3b360a730d54ec5123fc0e1f10e87695`.
It selects the derived installation and private API environment explicitly.
Full receipt bindings and limitations are in
[the private qualification evidence](evidence/port11b-private-qualification.json).
This qualifies the bounded probes, not wide-line rasterization or NMS.
Admission and any game run remain owned by the parent. No publication occurred.

### Port-11b performance environment sibling

Owner-directed REQ-N13/N25 scope recorded by Whiny commit `56998de`
authorized one data-only sibling of frozen `fbb6b9cb...`. Its full SHA-256 is
`170ca4ad08a5274b614e74bf740866ef219a97fdc7855270c5d8fa03192ed609`.
The local file is
`build/winehq-11.20/metal-port-11b-private-binding-01/calimocho-wine11.20-gptk4b3-tls-vulkan-private.registry.local.PERF-FROZEN-170ca4ad.json`.

The complete semantic diff is limited to `engines[0].environment`:
`WINEDEBUG` changes from `+loaddll,+seh,+macdrv_d3dmtl,+unixlib` to `-all`,
`DYLD_PRINT_LIBRARIES=1` is removed, and `MTL_HUD_ENABLED=1` is added.
Every other JSON value is identical, including the engine name, installation,
private API and argument buffers values of 1, all asset/dependency paths and
pins, and historical qualification timestamps, environments and receipts.
The existing exporter verified all 45 referenced files. Frozen `fbb6b9cb...`
is unchanged.

The existing engine name is retained; prefix admission remains the owner's
contract, not a guarantee made by this derivation. Qualification from source
commit `671ca6443a126305649a981940a2d8377f954ee7` and evidence SHA-256
`f729ff3deb1572e110ccffb1a21604781f3670a697c27584f2c0b644884dd57c`
is inherited binary evidence only. There is no new performance, HUD or game
observation. No rebuild, native execution, prefix change, admission change or
publication occurred.

### Source-only argument-buffer sampler inspection

Whiny scope `2ce958d` requested inspection before any AB2 variant. The selected
MoltenVK 1.4.2 source remains clean at
`db66022459ffb663aa2b50f6b018bc2e124f5edf`. Contrary to the older enum model,
`useMetalArgumentBuffers` is `VkBool32` in `API/mvk_private_api.h:242` and
`Utility/MVKConfigMembers.def:81`. The pinned configuration documentation
at lines 580-588 calls it Boolean, default 1. `Utility/MVKEnvironment.cpp:111`
casts the numeric environment value to that member type.

In `GPUObjects/MVKDevice.mm:2703`, both nonzero values 1 and 2 enable the
same Boolean path when descriptor-set argument buffers are supported.
Hardware tier is queried separately at line 2691; value 2 does not select
Tier 2. The capability predicate at lines 2753-2754 also requires the
hardware tier. Ordinary `maxPerStageDescriptorSamplers` is assigned from
`maxPerStageSamplerCount` at line 2890, initialized to 16 at line 2430.
There is no AB1 versus AB2 branch in that assignment.

Update-after-bind sampler limits are different properties: line 863 uses
`getMaxSamplerCount()` when the actual Tier 2 predicate holds. That helper
at lines 3461-3466 reads Metal's `maxArgumentBufferSamplerCount` when
argument buffers are in use. Neither this property nor the hardware tier
should be confused with the ordinary per-stage sampler limit.
Research supplied the owner's existing dialog wording: NMS warns that the
driver does not support the number of per-stage descriptor samplers it
requires, with possible broken rendering or crashes. The dialog states no
numeric requirement. No numeric threshold is established by that evidence.
The CrossOver recipe uses a different MoltenVK fork, so its value 2 is not
evidence of different semantics in this pinned upstream source.

The existing Vulkan probe now prints the queried ordinary per-stage
descriptor limits, total per-stage resources, device identity and the
requested argument-buffer environment string. That string is explicitly
labelled environment, not proof of effective driver configuration.
The extension adds no feature request, window action or execution mode.
Ten focused checks pass, including warning-free compile-only validation.
No native query, new engine, AB2 record, admission or current-run change
occurred. A later headless comparison still needs separately scoped
preparation and a fresh native slot.

### REQ-N29 real sampler fixture preparation

The existing probe now accepts optional `--sampler-shader PATH`. It creates
17 combined image/sampler descriptors, dispatches a compute shader with
17 static sample operations and compares every output slot and channel
against exact alternating opaque white/black border colors. Insufficient
advertised capacity is an explicit error. Default presentation behavior and
the existing wideLines option remain available.

The shader source is `tests/vulkan_sampler17.spvasm`, SHA-256
`13eba4380e83828db513312ff26efff9cb499b0aef28e1d93b64ffe08bc9d985`.
An exclusively owned CPU assembler helper linked the existing pinned
source-built SPIRVTools library and validated it for Vulkan 1.0.
The resulting shader SHA-256 is
`6b3033f2ba525af7550bdb2cdc92812b7411876d5f3e867224e77e1dd66c8331`.
No GPU or Wine execution was involved in assembly/validation.

The warning-free linked probe is
`build/dependencies/moltenvk-sampler-n29-01/vulkan-sampler-probe.exe`,
SHA-256 `de2dfddf2f8999ba75b7d76a3f268db5fffb507fc8e199fedefd8a378d582812`.
The compile used the existing MinGW compiler, pinned Vulkan headers and exact
accepted Wine Vulkan import archive, not a new dependency. Eleven focused
checks pass. The initial source check expected the old single-argument parser
spelling; updating it for the multi-option parser fixed that check.
The fixture has not run on a GPU and does not yet test push descriptors.

The isolated `MVKDevice.mm` copy is byte-identical to the accepted pinned
source after rejecting a draft limit change. No capacity change or new
MoltenVK build remains. Capping all push descriptors to 16 would violate the
required minimum of 32. Removing only the extension would not remove the
mandatory Vulkan 1.4 core push capability. See
[ADR-0031](ADR/0031-test-sampler-capacity-before-advertising-it.md).
Real push argument buffers require changes to layout selection
(`MVKDescriptorSet.mm:184-193`), both push writers (lines 1820-1848), command
encoder CPU-only push storage (`MVKCommandEncoderState.mm:937-953`) and
pipeline resource encoding (`MVKPipeline.mm:295-323`). A capability-withdrawal
variant would instead need extension, core-feature and API-version changes
with explicit compatibility consequences. Neither path is implemented or
claimed qualified here.

### 11d AGS runtime probes and DIRT5 admission provenance

The isolated AGS5.4/minidump sibling completed its headless AGS device,
minidump and HTTPS positive/expired-certificate negative checks. Its actual
Vulkan, D3D11 and D3D12 probes each presented 120 frames and returned exactly
RGBA 51,102,204,255. The graphics guard recorded only the owner-authorized
Dock PID716/window33 exception. Foreground, payloads and baseline hashes
were unchanged; owned servers stopped and waited and prefix open-file
checks were clean.

The runtime-qualified registry `dcb8489851cafde7ffc9333de3d61a33c61e622b1e4b6a3262016c96ad42b7c7`
remains unchanged. The separate DIRT5 admission variant embeds the complete
`mscoree,mshtml=;amd_ags_x64=b` override instead of depending on external
environment merging. A fresh complete installed-inventory comparison and
independent profile-asset/dependency hashes establish `integrity: unchanged`,
not game qualification. Tracked producer evidence binds that audit, the
original registry, graphics/headless receipts and separate recipe. The
producer commit and upstream Wine commit are distinct identities.

See [ADR-0037](ADR/0037-add-an-opt-in-wine-built-ags54-adapter.md) and
`docs/evidence/11d-dirt5-runtime-provenance.json`. No DIRT5 title-screen
acceptance follows from these producer checks.

### Cell007 verified frameworks and completed factory diagnostics

The retained application and four declared frameworks passed pinned-root,
Store EKU, authenticated timestamp and complete installed block-map checks.
The owner-approved new sibling compiled graph-aware ntdll/kernelbase and
completed class/IID/HRESULT/registration diagnostics in combase. The native
windowless graph enumeration and loader sentinel fixture finished in 9.07
seconds with clean owned stop/wait and prefix open-file checks. The actual
completed fixture factory record returned COM-not-initialized, not a proven
missing class. The stream drain remained explicitly incomplete.

The earlier snapshot attempts rejected a missing WebView2 server and class
collisions. Source now records the missing manifest-declared payload instead
of fabricating it, and records first-declared framework precedence separately
from local duplicate rejection. The historical TSA failure was fixed by
validating the TSA at its signed time without disabling chain verification.
Compilation initially rejected an unavailable CRT helper and an oversized
debug-channel name; both were corrected before the actual installed fixture.
An incorrectly nested factory wrapper was caught by linking and moved to
file scope. No failing build was handed off as runnable.

Only the new isolated six-PE-module overlay changed. The delivered package
candidate, earlier cells and graphics-qualified 11d install remain untouched.
Fresh-prefix registration import and actual Xbox cell007 execution belong
to its owner. See
[ADR-0038](ADR/0038-resolve-verified-local-framework-activation.md).

### Cell008 package-local Launcher source and build

Actual Xbox cell007 reported a successful Uri factory and a class-not-registered
Launcher factory. No method, URI or protocol target was observed. The new
isolated sibling adds Windows.System.Launcher and replaces only its server.
The public URI method slots compile with explicit ABI assertions. Routing
uses verified manifest protocols, including the XboxPcTray executable override
on msgamelaunch. Unknown schemes return false without host fallback. The
AppL UWP route explicitly reports E_NOTIMPL until genuine activation delivery
exists; no invented command-line switch or success stub is used.

Both public XAML module basenames are collected with PID attribution. A
recorded started protocol child suppresses the direct-CE-only drain cutoff,
within the unchanged finite60s cap. No child exit is inferred from CE exit.
The focused source suite passes52 checks. The application and complete
framework graph passed another pinned-root authenticated-content verification.
The source freezer's recheck initially expected the signed digests in the
verifier return value; the verifier supplies them through its progress
mapping. Preserving that mapping fixed the caller without weakening any
signature or content check.

The earlier failed build and wrong-path registry artifacts remain retained.
The final DLL, server and both fixture/helper binaries compile. Native
Launcher fixture and actual Xbox cell008 remain unexecuted until the
scheduler grants their exclusive lane. Neither compilation nor the
deployed-inventory audit is a runtime, XAML, UI or game qualification.
See [ADR-0040](ADR/0040-route-only-verified-package-protocols.md).
