# Tested games

This is the list of games we have tried, on Calimocho and on the engines
that came before it, with what we actually observed. It is the source for
the README and for posts about the project, so keep it accurate: never drop
a game, only move a game up a level when a new test shows it, and record the
date.

## How these were tested

- **Hardware:** Apple M5 Max, macOS 27.0.
- **Games:** Xbox PC (Microsoft Store / Game Pass) versions, launched through
  Xode, each in its own fresh Wine prefix.
- **Engine:** Calimocho development builds (Wine 11.x with Apple D3DMetal
  4.0 beta 3), 24–25 October 2026. These tests ran **before** engine
  release `11.20-4.0b3-01`; re-check a game on the current release before
  calling it supported there.
- **FPS figures** come from Apple's Metal performance HUD during the test.
  They are observations from one session, not benchmarks.

### What the levels mean

| Level | Meaning |
|---|---|
| **Plays** | We reached actual gameplay, or the maintainer played it and confirmed it works. |
| **Menu** | The game reaches its title screen or main menu; gameplay was not verified. |
| **Opens** | The game opens and responds to input; we did not reach gameplay. |
| **Blocked** | The game starts but stops at a specific point before gameplay. |
| **Doesn't run** | The game exits or crashes before it is usable. |

## Plays

| Game | API | What we saw |
|---|---|---|
| No Man's Sky | Vulkan | In-world gameplay; the maintainer played and quit normally. One "descriptor samplers" warning at start. |
| Forza Horizon 6 | DX12 | Driving gameplay; Xbox controller works. Needs Forza-specific workarounds that are off for every other game. Periodic stutter: about one long frame (100–500 ms) every 1–2 seconds. |
| Hogwarts Legacy | DX12 | In-world at 60 FPS. |
| Valor Mortis | DX12 | In-world, 60 FPS after lowering some graphics settings (exclusive fullscreen; medium shadows, view distance, foliage, effects and shading; motion blur off). About 26 FPS before. |
| Beast of Reincarnation | DX12 | Maintainer confirmed. 29–60 FPS in game, typically 48. |
| Fallout 4 | DX11 | In-world at 60 FPS; played and quit normally. Known issue: mouse look doesn't work. |
| Neon Abyss 2 | DX11 | Gameplay at 60 FPS. |
| Final Fantasy IV | DX11 | In-game story scene at 60 FPS. |
| Quake | — | 59.5 FPS in game. |
| A Game About Digging A Hole | — | Maintainer confirmed. 43–59.5 FPS in game, median 59. |
| Echo Weaver | — | 55–60 FPS in game, median 59. |
| Luna Abyss | — | Maintainer confirmed. 49–60 FPS, typically 52. |
| Dishonored: Definitive Edition | — | Maintainer confirmed. |
| DREDGE | — | Maintainer confirmed. |
| Hollow Knight | — | Maintainer confirmed. |
| Deep Dish Dungeon | — | Maintainer confirmed. |

## Menu

| Game | API | What we saw |
|---|---|---|
| DIRT 5 | DX12 | Title screen in 19 s at 250–330 FPS; the maintainer reached the menu. Gameplay not verified. |
| DOOM 64 | DX11 | Title screen at 59 FPS. |
| Keeper | DX12 | Main menu at 60 FPS. |

## Opens

Abiotic Factor, Bluey's Happy Snaps, Brotato, DEATHLOOP, Hades II,
Monster Sanctuary, Oblivion GOTY, REPLACED, Stardew Valley, TUNIC,
Vampire Survivors.

## Blocked

| Game | Where it stops |
|---|---|
| The Witcher 3 Remastered | Crashes about 24 s in, during input setup. Wine's Xbox GameInput library is a stub and the game has no fallback. |
| Forever Ago | Hangs on the van loading screen; an Xbox service call never finishes. |
| Subnautica 2 | Stops at the terms screen; Agree doesn't work. |
| Chained Beasts | "Failed to initialize platform services". |
| Skyrim Special Edition | Stops on the "Detecting Video Hardware" dialog. |
| Halls of Torment | Opens a small window, then exits with an error. |
| Inscryption | Window opens, but the screen doesn't change. |
| Kingdom Come: Deliverance | No window within 2 minutes. |

## Doesn't run

| Game | What happens |
|---|---|
| Balatro | Exits right away. |
| LIMBO | No window; exits right away. |
| Mixtape | "Fatal error" crash inside the game. |

## Earlier engines (CrossOver or free Wine/GPTK recipes), 22–23 October 2026

Before Calimocho, these 12 titles passed a stricter test on an earlier
engine: actual gameplay, a normal quit, a fresh relaunch, and progress kept
across that relaunch. Each result holds only for the exact engine and recipe
it was recorded on; it doesn't carry over to Calimocho or to other engines.
Where a game's Calimocho result above differs, both are kept.

| Game | Earlier-engine result |
|---|---|
| Minecraft: Java Edition + Minecraft Launcher | Plays. Native Mac launcher and game, not Wine. World kept after relaunch. |
| No Man's Sky | Plays. Separate results on CrossOver and on free Wine with GPTK 3; counted once. |
| Hogwarts Legacy | Plays, save kept (accepted with a cave-checkpoint exception). |
| Hollow Knight: Voidheart Edition | Plays, progress kept. |
| Hades II | Plays, progress kept. |
| Halls of Torment | Plays, progress kept. (On Calimocho: Blocked, see above.) |
| Mixtape | Plays, progress kept. (On Calimocho: Doesn't run, see above.) |
| Abiotic Factor | Plays; world, character and an inventory marker kept. |
| Monster Sanctuary | Plays, progress kept. |
| TUNIC | Plays; Wooden Stick kept after relaunch. |
| Brotato | Plays; Chunky unlock kept after relaunch. Also verified through Xode's Play button. |
| Stardew Valley | Plays; Day 2 and seeds kept after relaunch. |

## Engine release checks, 26 October 2026

Short checks on the release builds, run from the command line in a fresh
prefix: launch, wait about 60 seconds, then close the game normally. They
show whether a game still starts on a release; they don't replace the
results above. Release -04 contains the same binaries as -03, so -03 results
apply to it.

| Game | Release | What we saw |
|---|---|---|
| Brotato | 11.20-4.0b3-02 and -03 | Menu rendered, still running at 60 s, clean quit. |
| Halls of Torment | 11.20-4.0b3-02 and -03 | Menu rendered, still running at 60 s, clean quit. Better than the earlier Calimocho result above. |
| Vampire Survivors | 11.20-4.0b3-01, -02 and -03 | Window opens, then the game exits with code 3 after about 20 s. The earlier Calimocho development engine does exactly the same with this command-line check, so the release isn't the cause. The likely difference is the launch method: this check runs without a signed-in Xbox user, while the result above came from a launch through Xode. |
| Balatro | 11.20-4.0b3-01, -02 and -03 | No window; exits after about 30 s. The earlier development engine does the same. |
| Forza Horizon 6 | 11.20-4.0b3-01 with the Forza-only workarounds (the set used in -02) | Title screen, then Continue with existing progress into free roam ("Explore Japan"). Exit Game from the menu quit cleanly. Driving input wasn't checked in this run. |
| Forza Horizon 6 | 11.20-4.0b3-04 with the Forza-only workarounds | Driver warning, then title screen, then a clean quit. Start Game showed "Sign In Required"; the -01 build now shows the same message, so this points to the Xbox account state, not the engine. Gameplay on -04 is not verified yet. |
| Brotato, Halls of Torment | 11.20-4.0b3-06 | Window rendered, still running until a normal close, clean exit. |
| Vampire Survivors, Balatro | 11.20-4.0b3-06 | Unchanged from earlier releases: Vampire Survivors exits with code 3 after about 20 s; Balatro shows no window. |
| Forza Horizon 6 | 11.20-4.0b3-06 with the Forza-only workarounds | Sign-in, Continue, story scene, then driving in free roam (about 110 mph). Uses Wine's own windows.web, with no Windows copy needed. On a prefix last used by an older release, the first -06 launch updates the prefix and replaces the Forza graphics shim (`d3d12.dll`); the game then shows "graphics card not supported" (FH206). Copying the shim back fixes it, so the shim has to be re-copied after every prefix update. |

## Counts (24–25 October 2026)

41 games tried on Calimocho: 16 play, 3 reach the menu, 11 open, 8 are
blocked and 3 don't run. Well Dweller was tested but its result hasn't been
reviewed yet. Including Minecraft Java from the earlier-engine section, 42
different titles have been tested.
