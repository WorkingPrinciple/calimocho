# Hades on Calimocho: title profile proposal, 2026-10-27

For L8 (Ode title profiles). Proven to the title screen only.

## Proposal

| Field | Value |
| --- | --- |
| Product | `9P8DL6W0JBB8` (Hades, Xbox) |
| Executable | `Hades.exe` (from `MicrosoftGame.config`) |
| Engine | the admitted production release engine (tested on `calimocho-11.20-4.0b3-06`, registry `7c65248f…`) |
| Game recipe | `hades-mscoree-v1` (L6 CLI `01b333e7` and later) |
| Effect | `mscoree=b` for the game process only. Prefix creation, update and wineboot keep `mscoree` disabled, so no Wine Mono prompt. |
| Wine Mono | not needed for start-up. Fetch per prefix (stage 2) only if a later run shows managed code at start. |

## Why

`BasecampBugReporter.Native.dll` is a C++/CLI mixed-mode DLL that
imports `_CorDllMain` from `mscoree.dll`. The engine default disables
`mscoree`, so the import fails. Wine's builtin `_CorDllMain` sets up the
vtable fix-ups and returns without loading Mono.
See `docs/research/hades-mscoree-2026-10-27.md`.

## Evidence

Run `4e43a5ce-d981-41a4-bbbe-214e0b36488b`, 2026-10-27, fresh prefix, no
input, `--diagnostic-wine-debug +loaddll,+mscoree,warn+gdkc,warn+xgameruntime`:

- builtin `mscoree.dll` loaded, then `BasecampBugReporter.Native.dll`
  (native) and `_CorDllMain(…, 1, …)`;
- zero Mono references, no `install_mono` prompt;
- the "Press Any Button" title rendered;
- `WM_CLOSE` quit, CLI exit 0, Wine exit 0.

## Open

- Sign-in: the Xbox user step fails with `0x8007000d` at the RPS ticket
  bridge (`load_game_config`, legacy config without `MSAAppId`). L12 owns
  this (REQ-32).
- Gameplay, saves and controller are not tested.
