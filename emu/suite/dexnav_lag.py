"""DexNav: how long the step onto the patch stalls the game: py -3 emu/suite/dexnav_lag.py <rom.gba> <rom.elf>

The rolls for a search (1 at search level 0, 21 at level 100 with a chain of 40) all run in the frame the player
steps onto the patch. The stall is measured as frames the game's main loop lost: emulator frames minus main-loop
iterations (the play-time counter, one tick per pass) from just before the step to 40 frames after. Each case runs several times; the
worst is reported. Results: emu/suite/out/<rom>/features/dexnav_lag.txt.
"""
import os
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
        for label, level, chain in (("1 roll", 0, 0), ("21 rolls", 100, 40)):
            worst = []
            for run in range(RUNS):
                g.cmd(f"load {c.path('lag_start.state')}", "wait 10")
                species, x, y, active = c.dexnav_patch(run % 3)
                if not active:
                    continue
                c.set_search(species, level, chain)
                px, py = c.pos()
                c.walk_to(x, y + 1 if py > y else y - 1 if py < y else y)
                if c.in_battle():
                    continue
                step = "Up" if c.pos()[1] > y else "Down" if c.pos()[1] < y else ("Left" if c.pos()[0] > x else "Right")
                lost, rolled = lost_frames(c, step)
                worst.append((lost, rolled and c.in_battle()))
            results[label] = worst
            print(label, worst, flush=True)
    finally:
        emu.stop()
    lines = [f"{label}: lost frames per run {[w for w, _ in runs]} (rolled and battle started {[b for _, b in runs]}), "
             f"worst {max([w for w, _ in runs], default=None)}" for label, runs in results.items()]
    lines.append(f"done in {time.time() - t0:.0f}s")
    print("\n".join(lines))
    out = os.path.join(c.out, "dexnav_lag.txt")
    open(out, "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
