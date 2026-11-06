"""DexNav Surf catches for PKHeX: py -3 emu/suite/legality_water.py <rom.gba> <rom.elf> <out dir> [count]

On Route 13, the DexNav's WATER tab searches for Tentacool; the player surfs onto the rippling patch and throws a
Master Ball. Half the searches run at search level 100 with a chain of 40 (21 rolls, the best kept). Each catch is
written as a .pk3 (and its 16-box round trip) like legality.py's, for the PKHeX check.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dexnav_screen import (FLAG_BADGE05_GET, FLAG_GUNK_ENDLESS_REPEL_ON, MAP_ROUTE13, MOVE_SURF, STAND,  # noqa: E402
                           TRAINER_FLAGS_START, WATER_BEHAVIORS, Screen, map_behaviors)
from features import FLAG_SYS_POKEDEX_GET, FLAG_SYS_POKEMON_GET, ITEM, SB1_FLAGS, SB1_REGISTERED_ITEM, SPECIES  # noqa: E402
from legality import ITEM_MASTER_BALL, Catcher  # noqa: E402

SPECIES_TENTACOOL = 72


class WaterCatcher(Catcher):
    set_first_move = Screen.set_first_move

    def start_route13(self):
        g = self.g
        self.new_game(mons=[(SPECIES["PIKACHU"], 100)], items=[(ITEM_MASTER_BALL, 99), (ITEM["DEXNAV"], 1)],
                      flags=[FLAG_SYS_POKEMON_GET, FLAG_SYS_POKEDEX_GET, FLAG_GUNK_ENDLESS_REPEL_ON, FLAG_BADGE05_GET],
                      name="legality_water")
        self.warp(*MAP_ROUTE13, *STAND, name="legality_water_route13")
        g.wait_field(press="B", max_steps=60)
        g.cmd(f"write16 {self.sb1() + SB1_REGISTERED_ITEM} {ITEM['DEXNAV']}")
        for byte in range(TRAINER_FLAGS_START // 8, (TRAINER_FLAGS_START + 768) // 8):
            g.cmd(f"write8 {self.sb1() + SB1_FLAGS + byte} 255")
        self.seen_all()
        self.set_first_move(0, MOVE_SURF, 15)

    def surf_out(self, at):
        """From the closest shore tile next to the water, Surf (A, then YES)."""
        g = self.g
        px, py = self.pos()
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
        if best is None:
            return False
        _, sx, sy, d = best
        self.walk_to(sx, sy)
        g.cmd(f"press {d} 2", "wait 20", "press A 4", "wait 90", "press A 4", "wait 60", "press A 4", "wait 120")
        return g.u8(g.a("gPlayerAvatar")) & 0x8 != 0  # PLAYER_AVATAR_FLAG_SURFING

    def surf_to(self, at, tx, ty):
        """Surf to (tx, ty) along the shortest path over open water (a breadth-first search on the map)."""
        from collections import deque
        g = self.g
        start = self.pos()
        prev = {start: None}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            if (x, y) == (tx, ty):
                break
            for nx, ny in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)):
                if (nx, ny) in prev or not (0 <= nx < 72 and 0 <= ny < 20):
                    continue
                b, c = at(nx, ny)
                if b in WATER_BEHAVIORS and not c:
                    prev[(nx, ny)] = (x, y)
                    queue.append((nx, ny))
        if (tx, ty) not in prev:
            return False
        path = []
        node = (tx, ty)
        while node != start:
            path.append(node)
            node = prev[node]
        for nx, ny in reversed(path):
            for _ in range(4):  # a tap in a new direction only turns the player first
                x, y = self.pos()
                if (x, y) == (nx, ny) or self.in_battle():
                    break
                d = "Up" if ny < y else "Down" if ny > y else "Left" if nx < x else "Right"
                g.cmd(f"press {d} 8", "wait 10")
            if self.in_battle():
                return True
        return True

    def water_search(self):
        """The DexNav screen, the WATER tab, A on its first Pokemon: (species, x, y, active)."""
        g = self.g
        g.cmd("press Select 4", "wait 90")
        if self.g.u8(self.g.u32(g.a("sDexNavScreen")) + 2) != 1:  # struct DexNavScreen.tab: the chain may open WATER
            g.cmd("press R 4", "wait 20")
        species, x, y, active, _ = self.start_search()
        g.wait_field(press="A", max_steps=40)  # through the "rippling" message
        return species, x, y, active


def main():
    rom, elf, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3])
    count = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    c = WaterCatcher(rom, elf, out)
    g = c.g
    at = map_behaviors()
    t0 = time.time()
    caught = failed = unreachable = 0
    import emu
    try:
        c.start_route13()
        i = -1
        while caught < count and i < 3 * count:
            i += 1
            if i % 2:
                c.set_search(SPECIES_TENTACOOL, 100, 40)
            species, x, y, active = c.water_search()
            if not active or species != SPECIES_TENTACOOL:
                print(f"search {i}: species {species} active {active}", flush=True)
                failed += 1
                continue
            surfing = g.u8(g.a("gPlayerAvatar")) & 0x8 != 0
            if not surfing and not c.surf_out(at):
                print(f"search {i}: couldn't surf", flush=True)
                failed += 1
                continue
            if not c.surf_to(at, x, y):
                # a patch on water the player can't reach without landing and surfing again: let it go
                print(f"search {i}: patch {(x, y)} not reachable over water from {c.pos()}", flush=True)
                unreachable += 1
                g.cmd("wait 660")
                g.wait_field(press="A", max_steps=40)  # "The hidden POKeMON got away..."
                continue
            g.cmd("wait 120")
            raw = c.catch() if c.in_battle() else None
            if raw is None:
                print(f"search {i}: no catch (battle {c.in_battle()}, at {c.pos()}, patch {(x, y)})", flush=True)
                failed += 1
                continue
            c.keep(raw, "water_chain" if i % 2 else "water")
            caught += 1
    except RuntimeError as e:
        print("stall:", e, flush=True)
        failed += 1
    finally:
        emu.stop()
    print(f"{caught}/{count} passed (water catches written), {failed} failed, {unreachable} patches out of reach, "
          f"box changed {c.box_changed}, "
          f"in {time.time() - t0:.0f}s")
    sys.exit(1 if failed or caught < count or c.box_changed else 0)


if __name__ == "__main__":
    main()
