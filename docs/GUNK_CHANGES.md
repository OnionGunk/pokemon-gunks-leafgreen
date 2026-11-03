# Gunk's changes for LeafGreen: verdict list

Each Gunk's Platinum change, what LeafGreen already has, and what this hack does. The code comes from Gunk's
FireRed (same pret base); every check below was run again on the LeafGreen build. **Test** says how it was checked
in the emulator: `emu/suite/features.py` (feature checks, named in quotes) and `emu/suite/suite.py` (save
suite), both run after every build, plus `emu/suite/boxes.py` for the PC boxes. Status: **done** = in the build and checked in the emulator.

| # | Change | LeafGreen (vanilla) | What Gunk's LeafGreen does | Status | Test |
|---|---|---|---|---|---|
| 0 | Header title | `POKEMON LEAF` | `GUNK LG`; the game code stays `BPGE`, so emulators keep LeafGreen's save type | done | "header" |
| 1 | Save safety | Two slots; a slot loads when every sector's checksum is good | Also requires all 14 sectors of a slot to carry the same save counter (`src/save.c`) | done | save suite: 4 save cycles, 12 power cuts across the flash write, torn writes at every sector, damaged slots, and "mixed" (vanilla fails it, Gunk's passes) |
| 2 | Instant text | SLOW / MID / FAST | A fourth speed, INSTANT, prints everything up to the next button wait each frame; new games start on FAST | done | "text speed", "INSTANT text option", a battle on INSTANT ("exp all") |
| 3 | Faster EXP bar | 1 pixel a frame | 2 pixels a frame | done | seen in battle |
| 4 | Auto-run | Hold B with the Running Shoes | Runs by default with the Running Shoes; hold B to walk | done | "auto-run": 3 tiles in 32 frames, 2 holding B |
| 5 | Repel prompt | "REPEL's effect wore off…" | Offers another of the same Repel if the bag has one (last Repel in var 0x4029) | done | "repel prompt" |
| 6 | Endless Repel | — | Key item (slot 52, unused in vanilla): on/off, works like a Repel while on (flag 0x4A7) | done | "endless repel": 30 steps of grass, no battle |
| 7 | Reusable TMs | TMs are used up | TMs stay in the TM Case, like HMs | done | "reusable TMs" |
| 8 | Two registered items | One (SELECT) | The latest on SELECT, the one before on R (var 0x402A); the bag marks them. In the field R no longer opens Help while a second item is registered; L still does | done | "two registered items": R mounts the Bicycle |
| 9 | Bag sorting | Items move one at a time with SELECT | START sorts the open pocket by item number | done | "bag sort" |
| 10 | IV/EV view | — | A on the summary's SKILLS page cycles stats → IVs → EVs | done | screenshots match the decoded IVs and EVs |
| 11 | Exp. All | Exp. Share only | Key item (slot 53): while on, healthy party members that didn't battle get half a battler's EXP, and the EVs (flag 0x4A8) | done | "exp all" |
| 12 | Vitamins to 252 | Stop at 100 EVs | Work up to 252 | done | "vitamins to 252": 240 → 250 → 252, then refused and kept |
| 13 | Trade evolutions | Need a link trade | Kadabra at 36, Machoke, Graveler and Haunter at 37; the trade items (King's Rock, Metal Coat, Dragon Scale, Up-Grade, Deep Sea Tooth/Scale) can be used like stones. Gen 2/3 targets still wait for the National Pokédex, as vanilla's evolutions do | done | "trade evolution by level", "trade item as a stone" (no effect before the National Dex, Steelix after) |
| 14 | HMs without teaching | Need the move | A Pokémon that could learn the move from an HM in the bag can use it: by script (`checkpartymove`), by facing water (Surf) and from the party menu, which lists it while there's room. Badges still apply | done | "HM without teaching" (Route 2's Cut tree), "follower and Surf" (a Lapras without Surf) |
| 15 | Move Tutor | Move Maniac (Two Island, for mushrooms), Move Deleter (Fuchsia) | Every Pokémon Center PC has a free MOVE TUTOR row that remembers level-up moves and forgets moves | done | "PC move tutor" |
| 16 | Faster egg hatching | An egg cycle every 256 steps | Every 128 steps (`src/daycare.c`) | done | `emu/suite/eggs.py`: an egg with 1 cycle left hatches on step 255 (vanilla: 511), a whole Pidgey with its IVs, moves and personality |
| 17 | More PC boxes | 14 boxes; storage fills its 9 flash sectors | 16 boxes. Boxed Pokémon are packed from 80 to 70 bytes (`Gunk_PackBoxMon`), so they fit the same 9 sectors and both save slots stay. A vanilla LeafGreen save is converted when it loads. See `docs/PC_BOXES_PLAN.md` | done | `emu/suite/boxes.py`: a vanilla save with 420 Pokémon (eggs, Bad Eggs, edge values) converted byte for byte, a save and reload, the summary screen unpacking boxes 1, 7, 14 and 16, all 16 boxes full across a save, the box list wrapping to box 16 |
| 18 | DexNav | — | Key item (slot 54): lists the map's grass Pokémon; the chosen one hides in rustling grass nearby. Normal wild rolls; the search level and chain set how many are rolled (the best is kept). Search data in SaveBlock1's unused 400 bytes | done | "dexnav", "dexnav search level" |
| 19 | Following Pokémon | — | The lead walks behind the player: all 386 species, shinies in shiny colors. Movement ported from MinimalEffort07/pokefirered; sprites from pokeemerald-expansion. RETURN on the lead's party menu puts it away (flag 0x4AA), WALK brings it back. Its palette goes through the field tint like every NPC's, so the quest log ("Previously on your quest") restores it | done | `league.py` follower colors after 17 quest-log Continues, "follower on/off switch", "follower", "follower and Surf", "follower across a map edge", "follower through a door", "follower and saving", "follower palette after a menu", "story opening" |

The three new key items come from Oak with the Pokédex, when the parcel is delivered: before Brock, and the
parcel can't be skipped ("Oak gives the key items with the Pokedex"). A save already past that gets them from Mom
("Mom gives the key items"); Oak's aide in Pewter still offers them, which does nothing once they're owned.

## Map sweep

`emu/suite/sweep.py` continues into all 397 maps outside the link rooms with a follower out: 394 reach the field
(5 of them by way of a trainer who sees the player on arrival), and the other 3 are story scenes that are still
playing when the sweep stops pressing A (the Hall of Fame saving, Bill on One Island, the Two Island Game Corner).
The game keeps running in all of them. The first sweep found the cave hang fixed in "Fix a hang loading caves".

## Arrivals against vanilla

`emu/suite/arrival.py` arrives in the same 397 maps on Gunk's and on vanilla from the same save (no test hook, a
party written into RAM), presses A through any arrival scene, and compares the map, the player's position and every
flag and var in the save block. Gunk's own flags and vars, and the temp ones the game clears on every map load, are
left out. All 397 match. Four scenes (the Hall of Fame and credits, Four Island's rival, Two Island's Game Corner,
Six Island's Pokémon Center) need more than 60 presses; they are run again with up to 1500 on both ROMs.

## The league to the end

`emu/suite/league.py` plays one game per ROM: a level 100 Mewtwo beats the 8 gym leaders, the Elite Four and
the Champion (each reached by the save's continue-game warp, the leader talked to as a player would), then A
carries on through Oak, the Hall of Fame, the credits and CONTINUE. Each milestone's flag (badge, member defeated,
game clear) must be set and the save block's flags and vars must match vanilla's at the same point. Every warp is a
save and a CONTINUE right after a battle, so the quest log plays 17 times; the follower's colors are checked after
each. This run found the follower coming back black after the quest log (fixed in "Follower: keep its colors through
the quest log").

## Legality (PKHeX)

`emu/suite/legality.py` (shared with Gunk's FireRed) catches Pokémon in the emulator as a player does (a battle,
a Master Ball, no nickname) on Route 1, Route 2 and Viridian Forest, dumps each as a .pk3 and also its round trip
through the 16-box packing, and `PKHeX.Core` 26.10.18 checks them (Gen 3 legality: PID/IV method, nature and ability
from the PID, species and level for LeafGreen's tables, met data, ball, OT, moves). LeafGreen, 2026-11-02: 25
catches (12 wild, 6 plain DexNav, 6 DexNav chain at search level 100 with a chain of 40, so 21 rolls, and 1 shiny
from a chain search whose RNG seed was searched, not edited) plus their 25 box copies: 50 legal, 0 illegal, no box
copy changed. Methods 1, 2 and 4, all of which FRLG grass encounters produce. DexNav keeps one of its rolls
unedited, each a vanilla wild generation, so a shiny is a full legal reroll.

Tanoby chambers (`emu/suite/legality_unown.py`): an Unown's letter comes from its PID, and each chamber allows only
its own letters. DexNav places its patch only on tall grass, which the chambers don't have, so it never starts a
search there, locked or unlocked: Unown come only from the vanilla encounter, which needs the Tanoby Key puzzle's
flag as in vanilla. With the chambers unlocked, 2 wild Unown from each of the 7 chambers (A A, H D, N N, R P, Y G,
X V, Z Z) plus their box copies: 28 legal, 0 illegal; DexNav and chain searches started none.

## Not done yet

- Talking to the follower does nothing (vanilla would read a garbage script; it is skipped).
- A full hand playthrough: the checks cover the opening, the key-item gifts, each feature, every map's arrival
  against vanilla and every gym, Elite Four and Champion battle through the credits, not every scene in between
  (Silph Co., Pokémon Tower, the Sevii Islands' story).

## LeafGreen results (2026-11-02, build `f928171d`)

- Vanilla control: `make compare_leafgreen` reproduces the retail ROM (sha1 `574fa542…`); the save suite in
  `leafgreen-tools` passes on retail and vanilla (save cycles, crash after a save, 10 live torn saves, 5 exact cuts,
  damaged-slot recovery).
- Gunk's LeafGreen: `emu/suite/suite.py` 35/35, `emu/suite/features.py` 27/27, `emu/suite/boxes.py` 16/16,
  `emu/suite/eggs.py` 255 steps (vanilla 511), `emu/suite/league.py` 15/15 against vanilla.
- Arrival sweep (`emu/suite/arrival.py`): 397/397 maps match vanilla (run on build `50b1b796`, before the follower
  palette fix, which touches no story state).
- Map sweep (`emu/suite/sweep.py`, build `de46a5aa`, before the 16 boxes): 394/397. The other 3 are the same story scenes as on FireRed (Hall of Fame,
  One Island Pokémon Center with Bill, Two Island Game Corner), still playing when the sweep stops; the game keeps
  running in all of them.
