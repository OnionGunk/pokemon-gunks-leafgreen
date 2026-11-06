An area page for the DexNav, a Poké Ball for your follower, and Compound Eyes in Pokémon Gunk's LeafGreen Version.

## New

- **Area info**: press START on the DexNav screen to see:
  - the area's chance of a wild Pokémon and the levels, for grass, Surf, each rod and Rock Smash;
  - where the roaming legendary is now;
  - what your Repel lets through.
- **Your follower's Poké Ball**: when it goes back into its ball (while you surf, or when a story scene starts) and
  when it comes back out, a Poké Ball opens on its tile.
- **Compound Eyes**: with a Compound Eyes Pokémon at the front of your party, DexNav Pokémon hold items more often.
  The chances start at 60% for the common item and 20% for the rare one, instead of 50% and 5%.

## Changed

- In the Safari Zone, the DexNav now refuses every step of a search, not only the item itself. Safari Zone
  Pokémon are caught with Safari Balls only, so a DexNav battle there would give a catch no real game can make.
- The release ROM is now built without the emulator test hook.

## Patch it

You need your own dump of **Pokémon LeafGreen (USA) 1.0**:

```
sha1: 574fa542ffebb14be69902d1d36f1ec0a4afd71e
```

Apply `pokemon-gunks-leafgreen-v1.4.bps` with [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/), Floating
IPS, or `py tools/patch/bps.py apply`. Patch the clean retail ROM, not a ROM from an earlier version. The patcher
refuses any other ROM. The patched ROM should be:

```
sha1: b81e6103f94e843f8785fae9bb36132150e2b2c1
```

## Notes

- Saves from v1.0, v1.2 and v1.3 carry over, because the save layout is unchanged. A vanilla LeafGreen save still
  loads, and its 14 boxes are converted to 16. Back up your save anyway.
- Tested in the emulator before release:
  - **The release ROM itself**, with no test hook: the intro plays, NEW GAME goes through Oak's speech, and a save
    and Continue bring you back to the same spot.
  - **The story**: every story scene and every conversation with a person, played on both this game and vanilla
    LeafGreen, with the same outcomes. Eleven story milestones, up to the credits, with a save and Continue at each.
  - **Saving**: the save-safety suite covers power cuts, half-finished saves and damaged save slots.
  - **Features**: every feature check, the 16-box tests and the menus test.
  - **The DexNav**: the screen, area page, rules, lag, held-item and Safari Zone tests, plus the Quick Ball tests.
  - **The follower**: talking to it, a room with no space for it, a double battle with it in the lead, and a
    scene that walks straight into a warp.
  - **Legality**: DexNav catches from grass, water and chains, plus Unown, checked with PKHeX. All legal.
- A clean build of this release's source reproduces this ROM byte for byte (`make leafgreen_release`).
