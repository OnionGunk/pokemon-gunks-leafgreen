"""16 PC boxes: packed boxed-Pokemon storage tests.

Usage: py -3 emu/suite/boxes.py <gunk.gba> <gunk.elf> <vanilla.gba> <vanilla.elf>

1. Vanilla FireRed or LeafGreen: an intro to the bedroom, then 420 generated Pokemon (normal, eggs, Bad Eggs, empty slots and
   edge values) written into its 14 boxes, a renamed box and a changed wallpaper; saved with the player's
   continue warp set to a Pokemon Center PC.
2. Gunk's loads that save: the storage must be converted to the packed layout byte for byte as this file's own
   packer (an independent implementation of Gunk_PackBoxMon) does it, with box names, wallpapers and the current
   box kept and boxes 15-16 empty.
3. A Gunk's save and reload changes nothing.
4. The summary screen on boxes 1, 7 and 14 (the game unpacks the box for it): every unpacked Pokemon must be the
   original 80 bytes (Bad Eggs: the checksum must still fail); closing it writes the box back unchanged.
5. Boxes 15-16 filled with more generated Pokemon, saved and reloaded: all 16 boxes must survive, and the summary
   screen on box 16 must unpack them. The box list must wrap from box 1 to box 16.
Results: emu/suite/out/<gunk rom>/boxes/results.txt.
"""
import os
import random
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import FLAG_SYS_POKEMON_GET, SB1_FLAGS  # noqa: E402
from lib import FLASH_SIZE, SUBSTRUCT_ORDERS, Game  # noqa: E402

ERASED = b"\xff" * FLASH_SIZE
BOXES, VANILLA_BOXES, IN_BOX = 16, 14, 30
MON, PACKED = 80, 70
VANILLA_SIZE, GUNK_SIZE = 0x83D0, 0x83E8
NAMES_OFF, WALLS_OFF_VANILLA, WALLS_OFF, FORMAT_OFF = 0x8344, 0x83C2, 0x83D4, 0x83E4
GUNK_BOX_FORMAT = 0x31584247
PC_WARP = (5, 4, 11, 2)  # Viridian Pokemon Center 1F, below the PC (as in features.py)


# --- Gen 3 BoxPokemon, an independent reference ---
def checksum(subs):
    return sum(struct.unpack("<24H", b"".join(subs[c] for c in "GAEM"))) & 0xFFFF


def crypt(data48, key):
    return b"".join(struct.pack("<I", struct.unpack_from("<I", data48, i)[0] ^ key) for i in range(0, 48, 4))


def build(header28, subs, bad=False):
    """80 encrypted bytes from a 28-byte header and the four decrypted substructs (dict G/A/E/M)."""
    pid, otid = struct.unpack_from("<II", header28, 0)
    cs = checksum(subs)
    cs = (cs + 1) & 0xFFFF if bad else cs
    order = SUBSTRUCT_ORDERS[pid % 24]
    dec = b"".join(subs[c] for c in order)
    return header28 + struct.pack("<HH", cs, 0) + crypt(dec, pid ^ otid)


def split(raw):
    pid, otid = struct.unpack_from("<II", raw, 0)
    dec = crypt(raw[32:80], pid ^ otid)
    order = SUBSTRUCT_ORDERS[pid % 24]
    return {c: dec[i * 12:(i + 1) * 12] for i, c in enumerate(order)}


def text(rng, n):
    s = bytes(rng.randrange(0xA1, 0xEF) for _ in range(rng.randint(1, n)))
    return (s + b"\xff" * n)[:n]


def misc(rng, kind):
    """Substruct 3 with values the game can show: met data, ball, IVs, the egg bit to match, any ribbons."""
    edge = kind == "edge"
    met = (100 if edge else rng.randint(0, 100)) | (5 if edge else rng.randint(1, 5)) << 7         | (12 if edge else rng.randint(1, 12)) << 11 | rng.getrandbits(1) << 15
    ivs = 0x3FFFFFFF if edge else rng.getrandbits(30)
    ivs |= (kind == "egg") << 30 | rng.getrandbits(1) << 31
    ribbons = 0xFFFFFFFF if edge else rng.getrandbits(32)
    return struct.pack("<BBHII", rng.getrandbits(8), rng.randint(0x58, 0xC4), met, ivs, ribbons)


def make_mon(rng, kind):
    if kind == "empty":
        return bytes(MON)
    edge = kind == "edge"
    pid, otid = rng.getrandbits(32), rng.getrandbits(32)
    flags = 0b10 | (rng.getrandbits(1) << 3) | (rng.getrandbits(4) << 4)  # hasSpecies, blockBoxRS, unused bits
    if kind == "egg":
        flags |= 0b100
    if kind == "bad":
        flags |= 0b101
    header = struct.pack("<II", pid, otid) + text(rng, 10) + bytes([rng.randint(1, 7), flags]) + text(rng, 7) \
        + bytes([rng.getrandbits(4)])  # markings: 4 bits (the summary screen's marking sprite has 16 frames)
    species = 411 if edge else rng.randint(1, 411)
    item = 374 if edge else rng.choice([0, 0, rng.randint(1, 374)])
    exp = 1640000 if edge else rng.randint(0, 1640000)
    moves = [354, 1, 353, 0] if edge else [rng.randint(0, 354) for _ in range(4)]
    g = struct.pack("<HHIBBH", species, item, exp, rng.getrandbits(8), rng.getrandbits(8), 0)
    a = struct.pack("<4H4B", *moves, *[rng.randint(0, 64) for _ in range(4)])
    e = b"\xff" * 12 if edge else bytes(rng.getrandbits(8) for _ in range(12))
    m = misc(rng, kind)
    return build(header, {"G": g, "A": a, "E": e, "M": m}, bad=kind == "bad")


def pack(raw):
    subs = split(raw)
    species, item, exp, ppb, friend, _ = struct.unpack("<HHIBBH", subs["G"])
    moves = struct.unpack_from("<4H", subs["A"], 0)
    bits = species | item << 10
    for i, mv in enumerate(moves):
        bits |= mv << (20 + 10 * i)
    if checksum(subs) != struct.unpack_from("<H", raw, 28)[0]:
        bits |= 1 << 60
    return raw[:28] + struct.pack("<IBB", exp, ppb, friend) + subs["A"][8:12] + subs["E"] + subs["M"] \
        + struct.pack("<Q", bits)


def unpack(p):
    bits = struct.unpack_from("<Q", p, 62)[0]
    exp, ppb, friend = struct.unpack_from("<IBB", p, 28)
    moves = [(bits >> (20 + 10 * i)) & 0x3FF for i in range(4)]
    subs = {"G": struct.pack("<HHIBBH", bits & 0x3FF, (bits >> 10) & 0x3FF, exp, ppb, friend, 0),
            "A": struct.pack("<4H", *moves) + p[34:38], "E": p[38:50], "M": p[50:62]}
    raw = bytearray(build(p[:28], subs))
    if bits >> 60 & 1:
        struct.pack_into("<H", raw, 28, struct.unpack_from("<H", raw, 28)[0] ^ 0xFFFF)
    return bytes(raw)


def is_bad(raw):
    return checksum(split(raw)) != struct.unpack_from("<H", raw, 28)[0]


def make_box(rng, box):
    mons = []
    for pos in range(IN_BOX):
        if pos == 0:
            kind = "edge" if box % 5 == 0 else "normal"  # the summary screen opens on slot 1
        else:
            kind = rng.choices(["normal", "empty", "egg", "bad"], [70, 15, 10, 5])[0]
        mons.append(make_mon(rng, kind))
    return mons


class Boxes:
    def __init__(self, rom, elf, vrom, velf):
        self.rom, self.elf, self.vrom, self.velf = rom, elf, vrom, velf
        self.out = os.path.join(HERE, "out", os.path.splitext(os.path.basename(rom))[0], "boxes")
        os.makedirs(self.out, exist_ok=True)
        self.results = []
        self.rng = random.Random(16)

    def path(self, name):
        return os.path.join(self.out, name).replace("\\", "/")

    def record(self, check, ok, detail):
        self.results.append((check, ok, detail))
        print(("PASS " if ok else "FAIL ") + check + ": " + detail, flush=True)

    def storage_ptr(self, g):
        return g.u32(g.a("gPokemonStoragePtr"))

    def dump(self, g, size):
        addr = self.storage_ptr(g)
        path = os.path.join(self.out, "storage.bin")
        g.cmd(f"dump EWRAM {addr - 0x02000000} {size} {path.replace(chr(92), '/')}")
        return open(path, "rb").read()

    def poke(self, g, offset, data):
        path = os.path.join(self.out, "poke.bin")
        open(path, "wb").write(data)
        g.cmd(f"poke EWRAM {self.storage_ptr(g) + offset - 0x02000000} {path.replace(chr(92), '/')}")

    # --- 1. the vanilla save ---
    def vanilla_save(self):
        g = Game(self.vrom, self.velf)
        g.start()
        g.set_flash(ERASED)
        g.reboot()
        for _ in range(80):
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_MainMenu"):
                break
            g.cmd("press Start 4", "wait 30")
        if not g.wait_field(press="A", max_steps=1500, settle=5):
            raise RuntimeError("vanilla intro never reached the field")
        storage = bytearray(self.dump(g, VANILLA_SIZE))
        self.orig = [m for b in range(VANILLA_BOXES) for m in make_box(self.rng, b)]
        storage[0] = 3  # current box: BOX4
        storage[4:4 + len(self.orig) * MON] = b"".join(self.orig)
        storage[NAMES_OFF + 2 * 9:NAMES_OFF + 3 * 9] = bytes([0xC1, 0xCF, 0xC8, 0xC5, 0xFF, 0, 0, 0, 0])  # BOX3 "GUNK"
        storage[WALLS_OFF_VANILLA + 1] = 10
        self.vanilla_storage = bytes(storage)
        self.poke(g, 0, self.vanilla_storage)

        def edit():
            sb1, sb2 = g.u32(g.a("gSaveBlock1Ptr")), g.u32(g.a("gSaveBlock2Ptr"))
            grp, num, x, y = PC_WARP
            flag = sb1 + SB1_FLAGS + FLAG_SYS_POKEMON_GET // 8
            g.cmd(f"write8 {sb1 + 0xC} {grp}", f"write8 {sb1 + 0xD} {num}", f"write8 {sb1 + 0xE} 255",
                  f"write16 {sb1 + 0x10} {x}", f"write16 {sb1 + 0x12} {y}", f"write8 {sb2 + 9} {g.u8(sb2 + 9) | 1}",
                  f"write8 {flag} {g.u8(flag) | 1 << (FLAG_SYS_POKEMON_GET % 8)}")
        g.save(before_save=edit)
        flash = g.flash()
        import emu
        emu.stop()
        return flash

    # --- 2/3. the conversion ---
    def check_layout(self, data, mons, label):
        packed = [data[4 + i * PACKED:4 + (i + 1) * PACKED] for i in range(BOXES * IN_BOX)]
        want = [pack(m) for m in mons] + [bytes(PACKED)] * (BOXES * IN_BOX - len(mons))
        bad = [i for i in range(BOXES * IN_BOX) if packed[i] != want[i]]
        self.record(label, not bad, f"{BOXES * IN_BOX - len(bad)}/{BOXES * IN_BOX} packed slots as expected"
                    + (f", first wrong: box {bad[0] // 30 + 1} slot {bad[0] % 30 + 1}" if bad else ""))
        return packed

    def check_upgrade(self, data):
        self.check_layout(data, self.orig, "vanilla boxes converted")
        fmt = struct.unpack_from("<I", data, FORMAT_OFF)[0]
        names = [data[NAMES_OFF + i * 9:NAMES_OFF + (i + 1) * 9] for i in range(BOXES)]
        vnames = [self.vanilla_storage[NAMES_OFF + i * 9:NAMES_OFF + (i + 1) * 9] for i in range(VANILLA_BOXES)]
        box15 = bytes([0xBC, 0xC9, 0xD2, 0xA2, 0xA6, 0xFF])  # "BOX16"[:5] = B O X 1 5
        ok = fmt == GUNK_BOX_FORMAT and names[:14] == vnames and names[14].startswith(box15) \
            and names[15].startswith(bytes([0xBC, 0xC9, 0xD2, 0xA2, 0xA7, 0xFF])) \
            and data[WALLS_OFF:WALLS_OFF + 14] == self.vanilla_storage[WALLS_OFF_VANILLA:WALLS_OFF_VANILLA + 14] \
            and data[WALLS_OFF + 14:WALLS_OFF + 16] == bytes([2, 3]) and data[0] == 3
        self.record("box names, wallpapers, current box", ok,
                    f"format {fmt:#x}, current box {data[0] + 1}, BOX15/16 names {names[14][:6].hex()} "
                    f"{names[15][:6].hex()}, wallpapers {data[WALLS_OFF:WALLS_OFF + 16].hex()}")

    # --- 4. the summary screen ---
    def enter_storage(self, g):
        """Facing the PC: A through the boot message, SOMEONE'S PC (row 1), its messages and WITHDRAW (row 1)
        until the box screen is up."""
        g.cmd("press Up 2", "wait 20")
        for _ in range(40):
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_PokeStorage"):
                return True
            g.cmd("press A 4", "wait 40")
        raise RuntimeError("the box screen never opened")

    def open_summary(self, g, box):
        """From the PC savestate: Bill's PC -> WITHDRAW on box <box> -> slot 1 -> SUMMARY."""
        g.cmd(f"load {self.path('pc.state')}")
        g.cmd(f"write8 {self.storage_ptr(g)} {box}")
        self.enter_storage(g)
        storage_cb = g.a("CB2_PokeStorage")
        g.cmd("wait 90", f"shot {self.path(f'box{box + 1}.png')}", "press A 4", "wait 30", "press Down 4", "wait 10",
              "press A 4")
        for _ in range(40):
            ptr = g.u32(g.a("sGunkSummaryBox"))
            if ptr and (g.u32(g.a("gMain") + 4) & ~1) != storage_cb:
                break
            g.cmd("wait 15")
        g.cmd("wait 90", f"shot {self.path(f'summary_box{box + 1}.png')}")
        return ptr

    def check_summary(self, g, box, mons):
        g.cmd(f"load {self.path('pc.state')}")
        packed_before = self.dump(g, GUNK_SIZE)[4 + box * IN_BOX * PACKED:4 + (box + 1) * IN_BOX * PACKED]
        ptr = self.open_summary(g, box)
        if not ptr:
            self.record(f"summary box {box + 1}", False, "the summary screen never opened")
            return
        path = os.path.join(self.out, "summary.bin")
        g.cmd(f"dump EWRAM {ptr - 0x02000000} {IN_BOX * MON} {path.replace(chr(92), '/')}")
        got = open(path, "rb").read()
        wrong = []
        for pos in range(IN_BOX):
            raw, want = got[pos * MON:(pos + 1) * MON], mons[pos]
            if is_bad(want):
                # GetBoxMonData marks a failing Pokemon as a Bad Egg in place (as vanilla does): compare the
                # header but the flags byte, and the checksum must still fail
                ok = raw[:19] == want[:19] and raw[20:28] == want[20:28] and is_bad(raw)
            else:
                ok = raw == want
            if not ok:
                wrong.append(pos + 1)
        self.record(f"summary box {box + 1}", not wrong, f"{IN_BOX - len(wrong)}/{IN_BOX} unpacked Pokemon match"
                    + (f", wrong slots {wrong}" if wrong else ""))
        for _ in range(30):
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_PokeStorage") and not g.u32(g.a("sGunkSummaryBox")):
                break
            g.cmd("press B 4", "wait 30")
        g.cmd("wait 60", f"shot {self.path(f'after_summary_box{box + 1}.png')}")
        after = self.dump(g, GUNK_SIZE)[4 + box * IN_BOX * PACKED:4 + (box + 1) * IN_BOX * PACKED]
        changed = [pos + 1 for pos in range(IN_BOX)
                   if after[pos * PACKED:(pos + 1) * PACKED] != packed_before[pos * PACKED:(pos + 1) * PACKED]
                   and not is_bad(mons[pos])]
        self.record(f"summary box {box + 1} written back", not changed and not g.u32(g.a("sGunkSummaryBox")),
                    f"changed slots {changed}" if changed else "box unchanged after the summary screen")

    def check_wrap(self, g):
        """In the box screen, Left on the box title from box 1 must go to box 16."""
        g.cmd(f"load {self.path('pc.state')}")
        g.cmd(f"write8 {self.storage_ptr(g)} 0")
        self.enter_storage(g)
        g.cmd("wait 90", "press Up 4", "wait 30", "press Left 4", "wait 120", f"shot {self.path('wrap.png')}")
        box = g.u8(self.storage_ptr(g))
        self.record("box list wraps to box 16", box == 15, f"current box after Left from box 1: {box + 1}")

    def run(self):
        flash = self.vanilla_save()
        g = Game(self.rom, self.elf)
        g.start()
        g.set_flash(flash)
        g.reboot()
        status = g.boot_continue()
        g.cmd("wait 30", f"save {self.path('pc.state')}", f"shot {self.path('pc.png')}")
        data = self.dump(g, GUNK_SIZE)
        self.record("vanilla save loads", status == 1, f"save status {status}")
        self.check_upgrade(data)
        # Python reference round trip (no game involved)
        rt = [i for i, m in enumerate(self.orig) if not is_bad(m) and unpack(pack(m)) != m]
        self.record("reference pack/unpack round trip", not rt, f"{len(self.orig) - len(rt)}/{len(self.orig)}")

        # 3. save and reload in Gunk's
        g.save()
        g.reboot()
        status = g.boot_continue()
        again = self.dump(g, GUNK_SIZE)
        self.record("Gunk's save and reload", status == 1 and again[4:FORMAT_OFF + 4] == data[4:FORMAT_OFF + 4],
                    f"status {status}, storage {'identical' if again[4:] == data[4:] else 'CHANGED'}")
        g.cmd(f"save {self.path('pc.state')}")

        # 4. the summary screen unpacks
        for box in (0, 6, 13):
            self.check_summary(g, box, self.orig[box * IN_BOX:(box + 1) * IN_BOX])

        # 5. boxes 15-16
        g.cmd(f"load {self.path('pc.state')}")
        extra = [m for b in range(VANILLA_BOXES, BOXES) for m in make_box(self.rng, b)]
        self.poke(g, 4 + VANILLA_BOXES * IN_BOX * PACKED, b"".join(pack(m) for m in extra))
        g.save()
        g.reboot()
        status = g.boot_continue()
        full = self.dump(g, GUNK_SIZE)
        self.record("16 boxes saved and reloaded", status == 1, f"save status {status}")
        self.check_layout(full, self.orig + extra, "all 16 boxes after a save")
        g.cmd("wait 30", f"save {self.path('pc.state')}")
        self.check_summary(g, 15, extra[IN_BOX:])
        self.check_wrap(g)
        import emu
        emu.stop()


def main():
    rom, elf, vrom, velf = (os.path.abspath(a) for a in sys.argv[1:5])
    t0 = time.time()
    b = Boxes(rom, elf, vrom, velf)
    try:
        b.run()
    finally:
        import emu
        emu.stop()
    failed = [r for r in b.results if not r[1]]
    print(f"{len(b.results) - len(failed)}/{len(b.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(b.out, "results.txt"), "w") as f:
        for check, ok, detail in b.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
