"""DexNav held items: py -3 emu/suite/dexnav_items.py <rom.gba> <rom.elf> [searches]

On Route 13, Ditto (no common item, Metal Powder as its rare one). The search chooses what its Pokemon holds as it
starts (src/gunk_dexnav.c, ChooseHeldItem): the species' own wild items, at 5% for the rare one at search level 0
with no chain, up to 20% at the top (search level 100 and a chain of 40: 5 + 20 + 80, capped).
- <searches> searches at the top: every item is Metal Powder or nothing, and Metal Powder comes up clearly more
  often than vanilla's 5% (at least 10%: 20% expected; with 40 searches, under 10% has odds of about 1 in 30);
- one of them is fought: the battle's Pokemon holds what the search chose (SetWildMonHeldItem asks
  Gunk_DexNavHeldItem in a DexNav battle).
Results: emu/suite/out/<rom>/features/dexnav_items.txt.
"""
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dexnav_screen import MAP_ROUTE13, STAND, TRAINER_FLAGS_START, Screen  # noqa: E402
from features import (FLAG_SYS_POKEDEX_GET, FLAG_SYS_POKEMON_GET, ITEM, SB1_FLAGS, SB1_GUNK_DEXNAV,  # noqa: E402
                      SB1_REGISTERED_ITEM, SPECIES)
from lib import decode_mon  # noqa: E402

SPECIES_DITTO = 132
ITEM_METAL_POWDER = 223
FLAG_GUNK_ENDLESS_REPEL_ON = 0x4A7
SEARCH_HELD_ITEM = 32  # struct DexNavSearch.heldItem
CHAIN_SPECIES = 386  # in the DexNav save data: the chain's species (u16), then its count
CHAIN_COUNT = 388


class Items(Screen):
    def held(self):
        return struct.unpack("<H", bytes.fromhex(self.g.cmd(
            f"read {self.g.a('sSearch') + SEARCH_HELD_ITEM} 2")[0].replace(" ", "")))[0]

    def state(self):
        g = self.g
        return {"callback2": hex(self.callback2()), "field_ready": g.field_ready(), "in_battle": self.in_battle(),
                "locked": g.u8(g.a("sLockFieldControls")), "script": g.u8(g.a("sGlobalScriptContextStatus")),
                "screen": hex(g.u32(g.a("sDexNavScreen"))), "pos": self.pos(), "search": self.search(),
                "registered": self.u16(self.sb1() + SB1_REGISTERED_ITEM)}

    def search_ditto(self, row):
        """One search for Ditto: the item it chose, or None. Stops the test at the first search that can't start,
        with the field's state as it was (nothing pressed since), to tell a game fault from a test one."""
        g = self.g
        g.cmd("wait 30")
        before = self.state()
        self.shot("dexnav_items_before.png")
        if self.open_screen("dexnav_items_screen.png") is None or not self.goto_cell(row, 0):
            print(f"the screen didn't open or the cursor didn't reach row {row}", flush=True)
            print(f"  before SELECT: {before}", flush=True)
            print(f"  now: {self.state()}", flush=True)
            self.shot("dexnav_items_no_screen.png")
            raise RuntimeError("the DexNav screen didn't open (state above; dexnav_items_before.png)")
        g.cmd("press A 4")
        if not self.back_in_field():
            return None
        g.wait_field(press="B", max_steps=30)  # "The grass is rustling nearby..."
        s = self.search()
        if not (s["active"] and s["species"] == SPECIES_DITTO):
            print(f"search didn't start for Ditto: {s}, cursor row {row}", flush=True)
            self.shot("dexnav_items_no_search.png")
            return None
        # the search's 10 seconds can run out before the next one starts (each loop takes longer), and its "got away"
        # message then blocks SELECT: give it all the time it needs; the next search ends it the normal way
        g.cmd(f"write16 {g.a('sSearch') + 8} 65535")
        return self.held()


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    t = Items(rom, elf)
    g = t.g
    t0 = time.time()
    import emu
    try:
        t.new_game(mons=[(SPECIES["PIKACHU"], 100)], items=[(ITEM["DEXNAV"], 1)],
                   flags=[FLAG_SYS_POKEMON_GET, FLAG_SYS_POKEDEX_GET, FLAG_GUNK_ENDLESS_REPEL_ON], name="dexnav_items")
        t.warp(*MAP_ROUTE13, *STAND, name="dexnav_items_route13")
        g.wait_field(press="B", max_steps=60)
        t.set_dex(SPECIES_DITTO, False)
        g.cmd(f"write16 {t.sb1() + SB1_REGISTERED_ITEM} {ITEM['DEXNAV']}")
        # every trainer beaten: Route 13's trainers would spot the player between searches and start a battle
        for byte in range(TRAINER_FLAGS_START // 8, (TRAINER_FLAGS_START + 768) // 8):
            g.cmd(f"write8 {t.sb1() + SB1_FLAGS + byte} 255")
        # the list is made when the screen opens
        t.open_screen("dexnav_items_first.png")
        g.cmd("press B 4")
        t.back_in_field()
        row = [sp for sp, area in t.list()].index(SPECIES_DITTO)
        dex = t.sb1() + SB1_GUNK_DEXNAV
        held = []
        for _ in range(n):
            # the top: search level 100 and a chain of 40 Ditto (set again each time: nothing here changes them)
            g.cmd(f"write8 {dex + SPECIES_DITTO - 1} 100", f"write16 {dex + CHAIN_SPECIES} {SPECIES_DITTO}",
                  f"write8 {dex + CHAIN_COUNT} 40")
            held.append(t.search_ditto(row))
        made = [h for h in held if h is not None]
        bad = [h for h in made if h not in (0, ITEM_METAL_POWDER)]
        powder = made.count(ITEM_METAL_POWDER)
        t.record("every search started", len(made) == n, f"{len(made)}/{n} searches started")
        t.record("only Ditto's own wild items", made and not bad, f"items {sorted(set(made))}")
        t.record("better odds at the top (at least 10% Metal Powder; 20% expected, 5% vanilla)",
                 made and powder * 10 >= len(made), f"Metal Powder {powder}/{len(made)}")

        # fight the last search's Ditto: it holds what the search chose
        # (the patch is across the fence from here: the search's patch moves to the tile right of the player, and
        # the step onto it starts the battle as on any patch; this checks the item, not the walk)
        if held[-1] is None:  # the battle needs a running Ditto search
            held.append(t.search_ditto(row))
        chosen = held[-1]
        px, py = t.pos()
        g.cmd(f"write16 {g.a('sSearch') + 2} {px + 1 + 7}", f"write16 {g.a('sSearch') + 4} {py + 7}")
        g.cmd("press Right 16")
        for _ in range(30):
            if t.in_battle():
                break
            g.cmd("wait 20")
        g.cmd("wait 120")
        enemy = decode_mon(bytes.fromhex(g.cmd(f"read {g.a('gEnemyParty')} 100")[0].replace(" ", "")))
        t.shot("dexnav_items_battle.png")
        t.record("the battle's Ditto holds the search's item", t.in_battle() and enemy["species"] == SPECIES_DITTO
                 and enemy["item"] == chosen, f"battle {t.in_battle()}, species {enemy['species']}, "
                 f"item {enemy['item']} (search chose {chosen})")
    except RuntimeError as e:
        t.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in t.results if not r[1]]
    print(f"{len(t.results) - len(failed)}/{len(t.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(t.out, "dexnav_items.txt"), "w") as f:
        for check, ok, detail in t.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
