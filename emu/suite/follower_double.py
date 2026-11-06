"""The follower in a double battle: py -3 emu/suite/follower_double.py <rom.gba> <rom.elf>

Victory Road 3F's Cool Couple, Ray and Tyra (a trainer double battle, sight 1, facing down), with the follower out
and the party's lead walking behind the player: the player walks up into their sight, the couple spot them, the
battle is a double one (BATTLE_TYPE_DOUBLE), it's won by pressing A (two level-100 Mewtwo), and the game is back on
the field with the couple beaten and the follower out beside the player. (Platinum froze in double battles with the
follower in the lead.) Every wait is bounded. Results: emu/suite/out/<rom>/features/follower_double.txt.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import FLAG_SYS_POKEMON_GET, Features  # noqa: E402

SPECIES_MEWTWO = 150
MAP_VICTORY_ROAD_3F = (1, 41)
COUPLE = (38, 13)  # Ray; Tyra stands at (39, 13). Both face down with a sight of 1
START = (38, 16)
TRAINER_COOL_COUPLE_RAY_TYRA = 485
TRAINER_FLAGS_START = 0x500
BATTLE_TYPE_DOUBLE = 1 << 0
BATTLE_TYPE_TRAINER = 1 << 3


class Double(Features):
    def battle_flags(self):
        return self.g.u32(self.g.a("gBattleTypeFlags"))


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    t = Double(rom, elf)
    g = t.g
    t0 = time.time()
    import emu
    try:
        t.new_game(mons=[(SPECIES_MEWTWO, 100), (SPECIES_MEWTWO, 100)], flags=[FLAG_SYS_POKEMON_GET], name="double")
        t.warp(*MAP_VICTORY_ROAD_3F, *START, name="double_warp")
        g.wait_field(press="B", max_steps=60)
        g.cmd("press Down 4", "wait 20", "press Up 4", "wait 20")  # a step's worth of turning: the follower spawns
        before = t.follower_pos()
        t.shot("double_before.png")
        t.record("the follower is out before the battle", before is not None, f"player {t.pos()}, follower {before}")

        # up into the couple's sight: they walk over and the battle starts
        for _ in range(4):
            if t.in_battle():
                break
            g.cmd("press Up 16", "wait 20")
        for _ in range(60):
            if t.in_battle():
                break
            g.cmd("press A 4", "wait 20")
        started = t.in_battle()
        g.cmd("wait 120")
        flags = t.battle_flags()
        t.shot("double_battle.png")
        t.record("a trainer double battle with the follower's Pokemon in the lead",
                 started and flags & BATTLE_TYPE_DOUBLE and flags & BATTLE_TYPE_TRAINER,
                 f"battle {started}, gBattleTypeFlags {flags:#x}, player {t.pos()}")

        # win by pressing A (each Mewtwo's first move on the first target), then through the couple's lines
        for _ in range(600):
            if not t.in_battle():
                break
            g.cmd("press A 4", "wait 16")
        back = g.wait_field(press="A", max_steps=60)
        g.cmd("press Down 16", "wait 30")  # a step: the follower catches up
        after, pos = t.follower_pos(), t.pos()
        beaten = t.flag(TRAINER_FLAGS_START + TRAINER_COOL_COUPLE_RAY_TYRA)
        t.shot("double_after.png")
        t.record("back on the field, the couple beaten, the follower out beside the player",
                 back and beaten and after is not None and abs(after[0] - pos[0]) + abs(after[1] - pos[1]) <= 2,
                 f"field {back}, beaten {beaten}, player {pos}, follower {after}")
    except RuntimeError as e:
        t.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in t.results if not r[1]]
    print(f"{len(t.results) - len(failed)}/{len(t.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(t.out, "follower_double.txt"), "w") as f:
        for check, ok, detail in t.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
