# calimocho — build log

Live notes from the build investigation. Will become structured docs once
the recipe is reliable.

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
  bottle (sourced from `/Users/gcenx/Documents/GitHub/wine-private/`),
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

## 2026-10-25: REQ-104 bounded NMS graphics investigation

### Requirements and correction recorded before source changes

Owner-directed local research/source slice, following the isolated-build
decision in committed runtime-adapter ADR-0022. This fresh worktree starts
at archived `c75be80`; it does not reopen a historical shipping phase.
The program requirements ledger remains parent-owned in ode-to-x `SPEC.md`.

| ID | Requirement | Acceptance |
|---|---|---|
| REQ-104 | Diagnose sampler capacity warning and Metal shader compilation separately within 45 active minutes (09:40-10:25 UTC). | Primary upstream evidence, exact source identity, focused before/after results or an evidence-backed blocker. |
| REQ-104 safety | Preserve the running game and frozen registry `170ca4ad08a5274b614e74bf740866ef219a97fdc7855270c5d8fa03192ed609`. | No input, process attachment, restart, prefix/settings/installed-engine mutation, or loaded-file replacement. |
| REQ-104 honesty | No dialog hiding or larger sampler limits without genuine support. | Separate advertised limits, actual descriptor paths, and functional tests. |
| REQ-104 candidate | Any candidate is isolated, source-built and digest-bound. | Source checks are not game acceptance; REQ-80/S2 admission and later parent-authorized Ode Play remain required. |

### Handoff and corrections

- The warning also existed on prior CLI runs. NMS currently renders and the
  owner reports good gameplay. This is not a proved Ode recipe regression.
- The log identifies MoltenVK 1.4.2. The address-space compilation error and
  unsupported integer-format blending are separate from sampler capacity.
- Historical REQ-N29 / ADR-0031 did not retain a sampler source patch.
  A 17-sampler fixture was assembled, not GPU-qualified. Do not retry a
  numerical limit increase or an argument-buffer value toggle as a fix.
- A CPU/source candidate may be tested here. No game launch is authorized.

### Shader root cause and source candidate

Primary source checked on 2026-10-25:
[SPIRV-Cross PR 2719](https://github.com/KhronosGroup/SPIRV-Cross/pull/2719),
opened 2026-10-20 by Faye Salwin, head
`51e4c6a6cc105fee81afcc0f88ff5e2fa9c8ce1f`, still open/unmerged.
The proposal names NMS terrain tessellation and the same compiler diagnostic.
This is a translator defect, not an Apple D3DMetal compiler-input assumption.
MoltenVK translates the vertex stage to a compute kernel for tessellation.
It lowers the user output block to thread-local storage, but a separate
storage classification still treats scalar stores as device-buffer writes.
That disagreement generates the invalid pointer cast. Builtin outputs have
different handling and must stay unchanged.

The tracked nine-line backport preserves that distinction. The independently
written minimal SPIR-V fixture validates for Vulkan 1.0. The exact pinned
baseline translator emits eight mismatching-address-space errors; the patched
translator emits direct component stores and Metal compilation exits 0.
Both ordinary vertex variants compile and are byte-identical. Builtin
position writes and the final copy of both user output vectors are checked.
No proprietary game shader or account data was uploaded.

MoltenVK `db66022459ffb663aa2b50f6b018bc2e124f5edf` and all seven dependency
Git identities were verified. Only SPIRV-Cross has a tracked source change:
nine added lines in `spirv_msl.cpp`. Its transformed SHA-256 is
`4b28957cfbab01450d218297fb3895b959cbbc74d73da5f1eb6899a6dab2600d`.
The source cache was copied to this owned worktree, never built in place.
Xcode 27.1 (27A9275), x86_64, Release, three build jobs, private Metal API
enabled and automatic signing disabled were used.

Two preparation failures were retained and corrected:

- The CLI CMake configuration requires HLSL/CPP/reflection backends even
  though this regression uses MSL. Re-enabled the required build options.
- The assembler's first compile incorrectly made the API's binary wrapper
  itself const. Removed that qualifier to match the pinned C API signature.

The first full MoltenVK build still had the old dylib digest. Building the
SPIRV-Cross target alone updates its product/staging archive but does not
replace the cached XCFramework consumed by MoltenVK. Copied the newly built
archive into the owned cached XCFramework, then relinked. The resulting
dylib differs from the accepted binary. This correction matters: a successful
Xcode exit alone would have falsely presented the unchanged shader compiler.

Ad-hoc signing used the retained Wine entitlements, `--force --deep --sign -`
and `--options runtime`. No identity/keychain, Gatekeeper, quarantine or global
setting changed. The signed candidate dylib SHA-256 is
`5b1260bab521a90408b0e92420eb695498b5451448441735d8876f02b8458188`.
`lipo` reports x86_64; `otool -L` has no `/usr/local` reference.

### Sampler warning: measured blocker, not a hidden dialog

Primary source checked on 2026-10-25:
[MoltenVK issue 1610](https://github.com/KhronosGroup/MoltenVK/issues/1610),
opened 2022-06-06. Its discussion distinguishes ordinary samplers from
update-after-bind descriptor indexing. The current pinned source, rather
than that older discussion's configuration syntax, governs this candidate.

The new native headless property probe explicitly loads this candidate
dylib with argument buffers and private Metal enabled. It creates an
instance only: no logical device, queue, window, rendering or GPU commands.
Actual reported limits are 16 ordinary per-stage samplers and 500000
update-after-bind samplers / sampler allocations. The higher values are
different properties, not evidence that NMS's startup check is satisfied.
The startup dialog's numeric requirement is still not established.

The source causal chain is:

- `MVKDevice.mm:2430,2890`: ordinary sampler count is fixed at 16.
- `MVKDevice.mm:863,3461`: update-after-bind uses the separate argument-buffer
  allocation limit when Tier 2 is available.
- `MVKDescriptorSet.mm:184-193`: push layouts always disable argument buffers.
- `MVKDescriptorSet.mm:1820-1848`: ordinary and template push writers assert
  that argument buffers are off.
- `MVKCommandEncoderState.mm:937-953`: pushed data is CPU-only storage.
- `MVKPipeline.mm:295-323`: non-argument-buffer bindings enforce individual
  Metal slots, including the 16-sampler limit.
- `MVKDevice.mm:2842,948`: Vulkan 1.4 core push support and its descriptor
  property remain enabled, independently of the extension name.

Consequently, a larger ordinary limit without new push support would be
dishonest. Real push argument buffers need storage, update/template,
command-lifetime and resource-encoding work with regular/push/mixed-layout
functional tests. Disabling the extension alone is insufficient. Withdrawing
core push and reducing the API version is a compatibility reduction, not an
equivalent fix. No such source change or environment toggle was applied.
The warning remains unresolved.

### Focused checks and reproducible local commands

The shader regression and six registry-transformation unit tests pass:

```bash
python3 tests/test_spirv_vertex_output.py \
  --assembler build/req104/spirv-assemble \
  --baseline build/req104/spirv-cross-baseline \
  --patched build/req104/spirv-cross-patched \
  --output build/req104/regression-02
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s tests -p 'test_freeze_nms_shader_candidate.py' -v
```

The assembler was compiled with `clang++ -arch x86_64 -std=c++17 -Wall
-Wextra -Werror`, the copied pinned SPIRV-Tools headers and its existing
source-built `libSPIRVTools.a`. The property probe was compiled with
`clang -arch x86_64 -std=c11 -Wall -Wextra -Werror` and pinned Vulkan headers.
The regression invokes `xcrun -sdk macosx metal -std=macos-metal2.1`.

The dependency target was `SPIRV-Cross-macOS` in
`ExternalDependencies.xcodeproj`; the relink target was
`MoltenVK Package (macOS only)` in `MoltenVKPackaging.xcodeproj`.
Both used `XCODE_XCCONFIG_FILE=build/req104/owned.xcconfig` (absolute path
when invoked), `-jobs 3`, `Release`, and `generic/platform=macOS`.
The new archive SHA-256 is
`b7dfdd453f4846d664c636fc459a1e4220d684b0699643d2d687adcb4ea9756f`.

### Frozen handoff and limitations

`tools/freeze_nms_shader_candidate.py audit` verifies the base registry,
actual source pins, patch, source regression and all hashed external assets.
It copies the source-built install while preserving Apple payload symlinks.
The full 3914-entry inventory differs in exactly
`lib/wine/x86_64-unix/libMoltenVK.dylib`; the source runtime inventory remains
unchanged. The first `win32u.so` rpath is `@loader_path/`, which places this
colocated library before its retained fallback rpaths. Actual Wine loading
of the new candidate is not observed.

Committed evidence lives in
[req104-nms-shader-candidate.json](evidence/req104-nms-shader-candidate.json).
After that evidence is committed, `tools/freeze_nms_shader_candidate.py freeze`
binds the immutable local registry to its producer commit and evidence hash.
It explicitly removes inherited graphics/TLS/smoke successes and labels the
candidate unadmitted. Candidate location:
`build/req104/candidate-01/registry.SOURCE-FROZEN.json`.

This is an early handoff on an actionable sampler implementation blocker,
within the 45-minute budget. The shader defect is reproduced and corrected
in a source-level regression; NMS rendering with this candidate is not proved.
REQ-80/S2 admission and a later parent-authorized real Ode Play are still
required. Integer-format blending remains a separate warning, not fixed here.
No game/prefix/settings/active registry was modified and no game was launched.

## 2026-10-25: REQ-104 owner-authorized sampler output probes

This is a later owner-authorized slice, not an extension hidden inside the
original 45-minute investigation. The parent granted serialized isolated GPU
execution after FH6 exited. No NMS game was launched for these checks. Neither
the frozen shader candidate nor the default runtime was modified.

The exact captured startup dialog contains no numerical sampler threshold.
Primary upstream reports do not establish a requirement of 32. The installed
game executable is not directly readable as a PE image; no protected content
was decrypted or bypassed. The exact NMS threshold remains unknown.

### Oracle and safety boundary

`tests/make_sampler_probe.py` generates three independently validated SPIR-V
fixtures. `tests/vulkan_sampler_render.cpp` runs headless compute sampling:

- Regular: 17 sampler descriptors in one ordinary set.
- Push: 17 sampler descriptors in one push set.
- Mixed: 8 samplers in a push set and 9 in an ordinary set.

Every sampler samples a zero-valued image outside its bounds. Alternating
edge and white-border samplers produce an exact 17-bit mask. The next
dispatch inverts all sampler states. The required outputs are `0xaaaa` and
`0x15555`. The same command buffer is replayed after clearing both output
words, requiring both masks again. Ordinary descriptor sets are distinct
per dispatch; updating a bound ordinary set in place would be an invalid
test. Push state changes are recorded between dispatches.

These are output tests, not on-screen rendering or tessellation tests.
On both libraries the advertised ordinary limit is still 16. The default
runner returns SKIP (77) before logical-device creation. Only the explicit
`--exercise-unsupported` flag permits the diagnostic. Successful output
beyond an advertised Vulkan limit does not make the application conformant
or establish general supported capacity.

### Commands and observed results

Use the existing pinned source dependencies, without installing new tools:

```bash
python3 tests/make_sampler_probe.py \
  --assembler build/req104/spirv-assemble \
  --output build/req104/sampler-render-02
clang++ -arch x86_64 -std=c++17 -Wall -Wextra -Werror \
  -Wno-missing-field-initializers \
  -Ibuild/req104/MoltenVK/External/Volk \
  -Ibuild/req104/MoltenVK/External/Vulkan-Headers/include \
  tests/vulkan_sampler_render.cpp -o build/req104/vulkan-sampler-render
```

For each mode, run the following only with an exclusive GPU slot. The
`LIBRARY` argument must select the exact source-built library under test.
The test harness used an outer 45-second subprocess timeout for each
process, in addition to the runner's 30-second fence timeout.

```bash
MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1 \
MVK_CONFIG_USE_METAL_PRIVATE_API=1 MTL_HUD_ENABLED=0 \
  build/req104/vulkan-sampler-render "$LIBRARY" regular \
  build/req104/sampler-render-02/regular.spv --exercise-unsupported
```

Replace both occurrences of `regular` with `push` or `mixed` for those
variants. Baseline library SHA-256 is `4b4bc6fe5fd68f8e2fda12b6a153e69f838d78f72623d062ebcb42374833a385`;
candidate is `5b1260bab521a90408b0e92420eb695498b5451448441735d8876f02b8458188`.

| Mode | Baseline 170ca | Shader candidate | Replay |
| --- | --- | --- | --- |
| Regular 17 | Exact output PASS | Exact output PASS | Both dispatch outputs exact |
| Push 17 | Pipeline creation FAIL (-3) | Pipeline creation FAIL (-3) | Cannot submit |
| Mixed 8 push + 9 regular | Exact output PASS | Exact output PASS | Both dispatch outputs exact |

The push failure is specific: Metal rejects `array<sampler, 17>` at
`[[sampler(0)]]` with `cannot reserve 'sampler' resource locations at index 0`.
MoltenVK then reports sampler indices 0 through 16 exceed the limit of 16.
This is not the previously fixed thread/device address-space error.

The first fixture attempt omitted the storage-buffer SPIR-V extension and
failed validation before GPU execution. Adding the required extension made
all three fixtures validate. No runtime workaround was used.

Local receipts and per-mode stdout/stderr are in
`build/req104/sampler-render-02/replay-results.json` and adjacent logs.
The exact failing push probe is retained for the next implementation slice.
All probe processes finished, and the GPU slot was explicitly released.

### Bounded implementation consequence

The ordinary argument-buffer path can execute this 17-sampler fixture.
Mixed success only demonstrates 8 direct push samplers plus 9 argument-buffer
samplers, not 17 push samplers. The shared failure on 170ca and the candidate
isolates an existing push representation gap, not a shader-backport regression.

The next implementation would touch at least these source seams:

- `MVKDescriptorSet.mm`: layout mode selection, shared CPU/GPU descriptor
  writers, both push write and push-template paths.
- `MVKCommandEncoderState.h/.mm`: owned push GPU bytes, state copy/replay,
  dirty tracking, immutable snapshots and resource-use tracking.
- The existing command-completion allocator in `MVKCommandBuffer.mm` can
  provide transient storage; reuse it rather than introducing another pool.
- `MVKPipeline.mm`: verify layout resource counts and translation agree
  with the new representation, without changing advertised limits.

This is an estimated 4 to 6 source-file surface plus tests, not a one-line
fix. Before capability changes it needs push-template, partial-update,
resource-lifetime and graphics-stage coverage beyond this compute oracle.
No broad implementation was started in this slice. The startup warning,
unknown game threshold and separate live-game stuttering remain unresolved.

### Parent-authorized push argument-buffer slice

After the red probes, the parent authorized implementation on this owned
branch, local commits only. The limits stay at 16. New tests were added
before the implementation: push template writes, single-element partial
sampler updates, command replay, and an offscreen fragment-stage draw.
Every variant retains the two-state bitmask oracle.

Implementation source is isolated in `build/req104/push-ab-01-source`.
It does not modify the original source cache, frozen shader candidate or
170ca install. A compile-time `REQ104_PUSH_ARGUMENT_BUFFERS=1` enables only
the direct Metal3 push path; encoder-based argument-buffer devices keep
their old push representation. CPU resource tracking is preserved. GPU
bytes are copied into command-completion-owned storage before binding,
and address-dependent auxiliary pointers are rebased in each snapshot.
CPU/GPU host storage is copied when command state is copied.

The first build failed because `MVKSmallVector` deletes same-type copy
assignment. Using its existing iterator `assign` API corrected that compile
error. The Release rebuild succeeded. GPU execution is separately held
until the parent grants the serialized slot.

The parent granted that slot after Forza released it. A fresh process check
found no NMS or Forza game. The isolated suite ran baseline first, then
candidate. All 12 expected outcomes matched: baseline push, template,
partial and graphics fail with direct sampler allocation errors; baseline
regular and mixed pass; all six candidate cases pass. Each successful case
reads exactly `0xaaaa,0x15555` after both original execution and replay.
The default safety guard returns 77 for both libraries before logical
device creation. No NMS launch was performed. The GPU slot was released
immediately after the bounded suite.

```bash
python3 tests/test_sampler_render.py --execute \
  --runner build/req104/vulkan-sampler-render-03 \
  --baseline /path/to/170ca/install/lib/wine/x86_64-unix/libMoltenVK.dylib \
  --candidate build/req104/push-ab-01-source/Package/Release/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib \
  --fixtures build/req104/sampler-render-03 \
  --output build/req104/push-ab-test-01
```

`/path/to/170ca` above denotes the read-only baseline location; the actual
command used the retained baseline install. The committed receipt is
`docs/evidence/req104-push-argument-buffers-tests.json`, SHA-256
`a581f12ea0cebc6ae9eada7b432793925508d557572c8935fe1c487dce0840ef`.
The signed candidate library is SHA-256
`5d8c0af0a40b522134ffe07661544298deb549dadc9203122a4286f72f1ca9de`.
The source delta is four files, 80 insertions and 38 deletions, retained in
`patches/moltenvk/0001-snapshot-metal3-push-argument-buffers.patch`.

This establishes the bounded sampler-state snapshot and replay behavior,
not comprehensive descriptor support. Distinct texture/buffer lifetime
changes and immutable sampler combinations still need wider coverage before
changing any capability. Advertised capacity remains 16. NMS warning-free
startup, the unknown game threshold and performance are not accepted.

### REQ-104 follow-up: resource lifetime and immutable samplers

The parent accepted push-ab-01 as a frozen candidate only and assigned
source-only coverage work while S2 admission and Forza's queued capture run.
The existing candidate stays immutable. No new GPU work or NMS launch is
authorized by this follow-up alone.

Extend the independent runner before changing any advertised limit:

- Replace both texture and storage-buffer bindings between dispatches.
  Use black and white images plus separate output buffers. Require
  `0xaaaa,0x1ffff` and unchanged sentinel words in the unselected buffers.
  Keep Vulkan resources valid through completion and replay; do not use
  illegal early destruction as a lifetime test.
- Exercise immutable standalone samplers in ordinary, push and mixed sets.
  Exercise immutable combined image samplers in ordinary and push sets.
  Require `0xaaaa,0xaaaa` across updates and replay.
- Preserve the original six-mode suite and default limit guard.

The combined-image SPIR-V fixture validates and the extended runner compiles.
These new cases have not executed at this point. Their acceptance requires
the next explicit GPU grant, then exact readback and retained log hashes.

The first conservative higher-limit proposal is 17, not a claim about NMS's
unknown threshold. It matches the width of the existing functional oracle.
Promotion is conditional on closing the new coverage and proving the path
selection invariant. Metal3, Tier 2, enabled argument buffers and native
texture swizzle are necessary gates: layout selection can otherwise fall
back to direct binding. Encoder-based and argument-buffers-disabled devices
must keep 16. Do not increase Metal's direct slot constants.

The source audit also found a query seam that must not be missed:
`getDescriptorVariableDescriptorCountLayoutSupport` subtracts from the
direct Metal sampler count, even when an argument-buffer layout is used.
Any separate promoted candidate must reconcile that query with its selected
representation, and test standalone and combined variable-count bindings.
`getDescriptorSetLayoutSupport` explicitly does not check per-stage limits
under the Vulkan contract; do not turn it into an unrelated validator.
Legacy and Vulkan 1.4 push APIs share the same two internal command classes,
but source convergence alone is not runtime coverage of every entrypoint
or shader stage. No higher-limit candidate is frozen or accepted yet.

### Authorized width sweep and separate 128-gated build

The parent expanded the follow-up to widths 17, 32, 64 and 128, with larger
push widths deferred until their independent push-count bound is justified.
The Apple feature PDF was fetched successfully and inspected with system
PDFKit. Its 2026-05-21 table, page 8, lists 128 AB samplers per stage for
Apple6, 996 for Apple7/8 and 500K for Apple9/10. This is distinct from unique
sampler objects per application. The actual diagnostic identifies an Apple
M5 Max, Apple10 GPU family. Do not infer that every Tier 2 device supports
500K entries.

The first extended runner was accidentally built arm64. Its guard failed
at `dlopen` before device creation against the x86_64 library. Inspection
identified the architecture mismatch; explicit `clang++ -arch x86_64`
corrected it before the authorized sweep.

The sweep then ran 18 modes per library at each width. All 72 source
candidate executions passed their exact readbacks and command replay,
including separate texture/buffer updates, standalone/combined immutable
samplers, and core/KHR/maintenance6 push APIs. Widths above 17 use a weighted
sum of every sampled value rather than overflowing a 17-bit mask.
The 17/32/64 aggregate receipts pass. The 128 aggregate deliberately remains
failed: baseline immutable-combined exposed a redundant standalone image
in that fixture, making 129 image descriptors versus the advertised 128.
The candidate's success on that invalid case is not accepted evidence.
The fixture source now omits that image and its write, reserving binding 1
with count 0. The original receipt remains unchanged for audit.

All four receipts are retained under `build/req104/sweep-01-results-WIDTH/`.
The GPU slot was released immediately after the queued sweep, without any
extra round or NMS launch. The parent directed the corrected combined case
to run with the promoted candidate's next suite, after Forza's capture.

A new isolated source copy, `build/req104/push-ab-02-source`, builds with
`REQ104_SAMPLER_LIMIT=128` in addition to the push snapshot define. It applies
the gated predicate and variable-count query correction described by
ADR-0057. The Release x86_64 build succeeds. It has not executed on a GPU.
The complete variant patch includes the earlier push implementation and
must be applied instead of patch 0001, not on top of it. This build is
source-frozen only; functional acceptance and runtime admission are pending.

### Promoted 128-02 isolated functional result

The parent granted one serialized round after Forza released its capture.
A fresh process check found no NMS or Forza game. The corrected combined
fixture validates, and four source-only fixture invariant tests pass.
The promoted x86_64 runner then produced all 38 expected baseline/candidate
outcomes. All 18 candidate rendering modes pass exact weighted readback
and command replay. The corrected 128 combined fixture has no redundant
129th sampled image.

Legacy properties and properties2 both report 128 ordinary samplers.
`maxPushDescriptors=287`, so the 130-descriptor pure-push layout is within
its independent limit. Standalone and combined variable-count queries
support 128 with maximum 128, and reject 129. A separate instance-only
query with argument buffers disabled reports the unchanged limit 16 and
creates no logical device. No NMS launch occurred; the slot was released
immediately after this round.

The receipt SHA-256 is
`72beaf31e572577e14f0df6306b55c7a405ea6983584bfe5ae874a1773befa1c`.
It is committed as `docs/evidence/req104-sampler-limit-tests.json`.
The source-frozen registry is unchanged, SHA-256
`3b4f31ad8ec93ed55f2efd26e37c059a6904d200ecc2cbff598cffe8b26a1d25`.
Separate acceptance evidence records this later result without rewriting
the original pending-test provenance. Compute and fragment coverage is not
every graphics stage or Vulkan conformance. NMS warning removal and
performance remain unaccepted. Independent S2 admission is the next gate,
followed by a separately authorized single NMS launch.

### 128-02 NMS runtime: performance rejected by owner

S2 admitted the candidate in private admission commit
`3be5c656062fa6e0b5accec7c404b648f30f0d6a`. The parent explicitly granted one
NMS launch. The signed diagnostic CLI was verified as SHA-256
`56b902dc7e74c087a2bcf4f53e004d6ee114a709edf25c27f7c085b68fc91b3f`.
The exact registry inspected admitted/ready, but unqualified. Four current
save files were backed up and verified before launch, with no restoration.

Run `0e1ed18f-e1dc-488a-99f2-1bff6266025d` used the preserved prefix and
existing runtime/shims. `lsof` confirmed the candidate-02 MoltenVK mapping.
Startup reached the save selector without a sampler dialog and without
agent input. The original address-space, shader-library and vertex-pipeline
errors were absent during observation. This does not establish the exact
numeric NMS threshold or comprehensive shader-path acceptance.

The owner reported continued stutter and rejected the experience. Record
**performance FAIL**, not a successful game fix. Loading screenshots showed
7.73 and 8.07 FPS; a later loading transition showed 25.09 and inventory
27.38. These are not comparable in-world baseline frame-time samples.
Historical baseline logs contain no continuous FPS measurements, so they
cannot establish whether earlier working runs also loaded at 7 FPS.
The owner's in-world judgment remains the relevant discriminator.

Nothing is adopted. The parent directed normal quit first, then exactly
one original-170ca launch with the same prefix/save and owner smoothness
judgment. At this entry, normal exit is not yet verified, so no baseline
launch has occurred. A further source-only bisect removes proposal 2719
from a new owned copy and gives it a distinct pipeline-cache UUID namespace,
without deleting user caches. It still needs a rebuilt translator archive,
separate frozen identity, tests and independent admission. The backport is
a hypothesis, not a proven stutter cause.

### Original 170ca baseline: owner-smooth, experiments stopped

After the candidate exited normally, run
`bed6f80e-799c-4dc5-b7e6-9c98d5c83be3` launched the original engine
`calimocho-wine11.20-gptk4b3-tls-vulkan-private` (registry SHA-256
`170ca4ad08a5274b614e74bf740866ef219a97fdc7855270c5d8fa03192ed609`) with the
same prefix and save. `lsof` confirmed the original MoltenVK mapping. No
graphics settings, resolution, cache or save were changed.

The owner judged in-world movement "Smooth again, like the earlier working
run." The original sampler warning dialog is still shown. The run exited
naturally after the owner quit, with CLI exit 0, Wine exit 0 and no signal
sent by the agent. A fresh process check found no NMS, launcher or prefix
wineserver.

The owner then directed: no quick fix, leave it be. The no-2719 bisect copy
was never compiled, frozen or admitted. No candidate is adopted or
deployed. The stutter cause stays unproven; the warning stays unresolved by
owner choice.
