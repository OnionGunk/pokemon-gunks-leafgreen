# Gunk's changes for LeafGreen: verdict list

Each Gunk's Platinum change, what LeafGreen already has, and what this hack does. The code comes from Gunk's
FireRed (same pret base); every check below was run again on the LeafGreen build. **Test** says how it was checked
in the emulator: `emu/suite/features.py` (feature checks, named in quotes) and `emu/suite/suite.py` (save
suite), both run after every build. Status: **done** = in the build and checked in the emulator.

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
| 16 | Faster egg hatching | An egg cycle every 256 steps | Every 128 steps (`src/daycare.c`) | done | code only; the test hook can't make an egg yet |
| 17 | More PC boxes | 14 boxes; storage fills its 9 flash sectors | Approved: 17 boxes by packing box Pokémon in the save. Blocked on RAM: EWRAM has 1.1 KB free and 17 boxes need 7.2 KB, which only a smaller heap can give; see `docs/PC_BOXES_PLAN.md` | planned | |
| 18 | DexNav | — | Key item (slot 54): lists the map's grass Pokémon; the chosen one hides in rustling grass nearby. Normal wild rolls; the search level and chain set how many are rolled (the best is kept). Search data in SaveBlock1's unused 400 bytes | done | "dexnav", "dexnav search level" |
| 19 | Following Pokémon | — | The lead walks behind the player: all 386 species, shinies in shiny colors. Movement ported from MinimalEffort07/pokefirered; sprites from pokeemerald-expansion. RETURN on the lead's party menu puts it away (flag 0x4AA), WALK brings it back | done | "follower on/off switch", "follower", "follower and Surf", "follower across a map edge", "follower through a door", "follower and saving", "follower palette after a menu", "story opening" |

The three new key items come from Oak's aide in Pewter City with the Running Shoes, or from Mom on a save that is
already past that ("Pewter aide gives the key items", "Mom gives the key items").

## Map sweep

`emu/suite/sweep.py` continues into all 397 maps outside the link rooms with a follower out: 394 reach the field
(5 of them by way of a trainer who sees the player on arrival), and the other 3 are story scenes that are still
playing when the sweep stops pressing A (the Hall of Fame saving, Bill on One Island, the Two Island Game Corner).
The game keeps running in all of them. The first sweep found the cave hang fixed in "Fix a hang loading caves".

## Not done yet

- Talking to the follower does nothing (vanilla would read a garbage script; it is skipped).
- An emulator check for egg hatching.
- A whole playthrough: the checks cover the opening, the key-item gifts, each feature and every map's arrival,
  not every story scene.

## LeafGreen results (2026-11-02, build `de46a5aa`)

- Vanilla control: `make compare_leafgreen` reproduces the retail ROM (sha1 `574fa542…`); the save suite in
  `leafgreen-tools` passes on retail and vanilla (save cycles, crash after a save, 10 live torn saves, 5 exact cuts,
  damaged-slot recovery).
- Gunk's LeafGreen: `emu/suite/suite.py` 35/35, `emu/suite/features.py` 27/27.
- The map sweep (`emu/suite/sweep.py`) hasn't been run on LeafGreen yet.
