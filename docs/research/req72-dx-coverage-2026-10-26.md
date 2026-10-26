# REQ-72 DX11 and DX12 coverage on Calimocho, 2026-10-26

Status: engine-side coverage analysis. REQ-72 is blocked on REQ-71
(route and provenance), which is Ode work, not engine work.

## Rendering paths in the shipped engine (0.1120.4.6)

| API | Path | Source in this repository | Evidence |
| --- | --- | --- | --- |
| Direct3D 12 | Apple D3DMetal `d3d12.dll`, unmodified (GPTK 4.0b3) | `tools/port_d3dmetal.py`, patch 0001 (Wine-side integration) | Hogwarts Legacy run `a8e31dab…`; FH6 free roam on -06 |
| Direct3D 12 + gaps | Highball tsshim in front of Apple's `d3d12.dll`, FH6 only | `versions.json` `tsshim`, ADR-0079 | FH6 title and free roam on -06 |
| Direct3D 11 | Apple D3DMetal `d3d11.dll` through patch 0001 (no 0004 shim) | patch 0001 | Fallout 4 run `29b18055…` (D3D11 renderer/module evidence); owned D3D11 parity probe, 120/120 Presents |
| Direct3D 9/10 | Wine's wined3d | upstream Wine 11.20 | no D3D9/10 title recorded |
| Vulkan | winevulkan + MoltenVK 1.4.x (source-built) | `tools/build_moltenvk.py` | NMS on 170ca |

## Gaps that matter for REQ-72

1. **Both titles have rendered, but not under REQ-71 provenance.** The
   Hogwarts (DX12) and Fallout 4 (DX11) scenes came from controlled
   runs that needed non-ordinary cleanup. The engine side is done; the
   row waits on Ode's route evidence.
2. **DX11 on D3DMetal has less evidence here than DX12.** One title
   (Fallout 4) and one probe. A title that fails there has no fallback, because we don't ship DXVK or DXMT. Adding DXMT (FOSS,
   Metal-based D3D11) is the obvious extension, but it is a new
   renderer, so it needs an ADR and is not MVP scope.
3. **No D3D9/D3D10 title evidence.** wined3d is present but untested on
   any owned D3D9/10 title.
4. **Feature flags.** `D3DM_SUPPORT_DXR` (ray tracing) and
   `D3DM_ENABLE_METALFX` are not in the engine default environment.
   FH6 runs with `D3DM_MTL4=0`. Each is title-profile scope.

## What the engine lane can still do for REQ-72

- Nothing blocks on the engine for the two candidate titles. When
  REQ-71 is ready, re-run Hogwarts and Fallout 4 on the latest admitted
  engine through the Ode route, one at a time in the Wine slot, with
  saves backed up, and record the exact engine ID, registry digest and
  renderer module hashes.
- The REQ-120 NVAPI stub doesn't affect these titles: it is copied only
  by the FH6 profile.
