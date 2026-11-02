# Gunk's changes: LeafGreen verdicts

Every Gunk's change, what LeafGreen already has, and what this hack does about it. "Checked" means seen working in
the emulator; the save suite (`leafgreen-tools/emu/suite`) runs after every build.

| # | Change | LeafGreen today | Verdict | Status |
| - | --- | --- | --- | --- |
| 1 | Title `GUNK LG` | Header title `POKEMON LEAF` | Header title `GUNK LG` (game code `BPGE` stays, so emulators keep the flash save type) | planned |
| 2 | Save-safety suite | — | Harness + suite: save cycles, power cut after a save, torn saves (live and byte-exact), damaged-slot recovery | **done on retail** |
| 3 | Instant text | SLOW / MID / FAST | Add INSTANT; new games start on FAST | planned |
| 4 | Faster EXP bar | Slow fill | Fill ×2 or more, same final values | planned |
| 5 | Auto-run | Running Shoes: hold B | Run by default once you have the shoes; hold B to walk | planned |
| 6 | Repel prompt | Message only | "Use another?" when one wears off and you have more | planned |
| 7 | Endless Repel | — | New key item, toggled from the bag | planned |
| 8 | Reusable TMs | Single-use TMs | TMs aren't consumed (HMs already aren't) | planned |
| 9 | Two registered items | One (Select) | Second registered item; button to be decided (L/R are taken by the help system's L=A mode and bag pockets) | planned |
| 10 | Bag sorting | None | Sort a pocket by name / number | planned |
| 11 | IV/EV view | None | Summary page cycles stats → IVs → EVs | planned |
| 12 | Exp. All | Exp. Share (held item) | New key item: the whole party shares EXP (and EVs); toggleable | planned |
| 13 | Vitamins to 252 | Stop at 100 EVs per stat | Up to 252, total still 510 | planned |
| 14 | Trade evolutions | Need a link trade | By level (or item use) without trading | planned |
| 15 | HMs without teaching | Must know the move | Field moves work if a party Pokémon can learn the HM and you have the HM + badge | planned |
| 16 | Move Tutor | Move Reminder on Two Island, Deleter in Fuchsia | Reminder/Deleter in every Pokémon Center | planned |
| 17 | Faster eggs | Normal cycles | Egg cycles halved | planned |
| 18 | More PC boxes | 14 boxes | Plan first: the flash is fully allocated (2 × 14 sectors + Hall of Fame + Trainer Tower). See `docs/PC_BOXES_PLAN.md` | planned |
| 19 | DexNav | None | Port (credit the pokeemerald-expansion / Ghoulslash DexNav) | planned |
| 20 | Following Pokémon | None | Port (credit the expansion's overworld-Pokémon implementation) | planned |

## Save suite results

| Build | save_cycles | crash_after_save | torn_save | torn_save_exact | backup_recovery |
| --- | --- | --- | --- | --- | --- |
| retail LeafGreen 1.0 | pass | pass | pass (10 captures, 8 mid-write) | | pass |
