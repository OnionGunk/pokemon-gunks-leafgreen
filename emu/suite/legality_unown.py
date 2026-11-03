"""Tanoby chambers: catch wild and DexNav Unown in each of the 7 chambers for a PKHeX check.

Usage: py -3 emu/suite/legality_unown.py <rom.gba> <rom.elf> <out_dir> [per_chamber]

Uses legality.py's Catcher. In each chamber (Seven Island, map group 2, maps 27-33; the player starts two tiles
above the entrance), <per_chamber> random encounters, then as many plain DexNav searches and as many chain searches
(search level 100, chain 40: 21 rolls), with the
chambers unlocked (FLAG_SYS_UNLOCKED_TANOBY_RUINS). An Unown's letter comes from its PID, and each chamber allows only its own
letters (sUnownLetterSlots in src/wild_encounter.c): PKHeX checks the letter against the chamber, so a reroll that
made another chamber's letter would show as illegal. The letter of each catch is printed.
"""
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from legality import Catcher  # noqa: E402

CHAMBERS = [(27, "Monean"), (28, "Liptoo"), (29, "Weepth"), (30, "Dilford"), (31, "Scufib"), (32, "Rixy"),
            (33, "Viapois")]
START = (11, 13)
FLAG_SYS_UNLOCKED_TANOBY_RUINS = 0x849  # set by the Tanoby Key puzzle; without it the chambers have no encounters


def letter(raw):
    pid = struct.unpack_from("<I", raw, 0)[0]
    n = (((pid >> 24) & 3) << 6 | ((pid >> 16) & 3) << 4 | ((pid >> 8) & 3) << 2 | (pid & 3)) % 28
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ!?"[n]


def main():
    rom, elf, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3])
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    c = Catcher(rom, elf, out)
    t0 = time.time()
    letters = {}
    import emu
    try:
        for num, name in CHAMBERS:
            place = ((2, num), START)
            c.start(place)
            flag = c.sb1() + 0x0EE0 + FLAG_SYS_UNLOCKED_TANOBY_RUINS // 8  # SaveBlock1 flags
            c.g.cmd(f"write8 {flag} {c.g.u8(flag) | 1 << FLAG_SYS_UNLOCKED_TANOBY_RUINS % 8}")
            c.shot(f"unown_{name}.png")
            got = letters.setdefault(name, [])
            for kind, fn in [("wild", lambda: c.wild(place)), ("dexnav", lambda: c.dexnav(0)),
                             ("chain", lambda: c.dexnav(0, level=100, chain=40))]:
                for _ in range(n):
                    raw = fn()
                    if raw:
                        c.keep(raw, f"{name}_{kind}")
                        got.append(f"{kind}:{letter(raw)}")
                    else:
                        got.append(f"{kind}:none")
            print(f"{name}: {' '.join(got)}", flush=True)
    finally:
        emu.stop()
    print(f"{c.n} Unown written to {out} in {time.time() - t0:.0f}s; box round trip changed {c.box_changed or 'none'}")


if __name__ == "__main__":
    main()
