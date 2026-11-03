"""Egg hatching: how many steps an egg takes, and that the hatched Pokemon is whole.

Usage: py -3 emu/suite/eggs.py <rom.gba> <rom.elf> [<vanilla.gba> <vanilla.elf>]

Each ROM: a new game to the bedroom, then a party of a Bulbasaur and a Pidgey egg with 1 egg cycle left is written
into RAM, the day-care step counter is set to 0, and the player paces the bedroom until the hatch scene starts.
The game's day care (src/daycare.c) takes an egg cycle off every 256 steps in vanilla and every 128 in Gunk's, and
an egg hatches on the cycle after it reaches 0: vanilla hatches on step 511, Gunk's on step 255. After the scene
(no nickname) the Pokemon must be a Pidgey that is no longer an egg, with its IVs, moves and personality kept and a
valid checksum, back in the field. Works on FireRed and LeafGreen.
Results: emu/suite/out/<rom name>/eggs/.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from boxes import build, checksum, split  # noqa: E402
from features import ERASED, FLAG_SYS_POKEMON_GET, SB1_FLAGS  # noqa: E402
from lib import Game  # noqa: E402

SB1_DAYCARE_STEP_COUNTER = 0x309A  # offsetof(struct SaveBlock1, daycare) 0x2F80 + 2 * sizeof(DaycareMon) + 2
PARTY_MON = 100
SPECIES_BULBASAUR, SPECIES_PIDGEY = 1, 16
MOVE_TACKLE, MOVE_GROWL, MOVE_SAND_ATTACK = 33, 45, 28
EGG_PID, EGG_OTID, EGG_IVS = 0x1234ABCD, 0x00C0FFEE, 0x2B5A3D1F  # IVs: 30 bits, any values


def party_mon(species, level, moves, egg=False, cycles=0, exp=135, otid=EGG_OTID, ot=None, stats=None):
    """100 bytes of struct Pokemon: the BoxPokemon plus level and stats (the game recalculates them on hatching).
    otid/ot (7 bytes): the player's, for a Pokemon that must obey; stats: (hp, atk, def, spe, spa, spd)."""
    pid = EGG_PID if egg else 0x00000101
    name = bytes([0xBF, 0xC1, 0xC1, 0xFF]) if egg else bytes([0xBC, 0xCF, 0xC6, 0xBC, 0xBB, 0xCD, 0xBB, 0xCF, 0xCC, 0xFF])
    flags = 0b10 | (0b100 if egg else 0)  # hasSpecies, isEgg
    ot = ot or bytes([0xBB, 0xC9, 0xC8, 0xD3, 0xFF, 0xFF, 0xFF])
    header = struct.pack("<II", pid, otid) + (name + b"\xff" * 10)[:10] + bytes([1 if egg else 2, flags]) + ot + b"\0"
    g = struct.pack("<HHIBBH", species, 0, 0 if egg else exp, 0, cycles if egg else 70, 0)
    a = struct.pack("<4H4B", *moves, *[35 if m else 0 for m in moves])
    e = bytes(12)
    met = (0 if egg else level) | 1 << 7 | 4 << 11  # met level, game LeafGreen/FireRed-ish, Poke Ball
    m = struct.pack("<BBHII", 0, 0 if egg else 88, met, EGG_IVS | (egg << 30), 0)
    box = build(header, {"G": g, "A": a, "E": e, "M": m})
    hp, atk, df, spe, spa, spd = stats or (20, 10, 10, 10, 10, 10)
    return box + struct.pack("<IBBHHHHHHH", 0, level, 0xFF, hp, hp, atk, df, spe, spa, spd)


class Eggs:
    def __init__(self, rom, elf):
        self.g = Game(rom, elf)
        self.name = os.path.splitext(os.path.basename(rom))[0]
        self.out = os.path.join(HERE, "out", self.name, "eggs")
        os.makedirs(self.out, exist_ok=True)

    def shot(self, name):
        self.g.cmd(f"shot {os.path.join(self.out, name).replace(chr(92), '/')}")

    def sb1(self):
        return self.g.u32(self.g.a("gSaveBlock1Ptr"))

    def read(self, addr, n):
        return bytes.fromhex(self.g.cmd(f"read {addr} {n}")[0].replace(" ", ""))

    def poke_ram(self, addr, data):
        path = os.path.join(self.out, "poke.bin")
        open(path, "wb").write(data)
        self.g.cmd(f"poke EWRAM {addr - 0x02000000} {path.replace(chr(92), '/')}")

    def run(self):
        g = self.g
        g.start()
        g.set_flash(ERASED)
        g.reboot()
        for _ in range(80):
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_MainMenu"):
                break
            g.cmd("press Start 4", "wait 30")
        if not g.wait_field(press="A", max_steps=1500, settle=5):
            raise RuntimeError("intro never reached the field")
        party = party_mon(SPECIES_BULBASAUR, 5, [MOVE_TACKLE, MOVE_GROWL, 0, 0]) \
            + party_mon(SPECIES_PIDGEY, 5, [MOVE_TACKLE, MOVE_SAND_ATTACK, 0, 0], egg=True, cycles=1)
        self.poke_ram(g.a("gPlayerParty"), party)
        sb1 = self.sb1()
        flag = sb1 + SB1_FLAGS + FLAG_SYS_POKEMON_GET // 8
        g.cmd(f"write8 {g.a('gPlayerPartyCount')} 2", f"write8 {sb1 + SB1_DAYCARE_STEP_COUNTER} 0",
              f"write8 {flag} {g.u8(flag) | 1 << (FLAG_SYS_POKEMON_GET % 8)}")
        egg_before = self.read(g.a("gPlayerParty") + PARTY_MON, PARTY_MON)

        steps, last, hatch_step = 0, 0, None
        for _ in range(400):
            g.cmd("press Left 18", "wait 2", "press Right 18", "wait 2")
            counter = g.u8(self.sb1() + SB1_DAYCARE_STEP_COUNTER)
            steps += (counter - last) & 0xFF
            last = counter
            if not g.field_ready():
                hatch_step = steps
                break
            if steps > 700:
                break
        self.shot("hatch_scene.png")
        print(f"{self.name}: hatch scene started after {hatch_step} steps", flush=True)
        if hatch_step is None:
            return hatch_step, False, "no hatch scene within 700 steps"
        back = g.wait_field(press="B", max_steps=600)
        self.shot("after_hatch.png")
        raw = self.read(g.a("gPlayerParty") + PARTY_MON, PARTY_MON)
        subs = split(raw)
        species = struct.unpack_from("<H", subs["G"], 0)[0]
        ivword = struct.unpack_from("<I", subs["M"], 4)[0]
        moves = list(struct.unpack_from("<4H", subs["A"], 0))
        good_sum = checksum(subs) == struct.unpack_from("<H", raw, 28)[0]
        level = raw[84]
        ok = back and species == SPECIES_PIDGEY and not (ivword >> 30 & 1) and not (raw[0x13] & 0b101) \
            and (ivword & 0x3FFFFFFF) == EGG_IVS and moves[:2] == [MOVE_TACKLE, MOVE_SAND_ATTACK] \
            and raw[:4] == egg_before[:4] and good_sum and level == 5  # hatching sets the player as OT
        detail = (f"back in the field {back}, species {species}, egg bit {ivword >> 30 & 1}, flags {raw[0x13]:#x}, "
                  f"IVs kept {(ivword & 0x3FFFFFFF) == EGG_IVS}, moves {moves}, level {level}, checksum ok {good_sum}")
        return hatch_step, ok, detail


def main():
    import emu
    args = sys.argv[1:]
    roms = [(args[0], args[1], 255)] + ([(args[2], args[3], 511)] if len(args) >= 4 else [])
    lines, ok_all = [], True
    for rom, elf, want in roms:
        e = Eggs(rom, elf)
        try:
            step, ok, detail = e.run()
        finally:
            emu.stop()
        ok = ok and step == want
        ok_all &= ok
        line = f"{'PASS' if ok else 'FAIL'} {e.name}: hatched on step {step} (expected {want}); {detail}"
        print(line, flush=True)
        lines.append(line)
        open(os.path.join(e.out, "results.txt"), "w").write(line + "\n")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
