"""Menus: every menu opens and closes, and leaves the field's memory as it found it.

Usage: py -3 emu/suite/menus.py <rom.gba> <rom.elf>

A new game with a Pokedex, two Pokemon, items in each Bag pocket and both registered items (DexNav on SELECT,
the Bicycle on R), standing in Pallet Town. Each case opens a menu from the field, goes through it, and backs out
to the field; then the field must be ready again with the same state as before the case:
- the heap: the number of allocated blocks and their bytes (src/malloc.c's block list);
- the active tasks, the sprites in use and the active object events (the follower included);
- the player's map and position.
Cases: each Start menu entry (POKeDEX, POKeMON, BAG, the trainer card, SAVE (backed out of), OPTION), the party's
summary pages with the IV/EV view, every Bag pocket and Bag sorting, the DexNav list, and the R registered item
(the Bicycle: on and off). Screenshots in emu/suite/out/<rom>/features/menus_*.png.
"""
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import (FLAG_SYS_POKEDEX_GET, FLAG_SYS_POKEMON_GET, ITEM, ITEM_BICYCLE, ITEM_TM09,  # noqa: E402
                      SB1_REGISTERED_ITEM, SPECIES, Features)

MAP_PALLET_TOWN = (3, 0)
STARTMENU = {"POKEDEX": 0, "POKEMON": 1, "BAG": 2, "PLAYER": 3, "SAVE": 4, "OPTION": 5}
ITEM_POKE_BALL = 4
ITEM_POTION = 13
VAR_GUNK_REGISTERED_ITEM_R = 0x402A
TASK_SIZE, NUM_TASKS = 0x28, 16
SPRITE_SIZE, NUM_SPRITES = 0x44, 64
OBJ_SIZE, NUM_OBJS = 0x24, 16


class Menus(Features):
    def heap(self):
        """(allocated blocks, allocated bytes): walk src/malloc.c's block list from sHeapStart."""
        g = self.g
        start = g.u32(g.a("sHeapStart"))
        block, blocks, size = start, 0, 0
        for _ in range(4096):
            flag, magic, n, _, nxt = struct.unpack("<HHIII", bytes.fromhex(g.cmd(f"read {block} 16")[0].replace(" ", "")))
            if magic != 0xA3A3:
                return (-1, block)  # a damaged header
            if flag:
                blocks, size = blocks + 1, size + n
            block = nxt
            if block == start:
                break
        return (blocks, size)

    def count(self, sym, size, n, offset, mask):
        raw = bytes.fromhex(self.g.cmd(f"read {self.g.a(sym)} {size * n}")[0].replace(" ", ""))
        return sum(1 for i in range(n) if raw[i * size + offset] & mask)

    def snapshot(self):
        return {"heap": self.heap(), "tasks": self.count("gTasks", TASK_SIZE, NUM_TASKS, 4, 0xFF),
                "sprites": self.count("gSprites", SPRITE_SIZE, NUM_SPRITES, 0x3E, 1),
                "objects": self.count("gObjectEvents", OBJ_SIZE, NUM_OBJS, 0, 1), "pos": self.pos()}

    def case(self, name, keys):
        g = self.g
        # the field settles first: right after a warp, the map name popup's task and its window are still up
        before = self.snapshot()
        for _ in range(20):
            g.cmd("wait 30")
            now = self.snapshot()
            if now == before:
                break
            before = now
        for k in keys:
            if k.startswith("shot"):
                self.shot(f"menus_{name}{k[4:]}.png")
            elif k.startswith("wait"):
                g.cmd(k)
            elif k.startswith("start:"):
                self.startmenu(STARTMENU[k[6:]])
            else:
                g.cmd(f"press {k} 4", "wait 30")
        back = self.back_to_field()
        g.cmd("wait 60")
        after = self.snapshot()
        # a leak is growth; less is fine (the first menu after a warp frees what the field set up for it)
        diff = {k: (before[k], after[k]) for k in before
                if (after[k] > before[k] if k in ("heap", "tasks", "sprites") else after[k] != before[k])}
        self.record(f"menu: {name}", back and not diff, f"field back {back}; " + (
            f"changed {diff}" if diff else f"unchanged {after}"))


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    m = Menus(rom, elf)
    t0 = time.time()
    import emu
    try:
        m.new_game(mons=[(SPECIES["BULBASAUR"], 12), (SPECIES["PIKACHU"], 10)],
                   items=[(ITEM_POTION, 3), (ITEM["REPEL"], 2), (ITEM_POKE_BALL, 5), (ITEM["RARE_CANDY"], 1),
                          (ITEM_TM09, 1), (ITEM["DEXNAV"], 1), (ITEM_BICYCLE, 1)],
                   flags=[FLAG_SYS_POKEMON_GET, FLAG_SYS_POKEDEX_GET], name="menus")
        m.warp(*MAP_PALLET_TOWN, 8, 10, name="menus_warp")
        m.g.cmd(f"write16 {m.sb1() + SB1_REGISTERED_ITEM} {ITEM['DEXNAV']}")
        m.set_var(VAR_GUNK_REGISTERED_ITEM_R, ITEM_BICYCLE)
        m.case("pokedex", ["start:POKEDEX", "wait 60", "shot", "B", "B"])
        m.case("party", ["start:POKEMON", "shot", "B"])
        # the lead's summary: A, SUMMARY, the three pages, A on SKILLS for the IV/EV view, then out
        m.case("summary", ["start:POKEMON", "A", "A", "wait 60", "shot_info", "Right", "wait 30", "shot_skills", "A",
                           "wait 30", "shot_ivev", "A", "Right", "wait 30", "shot_moves", "B", "wait 60", "B"])
        m.case("bag", ["start:BAG", "shot_items", "Right", "shot_key", "Right", "shot_balls", "Left", "Left", "Start",
                       "wait 30", "shot_sorted", "B"])
        m.case("trainer_card", ["start:PLAYER", "wait 60", "shot", "A", "wait 60", "shot_back", "B", "wait 60"])
        m.case("save_backed_out", ["start:SAVE", "wait 30", "shot", "B"])
        m.case("option", ["start:OPTION", "shot", "B"])
        m.case("dexnav", ["Select", "wait 60", "shot", "B"])
        m.case("bicycle", ["R", "wait 60", "shot_on", "R", "wait 60", "shot_off"])
    except RuntimeError as e:
        m.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in m.results if not r[1]]
    print(f"{len(m.results) - len(failed)}/{len(m.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(m.out, "menus.txt"), "w") as f:
        for check, ok, detail in m.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
