# ADR-0031: Test sampler capacity before advertising it

## Context

REQ-N29 authorizes genuine sampler improvements in a new isolated candidate,
not a larger advertised number alone. The accepted MoltenVK 1.4.2 source
uses argument buffers for ordinary descriptor sets when supported, but
always uses the 16-slot binding path for push descriptors.

Increasing the ordinary per-stage limit would also allow applications to
request more than 16 push samplers. Limiting all push descriptors to 16 is
not a valid shortcut: Vulkan requires `maxPushDescriptors` of at least 32.
Removing only the push extension is insufficient because the selected source
also exposes the core Vulkan 1.4 push feature.

## Decision

Preserve all accepted limits, sources, binaries and records. First prepare
an opt-in functional fixture in the existing Vulkan probe. The fixture
statically samples 17 descriptor slots, writes 17 independent results, and
checks exact alternating white/black border colors, including alpha.
It must refuse insufficient advertised capacity rather than issue an invalid
dispatch against the accepted 16-sampler runtime.

`--sampler-shader PATH` selects the fixture. Without it, the existing probe
does not create the compute resources or require a compute queue. Shader
assembly and Vulkan validation are CPU build checks, not GPU evidence.
Any future GPU run needs exact shader, PE and runtime binding and the existing
native scheduling and cleanup policy.

Do not modify push behavior as part of fixture preparation. Two future paths
need an explicit source decision:

1. Implement real push argument buffers, including command lifetime,
   partial updates, descriptor templates, shader bindings and resource
   residency. This retains API support but crosses several source seams.
2. Withdraw affected push capabilities consistently and lower the advertised
   API below Vulkan 1.4 if required. This is a compatibility reduction, not
   an equivalent sampler fix, and could prevent an application from starting.

## Consequences

The fixture provides executable source for a real capacity check, but no
new GPU result or NMS fix exists yet. Regular descriptors, push descriptors,
mixed layouts and argument-buffer-off fallback still need functional
coverage before a new capacity implementation is accepted.

Fullscreen capture remains separate. A per-prefix registry selector does
not change the selected driver's `CGCaptureAllDisplays` call into a
target-display API. Neither that selector nor a games-category app bundle
alone proves Direct presentation or Game Mode.

Primary Vulkan references:
[required limits](https://docs.vulkan.org/spec/latest/chapters/limits.html) and
[feature requirements](https://docs.vulkan.org/spec/latest/chapters/features.html).
