# ADR 0017: Follow when a FOSS path exists; lead only when the only solution is paid

Status: Accepted
Date: 2026-06-01

## Context

[AGENTS.md](../../AGENTS.md) rule #4 ("We are visibly worse than
CrossOver, on purpose") closes with:

> **We follow, we don't lead.** We ship nothing CrossOver hasn't
> shipped first.

That blanket "we don't lead" has an edge case the original wording
didn't cover: situations where **no FOSS solution exists for a
problem calimocho's users hit, and the only available answer is a
paid product** (CrossOver, a proprietary library, a paid SaaS, etc.).
Strict "we follow" would force users either to buy or to give up,
even when a clean FOSS implementation is technically feasible and
upstream-compatible.

A concrete recent example: the D3DMetal d3d11/dxgi shims (ADR-0015,
ADR-0016). CrossOver does this differently (their proprietary
`d3d11.so` is part of paid product). gcenx ships nothing equivalent.
The only working free path for self-built Wine 11 on M-series is to
write the shim ourselves — i.e. **lead** on this specific piece.
Refusing to do it because "CrossOver did it first" would leave users
with no FOSS option at all.

## Decision

Refine rule #4's tagline from:

> **We follow, we don't lead.**

to:

> **We follow when a FOSS path exists. We lead only when the only
> alternative is a paid product, and only as narrowly as needed to
> remove that gating.**

The rest of rule #4 is unchanged. The eight anti-undercut levers
still apply. We still:

- ship nothing on the Wine engine layer that CodeWeavers hasn't
  shipped first (engine = the upstream-source-buildable part),
- keep the intentional 1–2 week release lag after each CrossOver
  release (lever 5),
- never go commercial (rule #2 + lever 6),
- still refer hard cases to CrossOver (lever 7),
- still mention CrossOver before any feature (lever 2),
- still donate up the chain only (lever 4).

What changes: where there is **no** working FOSS option and only a
paid product would otherwise solve the user's problem, we are
allowed to write the smallest possible piece of new code that
unblocks the FOSS path.

## Guardrails (must all hold before leading on a piece)

1. **No FOSS alternative ships today.** Document this in the ADR
   that authorizes the new code. List every FOSS project surveyed
   and what it lacks (e.g. ADR-0016's "Alternatives rejected"
   section).
2. **Only a paid product solves it.** Name the paid product(s)
   explicitly. If a hobbyist OSS effort is incomplete-but-active,
   contribute upstream there instead of leading downstream.
3. **Minimum viable surface.** Lead only on the narrowest piece
   that unblocks the FOSS user. Do not expand once the gate is
   removed. Code added under this clause is opt-in by design where
   possible (e.g. shim disabled unless explicitly enabled).
4. **Upstreamable.** Whatever we write should be designed so the
   upstream project could absorb it without changes. We don't fork
   to compete; we patch to unblock.
5. **Still no commercial features.** Rule #2 is absolute. Leading
   means writing code, not selling it.
6. **Still no scope creep beyond SN2.** Rule #5 is absolute. A
   piece of "lead" code that only helps games other than SN2 is
   out of scope.
7. **Public attribution.** Any leading code names the gap it
   removes (which paid product would otherwise be the only answer)
   so the trade-off is visible to any reader, including the paid
   product's maintainer.

## Consequences

### Positive

- Honest path forward in cases like ADR-0015/0016 where the strict
  "we follow" rule would leave users buying-or-quitting.
- Aligns calimocho's behavior with what's actually useful to the
  niche it serves (people on M-series who would *not* otherwise
  pay).
- Keeps the door open for narrow, principled contributions to the
  FOSS ecosystem rather than forcing every user to a paid product.

### Negative

- More judgment required per change. "Did we check FOSS hard
  enough?" is now a code-review question.
- Slight risk of mission creep if guardrails are forgotten.
  Mitigated by requiring an ADR for each leading-piece.

### Neutral

- Existing leading work (the d3d11 shim per ADR-0015 and the
  planned dxgi shim per ADR-0016) is retroactively validated by
  this rule — they were already leading; we now have a written
  policy that permits it.

## Compatibility with existing levers

| Lever | Status under ADR-0017 |
| --- | --- |
| 1. Visibly worse by honesty | unchanged |
| 2. Pre-purchase funnel | unchanged |
| 3. Co-promotion in release notes | unchanged |
| 4. Donate up the chain | unchanged |
| 5. Intentional release lag | **applies only to Wine engine layer that overlaps CrossOver's shipped feature set**; leading-pieces that fill a FOSS gap are not subject to this lag |
| 6. No commercial features ever | unchanged (absolute) |
| 7. Active referral on hard cases | unchanged |
| 8. Public non-competition statement | unchanged |

## Related

- [AGENTS.md](../../AGENTS.md) rule #4 (updated in same commit)
- [ADR-0014](0014-d3d-shim-strategy.md) — shim coupling cost
- [ADR-0015](0015-d3dmetal-shim-implementation.md) — first
  leading-piece under this policy (d3d11 shim)
- [ADR-0016](0016-dxgi-shim-required-for-cef.md) — second leading-
  piece (dxgi shim, in flight)
- [docs/relationship-with-codeweavers.md](../relationship-with-codeweavers.md) — to be updated to mirror this nuance
