# REQ-104 bisect: analysis and next run, 2026-10-26

Status: analysis of the signed, frozen bisect candidates on branch
`dragoshont-req104-bisect` (`98daef44`, tree `a528dadf`). No NMS run
has happened on A, B or C yet. Owner direction COR-241 still applies:
"if there is nt a quick fix leave it be". Candidate C is the quick fix
to try once. If it stutters, we drop the warning fix.

## What we know

| Engine | Sampler limit | PR 2719 shader fix | NMS result |
| --- | --- | --- | --- |
| 170ca (admitted) | 16 | no | smooth (owner, runs `bed6f80e`, `26d9c575`); warning shown |
| 128-02 | 128 | yes | no warning; owner rejected for stutter (run `0e1ed18f`) |
| A | 128 | no | not run |
| B | 16 | yes | not run |
| C | 128 + push snapshot reuse (0004) | no | not run |

128-02 changed two things at once, so its stutter has two suspects.

## Root-cause candidates, ranked

1. **The push argument-buffer path (patch 0002) rebuilt the push
   buffer on every draw.** This is measured, not guessed. In A,
   `bindMetalResources` clears the "already bound" bit on every draw and
   dispatch. Each bind then allocates a temporary Metal buffer,
   registers a completion handler, copies the push bytes and marks every
   push resource resident again, once per shader stage. The probe
   measured about 1.05 µs extra per dispatch (37 %) when the push data
   didn't change. Draws bind two stages, so expect about 2 µs per draw.
   NMS issues thousands of draws per frame, so 5,000 draws would add
   about 10 ms of CPU per frame, enough to turn 60 FPS into stutter. C
   (patch 0004) keeps one immutable snapshot per command buffer and
   rebinds only when the data or layout changes. That removes the extra
   cost in the measured case.
2. **PR 2719 makes about 34,000 pipelines that used to fail compile and
   run.** On 170ca those pipelines (mostly tessellation, from the
   address-space error) fail fast, and NMS skips those draws. With 2719
   they compile into Metal tessellation pipelines (a compute pass plus a
   vertex pass) and draw. That adds first-use compile hitches and real
   GPU work that 170ca never did. B isolates this. It doesn't touch the
   warning.
3. **The pipeline cache.** 128-02 shared 170ca's cache UUID, so stale
   entries could be reused. A, B and C each have their own namespace
   (patch 0003), so their first launch recompiles everything.

## Recommendation

- **Fix candidate for the owner's actual ask (the warning): C.** It
  keeps 170ca's shader translator byte for byte (the same
  `libSPIRVCross.a`), reports an honest limit of 128 samplers on this
  GPU, and removes the measured per-draw cost. The address-space
  failures stay exactly as on smooth 170ca, so the picture should match
  170ca (to be checked in the run below).
- **The address-space defect: explained, not shipped.** The root cause
  is upstream SPIRV-Cross (fixed by PR 2719). Shipping it adds work NMS
  skips today, so it ships only if B proves smooth.

## Next run (objective, without the owner)

One NMS launch on C through the CLI, with the same prefix and save as
`26d9c575`, after a verified save backup:

1. Wait out the first-launch recompile: launch once to the save
   selector, quit normally, then launch again. The cache is warm on the
   second launch.
2. Pass for the warning: no "insufficient per-stage descriptor
   samplers" dialog in screenshots every 15 s up to the save selector.
   Also check that the CLI popup record has none.
3. Performance, compared with 170ca on the same spot after loading the
   save: screenshots with the in-game FPS, `sample` of the NMS process
   (time in `MVKCommandEncoder` and push snapshot code), and, if the
   recipe allows it, Metal HUD frame-time maximums per second. The
   owner's judgment remains the final word for "smooth"; the agent
   records numbers only.
4. Normal quit, save hashes compared with the backup.

If C matches 170ca, hand the registry `aa0ee5de…` to REQ-80/S2
admission. If C stutters too, record the warning fix as dropped
(COR-241) and keep 170ca.
