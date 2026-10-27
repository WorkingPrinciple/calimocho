# REQ-104 candidate C: admission note, 2026-10-27

For the S2/REQ-80 admission. Source-frozen and Wine-tested for the
warning only, not admitted, not qualified for performance.

## Identity

| Item | Value |
| --- | --- |
| Engine name | `calimocho-req104-C-pushcache` |
| Registry | `build/req104/frozen/calimocho-req104-C-pushcache/registry.SOURCE-FROZEN.json`, SHA-256 `aa0ee5de38a5b89bc4fcba54d3decd49b8726cd3fdb91cc35db44ea5f1e5e98e` |
| Inventory | `inventory.FROZEN.json`, SHA-256 `69bc59633393a02d83991b3b9dde0ede0806a48ce5e8843c84e5cb9ba6305ddf` |
| Producer | `WorkingPrinciple/calimocho`, commit `109f613062f8ca6d97612bb54eff66edd60c72ce` (evidence), branch `dragoshont-req104-bisect` at `98daef44` |
| Evidence | `docs/evidence/req104-bisect-C.json`, SHA-256 `17f284fa986b1fda3131eed6ee660eb67e591bca40d56c8f1e39dffdeddfc70d` |
| `bin/wine` | `f6d0546fad2d0dafaa09a9fe6cabe75bb070567df6b0933ecd3622dcb6349194` (equal to 170ca) |
| `bin/wineserver` | `e3ec4e7e76cee273f17d5fa3459902642f73d6921e94c576aa74e8cdbdcd7da1` (equal to 170ca) |
| Only changed file | `lib/wine/x86_64-unix/libMoltenVK.dylib`, signed `e58c1cc1580b9d64a944dff10bc254ea9e9bf1cf82151c091eef2c25cc57a1a9` (unsigned build `780c3928…`) |
| MoltenVK source | v1.4.2 `db66022459ffb663aa2b50f6b018bc2e124f5edf` + patches 0002, 0003, 0004; SPIRV-Cross archive byte-identical to 170ca's (`9b0ffcf1…`) |
| Signature | Developer ID Application: Dragos Hont (M62Z4M5EUY), hardened runtime, secure timestamp |
| Environment | as 170ca: `MVK_CONFIG_USE_METAL_ARGUMENT_BUFFERS=1`, `MVK_CONFIG_USE_METAL_PRIVATE_API=1`, `WINEDEBUG=-all`, `WINEDLLOVERRIDES=mscoree,mshtml=` |
| Registry flag | `local_only: true`, integrity scope "unqualified" |

## Evidence so far

- Non-Wine probes (2026-10-26): 128 samplers advertised, 38 of 38
  sampler outcomes, push cost removed in the measured case.
- **Live A/B (2026-10-27, no input, no auto-dismiss).** Both runs used
  clones of the run `26d9c575` prefix, the app CLI with an `--wine`
  wrapper and the registry environment above.
  - Baseline with 170ca's MoltenVK (`4b4bc6fe…`, run
    `1251481c-c788-4824-9183-66c61fd2248d`): the dialog "Graphics Driver
    Error: Your graphics card or driver does not support the number of
    per-stage descriptor samplers…" appeared at 15 s and blocked
    `WM_CLOSE`.
  - C (run `e802f666-5f27-43f1-93b4-235c1cb35dee`): no dialog, normal
    `WM_CLOSE` quit, CLI exit 0, Wine exit 0.

## Not yet proven (admission must keep these open)

- In-world smoothness. 128-02, which shared C's sampler path, was
  rejected by the owner for stutter. C removes the measured per-draw
  push cost, but that is not proof. One owner-judged in-world run on C
  is required, compared with 170ca.
- Address-space pipeline failures are unchanged from 170ca by design.
- Save round trip and quit after loading a save.

## Admission ask

Admit `aa0ee5de` as a candidate-only, unqualified row (like
`d3cfe28a`/`3be5c656` before), so Ode can run it on the NMS title for
the owner's judgment. Keep `170ca4ad` admitted until C passes that
judgment.
