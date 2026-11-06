"""DexNav: the Pokemon a search makes is the best roll it peeked at.

Usage: py -3 emu/suite/dexnav_peek.py <rom.gba> <rom.elf> <out_dir> [searches]

Gunk_DexNavTryStartBattle peeks at each roll (Gunk_PeekWildMonOfSpecies: the PID and IV total, without making the
Pokemon), then puts the RNG back where the best one started and makes that one (Gunk_GenerateWildMonOfSpecies).
Exec hooks record each peek's starting RNG value and what it wrote to the caller's roll->personality /
roll->ivTotal (read as the peek returns, a peek that found no slot dropped: the roll is on the caller's stack, reused
soon after), and the RNG value the real roll starts from. For each
search: the real roll must start at the best peek's seed (most IVs, a shiny first, the first of equals), and the
caught Pokemon must have that peek's PID and IV total. <searches> plain searches (search level 0) and as many chain
searches (level 100, chain 40: 21 rolls, which run over several frames) on each of legality.py's places. The catches
are written to <out_dir> for PKHeX too.
"""
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from legality import PLACES, Catcher, is_shiny  # noqa: E402
from lib import SUBSTRUCT_ORDERS  # noqa: E402

HOOKS = (
    "PK = {} local reg = event.on_bus_exec or event.onmemoryexecute "
    "local function rd(a) return memory.read_u32_le(a, 'System Bus') end "
    "reg(function() PK[#PK + 1] = {seed = rd(RNG), pa = emu.getregister('R2')} end, PEEK, 'gunk_peek') "
    "reg(function() local p = PK[#PK] if p and p.pa and not p.pid then "
    "if emu.getregister('R0') % 256 == 0 then PK[#PK] = nil "
    "else p.pid = rd(p.pa) p.iv = memory.read_u8(p.pa + 9, 'System Bus') end end end, AFTER, 'gunk_peek_ret') "
    "reg(function() PK[#PK + 1] = {gen = true, seed = rd(RNG)} end, GEN, 'gunk_gen') "
    "reg(function() PK[#PK + 1] = {start = true} end, CHOOSE, 'gunk_choose') return 'ok'"
)
def peek_return(rom, sym):
    """The address of the peek's return (its one BX, after the roll is written), from the ROM's code: the function
    runs to the next symbol."""
    data = open(rom, "rb").read()
    start = sym["Gunk_PeekWildMonOfSpecies"] & ~1
    end = min(v & ~1 for v in sym.values() if start < v & ~1 < 0x09000000)
    bx = [a for a in range(start, end, 2) if struct.unpack_from("<H", data, a - 0x08000000)[0] & 0xFF80 == 0x4700]
    if len(bx) != 1:
        raise RuntimeError(f"expected one BX in the peek, found {len(bx)}")
    return bx[0]
DUMP = ("local s = {} for _, p in ipairs(PK) do s[#s + 1] = p.start and 'S' or p.gen and string.format('G%08X', p.seed) or "
        "string.format('P%08X,%08X,%d', p.seed, p.pid or 0, p.iv or 0) end PK = {} return table.concat(s, ' ')")


def iv_total(raw):
    pid, otid = struct.unpack_from("<II", raw, 0)
    dec = b"".join(struct.pack("<I", struct.unpack_from("<I", raw, 0x20 + i)[0] ^ pid ^ otid) for i in range(0, 48, 4))
    m = SUBSTRUCT_ORDERS[pid % 24].index("M")
    ivs = struct.unpack_from("<I", dec, m * 12 + 4)[0]
    return sum(ivs >> (5 * i) & 31 for i in range(6))


def check(c, log, raw):
    """(ok, text) for one search from the hook log and the caught Pokemon."""
    peeks, gens = [], []
    for e in log.split():
        if e == "S":  # a search started (ChooseSearchRoll): only the last search's peeks made the Pokemon
            peeks = []
        elif e[0] == "P":
            seed, pid, iv = e[1:].split(",")
            peeks.append((int(seed, 16), int(pid, 16), int(iv)))
        else:
            gens.append(int(e[1:], 16))
    if len(gens) != 1 or not peeks:
        return False, f"{len(peeks)} peeks, {len(gens)} real rolls"
    otid = struct.unpack_from("<I", raw, 4)[0]
    best = None
    for seed, pid, iv in peeks:
        score = iv + (0x1000 if is_shiny(struct.pack("<II", pid, otid)) else 0)
        if best is None or score > best[0]:
            best = (score, seed, pid, iv)
    _, seed, pid, iv = best
    got_pid, got_iv = struct.unpack_from("<I", raw, 0)[0], iv_total(raw)
    ok = gens[0] == seed and got_pid == pid and got_iv == iv
    return ok, (f"{len(peeks)} peeks, best {pid:08X} IVs {iv}; made from seed "
                f"{'the best' if gens[0] == seed else f'{gens[0]:08X} (best {seed:08X})'}: {got_pid:08X} IVs {got_iv}")


def main():
    rom, elf, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3])
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    c = Catcher(rom, elf, out)
    t0 = time.time()
    results = []
    import emu
    try:
        for place in PLACES:
            c.start(place)
            g = c.g
            peek = g.a("Gunk_PeekWildMonOfSpecies")
            hooks = HOOKS.replace("RNG", str(g.a("gRngValue"))).replace("PEEK", str(peek & ~1)).replace(
                "AFTER", str(peek_return(rom, g.sym))).replace("CHOOSE", str(g.a("ChooseSearchRoll") & ~1))
            assert g.cmd("lua " + hooks.replace("GEN", str(g.a("Gunk_GenerateWildMonOfSpecies") & ~1)))[0] == "lua ok"
            for kind, kw in [("plain", {}), ("chain", {"level": 100, "chain": 40})]:
                for _ in range(n):
                    for _ in range(3):
                        g.cmd("lua PK = {} return 1")
                        raw = c.dexnav(0, **kw)
                        for _ in range(10):  # the battle can start after dexnav() stops looking: catch it here
                            if raw or c.in_battle():
                                break
                            g.cmd("wait 30")
                        raw = raw or (c.catch() if c.in_battle() else None)
                        log = g.cmd("lua " + DUMP)[0][4:]
                        if "G" in log:
                            break
                        if raw:
                            # a random encounter on the walk to the patch, before any DexNav roll: search again
                            print(f"{place[0]} {kind}: a wild battle on the way, searching again", flush=True)
                            c.keep(raw, "peek_wild")
                        elif "P" in log:
                            # the search started, but its patch is out of the walk's reach (Catcher.dexnav walks in
                            # straight lines, and trees can stand between): search again
                            print(f"{place[0]} {kind}: the patch is out of reach, searching again", flush=True)
                        else:
                            break
                    if not raw:
                        results.append(False)
                        print(f"{place[0]} {kind}: no catch ({log})", flush=True)
                        continue
                    ok, text = check(c, log, raw)
                    results.append(ok)
                    c.keep(raw, f"peek_{kind}")
                    print(f"{'PASS' if ok else 'FAIL'} {place[0]} {kind}: {text}", flush=True)
    finally:
        emu.stop()
    print(f"{sum(results)}/{len(results)} searches made the peeked Pokemon in {time.time() - t0:.0f}s; "
          f"box round trip changed {c.box_changed or 'none'}")


if __name__ == "__main__":
    main()
