# ADR-0085: SDL controller bus in winebus.sys

Status: Accepted (source); in-game check pending (REQ-126)
Date: 2026-10-27

## Context

Calimocho engines up to -07 build `winebus.sys` without SDL. Wine's
configure never found SDL2, so `winebus.so` says "SDL support not
compiled in!" and the IOHID bus is the only controller path.
Patches 0004, 0015 and 0016 were needed just to make the owner's
Xbox One S pad (045e:0b20, Bluetooth LE) usable on that path, and no
in-game check has passed yet.

Every other macOS Wine distribution we checked uses SDL for
controllers: CrossOver 26.3 (SDL2 2.30.12), Highball (SDL2 2.32.10),
gcenx builds (`--with-sdl`) and the Wineskin/Sikarugir engines. SDL
handles Bluetooth Xbox pads with its HIDAPI driver (including rumble)
and wired first-party pads through Apple's GameController framework.
This is the FOSS path CodeWeavers already ships, so
[ADR-0017](0017-follow-when-foss-exists-lead-when-only-paid-exists.md)
says we follow it.

The research behind this decision is REQ-126 note
`req126-controller-research.md` (dragos-core ledger).

## Decision

1. `tools/build_sdl.py` builds SDL2 2.32.10 from its release tarball,
   pinned in `versions.json` (`sdl_source`, sha256 `5f5993c5...`, the
   GitHub release digest). x86_64, shared only. Joystick, haptic,
   HIDAPI and the MFi (GameController) driver stay on. Static, X11,
   libusb and libiconv are off. The build fails if the library links
   anything outside `/usr/lib` and `/System/Library`, or if
   GameController is not linked.
2. We use monolithic SDL2, not SDL3 with sdl2-compat. That matches
   CrossOver and avoids the failure Highball hit with sdl2-compat
   (wrong `libSDL3` file name, a hidden error dialog in `winedevice`,
   no controller at all).
3. `tools/release_engine.py` passes `--sdl`, configures Wine with
   `--with-sdl` (configure now fails if SDL2 is missing) and pins
   `SONAME_LIBSDL2` to `@rpath/libSDL2-2.0.0.dylib`. After install it
   refuses a `winebus.so` that still lacks the SDL bus. Assembly
   bundles `libSDL2-2.0.0.dylib` next to the other dependencies with an
   `@rpath` id, and copies SDL's `LICENSE.txt` (zlib).
4. Patch 0004 stays. When SDL loads, upstream logic drops IOHID
   gamepads, so there are no duplicate pads. When SDL fails to load,
   0004 keeps the IOHID gamepads, and 0015/0016 still apply to them.
5. Patch 0017 adds 045e:0b21 (Adaptive) and 045e:0b22 (Elite 2), the
   other Bluetooth LE Xbox pads in SDL's `usb_ids.h`, to
   `is_xbox_gamepad` for the IOHID fallback path.

## Consequences

- The engine grows by one zlib-licensed dylib (about 1.7 MB before stripping). The
  `release_engine.py` commands now need `--sdl`.
- Controller bugs on the SDL path match CrossOver's, so they can be
  routed upstream (SDL or WineHQ) instead of to our own patches.
- Rumble over Bluetooth should work through SDL HIDAPI. Wired
  first-party pads go through GameController, which cannot rumble on
  macOS (SDL issue #14800).
- GameInput is still a stub in Wine, CrossOver and Calimocho. Titles
  that only read GameInput (possibly Forza Horizon 6) still see no
  pad. That needs its own decision.
- Not done: the descriptor-driven remap (research R3), third-party
  wired GIP pads (R4) and GameInput (R5).
- Acceptance needs the owner's in-game check with a real pad. A
  build and these unit tests do not prove the pad works in a game.

## Result (local build, 2026-10-27)

- `-07-pad` was built from commit `32c9776`: Wine 11.20 with patches
  0001 to 0018, plus SDL2 2.32.10. Configure selected
  `SONAME_LIBSDL2 "@rpath/libSDL2-2.0.0.dylib"`. `winebus.so` imports
  the SDL calls and no longer says "SDL support not compiled in".
- Hashes: the built `libSDL2-2.0.0.dylib` (before stripping and
  signing) is `58bb0307...`. The shipped, signed copy is
  `658aeb57ad29f736540d2e6bcc34c4351635f1ac9524ab0b48c5e72ef93192ed`.
  `calimocho-engine.json` is written before signing, so it records
  the SDL version only. The signed hash of every shipped file,
  including this dylib, goes into `MANIFEST.sha256` at `package` time
  and into the release notes.
- With SDL loaded, the owner's pad uses the SDL bus. Patches 0015,
  0016 and 0017 now apply only on the IOHID fallback path.
- Follow-up for the next engine build (review `fe009cf0`, LOW): turn
  off SDL video, render and audio in `sdl_source.configure_flags`,
  then check that HIDAPI and the MFi driver still link
  (GameController in `otool -L`) and that a pad still enumerates.
  This is not done here, because changing the pins would no longer
  describe the `-07-pad` artifact.
