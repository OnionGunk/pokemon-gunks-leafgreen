"""The DexNav in every wild area of this game: py -3 emu/suite/dexnav_areas.py <rom.gba> <rom.elf> [first] [count]

For each map with an encounter table for this game (src/data/wild_encounters.json, the _FireRed or _LeafGreen
tables; the Safari Zone is left out, dexnav_safari.py covers it):
- list: warped there, the DexNav screen lists exactly that map's Pokemon (land, water, rod and Rock Smash);
- land / water search: standing where a land (or water) encounter tile is in DexNav range, a search for the
  map's first land (water) Pokemon starts. The stand tile is chosen from the map files: a passable tile with the
  most land (water) encounter tiles 2 to 5 tiles away, in the window the DexNav looks in.
Then, with "catch" as the 3rd argument instead: every species only this game has in its land tables, caught from
a DexNav search on one of its maps (a Master Ball), written to <out>/catches as .pk3 for PKHeX.
Every wait is bounded. Results: emu/suite/out/<rom>/features/dexnav_areas.txt (dexnav_areas_catch.txt).
"""
import collections
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dexnav_screen import AREA_TAB, Screen, rom_game  # noqa: E402
from features import FLAG_SYS_POKEDEX_GET, FLAG_SYS_POKEMON_GET, ITEM, SB1_FLAGS, SB1_REGISTERED_ITEM, SPECIES  # noqa: E402
from legality import Catcher  # noqa: E402
import story  # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
FLAG_GUNK_ENDLESS_REPEL_ON = 0x4A7
FLAG_BADGE05_GET = 0x824
FLAG_SYS_UNLOCKED_TANOBY_RUINS = 0x849  # without it the Tanoby chambers have no encounters
TRAINER_FLAGS_START = 0x500
ITEM_MASTER_BALL = 1
AREAS = ((0, "land_mons"), (1, "water_mons"), (2, "rock_smash_mons"), (3, "fishing_mons"))
TILE_ENCOUNTER_LAND, TILE_ENCOUNTER_WATER = 1, 2
# the DexNav's window (Gunk_DexNavStartSearch): 2 to 5 tiles away (dx + dy), at most 6 across and 4 up or down
# stand tiles: plain ground (normal, tall grass, cave, sand, indoor, mountain top, Mt. Ember's slope), so the
# warp puts the player exactly there
PLAIN = {0x00, 0x02, 0x08, 0x0B, 0x0C, 0x2B, 0x32}
WINDOW = [(dx, dy) for dy in range(-4, 5) for dx in range(-6, 7) if 2 <= abs(dx) + abs(dy) <= 5]


def species_ids():
    ids = {}
    for line in open(os.path.join(REPO, "include/constants/species.h")):
        p = line.split()
        if len(p) >= 3 and p[0] == "#define" and p[1].startswith("SPECIES_") and p[2].isdigit():
            ids[p[1]] = int(p[2])
    return ids


def tables():
    """{game: {map id: {(species, area)}}} from src/data/wild_encounters.json"""
    ids = species_ids()
    out = {"FireRed": collections.defaultdict(set), "LeafGreen": collections.defaultdict(set)}
    for group in json.load(open(os.path.join(REPO, "src/data/wild_encounters.json")))["wild_encounter_groups"]:
        for e in group["encounters"]:
            for game in out:
                if e["base_label"].endswith("_" + game):
                    for area, key in AREAS:
                        out[game][e["map"]] |= {(ids[m["species"]], area) for m in e.get(key, {}).get("mons", [])}
    return out


def tileset_attrs():
    """{tileset symbol: [u32 metatile attributes]}, from src/data/tilesets/headers.h and metatiles.h"""
    import re
    files = dict(re.findall(r"(gMetatileAttributes_\w+)\[\] = INCBIN_U32\(\"([^\"]+)\"\)",
                            open(os.path.join(REPO, "src/data/tilesets/metatiles.h")).read()))
    out = {}
    for name, attrs in re.findall(r"const struct Tileset (\w+) =\s*\{[^}]*?\.metatileAttributes = (\w+)",
                                  open(os.path.join(REPO, "src/data/tilesets/headers.h")).read()):
        raw = open(os.path.join(REPO, files[attrs]), "rb").read()
        out[name] = [struct.unpack_from("<I", raw, i)[0] for i in range(0, len(raw), 4)]
    return out


def map_tiles(m, layouts, attrs):
    """(width, height, at(x, y) -> (behavior, encounter type, collision)) for map <m>"""
    layout = layouts[m["layout"]]
    at = story.blocks(layout)
    prim, sec = attrs[layout["primary_tileset"]], attrs[layout["secondary_tileset"]]

    def tile(x, y):
        b = at(x, y)
        if b is None:
            return None
        meta = b & 0x3FF
        a = prim[meta] if meta < 640 else sec[meta - 640] if meta - 640 < len(sec) else 0
        return a & 0x1FF, (a >> 24) & 7, (b >> 10) & 3
    return layout["width"], layout["height"], tile


def stand_tile(m, layouts, attrs, encounter):
    """The passable tile (no object, warp or trigger on it) with the most <encounter>-type tiles in the DexNav's
    window, and how many of those are tall grass: (x, y, tiles, grass), or None."""
    w, h, tile = map_tiles(m, layouts, attrs)
    taken = {(o["x"], o["y"]) for key in ("object_events", "warp_events", "coord_events", "bg_events")
             for o in m.get(key) or []}
    best = None
    for y in range(h):
        for x in range(w):
            t = tile(x, y)
            if (x, y) in taken or t[2] or t[1] == TILE_ENCOUNTER_WATER or t[0] not in PLAIN:
                continue
            n = grass = 0
            for dx, dy in WINDOW:
                u = tile(x + dx, y + dy)
                if u and u[1] == encounter and not u[2] and (x + dx, y + dy) not in taken:
                    n += 1
                    grass += u[0] == 0x02
            if n and (best is None or n > best[2]):
                best = (x, y, n, grass)
    return best


class Areas(Catcher, Screen):
    def setup(self, game_maps, first):
        self.new_game(mons=[(SPECIES["PIKACHU"], 100)], items=[(ITEM_MASTER_BALL, 99), (ITEM["DEXNAV"], 1)],
                      flags=[FLAG_SYS_POKEMON_GET, FLAG_SYS_POKEDEX_GET, FLAG_GUNK_ENDLESS_REPEL_ON, FLAG_BADGE05_GET,
                             FLAG_SYS_UNLOCKED_TANOBY_RUINS],
                      name="dexnav_areas")
        g = self.g
        self.seen_all()
        g.cmd(f"write16 {self.sb1() + SB1_REGISTERED_ITEM} {ITEM['DEXNAV']}")
        for byte in range(TRAINER_FLAGS_START // 8, (TRAINER_FLAGS_START + 768) // 8):
            g.cmd(f"write8 {self.sb1() + SB1_FLAGS + byte} 255")

    def go(self, m, x, y):
        if not self.g.field_ready():
            # still in a battle or its messages: the Lv. 100 lead finishes it (the save needs the field)
            self.g.wait_field(press="A", max_steps=400)
        self.warp(m["group"], m["num"], x, y, name="dexnav_areas_warp")
        self.g.wait_field(press="B", max_steps=60)
        if self.pos() != (x, y):
            # a scene on arrival moved the player (Four Island's rival walks up and talks): walk back
            self.g.wait_field(press="B", max_steps=200)
            self.path_to(m, x, y)
        return self.pos() == (x, y)

    def path_to(self, m, tx, ty):
        """Walk to (tx, ty) along a shortest path over the map file's passable land tiles (not water, a ledge or a
        tile with someone on it), one press per tile; stops at a battle. True when there."""
        w, h, tile = map_tiles(m, story.neighbour.layouts, self.attrs)
        height = story.blocks(story.neighbour.layouts[m["layout"]])
        people = {(o["x"], o["y"]) for o in m.get("object_events") or []}

        def free(x, y, fx, fy):
            u = tile(x, y)
            if u is None or u[2] or u[1] == TILE_ENCOUNTER_WATER or 0x38 <= u[0] <= 0x3B:
                return False
            a, b = height(fx, fy) >> 12, height(x, y) >> 12  # elevations: 0 and 15 join any (CanStepOnFoot)
            return (a == b or 0 in (a, b) or 15 in (a, b)) and ((x, y) == (tx, ty) or (x, y) not in people)
        start = self.pos()
        prev = {start: None}
        todo = collections.deque([start])
        while todo and (tx, ty) not in prev:
            x, y = todo.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in prev and free(nx, ny, x, y):
                    prev[(nx, ny)] = (x, y)
                    todo.append((nx, ny))
        if (tx, ty) not in prev:
            return False
        path = [(tx, ty)]
        while prev[path[-1]] != start:
            path.append(prev[path[-1]])
        for nx, ny in reversed(path):
            for _ in range(4):  # a tap on a new direction only turns the player: press again until they move
                x, y = self.pos()
                if (x, y) == (nx, ny):
                    break
                d = "Right" if nx > x else "Left" if nx < x else "Down" if ny > y else "Up"
                self.g.cmd(f"press {d} 8", "wait 10")
                if self.in_battle():
                    return False
        return self.pos() == (tx, ty)

    def try_search(self, row, tab):
        """A on list row <row>: (search active, species, patch, message)"""
        g = self.g
        s = self.open_screen("dexnav_areas_screen.png")
        if not s or not self.goto_cell(row, tab):
            g.cmd("press B 4")
            self.back_in_field()
            return False, 0, None
        g.cmd("press A 4", "wait 150")
        found = self.search()
        g.wait_field(press="A", max_steps=40)
        if found["active"]:
            g.cmd("wait 20")
            self.shot(f"dexnav_areas_patch_{self.map_name}_{tab}.png")
        return bool(found["active"]), found["species"], (found["x"], found["y"])


def run_lists(t, todo, out_lines):
    g = t.g
    for name, m, expected in todo:
        land = stand_tile(m, story.neighbour.layouts, t.attrs, TILE_ENCOUNTER_LAND)
        water = stand_tile(m, story.neighbour.layouts, t.attrs, TILE_ENCOUNTER_WATER)
        spot = land or water
        t.map_name = name[4:].lower()
        if spot is None:
            t.record(f"{name}: a tile to stand on", False, "no land or water encounter tile in the map files")
            continue
        if not t.go(m, spot[0], spot[1]):
            t.record(f"{name}: warp", False, f"at {t.pos()}, wanted {spot[:2]}")
            continue
        t.open_screen("dexnav_areas_list.png")
        listed = t.list() if g.u8(g.a("sListCount")) else []
        g.cmd("press B 4")
        t.back_in_field()
        t.record(f"{name}: the list is this game's table", set(listed) == expected and len(listed) == len(expected),
                 f"{len(listed)} listed, missing {sorted(expected - set(listed))}, extra {sorted(set(listed) - expected)}")
        for area, stand, label in ((0, land, "land"), (1, water, "water")):
            rows = [i for i, (sp, a) in enumerate(listed) if a == area]
            if not rows:
                continue
            if stand is None:
                # a table with no tile for it (Route 21 South's land table: its grass is all on Route 21 North),
                # so no wild battle there either
                t.record(f"{name}: {label} search", True, f"no {label} encounter tile in the map: nothing to search")
                continue
            if stand[:2] != t.pos() and not t.go(m, stand[0], stand[1]):
                t.record(f"{name}: {label} search", False, f"warp to {stand[:2]} failed, at {t.pos()}")
                continue
            ok, sp, patch = t.try_search(rows[0], AREA_TAB[area])
            t.record(f"{name}: {label} search", ok and sp == listed[rows[0]][0],
                     f"from {stand[:2]} ({stand[2]} {label} tiles in range, {stand[3]} tall grass): "
                     f"active {ok}, species {sp}, patch {patch}")


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].isdigit() else "lists"
    nums = [int(a) for a in sys.argv[3:] if a.isdigit()]
    first, count = (nums + [0, 1000])[:2] if nums else (0, 1000)
    game = rom_game(rom)
    other = {"FireRed": "LeafGreen", "LeafGreen": "FireRed"}[game]
    tabs = tables()
    maps = {m["id"]: m for m in story.maps().values()}
    story.neighbour.layouts = story.layouts()
    todo = [(mid, maps[mid], exp) for mid, exp in sorted(tabs[game].items()) if "SAFARI_ZONE" not in mid]
    out_name = "dexnav_areas.txt" if mode == "lists" else "dexnav_areas_catch.txt"

    t = Areas(rom, elf, os.path.join(HERE, "out", os.path.splitext(os.path.basename(rom))[0], "catches"))
    t.attrs = tileset_attrs()
    t0 = time.time()
    import emu
    try:
        t.setup(maps, first)
        if mode == "lists":
            run_lists(t, todo[first:first + count], [])
        else:
            # the Endless Repel off: with it, the Lv. 100 lead would keep the searched Pokemon away too
            t.clear_flag(FLAG_GUNK_ENDLESS_REPEL_ON)
            mine = mine_land(tabs, game, other)
            if os.environ.get("CATCH_ONLY"):  # a comma-separated list of species, to retry a few
                mine &= {int(s) for s in os.environ["CATCH_ONLY"].split(",")}
            done = set()
            for mid, m, exp in todo:
                for sp in sorted(sp for sp, a in exp if a == 0 and sp in mine and sp not in done):
                    stand = stand_tile(m, story.neighbour.layouts, t.attrs, TILE_ENCOUNTER_LAND)
                    found, got, attempt = (0, 0, 0, 0, 0), 0, 0
                    for attempt in range(3):  # a random battle on the way to the patch: try again
                        if not stand or not t.go(m, stand[0], stand[1]):
                            break
                        t.open_screen("dexnav_areas_catch.png")
                        listed = t.list()
                        t.goto_cell([i for i, (s, a) in enumerate(listed) if (s, a) == (sp, 0)][0], 0)
                        found = t.start_search()
                        t.g.wait_field(press="A", max_steps=40)
                        if not found[3]:  # read before the screen had closed: read it again now
                            s = t.search()
                            found = (s["species"], s["x"], s["y"], s["active"], s["pid"])
                        raw = None
                        if found[3]:
                            t.path_to(m, found[1], found[2])
                            # a DexNav battle, not a random one on the way: sSearch.inBattle, set as the step
                            # starts it; the battle screen comes after the transition
                            dexnav_battle = False
                            for _ in range(40):
                                dexnav_battle = dexnav_battle or t.g.u8(t.g.a("sSearch") + 12) == 1
                                if t.in_battle():
                                    break
                                t.g.cmd("wait 10")
                            dexnav_battle = (dexnav_battle or t.g.u8(t.g.a("sSearch") + 12) == 1) and t.in_battle()
                            raw = t.catch() if dexnav_battle else None
                            if t.in_battle():
                                t.g.wait_field(press="A", max_steps=200)  # a random battle: the Lv. 100 lead wins it
                        got = struct.unpack_from("<H", t.decrypted(raw), 0)[0] if raw else 0
                        t.shot(f"dexnav_areas_catch_{sp}_{attempt}.png")
                        print(f"species {sp} try {attempt}: search {found[:4]}, at {t.pos()}, battle {t.in_battle()}, "
                              f"caught {got}", flush=True)
                        t.g.wait_field(press="B", max_steps=60)
                        if got == sp:
                            break
                    t.record(f"{mid}: DexNav catch of species {sp}", got == sp,
                             f"search active {bool(found[3])} species {found[0]}, caught {got}, tries {attempt + 1}")
                    if got == sp:
                        t.keep(raw, f"{mid[4:].lower()}_{sp}")
                        done.add(sp)
            t.record("every species only this game has on land was caught", mine <= done,
                     f"missing {sorted(mine - done)}")
    except RuntimeError as e:
        t.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in t.results if not r[1]]
    print(f"{len(t.results) - len(failed)}/{len(t.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(t.out, out_name), "w") as f:
        for check, ok, detail in t.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


def mine_land(tabs, game, other):
    """The species only <game> has, in some land table outside the Safari Zone"""
    theirs = {sp for exp in tabs[other].values() for sp, a in exp}
    return {sp for mid, exp in tabs[game].items() if "SAFARI_ZONE" not in mid for sp, a in exp if a == 0} - theirs


if __name__ == "__main__":
    main()
