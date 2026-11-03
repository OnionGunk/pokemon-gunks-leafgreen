# Pokémon Gunk's LeafGreen Version

A quality-of-life hack of Pokémon LeafGreen, built on [pret's FireRed/LeafGreen decompilation](https://github.com/pret/pokefirered).
It keeps the game's difficulty and story as they are and takes the grind and friction out, for long playthroughs.

**Status: in development.** There is no release yet. Every feature below is in the build and passes its emulator
check, and a test game beats every gym leader, the Elite Four and the Champion with the same story state as vanilla
at each step; [`docs/GUNK_CHANGES.md`](docs/GUNK_CHANGES.md) lists each change and its test results.

## Features

- **DexNav.** See each route's Pokémon (caught, seen or unseen) and search for one in the grass.
- **Pokémon follow you.**
- **16 PC boxes** instead of 14. A save from vanilla LeafGreen loads, with its boxes kept.
- **Faster play:** an INSTANT text speed, a faster EXP bar, auto-run, faster egg hatching.
- **Items:** reusable TMs, two registered items (SELECT and R), bag sorting (START), a prompt to use another
  Repel when one runs out, and an Endless Repel toggle. The new key items come from Oak with the Pokédex, before the first gym.
- **Quick Run and Quick Ball:** in battle, R runs and L throws your last-used ball (hold L and press Left/Right
  to pick another). A small icon shows which ball and how many are left.
- **Pokémon:** IV and EV view in the summary, Exp. All, vitamins up to 252 EVs, and trade evolutions without
  trading. HM moves work without teaching the move, and every Pokémon Center PC has a Move Tutor.

Save safety comes first: every build has to pass an emulator test suite that covers save cycles, power cuts
right after and during a save, and damaged-save recovery. The suite runs on the unmodified game too, as the control.

## Play it

Releases will ship a **BPS patch**, not a ROM. You need your own dump of **Pokémon LeafGreen (USA)**, version 1.0:

```
sha1: 574fa542ffebb14be69902d1d36f1ec0a4afd71e
```

1. Download the `.bps` file from [Releases](../../releases).
2. Apply it to your ROM with [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/) (in the browser),
   Floating IPS, or `py tools/patch/bps.py apply <leafgreen.gba> <patch.bps> <out.gba>`.
3. Play the result in any GBA emulator or flashcart. The patcher checks your ROM first and refuses the wrong one.

Back up your save before updating.

## Build it

Follow pret's [`INSTALL.md`](INSTALL.md), then run `make leafgreen`. `make compare_leafgreen` on the upstream
code reproduces the retail ROM byte for byte. [`docs/ENGINE.md`](docs/ENGINE.md) explains why this hack uses
the decompilation.

## Credits

- [pret](https://github.com/pret/pokefirered) for the FireRed/LeafGreen decompilation this hack is built on,
  and [agbcc](https://github.com/pret/agbcc).
- [pokeemerald-expansion](https://github.com/rh-hideout/pokeemerald-expansion) contributors: the DexNav
  (originally by Ghoulslash) this hack's version is based on, and the overworld Pokémon sprites. Quick Ball follows
  its `B_LAST_USED_BALL` and `B_LAST_USED_BALL_CYCLE`.
- MinimalEffort07's [pokefirered](https://github.com/MinimalEffort07/pokefirered) following-Pokémon code, which
  the follower is ported from.
- The DexNav idea comes from later Pokémon games and fan hacks such as Pokémon Unbound.
- Gunk's [Platinum](https://github.com/OnionGunk/pokemon-gunks-platinum) hack, and Gunk's FireRed, whose code
  this hack is built on.

Pokémon is © Nintendo, Creatures Inc. and GAME FREAK inc. This is a non-commercial fan project and contains
no ROM data; you need your own legally dumped copy of the game.
