"""Story milestones, each started where a player would be: py -3 emu/suite/milestones.py <gunk.gba> <gunk.elf>
<vanilla.gba> <vanilla.elf> [names...]

Each milestone starts from the story sweep's setup (story.py: the intro, then a Lv. 100 Mewtwo with the player's
trainer ID): the flags and items the event needs are set, the continue warp points next to the event, CONTINUE,
then the player faces the person (or the scene starts on arrival) and A is pressed until the player can walk again.
This runs on Gunk's and on vanilla FireRed from the same setup. A milestone passes when the milestone's own flag is
set on Gunk's, Gunk's ends on the same map with the same vars and flags as vanilla (but Gunk's own), and on Gunk's a
save, power cycle and CONTINUE comes back on that map.

Milestones: the eight gym leaders, the S.S. Anne captain (HM01 Cut), Snorlax on Route 12 (with the Poke Flute), and
the Champion (the battle, Oak, the Hall of Fame and its save, the credits, then CONTINUE).
Results: emu/suite/out/<gunk rom>/milestones.txt.
"""
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import story  # noqa: E402

SB1_KEY_ITEMS, SB2_ENCRYPTION_KEY = 0x3B8, 0xF20
FLAG_BADGE01_GET, FLAG_SYS_GAME_CLEAR = 0x820, 0x82C
FLAG_GOT_HM01, FLAG_HIDE_ROUTE_12_SNORLAX = 0x237, 0x054
FLAG_GOT_POKE_FLUTE = 0x23D  # the Snorlax script checks this flag, not the bag
ITEM_POKE_FLUTE = 350

# name, map folder, the person's tile (None: the scene starts on arrival), flags to set first, key items, the flag
# that must be set afterwards, A presses allowed
MILESTONES = [
    ("brock", "PewterCity_Gym", (6, 5), [], [], FLAG_BADGE01_GET, 600),
    ("misty", "CeruleanCity_Gym", (8, 6), [FLAG_BADGE01_GET], [], FLAG_BADGE01_GET + 1, 600),
    ("surge", "VermilionCity_Gym", (5, 2), [FLAG_BADGE01_GET + i for i in range(2)], [], FLAG_BADGE01_GET + 2, 600),
    ("erika", "CeladonCity_Gym", (6, 4), [FLAG_BADGE01_GET + i for i in range(3)], [], FLAG_BADGE01_GET + 3, 600),
    ("koga", "FuchsiaCity_Gym", (7, 13), [FLAG_BADGE01_GET + i for i in range(4)], [], FLAG_BADGE01_GET + 4, 600),
    ("sabrina", "SaffronCity_Gym", (14, 11), [FLAG_BADGE01_GET + i for i in range(5)], [], FLAG_BADGE01_GET + 5, 600),
    ("blaine", "CinnabarIsland_Gym", (5, 4), [FLAG_BADGE01_GET + i for i in range(6)], [], FLAG_BADGE01_GET + 6, 600),
    ("giovanni", "ViridianCity_Gym", (2, 2), [FLAG_BADGE01_GET + i for i in range(7)], [], FLAG_BADGE01_GET + 7, 600),
    ("captain", "SSAnne_CaptainsOffice", (5, 4), [], [], FLAG_GOT_HM01, 300),
    ("snorlax", "Route12", (14, 70), [FLAG_GOT_POKE_FLUTE], [ITEM_POKE_FLUTE], FLAG_HIDE_ROUTE_12_SNORLAX, 400),
    ("champion", "PokemonLeague_ChampionsRoom", None, [FLAG_BADGE01_GET + i for i in range(8)], [],
     FLAG_SYS_GAME_CLEAR, 4000),
]


class Milestones(story.Runner):
    def set_flag(self, flag):
        addr = self.sb1() + story.SB1_FLAGS + flag // 8
        self.g.cmd(f"write8 {addr} {self.g.u8(addr) | 1 << (flag % 8)}")

    def flag(self, outcome, flag):
        return bytes.fromhex(outcome["flags"])[flag // 8] >> (flag % 8) & 1

    def give_key_item(self, slot, item):
        key = struct.unpack("<I", self.read(self.sb2() + SB2_ENCRYPTION_KEY, 4))[0] & 0xFFFF
        self.write(self.sb1() + SB1_KEY_ITEMS + slot * 4, struct.pack("<HH", item, 1 ^ key))

    def at_title(self):
        g = self.g
        cb2 = g.u32(g.a("gMain") + 4) & ~1
        return cb2 in (g.a("CB2_MainMenu"), g.a("CB2_InitCopyrightScreenAfterBootup")) or g.a("CB2_InitTitleScreen") == cb2

    def milestone(self, spec):
        name, folder, person, flags, items, done_flag, presses = spec
        g = self.g
        m = story.neighbour.cache[folder]
        if person:
            wx, wy, direction = story.neighbour(folder, *person)
            warp_id = 255
        else:
            wx, wy, direction, warp_id = 0xFFFF, 0xFFFF, None, 0
        g.cmd(f"load {self.state}")
        for flag in flags:
            self.set_flag(flag)
        for slot, item in enumerate(items):
            self.give_key_item(slot, item)
        sb1 = self.sb1()
        g.cmd(f"write8 {sb1 + story.SB1_CONTINUE_WARP} {m['group']}", f"write8 {sb1 + story.SB1_CONTINUE_WARP + 1} {m['num']}",
              f"write8 {sb1 + story.SB1_CONTINUE_WARP + 2} {warp_id}",
              f"write16 {sb1 + story.SB1_CONTINUE_WARP + 4} {wx}", f"write16 {sb1 + story.SB1_CONTINUE_WARP + 6} {wy}",
              f"write8 {self.sb2() + 9} {g.u8(self.sb2() + 9) | 1}")
        g.cmd("press A 4", "wait 30")  # CONTINUE
        if person:
            if not g.wait_field(press="A", max_steps=120):
                return {"result": "setup: no field after CONTINUE"}
            g.cmd(f"press {direction} 2", "wait 10", "press A 4", "wait 30")
        else:
            for _ in range(80):  # the scene starts as the map comes up
                if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_Overworld"):
                    break
                g.cmd("press A 4", "wait 20")
        settled, title = 0, False
        for i in range(presses):
            if g.field_ready():
                settled += 1
                if settled >= 3:
                    break
                g.cmd("wait 20")
                continue
            settled = 0
            if self.at_title():
                # the credits end on the title screen: CONTINUE from the save the Hall of Fame made
                title = True
                print(f"title screen? cb2 {g.u32(g.a('gMain') + 4):#x} after {i} presses", flush=True)
                g.cmd("wait 60", f"shot {os.path.splitext(self.out)[0]}_{name}_title.png")
                try:
                    g.boot_continue()
                except RuntimeError as e:
                    return {"result": f"after the credits: {e}", "outcome": self.outcome()}
                continue
            g.cmd("press A 4", "wait 20")
            if os.environ.get("MILESTONE_SHOTS") and i % 100 == 0:
                g.cmd(f"shot {os.path.splitext(self.out)[0]}_{name}_{i}.png")
            if i % 100 == 99 and int(g.cmd(f"alive {g.a('gMain') + 0x24} 30")[0].split()[1]) == 0:
                g.cmd(f"shot {os.path.splitext(self.out)[0]}_{name}_hang.png")
                return {"result": "hang", "outcome": self.outcome()}
        g.cmd(f"shot {os.path.splitext(self.out)[0]}_{name}.png")
        if settled < 3:
            return {"result": "unfinished", "outcome": self.outcome()}
        out = self.outcome()
        return {"result": "finished", "outcome": out, "flag": self.flag(out, done_flag), "title": title}

    def follower_colors(self):
        """Colors 1-15 of the follower's palette that aren't black, or None with no follower out."""
        g = self.g
        objs = g.a("gObjectEvents")
        for i in range(16):
            raw = self.read(objs + i * 0x24, 12)
            if raw[0] & 1 and raw[8] == 254:  # active, LOCALID_FOLLOWER
                slot = struct.unpack("<H", self.read(g.a("gSprites") + raw[4] * 0x44 + 4, 2))[0] >> 12
                pal = struct.unpack("<16H", self.read(g.a("gPlttBufferFaded") + 0x200 + slot * 32, 32))
                return sum(1 for c in pal[1:] if c)
        return None

    def save_cycle(self):
        """Save, power-cycle, CONTINUE (after a battle the quest log's "previously on your quest" plays first).
        Returns the map before and after, and the follower's non-black colors after."""
        before = self.outcome()["map"]
        g = self.g
        g.save()
        g.reboot()
        g.boot_continue()
        g.cmd("wait 60")
        return before, self.outcome()["map"], self.follower_colors()


def main():
    rom, elf, vrom, velf = (os.path.abspath(a) for a in sys.argv[1:5])
    names = sys.argv[5:]
    todo = [s for s in MILESTONES if not names or s[0] in names]
    out_dir = os.path.join(HERE, "out", os.path.splitext(os.path.basename(rom))[0], "milestones")
    os.makedirs(out_dir, exist_ok=True)
    import emu
    t0 = time.time()
    results = {}
    try:
        v = Milestones(vrom, velf, os.path.join(out_dir, "vanilla.jsonl"))
        v.setup()
        for spec in todo:
            results[spec[0]] = {"vanilla": v.milestone(spec)}
            print(f"vanilla {spec[0]}: {results[spec[0]]['vanilla']['result']}", flush=True)
        emu.stop()
        g = Milestones(rom, elf, os.path.join(out_dir, "gunk.jsonl"))
        g.setup()
        for spec in todo:
            r = g.milestone(spec)
            if r["result"] == "finished":
                r["save_cycle"] = g.save_cycle()
            results[spec[0]]["gunk"] = r
    finally:
        emu.stop()
    lines, failed = [], 0
    for spec in todo:
        name = spec[0]
        gk, vn = results[name].get("gunk", {}), results[name]["vanilla"]
        detail = [f"Gunk's {gk.get('result')}", f"vanilla {vn.get('result')}"]
        ok = gk.get("result") == "finished" and gk.get("flag") == 1
        if not gk.get("flag"):
            detail.append("milestone flag not set")
        if gk.get("result") == "finished" and vn.get("result") == "finished":
            diff = story.outcome_diff(gk["outcome"], vn["outcome"])
            if diff:
                ok = False
                detail.append("differs from vanilla: " + "; ".join(diff[:6]))
        elif vn.get("result") != "finished":
            detail.append("(vanilla did not finish either: test setup)")
        if "save_cycle" in gk:
            before, after, colors = gk["save_cycle"]
            ok = ok and before == after and colors is not None and colors >= 4
            detail.append(f"save and CONTINUE: map {before} -> {after}, follower colors {colors}/15")
        if gk.get("title"):
            detail.append("credits reached the title screen")
        failed += not ok
        lines.append(("PASS " if ok else "FAIL ") + name + ": " + ", ".join(detail))
        print(lines[-1], flush=True)
    lines.append(f"{len(todo) - failed}/{len(todo)} milestones passed in {time.time() - t0:.0f}s")
    print(lines[-1])
    open(os.path.join(out_dir, "milestones.txt"), "w").write("\n".join(lines) + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
