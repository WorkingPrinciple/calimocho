# ADR-0088: Follow upstream wine!10258 for GameInputCreate

Status: Accepted (source); engine build waits for the Witcher 3 cause (REQ-158)
Date: 2026-10-27

## Context

Witcher 3 crashes on Calimocho with a read at address 0x118 right
after it loads `GameInput.dll` (REQ-140, L20 evidence). Wine 11.20's
`GameInputCreate` returns `E_NOTIMPL` and never writes the output
pointer, so it stays whatever the caller put there (`NULL` if the
caller zero-initialised it). The most likely cause is that the game
ignores that HRESULT and calls through the unwritten pointer. L20's two discriminator runs decide
whether GameInput is really the cause.

We checked other implementations on 2026-10-27:

| Source | `GameInputCreate` |
| --- | --- |
| Wine master, CrossOver 26.3 source, wine-staging | `E_NOTIMPL` stub |
| Proton `proton_11.0` and `proton_10.0` | `E_NOTIMPL` stub |
| Proton `bleeding-edge` | Real object with device enumeration, but a HACK limits it to one Steam game (CW-Bug-Id 24584) |
| Upstream merge request wine!10258 (Alistair Leslie-Hughes, open since 2026-03-06) | Returns one shared v0/v1/v2 object; its methods still return `E_NOTIMPL`; includes conformance tests |

A FOSS implementation exists upstream, so
[ADR-0017](0017-follow-when-foss-exists-lead-when-only-paid-exists.md)
says we follow it rather than write our own.

## Decision

1. Patch 0020 is wine!10258 as published (its three commits, authors
   and messages unchanged). It applies cleanly after 0001 to 0019.
2. Patch 0021 (ours, two lines) makes the v2 `GetCurrentReading` and
   `RegisterDeviceCallback` stubs clear `*reading` and `*token`. In
   wine!10258 they return `E_NOTIMPL` without writing them, unlike the
   v0 and v1 versions of the same methods (review `c2a68496`, F1). It
   is pinned in `versions.json` (sha256 `ba6c63fd...`) but **not in
   `series`**. It goes into a build only if L20's `+gameinput` trace
   shows Witcher 3 using the v2 interface. The same fix is drafted as
   review feedback for the merge request.
3. `tests/wine/test_gameinput.py` compiles the real `gameinput.c` on
   the host and calls it. It defines the GameInput IIDs itself, so
   stock Wine links and fails on behaviour.
   - `GameInputCreate` returns `S_OK` and one shared object; reference
     counting and `QueryInterface` work; unknown IIDs give
     `E_NOINTERFACE`.
   - v0 `GetCurrentReading` fails and leaves the reading `NULL`.
   - The v2 test checks that the two v2 stubs clear their outputs. It
     fails with 0020 alone (pass `--without-0021` to mark it an
     expected failure) and passes with 0021.

   Results: stock 11.20 fails 3/3 on assertions; 0001-0020 passes 2/3
   (v2 test red); 0001-0021 passes 3/3.
4. Other Calimocho behaviour (for example
   `GAMEINPUT_E_READING_NOT_FOUND` from reading calls, or callbacks
   that register cleanly) is added only if Witcher 3 still fails with
   0020 (and 0021 if needed).

## Consequences

- With 0020 the v0 and v1 stubs return `E_NOTIMPL` and clear their
  output arguments. Only with 0021 do the v2 stubs do the same. That
  does not make every method safe: a caller that ignores the `HRESULT`
  and uses a cleared reading or device still dereferences `NULL`.
- Games that only need a non-`NULL` GameInput object get one. Games that
  need devices or readings still get no controller input through
  GameInput.
- The patch only touches `configure.ac` for its test directory. The
  shipped `configure` is not regenerated, and the engine is built with
  `--disable-tests`, so the conformance test is not built in-tree.
- Known limitations of wine!10258, kept as published (rule #4, follow
  upstream): the shared object is not synchronised. Two first calls at
  the same time can create two objects (one leaks), and a `Release` to
  zero racing a `GameInputCreate` `AddRef` is a use-after-free. `out`
  is not checked for `NULL`. These are candidates for review feedback
  on the merge request, not a local change.
- When wine!10258 lands in a Wine release we rebase on, patch 0020 is
  dropped.
- Wiring GameInput to real pads (SDL or winebus) would follow Proton's
  device-enumeration commits, without its per-game HACK. That is
  separate work.
