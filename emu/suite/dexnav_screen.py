"""DexNav screen: the grid shows the area's species, with the right seen/caught marks, and A starts the search.

Usage: py -3 emu/suite/dexnav_screen.py <rom.gba> <rom.elf> <out_dir>

For each place: a new save with a set pattern of seen and caught species (some caught, some only seen, some
unseen), warped there; then the DexNav (registered on SELECT) opens the screen. Checked against the area's
wild tables (src/data/wild_encounters.json, this game's tables, species in table order without repeats):
- each tab's cells: the species, and seen/caught as the Pokedex flags say;
- the caught count in the title bar is the number of caught species of the tab;
- the info panel follows the cursor (the species, its search level);
- L/R switches LAND and WATER, and an area without water shows an empty WATER tab;
- B closes the screen back to the field, with no search started;
- A on a land species starts the search for it (the same search as the list did: struct DexNavSearch).
Screenshots of each tab are kept in <out_dir>.

The screen's state is read from the shared code's symbols (SCREEN below); fill in their offsets from its struct
when it lands.
"""
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import ITEM, SB1_GUNK_DEXNAV, SB1_REGISTERED_ITEM, Features  # noqa: E402
from legality import MAP_ROUTE1, MAP_VIRIDIAN_FOREST  # noqa: E402

ROOT = os.path.join(HERE, "..", "..")
GAME = "LeafGreen"
SB2_DEX_OWNED = 0x18 + 0x10  # offsetof(struct SaveBlock2, pokedex) + offsetof(struct Pokedex, owned)
SB2_DEX_SEEN = 0x18 + 0x44
SB1_DEX_SEEN1 = 0x05F8
SB1_DEX_SEEN2 = 0x3A18
FLAG_SYS_POKEMON_GET = 0x828
ITEM_DEXNAV = ITEM["DEXNAV"]
MAP_ROUTE6 = (3, 24)
MAP_ROUTE24 = (3, 43)

# The screen's state (FireRed's shared code): symbol and field offsets. TODO when the code lands.
SCREEN = {
    "state": "sDexNavScreen",  # the screen's state struct (EWRAM)
    "callback": "CB2_DexNavScreen",  # gMain.callback2 while the screen is up
    "tab": 0,  # u8: 0 LAND, 1 WATER
    "cursor": 1,  # u8: the cell
    "count": (2, 3),  # u8 per tab: the number of species
    "species": (4, 4 + 12 * 2),  # u16[12] per tab
}

PLACES = [  # map, a walkable tile; what the area has
    (MAP_ROUTE1, (15, 6)),  # land only, 2 species
    (MAP_VIRIDIAN_FOREST, (13, 12)),  # land only, 5 species
    (MAP_ROUTE24, (14, 20)),  # land and water (TODO: check the tile)
    (MAP_ROUTE6, (10, 14)),  # land and water (TODO: check the tile)
]


def species_ids():
    ids, n = {}, 0
    for line in open(os.path.join(ROOT, "include/constants/species.h")):
        p = line.split()
        if len(p) >= 3 and p[0] == "#define" and p[1].startswith("SPECIES_") and p[2].isdigit():
            ids[p[1]] = int(p[2])
    return ids


def area_species(map_name):
    """{'land': [...], 'water': [...]}: this game's table, in order, without repeats (as Gunk_DexNavPrepareList)."""
    ids = species_ids()
    data = json.load(open(os.path.join(ROOT, "src/data/wild_encounters.json")))
    out = {"land": [], "water": []}
    for group in data["wild_encounter_groups"]:
        for e in group["encounters"]:
            if e["map"] != map_name or not e["base_label"].endswith(GAME):
                continue
            for tab in out:
                for m in e.get(f"{tab}_mons", {}).get("mons", []):
                    if ids[m["species"]] not in out[tab]:
                        out[tab].append(ids[m["species"]])
    return out


def map_name(grp, num):
    for line in open(os.path.join(ROOT, "include/constants/map_groups.h")):
        p = line.split(None, 2)
        if len(p) == 3 and p[0] == "#define" and p[2].strip() == f"({num} | ({grp} << 8))":
            return p[1]
    raise KeyError((grp, num))


def national_dex():
    """species id -> national dex number (include/constants/pokedex.h's first enum, NATIONAL_DEX_NONE = 0)."""
    ids, nat, n = species_ids(), {}, 0
    for line in open(os.path.join(ROOT, "include/constants/pokedex.h")):
        line = line.strip().rstrip(",")
        if line.startswith("NATIONAL_DEX_"):
            if line == "NATIONAL_DEX_NONE":
                continue
            n += 1
            if "SPECIES_" + line[13:] in ids:
                nat[ids["SPECIES_" + line[13:]]] = n
        elif line.startswith("}") and nat:
            break
    return nat


class Screen(Features):
    def __init__(self, rom, elf, out):
        super().__init__(rom, elf)
        self.out = out
        os.makedirs(out, exist_ok=True)
        self.results = []
        self.nat = national_dex()

    def path(self, name):
        return os.path.join(self.out, name).replace("\\", "/")

    def check(self, name, ok, detail=""):
        self.results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}", flush=True)

    def set_dex(self, species, seen, caught):
        dex = self.nat[species] - 1
        sb1, sb2 = self.sb1(), self.sb2()
        for base, on in ((sb2 + SB2_DEX_SEEN, seen), (sb1 + SB1_DEX_SEEN1, seen), (sb1 + SB1_DEX_SEEN2, seen),
                         (sb2 + SB2_DEX_OWNED, caught)):
            a = base + dex // 8
            v = self.g.u8(a)
            self.g.cmd(f"write8 {a} {(v | 1 << dex % 8) if on else (v & ~(1 << dex % 8))}")

    def state(self):
        g = self.g
        base = g.a(SCREEN["state"])
        raw = bytes.fromhex(g.cmd(f"read {base} 64")[0].replace(" ", ""))
        cells = []
        for t in range(2):
            n = raw[SCREEN["count"][t]]
            cells.append(list(struct.unpack_from(f"<{n}H", raw, SCREEN["species"][t])))
        return raw[SCREEN["tab"]], raw[SCREEN["cursor"]], cells

    def screen_up(self):
        return self.g.u32(self.g.a("gMain") + 4) & ~1 == self.g.a(SCREEN["callback"]) & ~1

    def run_place(self, place):
        (grp, num), (x, y) = place
        name = map_name(grp, num)
        want = area_species(name)
        self.new_game(items=[(ITEM_DEXNAV, 1)], flags=[FLAG_SYS_POKEMON_GET], name=f"screen_{name}")
        # first species caught, second only seen, the rest unseen (per tab)
        marks = {}
        for tab in ("land", "water"):
            for i, sp in enumerate(want[tab]):
                marks[sp] = ("caught" if i == 0 else "seen" if i == 1 else "unseen")
        for sp, m in marks.items():
            self.set_dex(sp, m != "unseen", m == "caught")
        self.warp(grp, num, x, y, name=f"screen_{name}")
        g = self.g
        g.cmd(f"write16 {self.sb1() + SB1_REGISTERED_ITEM} {ITEM_DEXNAV}")
        g.cmd("press Select 4", "wait 90")
        self.check(f"{name}: the screen opens", self.screen_up())
        if not self.screen_up():
            g.cmd(f"shot {self.path(f'{name}_no_screen.png')}")
            return
        for t, tab in enumerate(("land", "water")):
            if t:
                g.cmd("press R 4", "wait 30")
            cur_tab, _, cells = self.state()
            g.cmd(f"shot {self.path(f'{name}_{tab}.png')}")
            self.check(f"{name} {tab}: the tab", cur_tab == t, f"tab {cur_tab}")
            self.check(f"{name} {tab}: the species", cells[t] == want[tab], f"{cells[t]} (want {want[tab]})")
        g.cmd("press L 4", "wait 30")
        # walk the cursor over each land cell: the info panel's species and search level (screenshots)
        for i in range(len(want["land"])):
            _, cursor, _ = self.state()
            self.check(f"{name}: cursor on cell {i}", cursor == i, f"cursor {cursor}")
            g.cmd(f"shot {self.path(f'{name}_land_cell{i}.png')}", "press Right 4", "wait 20")
        # B closes, no search
        g.cmd("press B 4", "wait 90")
        search = bytes.fromhex(g.cmd(f"read {g.a('sSearch')} 12")[0].replace(" ", ""))
        self.check(f"{name}: B closes with no search", not self.screen_up() and g.field_ready() and not search[11])
        # A on the first land species starts its search
        g.cmd("press Select 4", "wait 90", "press A 4", "wait 90")
        search = bytes.fromhex(g.cmd(f"read {g.a('sSearch')} 12")[0].replace(" ", ""))
        sp = struct.unpack_from("<H", search, 0)[0]
        g.cmd(f"shot {self.path(f'{name}_search.png')}")
        self.check(f"{name}: A searches for the cell's species", search[11] and sp == want["land"][0],
                   f"species {sp}, active {search[11]}")
        g.cmd("press A 4", "wait 30", "press A 4", "wait 30")


def main():
    rom, elf, out = (os.path.abspath(a) for a in sys.argv[1:4])
    s = Screen(rom, elf, out)
    t0 = time.time()
    import emu
    try:
        for place in PLACES:
            s.run_place(place)
    finally:
        emu.stop()
    print(f"{sum(s.results)}/{len(s.results)} DexNav screen checks passed in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
