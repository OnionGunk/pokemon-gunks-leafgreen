"""Quick Run (R) and Quick Ball (L) on every way back to the action menu: py -3 emu/suite/quickball_turns.py <rom.gba> <rom.elf>

Gunk's Platinum had both keys working only the first time the action menu opened. Here, in wild battles on
Route 1 (a Lv. 5 Pikachu whose first move is Growl, so turns pass without ending the battle):
- turn 2: FIGHT, Growl, then at the next action menu the widget shows and L throws (or R runs);
- FIGHT then B back to the action menu: the widget shows and L throws (R runs);
- BAG then B back: the same.
Results: emu/suite/out/<rom>/features/quickball_turns.txt.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dexnav_screen import Screen  # noqa: E402
from features import FLAG_SYS_POKEMON_GET, MAP_ROUTE1, SPECIES  # noqa: E402
from quickball import ITEM_POKE_BALL, QuickBall  # noqa: E402

MOVE_GROWL = 45


class Turns(QuickBall):
    def growl_turn(self):
        """FIGHT, the first move (Growl), then B through the turn to the next action menu."""
        self.g.cmd("press A 4", "wait 30", "press A 4", "wait 30")
        return self.wait_action_menu(max_steps=120)

    def fight_back(self):
        self.g.cmd("press A 4", "wait 30", "press B 4", "wait 40")
        return self.wait_action_menu()

    def bag_back(self):
        self.g.cmd("press Right 4", "wait 10", "press A 4", "wait 90", "press B 4", "wait 90")
        self.g.cmd("press Left 4", "wait 10")  # the cursor back on FIGHT
        return self.wait_action_menu()

    def throw(self, label):
        before = self.balls(ITEM_POKE_BALL)
        shown, _ = self.widget()
        self.g.cmd("press L 2", "wait 2", "wait 60")
        after = self.balls(ITEM_POKE_BALL)
        self.record(f"L after {label}", shown and after == before - 1,
                    f"widget {shown}, Poke Balls {before} -> {after}")
        self.back_to_field_after_battle()
        if self.in_battle():  # not caught: run
            for _ in range(6):
                self.wait_action_menu()
                self.g.cmd("press R 4", "wait 20")
                if self.back_to_field_after_battle(max_steps=30):
                    break

    def run(self, label):
        self.g.cmd("press R 4", "wait 20")
        ran = self.back_to_field_after_battle(max_steps=60)
        self.record(f"R after {label}", ran, f"back in the field {ran}")


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    t = Turns(rom, elf)
    t0 = time.time()
    import emu
    try:
        t.new_game(mons=[(SPECIES["PIKACHU"], 5)], items=[(ITEM_POKE_BALL, 30)], flags=[FLAG_SYS_POKEMON_GET],
                   name="quickball_turns")
        Screen.set_first_move(t, 0, MOVE_GROWL, 40)
        t.warp(*MAP_ROUTE1, 15, 6, name="quickball_turns_route1")
        for label, step in (("turn 1 (Growl)", Turns.growl_turn), ("FIGHT then B", Turns.fight_back),
                            ("BAG then B", Turns.bag_back)):
            for key in (Turns.throw, Turns.run):
                t.find_wild()
                ok = step(t)
                if not ok:
                    t.record(f"{key.__name__} after {label}", False, "no action menu after the step")
                    t.back_to_field_after_battle()
                    continue
                key(t, label)
    except RuntimeError as e:
        t.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in t.results if not r[1]]
    print(f"{len(t.results) - len(failed)}/{len(t.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(t.out, "quickball_turns.txt"), "w") as f:
        for check, ok, detail in t.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
