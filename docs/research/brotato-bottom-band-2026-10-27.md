# Brotato bottom band on Calimocho 0.1120.4.6, 2026-10-27

Status: analysis from L14's run evidence. Not reproduced or fixed yet.
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
