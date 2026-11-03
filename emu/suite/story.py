"""Story-trigger sweep: arriving in each map must set the same story flags and vars in Gunk's as in vanilla.

Usage:
  py -3 emu/suite/story.py run <rom.gba> <rom.elf> [first_map_index] [count]   one ROM, writes story_<first>.json
  py -3 emu/suite/story.py rerun <rom.gba> <rom.elf> <steps> <map,map,...>      those maps with up to <steps> A
      presses, for scenes longer than 60 (Gunk's faster text finishes some that vanilla doesn't); story_rerun.json
  py -3 emu/suite/story.py compare <gunk.json> <vanilla.json>                   the verdict

Each ROM gets the same start without its test hook (vanilla has none): the intro to the bedroom, a level 100
Bulbasaur written into the party, FLAG_SYS_POKEMON_GET and a long Repel, saved, and a savestate on the main menu.
For each map of sweep.py's list the state is loaded, the continue-game warp pointed at the map and CONTINUE chosen;
A is pressed until the field is ready (or 60 tries), as a player would through an arrival scene. Then the map, the
player's position and every flag and var in the save block are recorded. A map passes when Gunk's matches vanilla
outside Gunk's own flags and vars, and the follower's (which vanilla doesn't have). The map sweep covers whether
the game keeps running; this covers whether the story does the same thing.
Results: emu/suite/out/<gunk rom>/story.txt.
"""
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from eggs import SPECIES_BULBASAUR, party_mon  # noqa: E402
from features import (ERASED, FLAG_SYS_POKEMON_GET, SB1_FLAGS, SB1_VARS, VAR_REPEL_STEP_COUNT,  # noqa: E402
                      VAR_GUNK_LAST_REPEL)
from lib import Game  # noqa: E402
from sweep import maps  # noqa: E402

FLAGS_BYTES, VARS_COUNT = 0x120, 0x100
GUNK_FLAGS = set(range(0x4A7, 0x4AB))  # Endless Repel on, Exp. All on, Pewter gifts given, follower off
GUNK_VARS = {VAR_GUNK_LAST_REPEL, 0x402A}  # last Repel, second registered item
# Not story state, so not compared: the temp flags (FLAG_TEMP_*, 0x00-0x1F) and temp vars (VAR_TEMP_*, 0x4000-0x400F)
# are scratch that the game clears on every map load, and scripts fill some from the RNG (Vermilion Gym's trash-can
# switches), which runs differently in two ROMs.
IGNORED_FLAGS = set(range(0x00, 0x20))
IGNORED_VARS = set(range(0x4000, 0x4010))


def run(rom, elf, first, count, steps=60, only=None):
    g = Game(rom, elf)
    name = os.path.splitext(os.path.basename(rom))[0]
    out = os.path.join(HERE, "out", name, "story")
    os.makedirs(out, exist_ok=True)
    state = os.path.join(out, "story_menu.state").replace("\\", "/")
    g.start()
    g.set_flash(ERASED)
    g.reboot()
    for _ in range(80):
        if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_MainMenu"):
            break
        g.cmd("press Start 4", "wait 30")
    if not g.wait_field(press="A", max_steps=1500, settle=5):
        raise RuntimeError("intro never reached the field")
    mon = bytearray(party_mon(SPECIES_BULBASAUR, 100, [33, 45, 0, 0]))
    struct.pack_into("<7H", mon, 86, 300, 300, 250, 250, 250, 250, 250)
    path = os.path.join(out, "poke.bin")
    open(path, "wb").write(bytes(mon))
    g.cmd(f"poke EWRAM {g.a('gPlayerParty') - 0x02000000} {path.replace(chr(92), '/')}",
          f"write8 {g.a('gPlayerPartyCount')} 1")

    def edit():
        sb1 = g.u32(g.a("gSaveBlock1Ptr"))
        flag = sb1 + SB1_FLAGS + FLAG_SYS_POKEMON_GET // 8
        g.cmd(f"write8 {flag} {g.u8(flag) | 1 << (FLAG_SYS_POKEMON_GET % 8)}",
              f"write16 {sb1 + SB1_VARS + (VAR_REPEL_STEP_COUNT - 0x4000) * 2} 65535")
    g.save(before_save=edit)
    g.reboot()
    for _ in range(60):
        if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_MainMenu"):
            break
        g.cmd("press Start 4", "wait 30")
    g.cmd("wait 90", f"save {state}")

    results = {}
    t0 = time.time()
    todo = [m for m in maps() if m[2] in only] if only else maps()[first:first + count]
    for gi, mi, mname in todo:
        g.cmd(f"load {state}")
        sb1, sb2 = g.u32(g.a("gSaveBlock1Ptr")), g.u32(g.a("gSaveBlock2Ptr"))
        g.cmd(f"write8 {sb1 + 0xC} {gi}", f"write8 {sb1 + 0xD} {mi}", f"write8 {sb1 + 0xE} 0",
              f"write16 {sb1 + 0x10} 65535", f"write16 {sb1 + 0x12} 65535", f"write8 {sb2 + 9} {g.u8(sb2 + 9) | 1}")
        reached = g.wait_field(press="A", max_steps=steps, settle=3)
        sb1 = g.u32(g.a("gSaveBlock1Ptr"))
        x, y = struct.unpack("<hh", bytes.fromhex(g.cmd(f"read {sb1} 4")[0].replace(" ", "")))
        loc = bytes.fromhex(g.cmd(f"read {sb1 + 4} 2")[0].replace(" ", ""))
        flags = g.cmd(f"read {sb1 + SB1_FLAGS} {FLAGS_BYTES}")[0].replace(" ", "")
        vars_ = g.cmd(f"read {sb1 + SB1_VARS} {VARS_COUNT * 2}")[0].replace(" ", "")
        results[mname] = {"reached": reached, "map": list(loc), "pos": [x, y], "flags": flags, "vars": vars_}
        print(f"{gi:2}.{mi:<3} {mname}: field {reached}, map {tuple(loc)}, pos ({x},{y})", flush=True)
    import emu
    emu.stop()
    dest = os.path.join(out, "story_rerun.json" if only else f"story_{first}.json")
    json.dump(results, open(dest, "w"))
    print(f"{len(results)} maps in {time.time() - t0:.0f}s -> {dest}")


def diff(a, b):
    """(flags set/cleared differently, vars different) between two map records, without Gunk's own."""
    fa, fb = bytes.fromhex(a["flags"]), bytes.fromhex(b["flags"])
    flags = [i for i in range(FLAGS_BYTES * 8) if (fa[i // 8] >> (i % 8) & 1) != (fb[i // 8] >> (i % 8) & 1)
             and i not in GUNK_FLAGS and i not in IGNORED_FLAGS]
    va, vb = struct.unpack(f"<{VARS_COUNT}H", bytes.fromhex(a["vars"])), struct.unpack(f"<{VARS_COUNT}H", bytes.fromhex(b["vars"]))
    vars_ = [(0x4000 + i, va[i], vb[i]) for i in range(VARS_COUNT) if va[i] != vb[i]
             and 0x4000 + i not in GUNK_VARS and 0x4000 + i not in IGNORED_VARS]
    return flags, vars_


def load(path):
    """One json, or every story_*.json beside it merged (runs split by map range)."""
    folder = os.path.dirname(path)
    merged = {}
    for f in sorted(os.listdir(folder)):
        if f.startswith("story_") and f.endswith(".json"):
            merged.update(json.load(open(os.path.join(folder, f))))
    return merged


def compare(gpath, vpath):
    gk, vn = load(gpath), load(vpath)
    lines = []
    for name in vn:
        if name not in gk:
            lines.append(f"FAIL {name}: not in the Gunk's run")
            continue
        a, b = gk[name], vn[name]
        flags, vars_ = diff(a, b)
        same_place = a["map"] == b["map"] and a["pos"] == b["pos"] and a["reached"] == b["reached"]
        ok = not flags and not vars_ and same_place
        detail = f"field {a['reached']}/{b['reached']}, map {a['map']}/{b['map']}, pos {a['pos']}/{b['pos']}"
        if flags:
            detail += ", flags " + " ".join(f"{f:#x}" for f in flags)
        if vars_:
            detail += ", vars " + " ".join(f"{v:#x}={x}/{y}" for v, x, y in vars_)
        lines.append(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    failed = [l for l in lines if l.startswith("FAIL")]
    summary = f"{len(lines) - len(failed)}/{len(lines)} maps: Gunk's story state matches vanilla (Gunk's/vanilla)"
    print("\n".join(failed + [summary]))
    out = os.path.join(os.path.dirname(os.path.dirname(gpath)), "story.txt")
    open(out, "w").write("\n".join(lines + [summary]) + "\n")
    return not failed


def main():
    if sys.argv[1] == "run":
        first = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        count = int(sys.argv[5]) if len(sys.argv) > 5 else 10000
        run(os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3]), first, count)
    elif sys.argv[1] == "rerun":
        run(os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3]), 0, 0, int(sys.argv[4]), sys.argv[5].split(","))
    else:
        sys.exit(0 if compare(sys.argv[2], sys.argv[3]) else 1)


if __name__ == "__main__":
    main()
