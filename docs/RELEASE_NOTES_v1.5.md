DexNav searches in caves and buildings in Pokémon Gunk's LeafGreen Version.

## New

- **The DexNav works everywhere wild Pokémon live.** Before, a search could only start in tall grass or on water,
  so caves, the Pokémon Mansion, Pokémon Tower, the Power Plant, Mt. Ember, Tanoby and the Sevii Islands' caves
  could never be searched. Now a search can start on any floor where you meet wild Pokémon on foot.
  - On a cave or building floor, the Pokémon hides in **stirring dust** instead of rustling grass.
  - The DexNav shows how you find it: **Cave** or **Indoors** instead of Grass.
  - Every LeafGreen-only Pokémon found on foot can now be searched for, from Misdreavus in the Lost Cave and
    Sneasel in Icefall Cave to Vulpix and Muk in the Mansion.
- The hiding spot is now somewhere you can walk to: never behind a wall, on a ledge or across water. Where no such
  spot is close enough, the DexNav still picks one you can see.

## Changed

- The "can't search" message now reads "There's nowhere close enough for POKéMON to hide.", since a search no
  longer needs grass.

## Patch it

You need your own dump of **Pokémon LeafGreen (USA) 1.0**:

```
sha1: 574fa542ffebb14be69902d1d36f1ec0a4afd71e
```

Apply `pokemon-gunks-leafgreen-v1.5.bps` with [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/), Floating
IPS, or `py tools/patch/bps.py apply`. Patch the clean retail ROM, not a ROM from an earlier version. The patcher
refuses any other ROM. The patched ROM should be:

```
sha1: 3f99228c69fb7a21b942638a87a30fe454d519cd
```

## Notes

- Saves from v1.0 to v1.4 carry over, because the save layout is unchanged. A vanilla LeafGreen save still loads,
  and its 14 boxes are converted to 16. Back up your save anyway.
- **PokeDaisy and other memory-reading tools:** `PokeDaisy-v1.5.md` (and `.csv`) lists where this release's RAM
  addresses differ from retail LeafGreen: 419 of 886 RAM symbols moved. The party, the save-block pointers, boxes,
  `gMain`, tasks and sprites are where retail has them; the map header, objects and script variables moved. Detect
  the hack by its header title `GUNK LG` (game code `BPGE`).
- Tested in the emulator before release:
  - **A whole game:** New Game to the Hall of Fame and the credits on one save, with every gym, the Elite Four and
    the Champion. Each chapter saved, power cycled and continued, with DexNav catches and Quick Run along the
    way: 41/41.
  - **Every map with wild Pokémon:** the DexNav's list matches the map's encounter table, and a land and a water
    search start on each one (`dexnav_areas`, 266 of 267 in its first run; the one miss was the test itself, now fixed).
  - **The release ROM itself**, with no test hook: the intro plays, NEW GAME goes through Oak's speech, and a save
    and Continue bring you back to the same spot (5/5).
  - **Saving**: the save-safety suite (35/35) covers power cuts, half-finished saves and damaged save slots.
  - **The story**: every story scene and every conversation, compared with vanilla LeafGreen, plus 11 story
    milestones up to the credits.
  - **Features and the DexNav**: features 33/33, the screen 16/16, rules 6/6, held items 4/4 and 4/4, Safari Zone
    3/3, peek 12/12, Quick Ball 10/10 and 6/6, boxes 16/16, menus 9/9.
  - **Legality**: every DexNav catch checked with PKHeX, including the new cave catches and Unown in every Tanoby
    chamber: 402 checked, all legal.
- A clean build of this release's source reproduces this ROM byte for byte (`make leafgreen_release`).
