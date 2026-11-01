# ADR-0006: Scope is "the Windows games the maintainer misses on his Mac", currently SN2

Status: Accepted
Date: 2026-05-31

## Context

The project could be scoped as:

1. **A general Mac Wine distribution** like CrossOver: aim at hundreds
   of games, broad compat matrix, eventual community ecosystem.
2. **A Whisky-style free engine** for any DX12 game the user wants to
   try: pick the engine, you bring the game.
3. **A personal recipe** for one specific game (Subnautica 2) the
   maintainer wants to play with his family, published in case it helps
   anyone in the same situation.

Option 1 would put us in direct competition with CrossOver, which we do
not want (see relationship-with-codeweavers.md). Option 2 implies an
implicit promise to support games we have not tested. Option 3 is the
honest description of what the maintainer is actually doing.

## Decision

calimocho's scope is **Windows games the maintainer personally misses on
his Mac**. The current list:

| Game | Status |
| --- | --- |
| Subnautica 2 | The reason this exists. Working. |
| They Are Billions | Wishlist (not tested) |
| Hogwarts Legacy | Wishlist (not tested) |
| Green Hell | Wishlist (not tested) |

The list lives in `docs/games-i-miss-on-my-mac.md` and grows only when
the maintainer personally tests a new game. Community PRs adding tested
games are welcome but not promised to keep working.

The project sunsets when Unknown Worlds ships a native Mac build of
Subnautica 2, regardless of what else is on the list at that time.

## Consequences

### Positive

- Maintenance scope is bounded. We do not become a 50-game compat
  matrix.
- "Why doesn't X work?" has a one-line answer: "X is not on the list,
  buy CrossOver."
- The sunset clause means the project does not become a forever
  commitment.
- Honest framing: this is a personal project published openly, not a
  product.

### Negative

- We disappoint users who hoped calimocho would support their game.
  Mitigated by README being very clear about this.
- We cannot benchmark "calimocho compatibility" the way Wine has
  AppDB or CrossOver has CrossTie. We do not have a compat database.

### Neutral

- The wishlist can grow if the maintainer gets time to test more games.
- Forks could expand scope freely under the LGPL.

## Related

- docs/games-i-miss-on-my-mac.md
- docs/why-this-exists.md
- AGENTS.md rule #5 (SN2-scoped)
