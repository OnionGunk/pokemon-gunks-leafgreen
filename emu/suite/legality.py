"""Catch wild and DexNav Pokemon in the emulator and save them as .pk3 files for a PKHeX legality check.

Usage: py -3 emu/suite/legality.py <rom.gba> <rom.elf> <out_dir> [wild_count] [dexnav_count]

Every Pokemon is caught the way a player catches one: a battle, BAG, a Master Ball, no nickname. Each caught party
Pokemon (100 bytes, encrypted as in RAM) is written to <out_dir> as <n>_<kind>.pk3 and taken out of the party.
It is also put through the 16-box packing (boxes.py's packer, which matches the game's byte for byte on every slot of
emu/suite/boxes.py's test): box_<n>_<kind>.pk3 is the packed and unpacked copy, which must equal the original.

Kinds:
  wild       Route 1, Route 2 and Viridian Forest grass, random encounters
  dexnav     DexNav searches on the same maps, with search level 0 (1 roll)
  chain      DexNav with search level 100 and a chain of 40 for the species (21 rolls, best kept)
  shiny      a chain search whose RNG seed (gRngValue, written one step before the patch) makes one of its 21 rolls
             shiny: the seed is searched, the Pokemon is not edited
"""
import os
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import (FLAG_SYS_POKEMON_GET, ITEM, MAP_ROUTE1, MAP_ROUTE2, SB1_GUNK_DEXNAV, SPECIES,  # noqa: E402
                      Features)
from lib import NM, SUBSTRUCT_ORDERS  # noqa: E402
import boxes  # noqa: E402

ITEM_MASTER_BALL = 1
POCKET_BALLS = 2
SB1_REGISTERED_ITEM = 0x296  # SaveBlock1.registeredItem (as features.py's DexNav check)
MAP_VIRIDIAN_FOREST = (1, 0)
PLACES = [  # map, a tall-grass tile in a row of at least 5 (the walk goes Left/Right around it)
    (MAP_ROUTE1, (15, 6)),
    (MAP_ROUTE2, (5, 2)),
    (MAP_VIRIDIAN_FOREST, (13, 12)),
]


def is_shiny(raw):
    pid, otid = struct.unpack_from("<II", raw, 0)
    return ((otid & 0xFFFF) ^ (otid >> 16) ^ (pid & 0xFFFF) ^ (pid >> 16)) < 8


class Catcher(Features):
    def __init__(self, rom, elf, out_dir):
        super().__init__(rom, elf)
        self.dump_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.n = 0
        self.box_changed = []
        # HandleInputChooseAction is static in each battle controller (player, link, ...): any of them
        nm = subprocess.run([NM, elf], capture_output=True, text=True, check=True).stdout.splitlines()
        self.choose_action = {int(l.split()[0], 16) for l in nm if l.endswith(" HandleInputChooseAction")}

    def read(self, addr, n):
        return bytes.fromhex(self.g.cmd(f"read {addr} {n}")[0].replace(" ", ""))

    def party_count(self):
        return self.g.u8(self.g.a("gPlayerPartyCount"))

    def start(self, place):
        (grp, num), (x, y) = place
        self.new_game(mons=[(SPECIES["PIKACHU"], 50)],
                      items=[(ITEM_MASTER_BALL, 99), (ITEM["DEXNAV"], 1)],
                      flags=[FLAG_SYS_POKEMON_GET], name="legality")
        self.warp(grp, num, x, y, name=f"legality_{grp}_{num}")
        self.g.cmd(f"write16 {self.sb1() + SB1_REGISTERED_ITEM} {ITEM['DEXNAV']}")
        self.seen_all()

    def catch(self):
        """In a wild battle: BAG -> POKe BALLS -> Master Ball -> USE, then B through the dex entry and the
        nickname question. Returns the caught party Pokemon's 100 bytes, or None."""
        g = self.g
        count = self.party_count()
        for _ in range(60):  # the battle intro, up to the action menu
            g.cmd("press B 4", "wait 20")
            if g.u32(g.a("gBattlerControllerFuncs")) & ~1 in self.choose_action:
                break
        g.cmd("press Right 4", "wait 10", "press A 4", "wait 90")  # BAG
        for _ in range(4):
            if struct.unpack("<H", self.read(g.a("gBagMenuState") + 6, 2))[0] == POCKET_BALLS:
                break
            g.cmd("press Right 4", "wait 30")
        g.cmd("press A 4", "wait 30", "press A 4", "wait 60")  # Master Ball, USE
        for _ in range(120):
            if not self.in_battle() and g.field_ready():
                break
            g.cmd("press B 4", "wait 30")
        if self.party_count() != count + 1:
            g.cmd(f"shot {self.path(f'catch_failed_{self.n}.png')}")
            return None
        return self.read(g.a("gPlayerParty") + count * 100, 100)

    def keep(self, raw, kind):
        """Write the party Pokemon, then its round trip through a PC box, and take it out of the party."""
        g = self.g
        self.n += 1
        open(os.path.join(self.dump_dir, f"{self.n:03}_{kind}.pk3"), "wb").write(raw)
        # the 16-box packing (boxes.py's packer, which matches the game's byte for byte): pack and unpack the
        # Pokemon's 80 box bytes; they must come back unchanged, and the box copy is checked by PKHeX too
        box = boxes.unpack(boxes.pack(raw[:80]))
        open(os.path.join(self.dump_dir, f"box_{self.n:03}_{kind}.pk3"), "wb").write(box)
        if box != raw[:80]:
            self.box_changed.append(self.n)
        count = self.party_count()
        g.cmd(f"write8 {g.a('gPlayerPartyCount')} {count - 1}")
        empty = bytes(100)
        path = self.path("_empty.bin")
        open(path, "wb").write(empty)
        g.cmd(f"poke EWRAM {g.a('gPlayerParty') + (count - 1) * 100 - 0x02000000} {path}")
        print(f"{self.n:3} {kind:7} species {struct.unpack_from('<H', self.decrypted(raw), 0)[0]:3} "
              f"shiny {is_shiny(raw)}", flush=True)

    def decrypted(self, raw):
        pid, otid = struct.unpack_from("<II", raw, 0)
        dec = b"".join(struct.pack("<I", struct.unpack_from("<I", raw, 0x20 + i)[0] ^ pid ^ otid) for i in range(0, 48, 4))
        g = SUBSTRUCT_ORDERS[pid % 24].index("G")
        return dec[g * 12:g * 12 + 12]

    def wild(self, place):
        g = self.g
        self.walk_to(*place[1])
        for i in range(600):
            if i and i % 150 == 0:
                # no encounter yet: the spot is probably just off the grass; one tile down and on
                g.cmd("press Down 8", "wait 10")
            g.cmd("press Left 8" if (i // 2) % 2 == 0 else "press Right 8", "wait 6")
            if self.in_battle():
                return self.catch()
        g.cmd(f"shot {self.path(f'no_encounter_{self.n}.png')}")
        return None

    def set_search(self, species, level, chain):
        sb1 = self.sb1()
        dex = species_to_dex(species)
        g = self.g
        g.cmd(f"write8 {sb1 + SB1_GUNK_DEXNAV + dex - 1} {level}",
              f"write16 {sb1 + SB1_GUNK_DEXNAV + 386} {species}", f"write8 {sb1 + SB1_GUNK_DEXNAV + 388} {chain}")

    def open_dexnav_on(self, choice):
        """Open the DexNav screen (registered on SELECT) with the cursor on list entry <choice>."""
        g = self.g
        g.cmd("press Select 4", "wait 90")  # the DexNav screen, faded in
        for _ in range(16):  # to the first cell (the cursor starts on the chained species)
            g.cmd("press Left 4", "wait 6")
        for _ in range(choice):
            g.cmd("press Right 4", "wait 10")

    def start_search(self):
        """A on the DexNav screen: back to the field, the search starts (it chooses its Pokemon then)."""
        g = self.g
        g.cmd("press A 4", "wait 150")  # fade out, back to the field, fade in, the search starts
        raw = self.read(g.a("sSearch"), 32)
        species, sx, sy = struct.unpack_from("<Hhh", raw, 0)
        pid, = struct.unpack_from("<I", raw, 20)  # struct DexNavSearch.roll.personality
        return species, sx - 7, sy - 7, raw[11], pid  # struct DexNavSearch.active

    def dexnav_patch(self, choice):
        """Search for list entry <choice>: returns (species, x, y, active)."""
        self.open_dexnav_on(choice)
        species, x, y, active, _ = self.start_search()
        self.g.wait_field(press="A", max_steps=40)  # through the "rustling" message
        return species, x, y, active

    def trainer_id(self):
        return self.g.u32(self.sb2() + 0x0A)

    def dexnav(self, choice, level=0, chain=0, shiny=False):
        g = self.g
        if level or chain:
            # the search chooses its Pokemon as it starts: learn the species, then set its level and chain first
            g.cmd(f"save {self.path('predexnav.state')}")
            species, _, _, active = self.dexnav_patch(choice)
            g.cmd(f"load {self.path('predexnav.state')}", "wait 2")
            if not active:
                return None
            self.set_search(species, level, chain)
        self.open_dexnav_on(choice)
        if shiny:
            # a seed for which the search's chosen roll is shiny (the search keeps a shiny roll first)
            g.cmd(f"save {self.path('preshiny.state')}")
            otid = self.trainer_id()
            for seed in range(1, 2001):
                g.cmd(f"load {self.path('preshiny.state')}",
                      f"write32 {g.a('gRngValue')} {seed * 2654435761 & 0xFFFFFFFF}")
                species, x, y, active, pid = self.start_search()
                if active and ((otid & 0xFFFF) ^ (otid >> 16) ^ (pid & 0xFFFF) ^ (pid >> 16)) < 8:
                    print(f"shiny seed found after {seed} tries", flush=True)
                    break
            else:
                return None
        else:
            species, x, y, active, _ = self.start_search()
        g.wait_field(press="A", max_steps=40)  # through the "rustling" message
        if not active:
            return None
        # walk next to the patch, then step on
        px, py = self.pos()
        self.walk_to(x, y + 1 if py > y else y - 1 if py < y else y)
        if self.in_battle():
            return self.catch()
        step = "Up" if self.pos()[1] > y else "Down" if self.pos()[1] < y else ("Left" if self.pos()[0] > x else "Right")
        g.cmd(f"press {step} 8", "wait 40")
        if not self.in_battle():
            self.walk_to(x, y)
        return self.catch() if self.in_battle() else None


def species_to_dex(species):
    # Gen 3 internal species ids equal the National Dex number up to Celebi (251); the run only uses Kanto routes
    assert species <= 251, species
    return species


def main():
    rom, elf, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3])
    wild_n = int(sys.argv[4]) if len(sys.argv) > 4 else 12
    dex_n = int(sys.argv[5]) if len(sys.argv) > 5 else 12
    c = Catcher(rom, elf, out)
    t0 = time.time()
    import emu
    try:
        places = [int(i) for i in os.environ.get("LEGALITY_PLACES", "0,1,2").split(",") if i]
        for p, place in enumerate(PLACES):
            if p not in places:
                continue
            c.start(place)
            for i in range(wild_n // len(PLACES)):
                raw = c.wild(place)
                if raw:
                    c.keep(raw, "wild")
            for i in range(dex_n // len(PLACES)):
                raw = c.dexnav(i % 3)
                if raw:
                    c.keep(raw, "dexnav")
            for i in range(dex_n // len(PLACES)):
                raw = c.dexnav(i % 3, level=100, chain=40)
                if raw:
                    c.keep(raw, "chain")
        # last: a shiny from a chain search (a seed search; about 390 tries expected, capped)
        c.start(PLACES[0])
        raw = c.dexnav(0, level=100, chain=40, shiny=True)
        if raw:
            c.keep(raw, "shiny")
    finally:
        emu.stop()
    print(f"{c.n} Pokemon written to {out} in {time.time() - t0:.0f}s; box round trip changed {c.box_changed or 'none'}")


if __name__ == "__main__":
    main()
