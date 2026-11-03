"""The league to the end of the game: the 8 gym leaders, the Elite Four, the Champion, the Hall of Fame, the credits.

Usage:
  py -3 emu/suite/league.py run <rom.gba> <rom.elf>          one ROM, writes milestones.json beside its results
  py -3 emu/suite/league.py compare <gunk.json> <vanilla.json>

One game per ROM, without the test hook (vanilla has none): the intro to the bedroom, then a level 100 Mewtwo with
Psychic and the player's own OT (so it obeys) written into the party, healed the same way before every milestone.
Each gym leader: the save's continue-game warp puts the player below the leader, the player faces up and talks,
and A is pressed through the battle and the badge scene. Each Elite Four room and the Champion's: the player warps
onto the room's entrance (its entry scene plays as through the door), then, for the Elite Four, below the member.
After the Champion, A carries on through Oak, the Hall of Fame and the credits to the main menu, and CONTINUE must
reach the field. A milestone passes when its flag is set (badge, member defeated, game clear) and the save
block's flags and vars match vanilla's at the same point outside Gunk's own.
Results: emu/suite/out/<rom name>/milestones/.
"""
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from eggs import party_mon  # noqa: E402
from features import ERASED, FLAG_SYS_POKEMON_GET, SB1_FLAGS, SB1_VARS, VAR_REPEL_STEP_COUNT  # noqa: E402
from lib import Game  # noqa: E402
from arrival import diff  # noqa: E402
from sweep import maps  # noqa: E402

SPECIES_MEWTWO, MOVE_PSYCHIC = 150, 94
EXP_L100_SLOW = 1250000
FLAG_HIDE_VIRIDIAN_GIOVANNI = 0x055
FLAG_SYS_GAME_CLEAR = 0x82C
# (name, map, leader's script, flag set by winning)
GYMS = [("Brock", "PewterCity_Gym", "Brock", 0x820), ("Misty", "CeruleanCity_Gym", "Misty", 0x821),
        ("Lt. Surge", "VermilionCity_Gym", "LtSurge", 0x822), ("Erika", "CeladonCity_Gym", "Erika", 0x823),
        ("Koga", "FuchsiaCity_Gym", "Koga", 0x824), ("Sabrina", "SaffronCity_Gym", "Sabrina", 0x825),
        ("Blaine", "CinnabarIsland_Gym", "Blaine", 0x826), ("Giovanni", "ViridianCity_Gym", "Giovanni", 0x827)]
ELITE_FOUR = [("Lorelei", "PokemonLeague_LoreleisRoom", "Lorelei", 0x4B8),
              ("Bruno", "PokemonLeague_BrunosRoom", "Bruno", 0x4B9),
              ("Agatha", "PokemonLeague_AgathasRoom", "Agatha", 0x4BA),
              ("Lance", "PokemonLeague_LancesRoom", "Lance", 0x4BB)]
CHAMPION = ("Champion", "PokemonLeague_ChampionsRoom", None, 0x4BC)


def map_index():
    return {name: (gi, mi) for gi, mi, name in maps()}


def leader_tile(mapname, script):
    m = json.load(open(os.path.join(REPO, "data/maps", mapname, "map.json")))
    for o in m["object_events"]:
        if o.get("script", "").endswith("_EventScript_" + script):
            return o["x"], o["y"]
    raise KeyError(script)


class Milestones:
    def __init__(self, rom, elf):
        self.g = Game(rom, elf)
        self.name = os.path.splitext(os.path.basename(rom))[0]
        self.out = os.path.join(HERE, "out", self.name, "league")
        os.makedirs(self.out, exist_ok=True)
        self.maps = map_index()
        self.results = {}
        self.follower_colors = []  # (map, palette slot, black colors of 15) after each Continue

    def shot(self, name):
        self.g.cmd(f"shot {os.path.join(self.out, name).replace(chr(92), '/')}")

    def sb1(self):
        return self.g.u32(self.g.a("gSaveBlock1Ptr"))

    def sb2(self):
        return self.g.u32(self.g.a("gSaveBlock2Ptr"))

    def flag(self, flag):
        return (self.g.u8(self.sb1() + SB1_FLAGS + flag // 8) >> (flag % 8)) & 1

    def set_flag(self, flag, on):
        addr = self.sb1() + SB1_FLAGS + flag // 8
        b = self.g.u8(addr)
        self.g.cmd(f"write8 {addr} {(b | 1 << flag % 8) if on else (b & ~(1 << flag % 8))}")

    def heal(self):
        """The party: one Mewtwo, rewritten (full HP and PP) with the player's trainer ID and name."""
        g = self.g
        sb2 = self.sb2()
        ot = bytes.fromhex(g.cmd(f"read {sb2} 7")[0].replace(" ", ""))
        otid = g.u32(sb2 + 0xA)
        mon = party_mon(SPECIES_MEWTWO, 100, [MOVE_PSYCHIC, 0, 0, 0], exp=EXP_L100_SLOW, otid=otid, ot=ot,
                        stats=(999, 999, 999, 999, 999, 999))
        path = os.path.join(self.out, "poke.bin")
        open(path, "wb").write(mon)
        g.cmd(f"poke EWRAM {g.a('gPlayerParty') - 0x02000000} {path.replace(chr(92), '/')}",
              f"write8 {g.a('gPlayerPartyCount')} 1")

    def warp(self, mapname, x=None, y=None, warp_id=0, before=None):
        """Save with the continue-game warp at (x, y) on <mapname> (or onto its warp event <warp_id>), power-cycle,
        Continue. A is pressed until the field is ready, through any scene or battle on arrival."""
        g = self.g
        gi, mi = self.maps[mapname]

        def edit():
            sb1, sb2 = self.sb1(), self.sb2()
            if x is None:
                pos = [f"write8 {sb1 + 0xE} {warp_id}", f"write16 {sb1 + 0x10} 65535", f"write16 {sb1 + 0x12} 65535"]
            else:
                pos = [f"write8 {sb1 + 0xE} 255", f"write16 {sb1 + 0x10} {x}", f"write16 {sb1 + 0x12} {y}"]
            g.cmd(f"write8 {sb1 + 0xC} {gi}", f"write8 {sb1 + 0xD} {mi}", *pos, f"write8 {sb2 + 9} {g.u8(sb2 + 9) | 1}",
                  f"write16 {sb1 + SB1_VARS + (VAR_REPEL_STEP_COUNT - 0x4000) * 2} 65535")
            self.heal()
            if before:
                before()
        g.save(before_save=edit)
        g.reboot()
        g.boot_continue()
        self.check_follower_colors(mapname)

    def check_follower_colors(self, where):
        """Gunk's follower after a Continue, which plays the quest log ("Previously on your quest") of the last
        battle: its palette must be restored, not left black. Vanilla has no follower: nothing to check."""
        g = self.g
        objs = g.a("gObjectEvents")
        for i in range(16):
            raw = bytes.fromhex(g.cmd(f"read {objs + i * 0x24} 12")[0].replace(" ", ""))
            if raw[0] & 1 and raw[8] == 254:
                sprite = g.a("gSprites") + raw[4] * 0x44
                slot = struct.unpack("<H", bytes.fromhex(g.cmd(f"read {sprite + 4} 2")[0].replace(" ", "")))[0] >> 12
                colors = struct.unpack("<16H", bytes.fromhex(
                    g.cmd(f"read {g.a('gPlttBufferFaded') + 0x200 + slot * 32} 32")[0].replace(" ", "")))
                black = sum(1 for c in colors[1:] if c == 0)
                self.follower_colors.append((where, slot, black))
                if black == 15:
                    self.shot(f"black_follower_{len(self.follower_colors):02}.png")
                return

    def talk_up(self):
        """Face up, talk, and press A until the field is back (the battle, the badge, the TM)."""
        g = self.g
        g.cmd("press Up 3", "wait 20", "press A 4", "wait 60")
        return g.wait_field(press="A", max_steps=1500, settle=5)

    def record(self, label, flag, extra=""):
        sb1 = self.sb1()
        x, y = struct.unpack("<hh", bytes.fromhex(self.g.cmd(f"read {sb1} 4")[0].replace(" ", "")))
        rec = {"flag": self.flag(flag), "map": list(bytes.fromhex(self.g.cmd(f"read {sb1 + 4} 2")[0].replace(" ", ""))),
               "pos": [x, y], "flags": self.g.cmd(f"read {sb1 + SB1_FLAGS} 288")[0].replace(" ", ""),
               "vars": self.g.cmd(f"read {sb1 + SB1_VARS} 512")[0].replace(" ", "")}
        self.results[label] = rec
        self.shot(f"{len(self.results):02}_{label.replace(' ', '_').replace('.', '')}.png")
        print(f"{self.name} {label}: flag {flag:#x} = {rec['flag']}, map {tuple(rec['map'])}, pos ({x},{y}){extra}",
              flush=True)

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
        self.set_flag(FLAG_SYS_POKEMON_GET, True)

        for label, mapname, script, flag in GYMS:
            x, y = leader_tile(mapname, script)
            hide = (lambda: self.set_flag(FLAG_HIDE_VIRIDIAN_GIOVANNI, False)) if script == "Giovanni" else None
            self.warp(mapname, x, y + 1, before=hide)
            back = self.talk_up()
            self.record(label, flag, f", back in the field {back}")

        for label, mapname, script, flag in ELITE_FOUR:
            self.warp(mapname, warp_id=0)  # the entrance: the room's entry scene
            x, y = leader_tile(mapname, script)
            self.warp(mapname, x, y + 1)
            back = self.talk_up()
            self.record(label, flag, f", back in the field {back}")

        # the Champion: the entry scene starts the battle; A through Oak, the Hall of Fame and the credits
        label, mapname, _, flag = CHAMPION
        self.warp_and_finish(mapname, flag)
        self.check_follower_colors("after the credits")
        if self.follower_colors:
            black = [c for c in self.follower_colors if c[2] == 15]
            self.results["follower colors"] = {"checked": len(self.follower_colors), "black": black}
            print(f"{self.name} follower colors after {len(self.follower_colors)} Continues: "
                  f"{len(black)} black {black}", flush=True)
        return self.results

    def warp_and_finish(self, mapname, flag):
        g = self.g
        gi, mi = self.maps[mapname]

        def edit():
            sb1, sb2 = self.sb1(), self.sb2()
            g.cmd(f"write8 {sb1 + 0xC} {gi}", f"write8 {sb1 + 0xD} {mi}", f"write8 {sb1 + 0xE} 0",
                  f"write16 {sb1 + 0x10} 65535", f"write16 {sb1 + 0x12} 65535", f"write8 {sb2 + 9} {g.u8(sb2 + 9) | 1}")
            self.heal()
        g.save(before_save=edit)
        g.reboot()
        for _ in range(60):
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_MainMenu"):
                break
            g.cmd("press Start 4", "wait 30")
        g.cmd("wait 60")
        champion_seen = False
        t0 = time.time()
        menu = None
        for i in range(6000):
            cb2 = g.u32(g.a("gMain") + 4) & ~1
            if i > 20 and cb2 == g.a("CB2_MainMenu"):
                menu = i
                break
            if not champion_seen and self.flag(flag):
                champion_seen = True
                self.record("Champion", flag)
            g.cmd("press A 4", "wait 16")
        self.shot("credits_end.png")
        clear = None
        if menu is not None:
            g.cmd("wait 60")
            back = g.wait_field(press="A", max_steps=400, settle=5)
            self.record("Hall of Fame and credits", FLAG_SYS_GAME_CLEAR,
                        f", main menu after {time.time() - t0:.0f}s, CONTINUE reached the field {back}")
            clear = back
        else:
            self.results["Hall of Fame and credits"] = {"flag": 0, "map": [], "pos": [], "flags": "", "vars": "",
                                                       "error": "never reached the main menu"}
            print(f"{self.name}: never reached the main menu after the Champion", flush=True)
        return clear


def compare(gpath, vpath):
    gk, vn = json.load(open(gpath)), json.load(open(vpath))
    lines = []
    for label in [m[0] for m in GYMS + ELITE_FOUR] + ["Champion", "Hall of Fame and credits"]:
        a, b = gk.get(label), vn.get(label)
        if not a or not a.get("flags"):
            lines.append(f"FAIL {label}: not reached in Gunk's")
            continue
        detail = f"flag {a['flag']}/{b['flag'] if b else '-'}, map {a['map']}/{b['map'] if b else '-'}"
        ok = a["flag"] == 1
        if b and b.get("flags"):
            flags, vars_ = diff(a, b)
            ok = ok and not flags and not vars_ and a["map"] == b["map"]
            if flags:
                detail += ", flags " + " ".join(f"{f:#x}" for f in flags)
            if vars_:
                detail += ", vars " + " ".join(f"{v:#x}={x}/{y}" for v, x, y in vars_)
        lines.append(f"{'PASS' if ok else 'FAIL'} {label}: {detail} (Gunk's/vanilla)")
    colors = gk.get("follower colors")
    if colors:
        lines.append(f"{'FAIL' if colors['black'] else 'PASS'} follower colors after the quest log: "
                     f"{len(colors['black'])} black of {colors['checked']} Continues {colors['black'] or ''}")
    failed = [l for l in lines if l.startswith("FAIL")]
    summary = f"{len(lines) - len(failed)}/{len(lines)} milestones"
    print("\n".join(lines + [summary]))
    open(os.path.join(os.path.dirname(gpath), "results.txt"), "w").write("\n".join(lines + [summary]) + "\n")
    return not failed


def main():
    if sys.argv[1] == "run":
        m = Milestones(os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3]))
        try:
            m.run()
        finally:
            import emu
            emu.stop()
            json.dump(m.results, open(os.path.join(m.out, "league.json"), "w"))
    else:
        sys.exit(0 if compare(sys.argv[2], sys.argv[3]) else 1)


if __name__ == "__main__":
    main()
