# Windows games I miss and cannot play on my Mac

This is the complete list of games calimocho is built and tested for.
It will grow only when the maintainer personally misses a Windows-only
game enough to make it work on their own Mac.

It is not a service.
It is not a request line.
It is a small personal list, published in case it helps.

## The list

| Game | Why I miss it | API | Status | Hardware tested | Date |
| --- | --- | --- | --- | --- | --- |
| **Subnautica 2** (Early Access) | I bought the first two Subnautica games on Mac. The third should also run on Mac. | DX12 | Working (using CrossOver-equivalent stack) | M1 Max, macOS 26.5 | 2026-06 |
| **They Are Billions** | Steampunk colony defense game I loved on Windows years ago. No Mac build. | DX11 | Wishlist (not tested yet) | n/a | n/a |
| **Hogwarts Legacy** | The kind of game my kid would love to play with me. No Mac build. | DX12 | Wishlist (not tested yet) | n/a | n/a |
| **Green Hell** | Amazon jungle survival sim. Similar vibe to Subnautica but on land. No Mac build. | DX11 | Wishlist (not tested yet) | n/a | n/a |

That is the current list. It will grow if the maintainer gets time to test
more of his wishlist on calimocho.

### Wishlist convention

Rows with `Wishlist (not tested yet)` are games the maintainer would personally
like to play if calimocho ever gets there. They are **not** promises and they
are **not** open for community lobbying. They exist in the table so the project
shape stays honest: this can grow, but only along the maintainer's actual
gaming interests.

If you want to test one of the wishlist entries on your own Mac and report
back, PRs welcome (see "How to add a game" below).

## Why this list is short

calimocho started for one reason: my family bought
[Subnautica](https://store.steampowered.com/app/264710/Subnautica/) and
[Subnautica: Below Zero](https://store.steampowered.com/app/848450/Subnautica_Below_Zero/)
on Mac. Both run natively. When
[Subnautica 2](https://store.steampowered.com/app/2864380/Subnautica_2/)
launched in Early Access without a Mac build, we wanted to keep playing
together. So I built this.

If another Windows-only game shows up that I miss enough to make work on
my Mac, it will get added here. Otherwise this stays a one-row table.

For games that are not on this list, please use
[CrossOver](https://www.codeweavers.com/crossover). They support a much
wider catalog than this hobby project ever will.

## How to add a game

Community pull requests are welcome but optional. If you tested calimocho
with a Windows game on your own Mac and it worked:

1. Fork this repo
2. Add a row to the table above with your hardware, macOS version, and
   the date you tested
3. Open a pull request

The PR will be merged if the report is sincere. There is no guarantee the
game keeps working across calimocho updates. The maintainer tests only the
games on their own list.

## Things this list will never include

- Games with kernel-level anti-cheat (Valorant, Fortnite, etc.). They cannot
  run under any Wine, on any Mac, by anyone.
- Games the maintainer does not personally want to play. There is no system
  for accepting "please add support for X" requests.
- Games that already have a native Mac build. Use the native build.
- Games where the publisher actively does not want Mac users to play
  (some EA Sports games, some Riot games). We respect their wishes.

## What to do if your favorite game is not here

1. **Try it anyway.** calimocho is a generic Wine engine with D3DMetal.
   Many DX11 and DX12 games will probably run. Report back in a PR if it
   works.
2. **Try CrossOver's 14-day free trial.** They have actual per-game
   compatibility profiles for hundreds of titles. If it works there and
   not here, that is the gap they fill.
3. **Buy CrossOver if you can afford it.** Their work funds the Wine engine
   we all depend on. $74 per year is fair for what you get.
4. **Ask the game's publisher to ship a native Mac build.** That is the
   real long-term answer for any game you love on Mac.
