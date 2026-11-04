"""The follower in a room whose objects fill every slot: py -3 emu/suite/follower_full_slots.py <rom.gba> <rom.elf>

Lorelei's house (Four Island) shows 15 objects at once (Lorelei and her dolls), so with the player all 16 object
event slots are taken. The follower spawns after the map's own objects, so it must be the one left out: every doll
is there, the game doesn't crash or overflow, and the follower is back as soon as the player walks out.
Every wait is bounded. Results: emu/suite/out/<rom>/features/follower_full_slots.txt.
"""
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import FLAG_SYS_POKEMON_GET, SPECIES, Features  # noqa: E402

MAP_LORELEIS_HOUSE = (35, 4)
HOUSE_OBJECTS = 15
# FLAG_HIDE_LORELEI_IN_HER_HOUSE and FLAG_HIDE_LORELEI(S)_HOUSE_*_DOLL (include/constants/flags.h)
HOUSE_HIDE_FLAGS = [0x08C] + list(range(0x0A5, 0x0AD))
LOCALID_FOLLOWER = 254


class Slots(Features):
    def objects(self):
        """(localId, mapNum, mapGroup) of every active object event."""
        objs = self.g.a("gObjectEvents")
        out = []
        for i in range(16):
            raw = bytes.fromhex(self.g.cmd(f"read {objs + i * 0x24} 0x14")[0].replace(" ", ""))
            if raw[0] & 1:
                out.append((raw[8], raw[9], raw[10]))
        return out

    def overworld(self):
        return (self.g.u32(self.g.a("gMain") + 4) & ~1) == self.g.a("CB2_Overworld")


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    t = Slots(rom, elf)
    g = t.g
    t0 = time.time()
    import emu
    try:
        t.new_game(mons=[(SPECIES["BULBASAUR"], 10)], flags=[FLAG_SYS_POKEMON_GET], name="slots")
        # Lorelei home and every doll out (the dolls appear as the player catches each species)
        for flag in HOUSE_HIDE_FLAGS:
            t.clear_flag(flag)
        t.warp(*MAP_LORELEIS_HOUSE, 4, 6, name="slots_house")
        g.wait_field(press="A", max_steps=120)
        objs = t.objects()
        house = [o for o in objs if o[0] not in (255, LOCALID_FOLLOWER)]
        t.shot("slots_house_in.png")
        t.record("all of the house's objects spawn", len(house) == HOUSE_OBJECTS and len(objs) == 16,
                 f"{len(objs)} active, {len(house)} house objects: {house}")
        t.record("the follower is the one left out", t.follower_pos() is None, f"follower {t.follower_pos()}")
        # walk about, open and close the menu: the follower keeps trying to spawn and must never take a slot
        for d in ("Right", "Right", "Left", "Left", "Up", "Down"):
            g.cmd(f"press {d} 8", "wait 20")
        g.cmd("press Start 4", "wait 30", "press B 4", "wait 30")
        ok = g.wait_field(press="B", max_steps=60) and t.overworld()
        objs2 = t.objects()
        t.record("walking and the menu in the full room", ok and len(objs2) == 16 and t.follower_pos() is None,
                 f"field {ok}, {len(objs2)} active, follower {t.follower_pos()}")
        # out the door (4, 7): the follower is back on Four Island
        g.cmd("press Down 8", "wait 20", "press Down 8", "wait 120")
        g.wait_field(press="B", max_steps=120)
        g.cmd("press Down 8", "wait 30", "press Down 8", "wait 40")
        out = t.follower_pos()
        mg, mn = g.u8(t.sb1() + 4), g.u8(t.sb1() + 5)
        t.shot("slots_outside.png")
        t.record("the follower is back outside", (mg, mn) != MAP_LORELEIS_HOUSE and out is not None and t.overworld(),
                 f"map {mg}.{mn}, follower {out}")
    except RuntimeError as e:
        t.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in t.results if not r[1]]
    print(f"{len(t.results) - len(failed)}/{len(t.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(t.out, "follower_full_slots.txt"), "w") as f:
        for check, ok, detail in t.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
