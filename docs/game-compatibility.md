# Game compatibility (Xbox PC via Exodus)

Reported local observations as of 2026-10-24 on Calimocho Wine 11.20 with
Apple GPTK 4 beta 3 through Exodus. A startup or input check is not proof
that an entire game works. Frame rates describe only the observed scene.
The supplied test report groups the first 24 titles as 16 working,
5 partial and 3 failing. Those labels do not erase the limitations below.

| Game | Observed result |
|---|---|
| Abiotic Factor | Opens and responds |
| Bluey's Happy Snaps | Opens and responds across 15 screens |
| Brotato | Opens and responds |
| DEATHLOOP | Opens and responds across 8 screens |
| DREDGE | Reported working |
| Fallout 4 | In-world at 60 FPS; normal quit; mouse look broken |
| Hades II | Opens and responds |
| Hogwarts Legacy | In-world cutscene at 60 FPS |
| Hollow Knight | Reported working |
| Keeper | Menu at 60 FPS |
| Monster Sanctuary | Opens and responds across 15 screens |
| Oblivion GOTY | Opens and responds |
| REPLACED | Opens and responds across 15 screens |
| Stardew Valley | Opens and responds |
| TUNIC | Opens and responds across 4 screens |
| Vampire Survivors | Opens and responds |
| Halls of Torment | Small window, then error exit |
| Inscryption | Window opens; unchanged screen |
| Kingdom Come: Deliverance | No window within 2 minutes |
| Skyrim SE | Stops at hardware-detection dialog |
| Subnautica 2 | Stops at terms screen |
| Balatro | Immediate exit |
| LIMBO | No window; immediate exit |
| Mixtape | Fatal-error crash |

## No Man's Sky

| Runtime | Observed result |
|---|---|
| Calimocho port-11 | Instance creation, then graphics setup fails because Vulkan wideLines is unavailable |
| Calimocho port-11b | Private-Metal source build prepared; native feature/device/presentation qualification pending |
| CrossOver (separate comparison, not Calimocho) | Reported in-world at 51-60 FPS when focused |

Port-11b has not demonstrated an NMS fix. Its build is not native qualification
or launcher admission. The frozen public-API port-11 result remains unchanged.
