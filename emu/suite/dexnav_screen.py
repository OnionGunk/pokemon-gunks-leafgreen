"""The DexNav screen: py -3 emu/suite/dexnav_screen.py <rom.gba> <rom.elf>

On Route 13 (6 grass Pokemon, Tentacool on the water) the DexNav opens its screen: a LAND and a WATER tab with one
cell per Pokemon, an icon for the ones seen and "?" for the rest, a ball mark on the caught ones, the cursor moving
with the D-pad and L/R, B going back with no search, A starting a search for the highlighted one. Then a water
search: the patch is on water, and surfing onto it starts the battle with the Pokemon picked. Every wait is bounded.
Results: emu/suite/out/<rom>/features/dexnav_screen.txt.
"""
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import (FLAG_SYS_POKEDEX_GET, FLAG_SYS_POKEMON_GET, ITEM, SB1_FLAGS, SB1_GUNK_DEXNAV,  # noqa: E402
                      SB1_REGISTERED_ITEM, SPECIES, Features)
from lib import SUBSTRUCT_ORDERS  # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
MAP_ROUTE13 = (3, 31)
STAND = (54, 11)  # a tile on Route 13 with tall grass and water both in DexNav range
FLAG_GUNK_ENDLESS_REPEL_ON = 0x4A7
FLAG_BADGE05_GET = 0x824
MOVE_SURF = 57
TRAINER_FLAGS_START = 0x500
SB2_DEX_OWNED = 0x18 + 0x10
SB2_DEX_SEEN = 0x18 + 0x44
SB1_SEEN1 = 0x05F8
SB1_SEEN2 = 0x3A18
# Route 13's list: (species, area) with 0 land and 1 water
EXPECTED = {(48, 0), (16, 0), (43, 0), (132, 0), (17, 0), (44, 0), (72, 1)}
SEEN = {16, 43, 72}  # Pidgey, Oddish, Tentacool
CAUGHT = {16}  # Pidgey
COL_BALL = 14  # DXCOL_BALL (src/data/gunk_dexnav_skin.h)
MAX_SPRITES = 64
WATER_BEHAVIORS = {0x10, 0x11, 0x12, 0x15}


def map_behaviors():
    """Route 13's metatile behaviors and collision, from the repo's layout and tilesets."""
    def attrs(p):
        b = open(p, "rb").read()
        return [struct.unpack_from("<I", b, i)[0] & 0x1FF for i in range(0, len(b), 4)]
    prim = attrs(os.path.join(REPO, "data", "tilesets", "primary", "general", "metatile_attributes.bin"))
    sec = attrs(os.path.join(REPO, "data", "tilesets", "secondary", "lavender_town", "metatile_attributes.bin"))
    raw = open(os.path.join(REPO, "data", "layouts", "Route13", "map.bin"), "rb").read()
    w = 72
    grid = [struct.unpack_from("<H", raw, 2 * i)[0] for i in range(len(raw) // 2)]

    def at(x, y):
        m = grid[y * w + x]
        meta = m & 0x3FF
        return (prim[meta] if meta < 640 else sec[meta - 640]), (m >> 10) & 3
    return at


class Screen(Features):
    def callback2(self):
        return self.g.u32(self.g.a("gMain") + 4) & ~1

    def overworld(self):
        return self.callback2() == self.g.a("CB2_Overworld")

    def set_dex(self, species, owned):
        """Seen (in all three copies the game checks) and, if <owned>, caught."""
        sb1, sb2 = self.sb1(), self.sb2()
        for base, on in ((sb2 + SB2_DEX_SEEN, True), (sb1 + SB1_SEEN1, True), (sb1 + SB1_SEEN2, True),
                         (sb2 + SB2_DEX_OWNED, owned)):
            if on:
                addr = base + (species - 1) // 8
                self.g.cmd(f"write8 {addr} {self.g.u8(addr) | 1 << ((species - 1) % 8)}")

    def set_first_move(self, slot, move, pp):
        """Party slot <slot>'s first move becomes <move> (the encrypted attacks substruct, then the checksum)."""
        addr = self.g.a("gPlayerParty") + slot * 100
        raw = bytearray(bytes.fromhex(self.g.cmd(f"read {addr} 100")[0].replace(" ", "")))
        pid, otid = struct.unpack_from("<II", raw, 0)
        key = pid ^ otid
        dec = bytearray(b"".join(struct.pack("<I", struct.unpack_from("<I", raw, 0x20 + i)[0] ^ key)
                                 for i in range(0, 48, 4)))
        a = SUBSTRUCT_ORDERS[pid % 24].index("A") * 12
        struct.pack_into("<H", dec, a, move)
        dec[a + 8] = pp
        struct.pack_into("<H", raw, 0x1C, sum(struct.unpack_from("<24H", dec)) & 0xFFFF)
        for i in range(0, 48, 4):
            struct.pack_into("<I", raw, 0x20 + i, struct.unpack_from("<I", dec, i)[0] ^ key)
        path = self.path("_mon.bin")
        open(path, "wb").write(bytes(raw))
        self.g.cmd(f"poke EWRAM {addr - 0x02000000} {path}")

    def list(self):
        g = self.g
        n = g.u8(g.a("sListCount"))
        sp = struct.unpack(f"<{n}H", bytes.fromhex(g.cmd(f"read {g.a('sListSpecies')} {2 * n}")[0].replace(" ", "")))
        ar = bytes.fromhex(g.cmd(f"read {g.a('sListArea')} {n}")[0].replace(" ", ""))
        return list(zip(sp, ar))

    def screen(self):
        """struct DexNavScreen (src/gunk_dexnav_screen.c): count, cursor, tab, state, iconSpriteIds[17],
        cellX[17], cellY[17], row[17], col[17], tabCount[2]"""
        g = self.g
        ptr = g.u32(g.a("sDexNavScreen"))
        if not ptr:
            return None
        raw = bytes.fromhex(g.cmd(f"read {ptr} 91")[0].replace(" ", ""))
        return {"count": raw[0], "cursor": raw[1], "tab": raw[2], "icons": raw[4:21], "x": raw[21:38],
                "y": raw[38:55], "row": raw[55:72], "col": raw[72:89], "tabs": raw[89:91]}

    def goto_cell(self, target, area):
        """Move the cursor to list row <target> (in tab <area>): R to its tab, then Up/Down, then Left/Right."""
        g = self.g
        for _ in range(24):
            s = self.screen()
            cur = s["cursor"]
            if cur == target:
                return True
            if s["tab"] != area:
                g.cmd("press R 4", "wait 12")
            elif s["row"][cur] != s["row"][target]:
                g.cmd(f"press {'Down' if s['row'][cur] < s['row'][target] else 'Up'} 4", "wait 12")
            else:
                g.cmd(f"press {'Right' if s['col'][cur] < s['col'][target] else 'Left'} 4", "wait 12")
        return self.screen()["cursor"] == target

    def grid_pixel(self, x, y):
        """A pixel of the grid window (window 2, 16 tiles wide), as a palette index."""
        g = self.g
        tile_data = g.u32(g.a("gWindows") + 2 * 12 + 8)
        tile = (y // 8) * 16 + x // 8
        b = g.u8(tile_data + tile * 32 + (y % 8) * 4 + (x % 8) // 2)
        return (b >> 4) if x % 2 else (b & 0xF)

    def open_screen(self, name):
        g = self.g
        for i in range(60):
            if i % 15 == 0:
                g.cmd("press Select 4")
            g.cmd("wait 10")
            if self.callback2() == g.a("CB2_DexNavScreen") and self.screen():
                break
        g.cmd("wait 40")  # the fade in
        self.shot(name)
        return self.screen()

    def back_in_field(self, presses=20):
        g = self.g
        for _ in range(presses):
            g.cmd("wait 20")
            if self.overworld() and g.u32(g.a("sDexNavScreen")) == 0:
                return True
        return False

    def search(self):
        """struct DexNavSearch (src/gunk_dexnav.c), with the chosen roll (struct GunkDexNavRoll) at 20"""
        raw = bytes.fromhex(self.g.cmd(f"read {self.g.a('sSearch')} 32")[0].replace(" ", ""))
        species, sx, sy = struct.unpack_from("<Hhh", raw, 0)
        pid, = struct.unpack_from("<I", raw, 20)
        return {"species": species, "x": sx - 7, "y": sy - 7, "active": raw[11], "area": raw[14],
                "pid": pid, "level": raw[28]}

    def hud_shown(self):
        return self.g.u8(self.g.a("sHudShown"))


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    t = Screen(rom, elf)
    g = t.g
    t0 = time.time()
    at = map_behaviors()
    import emu
    try:
        t.new_game(mons=[(SPECIES["PIKACHU"], 100)], items=[(ITEM["DEXNAV"], 1)],
                   flags=[FLAG_SYS_POKEMON_GET, FLAG_SYS_POKEDEX_GET, FLAG_GUNK_ENDLESS_REPEL_ON, FLAG_BADGE05_GET],
                   name="dexnav_screen")
        t.warp(*MAP_ROUTE13, *STAND, name="dexnav_screen_route13")
        g.wait_field(press="B", max_steps=60)
        for sp in SEEN:
            t.set_dex(sp, sp in CAUGHT)
        g.cmd(f"write8 {t.sb1() + SB1_GUNK_DEXNAV + 16 - 1} 12")  # Pidgey's search level
        g.cmd(f"write16 {t.sb1() + SB1_REGISTERED_ITEM} {ITEM['DEXNAV']}")
        # every trainer beaten, so no trainer on Route 13 stops the walk to the shore
        for byte in range(TRAINER_FLAGS_START // 8, (TRAINER_FLAGS_START + 768) // 8):
            g.cmd(f"write8 {t.sb1() + SB1_FLAGS + byte} 255")

        s = t.open_screen("dexnav_screen_open.png")
        listed = t.list()
        t.record("the DexNav screen opens", s is not None and t.callback2() == g.a("CB2_DexNavScreen"),
                 f"callback {t.callback2():#x}, screen {s and s['count']}")
        if s is None:
            raise RuntimeError("the DexNav screen never opened")
        t.record("every grass and water Pokemon has a cell", set(listed) == EXPECTED and s["count"] == len(EXPECTED),
                 f"list {listed}")

        wrong = [(sp, s["icons"][i]) for i, (sp, area) in enumerate(listed)
                 if (s["icons"][i] < MAX_SPRITES) != (sp in SEEN)]
        t.record("an icon for each seen Pokemon, '?' for the rest", not wrong, f"wrong {wrong}")

        wrong = []
        for i, (sp, area) in enumerate(listed):
            if area != s["tab"]:
                continue
            ball = t.grid_pixel(s["x"][i] + 32 - 11 + 3, s["y"][i] + 3 + 1) == COL_BALL
            if ball != (sp in CAUGHT):
                wrong.append((sp, ball))
        t.record("a ball mark on the caught Pokemon only", not wrong, f"wrong {wrong}")

        water = [i for i, (sp, area) in enumerate(listed) if area == 1]
        t.record("LAND and WATER tabs", s["tab"] == 0 and list(s["tabs"]) == [6, 1]
                 and all(s["row"][i] == 0 and s["col"][i] == 0 for i in water),
                 f"tab {s['tab']}, tab counts {list(s['tabs'])}, "
                 f"water cells {[(s['row'][i], s['col'][i]) for i in water]}")

        start = s["cursor"]
        g.cmd("press Right 4", "wait 20")
        right = t.screen()["cursor"]
        g.cmd("press Down 4", "wait 20")
        down = t.screen()["cursor"]
        t.shot("dexnav_screen_moved.png")
        g.cmd("press Up 4", "wait 20")
        up = t.screen()["cursor"]
        t.record("the D-pad moves the cursor", right == start + 1 and s["row"][down] == s["row"][right] + 1
                 and up == right, f"start {start}, right {right}, down {down} (row {s['row'][down]}), up {up}")
        g.cmd("press R 4", "wait 30")
        r = t.screen()
        t.shot("dexnav_screen_water_tab.png")
        g.cmd("press L 4", "wait 30")
        back = t.screen()
        t.record("L/R switch between LAND and WATER", r["tab"] == 1 and r["cursor"] == water[0] and back["tab"] == 0,
                 f"after R tab {r['tab']} cursor {r['cursor']}, after L tab {back['tab']}")

        g.cmd("press B 4")
        ok = t.back_in_field()
        t.record("B goes back with no search", ok and not t.search()["active"],
                 f"field {ok}, search {t.search()}")

        # A on Pidgey: a grass search for it
        t.open_screen("dexnav_screen_reopen.png")
        pidgey = [i for i, (sp, area) in enumerate(listed) if sp == 16][0]
        t.goto_cell(pidgey, 0)
        t.shot("dexnav_screen_pidgey.png")
        g.cmd("press A 4")
        ok = t.back_in_field()
        g.cmd("wait 60")
        g.wait_field(press="B", max_steps=40)
        g.cmd("wait 30")
        t.shot("dexnav_screen_grass_search.png")
        sr = t.search()
        t.record("the search bar shows while a search runs", t.hud_shown() == 1,
                 f"bar {t.hud_shown()}, roll pid {sr['pid']:#x} level {sr['level']}")
        behavior = at(sr["x"], sr["y"])[0]
        t.record("A searches the grass for the Pokemon picked", ok and sr["active"] == 1 and sr["species"] == 16
                 and sr["area"] == 0 and behavior == 0x02,
                 f"field {ok}, search {sr}, patch behavior {behavior:#x}")
        g.wait_field(press="B", max_steps=40)

        # A on Tentacool: a water search, then surf onto the patch
        t.set_first_move(0, MOVE_SURF, 15)
        t.open_screen("dexnav_screen_water.png")
        t.goto_cell(water[0], 1)
        t.shot("dexnav_screen_tentacool.png")
        g.cmd("press A 4")
        ok = t.back_in_field()
        g.cmd("wait 40")
        t.shot("dexnav_screen_water_search.png")
        sr = t.search()
        behavior, coll = at(sr["x"], sr["y"])
        t.record("A searches the water for a water Pokemon", ok and sr["active"] == 1 and sr["species"] == 72
                 and sr["area"] == 1 and behavior in WATER_BEHAVIORS and not coll,
                 f"field {ok}, search {sr}, patch behavior {behavior:#x}")
        g.wait_field(press="B", max_steps=40)

        # surf from the closest shore tile next to the water, then onto the patch
        px, py = t.pos()
        best = None
        for (dx, dy, d) in ((0, -1, "Up"), (0, 1, "Down"), (-1, 0, "Left"), (1, 0, "Right")):
            for sx in range(px - 6, px + 7):
                for sy in range(py - 5, py + 6):
                    b, c = at(sx, sy)
                    wb, wc = at(sx + dx, sy + dy)
                    if b == 0 and not c and wb in WATER_BEHAVIORS and not wc:
                        cost = abs(sx - px) + abs(sy - py)
                        if best is None or cost < best[0]:
                            best = (cost, sx, sy, d)
        battle = False
        if best:
            _, sx, sy, d = best
            t.walk_to(sx, sy)
            g.cmd(f"press {d} 2", "wait 20", "press A 4", "wait 90", "press A 4", "wait 60", "press A 4",
                  "wait 120")
            t.shot("dexnav_screen_surfing.png")
            sr = t.search()
            t.walk_to(sr["x"], sr["y"])
            g.cmd("wait 200")
            battle = t.in_battle()
        t.shot("dexnav_screen_water_battle.png")
        sr = t.search()
        t.record("surfing onto the patch starts the battle", battle,
                 f"shore {best}, battle {battle}, player {t.pos()}, search {sr}")
        enemy_pid = g.u32(g.a("gEnemyParty"))
        enemy_level = g.u8(g.a("gEnemyParty") + 0x54)
        t.record("the battle's Pokemon is the one the search bar showed",
                 battle and enemy_pid == sr["pid"] and enemy_level == sr["level"] and t.hud_shown() == 0,
                 f"bar pid {sr['pid']:#x} Lv{sr['level']}, battle pid {enemy_pid:#x} Lv{enemy_level}, "
                 f"bar shown {t.hud_shown()}")
    except RuntimeError as e:
        t.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in t.results if not r[1]]
    print(f"{len(t.results) - len(failed)}/{len(t.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(t.out, "dexnav_screen.txt"), "w") as f:
        for check, ok, detail in t.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
