The DexNav screen, Surf searches and held items, and a livelier follower in Pokémon Gunk's LeafGreen Version.

## New

- **The DexNav screen**: use the DexNav to open a screen of the area's Pokémon, in LeafGreen's own colours. Pick one
  and press A to search for it. Pokémon you haven't seen show as a "?", and you can't search for them yet. A ball mark shows the ones you've
  caught.
  - **LAND** and **WATER** tabs: search the grass, or search the water while you surf.
  - An **OTHER** tab lists the area's Pokémon you can't search for. They come from the Old, Good and Super Rods and
    from Rock Smash, and the screen tells you how to find each one.
  - Switch tabs with L and R.
- **The search bar**: while a search runs, a bar shows the hidden Pokémon's level, moves and held item.
- **Held items**: a DexNav Pokémon can hold the same items as its wild kind. The chance of a rare item grows with the
  search level and the chain: 5% at the start, up to 20%.
- **Your follower reacts when you talk to it**:
  - wary: a "!"
  - shy: a "?"
  - steady: a note
  - tired: dots
  - happy and devoted: a smile

  The steady, tired, happy and devoted moods also play its cry.
- **Your follower goes back into its ball** while you surf and during story scenes, and comes back out after.

## Patch it

You need your own dump of **Pokémon LeafGreen (USA) 1.0**:

```
sha1: 574fa542ffebb14be69902d1d36f1ec0a4afd71e
```

Apply `pokemon-gunks-leafgreen-v1.3.bps` with [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/), Floating
IPS, or `py tools/patch/bps.py apply`. Patch the clean retail ROM, not a ROM from an earlier version. The patcher
refuses any other ROM. The patched ROM should be:

```
sha1: 9fc3e8dd67bd7be829c682bc7c4d30dbb787690c
```

## Notes

- Saves from v1.0 and v1.2 carry over, because the save layout is unchanged. A vanilla LeafGreen save still loads,
  and its 14 boxes are converted to 16. Back up your save anyway.
- Tested in the emulator before release:
  - Every story scene (256) and every conversation with a person (144) was played on both this ROM and vanilla
    LeafGreen, with the same outcomes.
  - Eleven story milestones, up to the credits, were checked with save and Continue.
  - The save-safety suite: power cuts, torn writes and damaged slots.
  - Every feature check, the 16-box tests and the menus test.
  - The DexNav screen, rules, lag and held-item tests, and the Quick Ball tests.
  - The follower talk and room checks.
  - DexNav catches from grass, water and chains, plus Unown, were checked with PKHeX: all legal.
- A GBA has one screen, so the DexNav screen opens over the field rather than on a second screen.
- If you use PokeDaisy or another tool that reads the game's memory, use a build made for Gunk's LeafGreen (header
  code BPGE, title "GUNK LG"), or turn it off. Vanilla addresses don't match this ROM.
