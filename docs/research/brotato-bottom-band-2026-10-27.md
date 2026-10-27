# Brotato bottom band on Calimocho 0.1120.4.6, 2026-10-27

Status: reproduced and traced (2026-10-27). Cause narrowed, not fixed.
Priority low (coordinator).

## Observation

L14 ran Brotato (Godot 3.6.1, Xbox build) on 0.1120.4.6 through the
Ode CLI on the built-in 1512 × 982 point display (Retina, scale 2). In
gameplay the picture stops short of the bottom. Evidence:
`~/Library/Application Support/L14-WineSampling/runs/brotato-calimocho06/shot-140-play.jpg`.

Measured on that screenshot (3024 × 1964 pixels):

- The picture ends at pixel row 1700, which is **850 points**. A 16:9
  picture as wide as the display is 1512 × 9 / 16 = 850.5 points high.
- Below that, the band is uniform RGB (77, 77, 76). That is 0.3 grey,
  Godot's default clear colour.
- The Metal HUD reports a 1512 × 982 drawable, "Direct" presentation,
  119 FPS.
- The macOS visible frame (without the menu bar and Dock) is 1512 × 889,
  so the band is not the Dock or work-area height.

## Interpretation

Godot draws into the full 1512 × 982 back buffer and clears it to grey,
but lays out its 16:9 viewport from the top instead of centring it with
black bars. So Godot's idea of its window size (16:9) and the size of
the surface it presents (the full display) disagree. Two candidates:

1. **Display-mode emulation in winemac.drv.** Godot's fullscreen asks
   for a display mode. If it got a 16:9 mode that the Mac display
   doesn't have, Wine may report that mode to the game while the window
   still covers the whole screen without scaling.
2. **A window size change the game never saw.** The window was resized
   from 16:9 to full screen (the Mac driver's fullscreen handling), but
   Godot didn't get `WM_SIZE`, so it kept the old viewport.

The quit problem is a different issue. Cmd-Q and `WM_CLOSE` did not end
Brotato on Calimocho, CrossOver 26.3 or gcenx staging 11.18 alike. That
points at the game (Godot's close handling), not at Calimocho.

## Discriminating test (one short Wine slot, no input)

Run Brotato on a fresh prefix with `WINEDEBUG=+macdrv` limited to
display and window events. That needs the diagnostic CLI option L6 is
adding. Record:

- `EnumDisplaySettings`/`ChangeDisplaySettingsEx` calls and the mode set;
- `WM_SIZE` and `WM_WINDOWPOSCHANGED` for the game window;
- the client rectangle from `GetClientRect` against the Mac view size.

If the game set a 16:9 mode, candidate 1 holds. The fix would be in
winemac.drv's mode emulation: scale the drawable, or don't offer
non-native fullscreen modes. If no mode change and no final `WM_SIZE`
appear, candidate 2 holds. A run in windowed mode (Brotato's own
setting) is a cheap control: the band should go away.

## Trace result (2026-10-27)

One run with the diagnostic CLI (`--diagnostic-wine-debug
+pid,+timestamp,+macdrv,+system`, run `fe9dbaef`), fresh prefix, no
input. The band reproduced on the main menu at the same row (pixel 1700
of 1964, RGB 77, 77, 77).

- **Candidate 1 is ruled out.** Brotato never calls
  `ChangeDisplaySettingsEx`. Its only display call is
  `EnumDisplaySettings` with `ENUM_CURRENT_SETTINGS`.
- **The window resize works.** The game window starts as a windowed
  1280 × 720 client area (16:9). Twelve seconds later Godot switches it
  to a borderless popup, and winemac.drv applies the full
  (0,0)-(1512,982) rectangle (`WindowPosChanged`, Cocoa frame
  1512 × 982, not macOS fullscreen).
- So Wine gives the game a correct 1512 × 982 window. The 16:9 picture
  drawn from the top must come from the swap chain or the game: either
  Godot keeps its 16:9 render size and anchors it at the top, or the
  D3D12 swap chain buffers aren't resized and D3DMetal presents them
  top-left. winemac.drv is not the cause; this is not a Calimocho engine
  patch target.
- Quit: in this run, `WM_CLOSE` ended Brotato normally (CLI exit 0,
  Wine exit 0, 16 s after the message). L14's failure was Cmd-Q while
  the game was not frontmost, plus a different harness.

Next discriminator, if anyone needs it: the same title on CrossOver
26.3 (same D3DMetal, different Wine) in the foreground. If it shows the
same band, the cause is D3DMetal or Godot, not Wine.
