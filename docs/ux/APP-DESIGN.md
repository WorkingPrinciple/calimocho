# UX: Calimocho.app design

> The Phase 3 SwiftUI app. Menubar item, first-run wizard, hidden
> power-user menu, About box, error dialogs.
>
> Companion to USER-JOURNEY.md (the flows) and SPECS.md (the contracts).

## App identity

- Bundle ID: `com.dragoshont.calimocho`
- Display name: `Calimocho`
- Category: `public.app-category.utilities`
- Icon: a stylized wine glass (we'll generate a placeholder for v0.5; a
  designed icon if/when someone donates art)
- Window mode: **menubar only**, no Dock icon, no main window
- Auto-launch at login: opt-in via menu toggle

## Menubar item

### Default state

Icon: 🍷 (16×16 template image, monochrome, follows menubar tint)

Click → dropdown menu (the ONE visible action):

```text
   🍷 Calimocho v1.0.0

   ▶ Open Steam for Windows
   ────────────────────────
   About Calimocho
   Quit Calimocho
```

That is the entire menu in normal mode. Three lines.

### State-aware variations

| Engine state | Top menu item |
| --- | --- |
| Steam not installed yet | `▶ Install Steam` |
| Steam installed, not running | `▶ Open Steam for Windows` |
| Steam launching | `⌛ Starting Steam...` (disabled) |
| Steam running, focused | `Bring Steam to Front` |
| Steam unresponsive | `⚠ Restart Steam` + warning color |
| Update available | adds `⬇ Update to vX.Y.Z` row below the separator |

### Option-click (held when clicking icon)

Reveals the power-user menu. macOS convention; users discover it once
they need it.

```text
   🍷 Calimocho v1.0.0 (debug menu)

   ▶ Open Steam for Windows
   ────────────────────────
   📂 Open Calimocho folder in Finder
   📜 View logs
   🔄 Reinstall engine
   🗑 Reset Steam bottle...
   🔍 Check for updates
   🧪 Run self-test
   📦 Generate diagnostic bundle
   ────────────────────────
   ⚙ Settings...
   ────────────────────────
   About Calimocho
   Quit Calimocho
```

### Settings window (opened via the debug menu)

Small NSWindow, two tabs:

**General**:
- ☐ Launch Calimocho at login
- ☐ Show update notifications
- ☐ Send anonymous crash reports (default OFF, always OFF unless user
  flips it; even if flipped, they go to a self-hosted Sentry not a
  third party)
- "Engine version: 11.0+cw26.1 (built on Jun 2 2026)"

**Advanced**:
- Bottle list (currently always exactly: STEAM)
- Per-bottle config preview (read-only, points users to the JSON file
  if they want to edit)
- Reset to defaults button

That's the whole Settings surface. We do not expose Wine flags, DLL
overrides, or Winetricks. Users who need that level of control should
use CrossOver instead.

## First-run wizard

Shown once, when Calimocho.app launches and finds no Steam bottle.

### Window characteristics

- Title: "Welcome to Calimocho"
- Modal? **No.** Window is a normal floating window; user can quit it.
- Width: 540pt
- Height: dynamic per step (300pt to 480pt)
- Layout: one step per screen, with previous/next/skip buttons

### Step 1: Welcome

```text
   ╭────────────────────────────────────────────────────────╮
   │ 🍷                                                     │
   │                                                        │
   │ Welcome to Calimocho                                   │
   │                                                        │
   │ Calimocho lets you run Steam for Windows on your Mac, │
   │ so you can play Windows-only games like Subnautica 2. │
   │                                                        │
   │ It uses CodeWeavers' Wine engine, Apple's Game        │
   │ Porting Toolkit, and our own bottle layout to do it.  │
   │                                                        │
   │ This wizard takes about 5 minutes.                    │
   │                                                        │
   │ ⓘ Calimocho is free, non-commercial. If you can      │
   │   afford it, please consider buying CrossOver         │
   │   instead — they fund the Wine engine this all       │
   │   builds on.                                           │
   │   [Learn more about CrossOver]                        │
   │                                                        │
   │                  [Skip Setup]    [Continue]            │
   ╰────────────────────────────────────────────────────────╯
```

The CrossOver mention is in the **first window of the app**. Users see
the homage before they see any feature.

### Step 2: System check

```text
   ╭────────────────────────────────────────────────────────╮
   │ System check                                           │
   │                                                        │
   │ ✓ macOS 15.7 (supported)                              │
   │ ✓ Apple Silicon (M1 Max)                              │
   │ ✓ 615 GB free (need at least 20 GB)                   │
   │ ✓ Network reachable                                    │
   │                                                        │
   │ Everything looks good.                                 │
   │                                                        │
   │                  [Back]              [Continue]        │
   ╰────────────────────────────────────────────────────────╯
```

If something fails:

```text
   ✗ Only 8 GB free (need at least 20 GB)
     [Open Storage Settings]
```

Wizard does not let the user continue until criteria are met.

### Step 3: Install Steam

```text
   ╭────────────────────────────────────────────────────────╮
   │ Install Steam                                          │
   │                                                        │
   │ Calimocho will:                                        │
   │  1. Create a Steam bottle (Wine prefix for Steam)     │
   │  2. Download SteamSetup.exe from Steam's CDN (3 MB)   │
   │  3. Run the Steam installer inside the bottle         │
   │                                                        │
   │ Total time: ~3 minutes                                 │
   │ Total download: ~3 MB now, then ~300 MB once Steam   │
   │  runs and updates itself                              │
   │                                                        │
   │ ⓘ Already have Steam installed elsewhere?            │
   │   You'll still need a separate Windows-Steam install  │
   │   inside Calimocho's bottle. Mac Steam and Windows    │
   │   Steam run side by side.                             │
   │                                                        │
   │                  [Back]    [Install Steam]             │
   ╰────────────────────────────────────────────────────────╯
```

### Step 4: Progress

```text
   ╭────────────────────────────────────────────────────────╮
   │ Installing Steam                                       │
   │                                                        │
   │ ✓ Bottle created                                       │
   │ ✓ Downloaded SteamSetup.exe (3 MB)                    │
   │ ⌛ Running Steam installer inside bottle...           │
   │   [████████░░░░░░░░░░] 40%                            │
   │                                                        │
   │ This usually takes 1-3 minutes. Don't quit Calimocho │
   │ during install.                                        │
   │                                                        │
   ╰────────────────────────────────────────────────────────╯
```

### Step 5: Done

```text
   ╭────────────────────────────────────────────────────────╮
   │ ✓ Steam is installed.                                  │
   │                                                        │
   │ Click below to launch Steam. Sign in with your Steam  │
   │ account; the Steam client will update itself and then │
   │ show your library.                                     │
   │                                                        │
   │ Already know what you're doing? Click 🍷 in the      │
   │ menubar any time to launch Steam.                     │
   │                                                        │
   │            [Launch Steam Later]   [Launch Steam Now]   │
   ╰────────────────────────────────────────────────────────╯
```

Click "Launch Steam Now" → wizard closes, calls into SteamLauncher,
Steam appears. Future launches use the menubar icon.

## About box

Standard macOS About panel (NSAboutWindow), with:

```text
   🍷
   Calimocho
   v1.0.0 (engine: Wine 11.0 + GPTK 3.0)

   A personal recipe for the Windows games I miss on my Mac.

   Built on:
   • Wine 11 (CodeWeavers patches, LGPL)
   • Apple Game Porting Toolkit (D3DMetal, non-commercial)
   • MoltenVK (KhronosGroup, Apache 2.0)

   If you can afford it, please buy CrossOver to support
   the people who make this possible:
   [codeweavers.com/crossover]

   Donate to Wine: [winehq.org/donate]

   Source and license: [github.com/dragoshont/calimocho]
```

Links open in default browser.

## Error dialogs

Standard NSAlert pattern. Title, message, 2-3 buttons, optional secondary
text. All errors include a "Diagnose" button that generates a redacted
zip and opens it in Finder.

Example:

```text
   ╭──────────────────────────────────────────────╮
   │  ⚠ Steam can't start                         │
   │                                              │
   │  The Wine engine timed out waiting for       │
   │  Steam to show its main window.              │
   │                                              │
   │  Reason: steamwebhelper crashed (exit code   │
   │  5). This is a Wine/Steam compatibility      │
   │  issue.                                      │
   │                                              │
   │  Fixes to try in order:                      │
   │  1. Restart Steam with extra flags           │
   │  2. Reset Steam UI cache (~/Library/...)     │
   │  3. Try CrossOver (paid, but maintained)     │
   │                                              │
   │   [Diagnose]  [Try CrossOver]  [Restart]    │
   ╰──────────────────────────────────────────────╯
```

The CrossOver button is always available on a failure. If we cannot fix
it, we recommend the working alternative.

## Accessibility

- Full VoiceOver labels on every menu item and dialog button
- Reduce Motion respected (no animated dock bounce, no spinning icons
  beyond standard NSProgressIndicator)
- High Contrast Mode respected (icon is template image; system colors
  for menu text)
- All keyboard navigable; the menubar dropdown can be opened with
  Cmd+Shift+the menubar key combo Calimocho registers (if user assigns
  one in Settings → Keyboard)

## Internationalization

- v1.0 ships English only
- Strings live in `Localizable.strings`, ready for translation
- Community PRs welcome for additional languages but not solicited
- No telemetry on language usage

## What we will NOT add to Calimocho.app

These are deliberate omissions, not TODOs:

- No game library UI. Use Steam.
- No bottle manager UI. There is one bottle.
- No Wine version picker. There is one Wine version.
- No DXVK/D3DMetal toggle. The choice is fixed at install time.
- No CrossOver-style "Install Software" wizard. Steam is the only thing.
- No tray notifications for "Steam download finished" etc. Use Steam's
  own notifications.
- No achievement tracker, no playtime tracker. Steam does that.
- No mod manager. Mods are an advanced feature; users do them manually.
- No first-launch animation or splash screen.
- No telemetry, anonymous or otherwise. Privacy by absence.

These omissions are the **product**. Calimocho is the smallest possible
shim between "user wants to play a Windows game" and "the game runs".
