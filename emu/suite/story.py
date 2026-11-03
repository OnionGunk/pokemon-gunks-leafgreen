"""Story-trigger sweep: every var-gated story trigger, played on a ROM, outcomes saved for comparing with vanilla.

Usage: py -3 emu/suite/story.py run <rom.gba> <rom.elf> <out.jsonl> [first] [count]
       py -3 emu/suite/story.py compare <gunk.jsonl> <vanilla.jsonl>

Triggers: every coord_event of type trigger in data/maps/*/map.json (the player steps on it), and every
map_script_2 entry of an ON_FRAME table in data/maps/*/scripts.inc (it runs when the map loads).

Setup (the same on both ROMs; vanilla has no test hook): the intro is played to the bedroom, a Lv. 100 Mewtwo with
the player's trainer ID is written into the party (so battles end quickly) and the game saved; then, from the main
menu with that save loaded, for each trigger: its var is set to the trigger's value, the continue warp points at a
free tile next to it (ON_FRAME: the map's first warp), CONTINUE, one step onto the trigger. If a script starts, A is
pressed until the player can walk again (a scene that never gives control back within about 4 minutes of game time
is "unfinished"; a stopped main loop is a "hang"). The outcome is the map, position, every save var and flag, and the
party species.

compare: a trigger fails when Gunk's ends unfinished or hung and vanilla finished. Scenes that end with other vars or
flags than vanilla's are listed for review (Gunk's own vars and flags are left out of that).
"""
import json
import os
import re
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from boxes import build  # noqa: E402
from lib import FLASH_SIZE, Game  # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
ERASED = b"\xff" * FLASH_SIZE
SB1_POS, SB1_LOCATION, SB1_CONTINUE_WARP = 0x0, 0x4, 0xC
SB1_FLAGS, SB1_VARS = 0x0EE0, 0x1000
FLAGS_SIZE, VARS_COUNT = 288, 256
SB2_NAME, SB2_TRAINER_ID = 0x0, 0xA
FLAG_SYS_POKEMON_GET = 0x828
# Gunk's own save data, and data a scene changes as a side effect (steps, the quest log, the follower's flag)
GUNK_VARS = {0x4029, 0x402A}
GUNK_FLAGS = set(range(0x4A7, 0x4AB))
DIRS = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}


# --- what the maps say ---
def const_ids(header, prefix):
    text = open(os.path.join(REPO, "include", "constants", header), encoding="utf8").read()
    ids = {}
    for name, value in re.findall(rf"#define\s+({prefix}\w+)\s+(\(?[^\n/]+)", text):
        value = value.strip().strip("()")
        try:
            ids[name] = int(value, 0)
        except ValueError:
            m = re.match(r"(\w+)\s*\+\s*(0x[0-9A-Fa-f]+|\d+)", value)
            if m and m.group(1) in ids:
                ids[name] = ids[m.group(1)] + int(m.group(2), 0)
    return ids


def var_ids():
    ids = const_ids("vars.h", "VAR_")
    ids.update({f"VAR_TEMP_{i:X}": 0x4000 + i for i in range(16)})  # (TEMP_VARS_START + n): cleared on every map load
    return ids


def maps():
    groups = json.load(open(os.path.join(REPO, "data/maps/map_groups.json")))
    out = {}
    for gi, gname in enumerate(groups["group_order"]):
        for mi, folder in enumerate(groups[gname]):
            m = json.load(open(os.path.join(REPO, "data/maps", folder, "map.json"), encoding="utf8"))
            out[folder] = dict(m, group=gi, num=mi, folder=folder, link=gname == "gMapGroup_Link")
    return out


def layouts():
    data = json.load(open(os.path.join(REPO, "data/layouts/layouts.json")))
    return {l["id"]: l for l in data["layouts"] if "id" in l}


def blocks(layout):
    raw = open(os.path.join(REPO, layout["blockdata_filepath"]), "rb").read()
    w = layout["width"]
    return lambda x, y: struct.unpack_from("<H", raw, (y * w + x) * 2)[0] if 0 <= x < w and 0 <= y < layout["height"] else None


def on_frame_scripts(folder):
    path = os.path.join(REPO, "data/maps", folder, "scripts.inc")
    if not os.path.exists(path):
        return []
    text = open(path, encoding="utf8").read()
    out = []
    for label in re.findall(r"map_script MAP_SCRIPT_ON_FRAME_TABLE, (\w+)", text):
        m = re.search(rf"^{label}::?[ 	]*$", text, re.M)
        if not m:
            continue  # a table shared with another map, listed there
        body = text[m.end():].split(".2byte 0", 1)[0]
        out += re.findall(r"map_script_2 (VAR_\w+), (\w+), (\w+)", body)
    return out


def triggers():
    """[(kind, map folder, var, value, x, y, script)]; for steps x, y is the trigger tile."""
    all_maps, lays = maps(), layouts()
    out = []
    for folder, m in all_maps.items():
        if m["link"]:
            continue
        for c in m.get("coord_events") or []:
            if c.get("type") == "trigger" and c["var"] not in ("0", ""):
                out.append(("step", folder, c["var"], c["var_value"], c["x"], c["y"], c["script"]))
        if m.get("warp_events"):
            for var, value, script in on_frame_scripts(folder):
                out.append(("frame", folder, var, value, None, None, script))
    return out


def neighbour(folder, x, y):
    """A free tile next to (x, y) and the direction from it onto (x, y), or None."""
    spots = neighbours(folder, x, y)
    return spots[0] if spots else None


def neighbours(folder, x, y):
    """Every free tile next to (x, y), with the direction from it onto (x, y): passable in the map file, not a
    trigger, no object on it. A tile a map script closes at run time (a door) still counts: play() then moves on."""
    out = []
    m = neighbour.cache[folder]
    layout = neighbour.layouts[m["layout"]]
    at = blocks(layout)
    taken = {(c["x"], c["y"]) for c in m.get("coord_events") or []} | {(o["x"], o["y"]) for o in m.get("object_events") or []}
    elevation = (at(x, y) or 0) >> 12
    for name, (dx, dy) in (("Up", (0, 1)), ("Down", (0, -1)), ("Left", (1, 0)), ("Right", (-1, 0))):
        nx, ny = x + dx, y + dy
        b = at(nx, ny)
        if b is None or (nx, ny) in taken or (b >> 10) & 3:
            continue
        if b >> 12 not in (elevation, 0, 15) and elevation not in (0, 15):
            continue
        out.append((nx, ny, name))
    return out


# --- the runner ---
def text_bytes(s):
    table = {c: 0xBB + i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
    return bytes(table[c] for c in s)


class Runner:
    def __init__(self, rom, elf, out):
        self.g = Game(rom, elf)
        self.out = out
        self.state = os.path.splitext(out)[0] + "_menu.state"
        self.vars = var_ids()
        neighbour.cache = maps()
        neighbour.layouts = layouts()

    def sb1(self):
        return self.g.u32(self.g.a("gSaveBlock1Ptr"))

    def sb2(self):
        return self.g.u32(self.g.a("gSaveBlock2Ptr"))

    def read(self, addr, n):
        return bytes.fromhex(self.g.cmd(f"read {addr} {n}")[0].replace(" ", ""))

    def write(self, addr, data):
        path = os.path.splitext(self.out)[0] + "_poke.bin"
        open(path, "wb").write(data)
        self.g.cmd(f"poke EWRAM {addr - 0x02000000} {path.replace(chr(92), '/')}")

    def mewtwo(self):
        name, tid = self.read(self.sb2() + SB2_NAME, 7), self.read(self.sb2() + SB2_TRAINER_ID, 4)
        header = struct.pack("<I", 0) + tid + (text_bytes("MEWTWO") + b"\xff" * 4) + bytes([2, 0b10]) + name + b"\0"
        subs = {"G": struct.pack("<HHIBBH", 150, 0, 1250000, 0, 70, 0),
                "A": struct.pack("<4H4B", 94, 85, 58, 53, 10, 15, 10, 15),  # Psychic, Thunderbolt, Ice Beam, Flamethrower
                "E": bytes(12),
                "M": struct.pack("<BBHII", 0, 0x58, 70 | 4 << 7 | 1 << 11, 0x3FFFFFFF, 0)}
        return build(header, subs) + struct.pack("<IBBH6H", 0, 100, 0xFF, 353, 353, 256, 216, 296, 344, 216)

    def setup(self):
        g = self.g
        g.start()
        g.set_flash(ERASED)
        g.reboot()
        for _ in range(80):
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_MainMenu"):
                break
            g.cmd("press Start 4", "wait 30")
        if not g.wait_field(press="A", max_steps=1500, settle=5):
            raise RuntimeError("the intro never reached the field")

        def edit():
            self.write(g.a("gPlayerParty"), self.mewtwo())
            g.cmd(f"write8 {g.a('gPlayerPartyCount')} 1")
            flag = self.sb1() + SB1_FLAGS + FLAG_SYS_POKEMON_GET // 8
            g.cmd(f"write8 {flag} {g.u8(flag) | 1 << (FLAG_SYS_POKEMON_GET % 8)}")
        g.save(before_save=edit)
        g.reboot()
        for _ in range(60):
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_MainMenu"):
                break
            g.cmd("press Start 4", "wait 30")
        g.cmd("wait 90", f"save {self.state}")

    def outcome(self):
        sb1 = self.sb1()
        loc = self.read(sb1 + SB1_LOCATION, 2)
        x, y = struct.unpack("<hh", self.read(sb1 + SB1_POS, 4))
        party = [struct.unpack_from("<H", self.read(self.g.a("gPlayerParty") + i * 100, 100), 0)[0]
                 for i in range(self.g.u8(self.g.a("gPlayerPartyCount")))]
        return {"map": [loc[0], loc[1]], "pos": [x, y], "vars": self.read(sb1 + SB1_VARS, VARS_COUNT * 2).hex(),
                "flags": self.read(sb1 + SB1_FLAGS, FLAGS_SIZE).hex(), "party_count": len(party)}

    def arrive(self, m, var, val, wx, wy, warp_id):
        """From the main-menu savestate: set the var, point the continue warp at (wx, wy) on map m, CONTINUE."""
        g = self.g
        g.cmd(f"load {self.state}")
        sb1 = self.sb1()
        g.cmd(f"write16 {sb1 + SB1_VARS + (self.vars[var] - 0x4000) * 2} {val}",
              f"write8 {sb1 + SB1_CONTINUE_WARP} {m['group']}", f"write8 {sb1 + SB1_CONTINUE_WARP + 1} {m['num']}",
              f"write8 {sb1 + SB1_CONTINUE_WARP + 2} {warp_id}",
              f"write16 {sb1 + SB1_CONTINUE_WARP + 4} {wx}", f"write16 {sb1 + SB1_CONTINUE_WARP + 6} {wy}",
              f"write8 {self.sb2() + 9} {g.u8(self.sb2() + 9) | 1}")
        g.cmd("press A 4", "wait 30")  # CONTINUE

    def script_running(self):
        g = self.g
        return not g.field_ready()

    def play(self, t):
        kind, folder, var, value, x, y, script = t
        g = self.g
        m = neighbour.cache[folder]
        res = {"kind": kind, "map": folder, "var": var, "value": value, "x": x, "y": y, "script": script}
        if var not in self.vars:
            return dict(res, result="skipped", why="unknown var")
        try:
            val = int(value, 0)
        except ValueError:
            val = const_ids("vars.h", "").get(value)
            if val is None:
                return dict(res, result="skipped", why="unknown value")
        spots = neighbours(folder, x, y) if kind == "step" else [(0xFFFF, 0xFFFF, None)]
        if not spots:
            return dict(res, result="skipped", why="no free tile next to it")
        for wx, wy, direction in spots:
            self.arrive(m, var, val, wx, wy, 255 if kind == "step" else 0)
            if kind != "step":
                break
            if not g.wait_field(press="A", max_steps=120):
                return dict(res, result="setup", why="the field never came up after CONTINUE")
            g.cmd(f"press {direction} 2", "wait 8", f"press {direction} 6", "wait 30")
            began = self.script_running()
            pos = list(struct.unpack("<hh", self.read(self.sb1() + SB1_POS, 4)))
            if began or pos != [wx, wy]:
                break
            # the step didn't happen: the tile is closed at run time (a door a map script shuts); try the next
        if kind != "step":
            # an ON_FRAME scene starts as the map comes up: the overworld runs with the controls locked
            began = False
            for _ in range(80):
                if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_Overworld"):
                    break
                g.cmd("press A 4", "wait 20")
            for _ in range(8):
                g.cmd("wait 15")
                if self.script_running():
                    began = True
                    break
        if not began:
            return dict(res, result="not started", outcome=self.outcome())
        frames = int(g.cmd(f"alive {g.a('gMain') + 0x24} 30")[0].split()[1])
        settled = 0
        for i in range(600):
            if g.field_ready():
                settled += 1
                if settled >= 3:
                    return dict(res, result="finished", presses=i, outcome=self.outcome())
                g.cmd("wait 20")
                continue
            settled = 0
            g.cmd("press A 4", "wait 20")
            if i % 50 == 49:
                frames = int(g.cmd(f"alive {g.a('gMain') + 0x24} 30")[0].split()[1])
                if frames == 0:
                    g.cmd(f"shot {os.path.splitext(self.out)[0]}_hang_{folder}_{x}_{y}.png")
                    return dict(res, result="hang", outcome=self.outcome())
        g.cmd(f"shot {os.path.splitext(self.out)[0]}_unfinished_{folder}_{x}_{y}.png")
        return dict(res, result="unfinished", outcome=self.outcome())


def run(rom, elf, out, first=0, count=100000):
    r = Runner(rom, elf, out)
    todo = triggers()[first:first + count]
    done = set()
    if os.path.exists(out):
        done = {(d["kind"], d["map"], d["var"], d["value"], d["x"], d["y"]) for d in map(json.loads, open(out))}
    r.setup()
    t0 = time.time()
    with open(out, "a") as f:
        for n, t in enumerate(todo):
            if t[:6] in done:
                continue
            try:
                res = r.play(t)
            except RuntimeError as e:
                res = {"kind": t[0], "map": t[1], "var": t[2], "value": t[3], "x": t[4], "y": t[5], "script": t[6],
                       "result": "error", "why": str(e)}
                import emu
                emu.stop()
                r.setup()
            f.write(json.dumps(res) + "\n")
            f.flush()
            print(f"{n + 1}/{len(todo)} {res['result']:12} {t[1]} {t[2]}={t[3]} {t[6]} ({time.time() - t0:.0f}s)",
                  flush=True)
    import emu
    emu.stop()


def flags_set(hexs):
    b = bytes.fromhex(hexs)
    return {i for i in range(len(b) * 8) if b[i // 8] >> (i % 8) & 1}


def outcome_diff(a, b):
    diff = []
    if a["map"] != b["map"]:
        diff.append(f"map {a['map']} vs {b['map']}")
    va, vb = bytes.fromhex(a["vars"]), bytes.fromhex(b["vars"])
    for i in range(VARS_COUNT):
        x, y = struct.unpack_from("<H", va, i * 2)[0], struct.unpack_from("<H", vb, i * 2)[0]
        if x != y and 0x4000 + i not in GUNK_VARS and not 0x4000 <= 0x4000 + i <= 0x400F:
            diff.append(f"var {0x4000 + i:#x} {x} vs {y}")
    fa, fb = flags_set(a["flags"]), flags_set(b["flags"])
    for flag in sorted((fa ^ fb) - GUNK_FLAGS):
        if flag >= 0x20:  # 0x00-0x1F are the temporary flags
            diff.append(f"flag {flag:#x} {'set' if flag in fa else 'clear'} vs {'set' if flag in fb else 'clear'}")
    if a["party_count"] != b["party_count"]:
        diff.append(f"party {a['party_count']} vs {b['party_count']}")
    return diff


def compare(gunk_path, vanilla_path):
    key = lambda d: (d["kind"], d["map"], d["var"], d["value"], d["x"], d["y"])  # noqa: E731
    gunk = {key(d): d for d in map(json.loads, open(gunk_path))}
    van = {key(d): d for d in map(json.loads, open(vanilla_path))}
    counts, failures, different, setup = {}, [], [], []
    for k, d in gunk.items():
        v = van.get(k)
        counts[d["result"]] = counts.get(d["result"], 0) + 1
        label = f"{d['kind']} {d['map']} {d['var']}={d['value']} at ({d['x']},{d['y']}) {d['script']}"
        if v is None:
            continue
        if d["result"] in ("unfinished", "hang", "error", "setup") and v["result"] == "finished":
            failures.append(f"{label}: {d['result']} on Gunk's, finished in vanilla")
        elif d["result"] in ("unfinished", "hang", "error", "setup"):
            setup.append(f"{label}: {d['result']} (vanilla: {v['result']})")
        elif d["result"] != v["result"] and "not started" in (d["result"], v["result"]):
            failures.append(f"{label}: {d['result']} on Gunk's, {v['result']} in vanilla")
        elif d["result"] == v["result"] == "finished":
            diff = outcome_diff(d["outcome"], v["outcome"])
            if diff:
                different.append(f"{label}: " + "; ".join(diff[:8]) + (" ..." if len(diff) > 8 else ""))
    print("Gunk's results:", counts)
    print(f"{len(failures)} failing, {len(setup)} unfinished in vanilla too (test setup), {len(different)} finished "
          "differently")
    for line in failures:
        print("FAIL " + line)
    for line in setup:
        print("setup " + line)
    for line in different:
        print("different " + line)
    return 1 if failures else 0


if __name__ == "__main__":
    if sys.argv[1] == "run":
        a = sys.argv[2:]
        run(os.path.abspath(a[0]), os.path.abspath(a[1]), os.path.abspath(a[2]),
            int(a[3]) if len(a) > 3 else 0, int(a[4]) if len(a) > 4 else 100000)
    else:
        sys.exit(compare(sys.argv[2], sys.argv[3]))
