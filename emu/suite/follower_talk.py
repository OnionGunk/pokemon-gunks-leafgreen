"""Talking to the follower: py -3 emu/suite/follower_talk.py <rom.gba> <rom.elf>

On Route 1 with a Bulbasaur following: the player turns to it and presses A. Each case must start the follower's
talk script with its nickname in STR_VAR_1 and the line for its state in VAR_RESULT (Gunk_FollowerTalkPrepare),
then give the field back after the message, with the follower still following:
  wary (friendship 10), happy (220), devoted (255), tired (friendship 255 but under a quarter of its HP)
Every wait is bounded. Results: emu/suite/out/<rom>/features/follower_talk.txt.
"""
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import FLAG_SYS_POKEMON_GET, MAP_ROUTE1, SPECIES, Features  # noqa: E402
from lib import SUBSTRUCT_ORDERS  # noqa: E402

TIRED, WARY, SHY, STEADY, HAPPY, DEVOTED = range(6)
CASES = [("wary", 10, False, WARY), ("happy", 220, False, HAPPY), ("devoted", 255, False, DEVOTED),
         ("tired", 255, True, TIRED)]
VAR_RESULT_ADDR = "gSpecialVar_Result"
BULBASAUR_NAME = bytes([0xBC, 0xCF, 0xC6, 0xBC, 0xBB, 0xCD, 0xBB, 0xCF, 0xCC])  # BULBASAUR


class Talk(Features):
    def edit_lead(self, friendship=None, hp=None):
        addr = self.g.a("gPlayerParty")
        raw = bytearray(bytes.fromhex(self.g.cmd(f"read {addr} 100")[0].replace(" ", "")))
        pid, otid = struct.unpack_from("<II", raw, 0)
        key = pid ^ otid
        dec = bytearray(b"".join(struct.pack("<I", struct.unpack_from("<I", raw, 0x20 + i)[0] ^ key)
                                 for i in range(0, 48, 4)))
        if friendship is not None:
            dec[SUBSTRUCT_ORDERS[pid % 24].index("G") * 12 + 9] = friendship
        struct.pack_into("<H", raw, 0x1C, sum(struct.unpack_from("<24H", dec)) & 0xFFFF)
        for i in range(0, 48, 4):
            struct.pack_into("<I", raw, 0x20 + i, struct.unpack_from("<I", dec, i)[0] ^ key)
        if hp is not None:
            struct.pack_into("<H", raw, 0x56, hp)
        path = self.path("_lead.bin")
        open(path, "wb").write(bytes(raw))
        self.g.cmd(f"poke EWRAM {addr - 0x02000000} {path}")

    def face_follower(self):
        fx, fy = self.follower_pos()
        px, py = self.pos()
        d = {(0, -1): "Up", (0, 1): "Down", (-1, 0): "Left", (1, 0): "Right"}.get((fx - px, fy - py))
        if d is None:
            return False
        self.g.cmd(f"press {d} 2", "wait 10")
        return True


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    t = Talk(rom, elf)
    g = t.g
    t0 = time.time()
    import emu
    try:
        t.new_game(mons=[(SPECIES["BULBASAUR"], 10)], flags=[FLAG_SYS_POKEMON_GET], name="talk")
        t.warp(*MAP_ROUTE1, 4, 18, name="talk_route1")
        # single steps until the follower is on the next tile (it catches up a step after a walk ends)
        for _ in range(6):
            fx, fy = t.follower_pos()
            px, py = t.pos()
            if abs(fx - px) + abs(fy - py) == 1:
                break
            g.cmd("press Up 8", "wait 40")
        g.cmd("wait 30", f"save {t.path('talk.state')}")
        maxhp = struct.unpack("<H", bytes.fromhex(g.cmd(f"read {g.a('gPlayerParty') + 0x58} 2")[0].replace(" ", "")))[0]
        for name, friendship, tired, want in CASES:
            g.cmd(f"load {t.path('talk.state')}")
            t.edit_lead(friendship=friendship, hp=max(1, maxhp // 5) if tired else maxhp)
            g.cmd(f"write16 {g.a(VAR_RESULT_ADDR)} 99")
            faced = t.face_follower()
            g.cmd("press A 4", "wait 40")
            started = not g.field_ready()
            line = struct.unpack("<H", bytes.fromhex(g.cmd(f"read {g.a(VAR_RESULT_ADDR)} 2")[0].replace(" ", "")))[0]
            nick = bytes.fromhex(g.cmd(f"read {g.a('gStringVar1')} 9")[0].replace(" ", ""))
            t.shot(f"talk_{name}.png")
            back = g.wait_field(press="A", max_steps=60)
            before, pbefore = t.follower_pos(), t.pos()
            # walk away from it (Up: it's behind, below): it must come along. (Walking into it would swap places
            # and land it back on the same tile.)
            g.cmd("press Up 8", "wait 30", "press Up 8", "wait 40")
            after, pafter = t.follower_pos(), t.pos()
            t.shot(f"talk_{name}_after.png")
            # the player went up and the follower came along behind, in line, at most two tiles back (after a swap it
            # trails a tile further until the next step, as it does anywhere)
            followed = pafter[1] < pbefore[1] and after != before and after[0] == pafter[0]                 and 1 <= after[1] - pafter[1] <= 2
            t.record(f"follower talk: {name}", faced and started and line == want and nick == BULBASAUR_NAME and back
                     and followed,
                     f"faced {faced}, script {started}, line {line} (want {want}), name {nick.hex()}, field back {back}, "
                     f"player {pbefore} -> {pafter}, follower {before} -> {after}")
    except RuntimeError as e:
        t.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in t.results if not r[1]]
    print(f"{len(t.results) - len(failed)}/{len(t.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(t.out, "follower_talk.txt"), "w") as f:
        for check, ok, detail in t.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
