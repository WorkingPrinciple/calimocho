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

### Later authorized sampler probes

The owner subsequently authorized isolated GPU probes through the parent.
Keep these tests separate from the frozen shader candidate and its evidence.
Use headless compute sampling with a deterministic readback, not a window or
process-liveness assertion. Exercise regular, push and mixed descriptors,
two different descriptor states and command-buffer replay. A diagnostic that
exceeds the advertised limit must require an explicit flag and must not be
reported as Vulkan conformance or NMS acceptance.

The probes do not change the reported limit. Further push argument-buffer
implementation remains a separate slice, reviewed against these failures
before expanding into descriptor storage, templates and command lifetime.

### Later authorized Metal3 push implementation

The parent then authorized that separate slice locally, without remote
publication. Keep the shader-only candidate and original runtime immutable.
Compile the experimental path only with `REQ104_PUSH_ARGUMENT_BUFFERS=1`.
Use existing Metal3 descriptor writers and resource tracking. Copy push
bytes into a command-completion-owned allocation at each bind, repairing
self-relative pointers in the copy. Never bind mutable push host storage.
Reuse the ordinary descriptor metadata initializer for these snapshots.
Devices using the older argument encoder retain their existing path.

Test push-17 compute, templates, partial writes, two updates in one command
buffer, replay and fragment-stage use before freezing another candidate.
Keep the advertised limit at 16. These diagnostics exceed that limit and
do not establish Vulkan conformance or the unknown NMS warning threshold.
GPU execution still requires the parent's exclusive slot grant. An
experimental candidate must have a new identity, committed source patch,
test receipt and full inventory. No existing runtime or default changes.

### Later authorized sampler-limit experiment

The parent then requested width-parameterized probes at 17, 32, 64 and 128.
The [Apple feature tables][metal-limits], dated 2026-05-21, page 8, list
128 argument-buffer samplers per stage for Apple6, 996 for Apple7/8 and
500,000 for Apple9/10. This is not the unique sampler-object limit exposed
by `maxArgumentBufferSamplerCount`. Reusing two sampler objects can exercise
many descriptor entries without exercising unique-object capacity.

Prepare a separate source-frozen, unqualified candidate capped at 128,
pending its own GPU suite. Gate the experiment to macOS, enabled argument
buffers, Tier 2, no argument encoder, native texture swizzle and Apple6 or
newer. These predicates exclude the layout selector's direct-binding
fallbacks. Keep all other devices and configurations at 16, and never
raise direct Metal sampler slot constants. Align variable-count standalone
and combined sampler queries with the gated advertised limit, including
saturating subtraction when other bindings exhaust it.

128 is the highest width of the authorized initial sweep, not an NMS
threshold claim or a new hardware maximum. No larger push width is justified
until the independent push-count limit is addressed. The promoted binary
must repeat coverage, including the corrected combined-image fixture, before
it has functional acceptance. Core, KHR and maintenance6 push entrypoints
share internal command paths but get explicit runtime cases too.

## Consequences

An upstream-backed compiler fix can be evaluated without risking current
gameplay. The sampler warning and integer-format blending warning remain
unresolved. No broader game-compatibility conclusion follows. A compiled,
signed or frozen artifact is not an admitted runtime or a fixed game.

[shader]: https://github.com/KhronosGroup/SPIRV-Cross/pull/2719
[samplers]: https://github.com/KhronosGroup/MoltenVK/issues/1610
[metal-limits]: https://developer.apple.com/metal/Metal-Feature-Set-Tables.pdf
