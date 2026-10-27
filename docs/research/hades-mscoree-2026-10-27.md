# Hades and mscoree on Calimocho 0.1120.4.6, 2026-10-27

Status: plan (source research). Nothing built or run.

## Problem

Hades (Xbox, product `9P8DL6W0JBB8`) loads
`BasecampBugReporter.Native.dll`, which imports `mscoree.dll`
(`_CorDllMain`). It is a C++/CLI mixed-mode DLL: native imports plus a
CLR header. The engine's default environment sets
`WINEDLLOVERRIDES=mscoree,mshtml=`, which disables `mscoree.dll`, so the
import fails and Hades can't start.

## What 0.1120.4.6 has

- Wine's builtin `mscoree.dll` is in `lib/wine/x86_64-windows/`. It is
  only disabled by the override.
- No Wine Mono. `share/wine` holds only `fonts`, `nls`, `wine.inf` and
  `winmd`. Wine 11.20 expects Wine Mono **11.3.0** (`WINE_MONO_VERSION`).
  It looks for it in `C:\windows\mono\mono-2.0`, then
  `HKCU\Software\Wine\Mono\RuntimePath`, then
  `<WINEDATADIR>\mono\wine-mono-11.3.0` (the engine's own
  `share/wine/mono`), then `/usr/share/wine/mono` and `/opt/wine/mono`.

## Key fact: Mono is not needed to load the DLL

Wine's `_CorDllMain` (`dlls/mscoree/corruntimehost.c`) reads the CLR
header, sets up vtable fix-up thunks and returns `TRUE`. It loads Mono
only when managed code is actually called through those thunks, which
here means when the bug reporter runs (normally after a crash).

## Plan

1. **Stage 1, no Mono (try first).** Add a Hades title profile that
   changes only the override, from `mscoree,mshtml=` to
   `mshtml=;mscoree=b`. The DLL loads and Hades should start. If the bug
   reporter ever runs, its managed part fails instead of the whole game.
   That needs a profile entry in Ode's title profiles (Ode lane) and no
   engine change.
   - Risk: with `mscoree` enabled while the prefix is created or
     updated, `wineboot` offers to install Wine Mono (the "install_mono"
     prompt). The profile should keep the default override for prefix
     setup and set `mscoree=b` only for the game process. Otherwise, set
     `HKCU\Software\Wine\Mono` to point at a folder before setup.
   - Test: one Hades launch to the title, no input, normal quit.
2. **Stage 2, only if Hades calls managed code at start.** Wine Mono
   11.3.0 for x86 (`wine-mono-11.3.0-x86.tar.xz`, 39,412,620 bytes,
   sha256 `54a1b0111c3fe4b785eae688af94d27e64995707ad648b6fee8000381b80d298`,
   released 2026-08-17). Two ways to provide it:
   - **Per-prefix fetch (recommended).** The Hades profile downloads the
     official MSI (`wine-mono-11.3.0-x86.msi`, sha256
     `df2dfc1665c2511882e7cabd56eafd0c0a3d94e5a7e86f969277f6c189d418d3`,
     the same hash Wine 11.20 pins) and installs it into that prefix.
     That is what stock Wine does on first boot. Calimocho redistributes
     nothing, so AGENTS rule 1 ("never ship someone else's binary") is
     not touched.
   - **Bundle in the engine** under `share/wine/mono/wine-mono-11.3.0`
     (about 40 MB compressed). Rule 1 then requires building it from the
     306 MB source tarball, whose build targets Linux. That is heavy and
     not MVP scope. Bundling the upstream binary would need a new ADR
     that relaxes rule 1.

## Licensing (wine-mono `COPYING`)

Mostly MIT, with Mono parts under LGPL or MIT X11. ICSharpCode.SharpZipLib
is GPL with an exception, FNA is MS-PL and MIT, and its native
dependencies are zlib-licensed. Everything is redistributable for
non-commercial use (and commercial use). A bundled copy would need the
notices and an LGPL source offer, as for Wine itself. The per-prefix
fetch avoids redistribution entirely.
