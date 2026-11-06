# Pokémon Gunk's LeafGreen Version

A quality-of-life hack of Pokémon LeafGreen, built on [pret's FireRed/LeafGreen decompilation](https://github.com/pret/pokefirered).
It keeps the game's difficulty and story as they are and takes the grind and friction out, for long playthroughs.

**Latest release: [v1.4](../../releases/tag/v1.4)** (after [v1.3](../../releases/tag/v1.3), [v1.2](../../releases/tag/v1.2) and [v1.0](../../releases/tag/v1.0)). Every
feature below passes its emulator check, and a test game beats every gym leader, the Elite Four and the Champion
with the same story state as vanilla at each step; [`docs/GUNK_CHANGES.md`](docs/GUNK_CHANGES.md) lists each
change and its test results, and `docs/RELEASE_NOTES_v*.md` each release.

## Features

- **DexNav.** A key item (use it from the Bag or register it to SELECT) that opens the DexNav screen for the place
  you're in:
  - a title bar with the area's name and how many of its Pokémon you've caught;
  - LAND and WATER tabs (switch with L/R), each a grid of the area's grass or surfing Pokémon: an icon once seen,
    "?" before that, a ball mark once caught;
  - an OTHER tab with the area's Pokémon found by the Old, Good and Super Rods and by Rock Smash, and where to look;
  - an info panel for the highlighted Pokémon: name and status, where it's found, its level range, search level
    and chain.

  Pick a Pokémon you've seen and it hides nearby, in a patch of rustling grass or rippling water. Step (or Surf)
  into the patch within 10 seconds to battle it. While you look, a bar at the top of the screen shows what's
  hiding: name, level, a shiny mark, nature, ability, a gold star for each perfect IV, and its held item. Every
  Pokémon it finds is a legal wild roll for that spot. Search levels and chains raise the odds of good IVs, shinies
  and rare held items. A GBA has one screen, so there's no second-screen DexNav view.
- **Area info:** START on the DexNav screen shows the area's encounter odds and levels for grass, water, each rod
  and Rock Smash, where the roaming legendary is now, and what your Repel lets through.
- **Pokémon follow you.** Your lead Pokémon walks behind you, any of the 386 species, shinies in their shiny
  colours. Walk into it to swap places. Talk to it and it reacts (an emote, its cry) with a line that shows how it
  feels about you. It goes back into its ball (a Poké Ball opens on its tile) while you Surf or a scene plays
  out, and comes back out after. RETURN in its party menu puts it away, WALK brings it back.
- **Faster play:** instant text, a faster EXP bar, auto-run (hold B to walk), eggs that hatch twice as fast.
- **Items:** reusable TMs, two registered items (SELECT and R), bag sorting (START in the bag), a prompt to use
  another Repel when one runs out, and an Endless Repel you switch on and off.
- **Pokémon:** IV and EV view in the summary (A on the SKILLS page), Exp. All (half the EXP and the EVs for the
  Pokémon that didn't battle), vitamins up to 252 EVs, and trade evolutions without trading. HM moves work without
  teaching the move, and every PC has a free Move Tutor that remembers and forgets moves.
- **16 PC boxes** instead of 14. A save from vanilla LeafGreen loads, with its boxes kept.
- **Quick Run and Quick Ball:** in battle, R runs and L throws your last-used ball (hold L and press Left/Right
  to pick another). A small icon shows which ball and how many are left.

Oak gives the Endless Repel, the Exp. All and the DexNav with the Pokédex, before the first gym. On a save that's
already past that, Mom has them, and Oak's aide in Pewter City offers them too.

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

**PokeDaisy and other memory-reading companions:** these read the game's RAM at fixed addresses for retail
LeafGreen. The ROM header keeps game code `BPGE` (so emulators pick the right save type) but its title is
`GUNK LG`, and Gunk's code moves many addresses. Use a companion build that lists this exact release, or turn the
companion off: a mismatched one can show wrong data or upset the game. Each release's addresses can be read from
its build's `.sym` file.

## Build it

Follow pret's [`INSTALL.md`](INSTALL.md), then run `make leafgreen_release` for the release ROM
(`pokeleafgreen_release.gba`, which the patch is made from). `make leafgreen` builds the test ROM the emulator
suite uses: the same game plus a test hook that sets up new games. `make compare_leafgreen` on the upstream code
reproduces the retail ROM byte for byte. [`docs/ENGINE.md`](docs/ENGINE.md) explains why this hack uses
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
