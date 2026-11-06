"""DexNav: how long a search stalls the game: py -3 emu/suite/dexnav_lag.py <rom.gba> <rom.elf>

The rolls for a search (1 at search level 0, 21 at level 100 with a chain of 40) are peeked at as the search starts,
and the chosen one is made as the player steps onto the patch. Both moments are timed, as frames the game's main
loop lost: emulator frames minus main-loop iterations (the play-time counter, one tick per overworld pass), from the
field being back after the DexNav screen to 80 frames later, and from just before the step to 40 frames after.
Each case runs several times; the worst is reported. Results: emu/suite/out/<rom>/features/dexnav_lag.txt.
"""
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from legality import PLACES, Catcher  # noqa: E402

RUNS = 4


def play_ticks(c):
    """The play-time counter in 1/60 s ticks. PlayTimeCounter_Update adds one per main-loop pass (from the
    overworld's callback, not an interrupt), so a pass that overruns its frame shows as a tick missing."""
    raw = c.read(c.sb2() + 0x0E, 5)
    hours = raw[0] | raw[1] << 8
    return ((hours * 60 + raw[2]) * 60 + raw[3]) * 60 + raw[4]


def lost_frames(c, step):
    """(lost frames, rolled): rolled is whether the DexNav filled gEnemyParty[0] (zeroed first) on the step."""
    g = c.g
    enemy = g.a("gEnemyParty")
    g.cmd(f"write32 {enemy} 0")
    f0, m0 = g.frame(), play_ticks(c)
    g.cmd(f"press {step} 8", "wait 40")
    f1, m1 = g.frame(), play_ticks(c)
    rolled = g.u32(enemy) != 0
    g.cmd("wait 120")
    return (f1 - f0) - (m1 - m0), rolled


def search_start_lost(c, choice):
    """(lost frames, active, x, y) from the field being back after the DexNav screen to 80 frames later."""
    g = c.g
    c.open_dexnav_on(choice)
    g.cmd("press A 4")
    for _ in range(60):
        g.cmd("wait 2")
        if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_Overworld"):
            break
    f0, m0 = g.frame(), play_ticks(c)
    g.cmd("wait 80")
    f1, m1 = g.frame(), play_ticks(c)
    raw = c.read(g.a("sSearch"), 12)
    species, sx, sy = struct.unpack_from("<Hhh", raw, 0)
    g.wait_field(press="A", max_steps=40)  # through the "rustling" message
    return (f1 - f0) - (m1 - m0), raw[11], sx - 7, sy - 7


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    c = Catcher(rom, elf, os.path.join(HERE, "out", "dexnav_lag_pk3"))
    g = c.g
    import emu
    results = {}
    t0 = time.time()
    try:
        c.start(PLACES[0])
        g.cmd(f"save {c.path('lag_start.state')}")
        species_of = {}
        for choice in range(3):
            g.cmd(f"load {c.path('lag_start.state')}", "wait 10")
            species_of[choice] = c.dexnav_patch(choice)[0]
        for label, level, chain in (("1 roll", 0, 0), ("21 rolls", 100, 40)):
            worst = []
            for run in range(RUNS):
                g.cmd(f"load {c.path('lag_start.state')}", "wait 10")
                c.set_search(species_of[run % 3], level, chain)
                start_lost, active, x, y = search_start_lost(c, run % 3)
                worst.append((start_lost, "search start"))
                if not active:
                    continue
                px, py = c.pos()
                c.walk_to(x, y + 1 if py > y else y - 1 if py < y else y)
                if c.in_battle():
                    continue
                step = "Up" if c.pos()[1] > y else "Down" if c.pos()[1] < y else ("Left" if c.pos()[0] > x else "Right")
                lost, rolled = lost_frames(c, step)
                worst.append((lost, "step, battle" if rolled and c.in_battle() else "step, NO BATTLE"))
            results[label] = worst
            print(label, worst, flush=True)
    finally:
        emu.stop()
    lines = [f"{label}: lost frames per moment {[w for w, _ in runs]} ({[b for _, b in runs]}), "
             f"worst {max([w for w, _ in runs], default=None)}" for label, runs in results.items()]
    lines.append(f"done in {time.time() - t0:.0f}s")
    print("\n".join(lines))
    out = os.path.join(c.out, "dexnav_lag.txt")
    open(out, "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
