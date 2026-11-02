# More PC boxes: plan

Nothing here is built yet. This is the plan to agree on first, because it changes the save format.

## The constraint

LeafGreen's 128 KB flash is fully allocated (`include/save.h`, `src/save.c`):

| Sectors | Use |
| --- | --- |
| 0-13 and 14-27 | Two save slots, written alternately. Each slot: SaveBlock2 (1 sector), SaveBlock1 (4), PokemonStorage (9) |
| 28-29 | Hall of Fame |
| 30-31 | Trainer Tower e-Reader data (`src/cereader_tool.c`) |

`struct PokemonStorage` is 0x83D0 bytes: the current box, 14 × 30 `BoxPokemon` of 80 bytes, the box names and the
wallpapers. Nine sectors hold 9 × 3968 = 35,712 bytes, which leaves **1,968 bytes free**: not enough for one more
box (30 × 80 = 2,400).

The two-slot scheme is what makes a power cut during a save harmless (the suite's `torn_save` tests it), so any
extra boxes must be inside the slots, not in a single-copy area.

## Options

1. **Pack box Pokémon losslessly in the save file (recommended).** RAM keeps the normal 80-byte `BoxPokemon`;
   only the save serializer packs them. The 80 bytes carry encryption, a checksum and padding. Packed bit fields
   need about 66 bytes: personality 32, OT ID 32, nickname 80, language 3, flags 4, OT name 56, markings 4,
   species 9, item 9, EXP 21, PP Ups 8, friendship 8, moves 4 × 9, PP 4 × 7, EVs 48, contest stats 48,
   Pokérus 8, met location 8, origin 16, IVs/egg/ability 32, ribbons 32. That is 522 bits. At 66 bytes per Pokémon
   plus 10 bytes of name and wallpaper per box, the nine sectors hold **17 boxes** (+3), with nothing lost and both
   slots kept. The checksum and encryption are rebuilt on load, as the game does already.
2. **Drop data FRLG can't use** (contest stats, PP that the box could restore) to reach about 58 bytes and 19-20
   boxes. Contest stats matter when trading to Ruby/Sapphire/Emerald, so this loses information. Not recommended.
3. **Use the Trainer Tower sectors 30-31.** Only the e-Reader card feature uses them. They are single copies, so a
   power cut while writing them could lose those boxes; double-buffering them gives just one box. Not recommended.

## Plan for option 1

- Save version tag in SaveBlock2's spare bytes (92 free). A save without the tag is a retail save: load it as is
  and write the packed format on the next save. Retail saves carry over; the hack's saves don't go back to retail.
- Pack and unpack in `SaveSerializedGame` / `LoadSerializedGame` paths only (`src/load_save.c`), through a
  separate buffer, so the sector writer and the slot logic in `src/save.c` stay unchanged.
- `TOTAL_BOXES_COUNT` 14 → 17. Check every user: the PC UI (box list, jump menu), `GetBoxNamePtr`, wallpapers,
  "the box is full" messages and the auto-send of caught Pokémon.
- Tests: full boxes (17 × 30) through save cycles and torn saves; a retail save upgraded and every box checked;
  every field of every Pokémon compared before and after a save and reload.
