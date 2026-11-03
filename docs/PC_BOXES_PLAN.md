# More PC boxes: plan and verdict

**Verdict: done, 16 boxes** (vanilla has 14), by packing boxed Pokémon tighter (option 4 below). Both save slots
stay, and a vanilla FireRed or LeafGreen save still loads.

## The layout (src/save.c, include/save.h)

128 KB flash = 32 sectors of 4 KB, each with 3,968 data bytes and a 128-byte footer.

| Sectors | Holds | Double-buffered |
|---|---|---|
| 0-13 | Save slot 1 | yes |
| 14-27 | Save slot 2 | yes |
| 28-29 | Hall of Fame | no |
| 30-31 | Trainer Tower (e-Reader) | no |

Each slot holds 14 sectors: SaveBlock2 (1 sector), SaveBlock1 (4 sectors), PokemonStorage (9 sectors).

| Block | Size | Room in its sectors | Free |
|---|---|---|---|
| SaveBlock2 | 0xF24 = 3,876 | 3,968 | 92 |
| SaveBlock1 | 0x3D68 = 15,720 | 15,872 | 152 |
| PokemonStorage, vanilla (14 boxes) | 0x83D0 = 33,744 | 35,712 | 1,968 |
| PokemonStorage, Gunk's (16 boxes) | 0x83E8 = 33,768 | 35,712 | 1,944 |

One more box in the vanilla format costs 30 × 80 + 9 (name) + 1 (wallpaper) = 2,410 bytes, more than the slot's
2,212 free bytes. RAM is the other limit: EWRAM had about 680 bytes free, so the boxes can't be kept unpacked in
RAM either (two more vanilla boxes need 4,820).

## Options considered

1. **Use the free bytes in the slot.** 2,212 < 2,410: not even one box.
2. **Free unused SaveBlock1 fields.** About 1-2 KB, so one box at most, split across blocks.
3. **Use sectors 30-31.** Not double-buffered: a power cut while saving could lose those boxes. Rejected.
4. **Pack boxed Pokémon tighter.** Chosen.
5. **Bigger flash.** 128 KB is the largest GBA flash chip.

## What was done

Boxed Pokémon are kept packed in RAM as well as in the save, 70 bytes each (`Gunk_PackBoxMon` and
`Gunk_UnpackBoxMon` in `src/pokemon.c`). They are stored decrypted, in a fixed substructure order:

| Offset | Bytes | Holds |
|---|---|---|
| 0 | 28 | personality, OT ID, nickname, language, flags byte, OT name, markings (as in struct BoxPokemon) |
| 28 | 10 | experience, PP bonuses, friendship, the four PP |
| 38 | 24 | substructs 2 and 3 as they are (EVs, contest stats, met data, IVs, ribbons) |
| 62 | 8 | 10-bit species, held item and four moves, then one bit: the checksum failed |

Dropped: the checksum (recomputed on unpack; a Bad Egg's bit makes the recomputed one fail again), the u16 after
it (never read; only Shedinja's creation writes it, with 0) and substruct 0's filler. Species, item and move IDs
are all below 1,024 (checked by a STATIC_ASSERT). The storage struct grows by 24 bytes.

Every box access goes through `src/pokemon_storage_system.c` (`GetBoxMonDataAt`, `SetBoxMonAt`,
`CopyBoxMonAt`...), which unpack a copy and repack writes. `GetBoxedMonPtr` is gone; its callers copy. The summary
screen needs a box as an array, so it gets an unpacked copy (2,400 bytes on the heap) that is written back when it
returns.

A vanilla save is recognized by `gunkFormat` ("GBX1"), which lies past the vanilla struct's end, where a vanilla
save has zeros (those zeros also leave the sector checksum unchanged). `Gunk_UpgradeBoxStorage` converts the 14
boxes in place after loading, keeping names, wallpapers and the current box; boxes 15 and 16 start empty.

## Tests (`emu/suite/boxes.py`)

A save made in vanilla FireRed with 420 generated Pokémon (normal ones, eggs, Bad Eggs, empty slots, edge values
such as Chimecho with item 374 and Psycho Boost), a renamed box and a changed wallpaper:

- the conversion matches an independent Python packer byte for byte (480/480 slots); names, wallpapers and the
  current box are kept, and boxes 15-16 are named BOX15/BOX16;
- a Gunk's save and reload leaves the storage identical;
- the summary screen on boxes 1, 7, 14 and 16 gets all 30 Pokémon unpacked to the original 80 bytes (Bad Eggs
  still fail their checksum), and closing it writes the box back unchanged;
- 16 full boxes survive a save and reload;
- the box list wraps from box 1 to box 16.

The save suite (`emu/suite/suite.py`) and the feature checks also pass on this build.
