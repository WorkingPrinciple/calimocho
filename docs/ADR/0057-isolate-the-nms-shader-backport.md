# ADR-0057: Isolate the NMS shader backport from sampler capacity

## Context

REQ-104 assigns a 45-minute source-only investigation while the owner plays
NMS on the frozen `170ca4ad` runtime. The modern isolated-build policy is
recorded in runtime-adapter branch ADR-0022. This fresh worktree starts on
archived main; it does not restore the old release plan or its shipping gates.

The runtime log identifies MoltenVK 1.4.2 and rejects generated vertex
shader stores that cast thread-local `float4` pointers to `device float*`.
The public [SPIRV-Cross proposal 2719][shader] by Faye Salwin, opened on
2026-10-20, describes that exact defect in NMS terrain tessellation.
It remains open, not merged, when checked on 2026-10-25.

The sampler warning is separate. The pinned MoltenVK source advertises
16 ordinary per-stage samplers. Higher update-after-bind limits do not
replace that property. Push descriptors always take the non-argument-buffer
path. The retained runtime-adapter ADR-0031 documents why merely raising
the limit or disabling only the push extension is not a complete fix.
[Upstream discussion 1610][samplers] distinguishes the ordinary and
update-after-bind paths. Historical enum values are not current guidance:
the pinned 1.4.2 configuration documents a Boolean, enabled by default.

## Decision

Backport only proposal 2719's nine-line correction onto the exact active
SPIRV-Cross revision `6c09849fe88c48eaed08413aa022aaa136a3a057`.
Retain upstream attribution and licensing. Reuse the verified source-built
MoltenVK 1.4.2 cache only in this owned worktree. Do not copy proprietary
CrossOver binaries, install dependencies, or change the running runtime.

Use independent minimal valid SPIR-V to require the exact eight original
Metal errors before the patch, successful Metal compilation after it,
unchanged non-tessellated output, and preserved builtin position writes.
These are compiler checks, not observed NMS rendering.

Produce a separate private-Metal x86_64 candidate with a full inventory and
committed provenance. Remove inherited runtime/game success metadata from
its registry. REQ-80/S2 admission and later parent-authorized Ode Play remain
required. Do not install, launch, mutate prefixes, or suppress the warning.

Leave sampler capabilities unchanged. Real push argument-buffer support
requires layout selection, descriptor storage/update/template handling,
command lifetime and resource encoding work plus regular/push/mixed-layout
functional coverage. This is not a one-number change and is not implemented
in this shader backport.

## Consequences

An upstream-backed compiler fix can be evaluated without risking current
gameplay. The sampler warning and integer-format blending warning remain
unresolved. No broader game-compatibility conclusion follows. A compiled,
signed or frozen artifact is not an admitted runtime or a fixed game.

[shader]: https://github.com/KhronosGroup/SPIRV-Cross/pull/2719
[samplers]: https://github.com/KhronosGroup/MoltenVK/issues/1610
