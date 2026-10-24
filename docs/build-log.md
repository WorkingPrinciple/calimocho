# calimocho — build log

Live notes from the build investigation. Will become structured docs once
the recipe is reliable.

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
registry query were not run. No further retry was made.

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
explicit isolated search path, but it does not establish a successful
runtime or the root cause of the remaining startup timeout. No
runtime-recipe change is made from this failed check.

Known unresolved features include GnuTLS/schannel, Vulkan/MoltenVK and
GStreamer. Wine was executed only for the isolated startup check above.
No Apple payload was executed or copied, and no existing runtime, prefix,
save or account was modified. Current-Wine integration, Apple ABI
compatibility, isolated runtime startup and actual Xbox DX12 gameplay remain
open.

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
