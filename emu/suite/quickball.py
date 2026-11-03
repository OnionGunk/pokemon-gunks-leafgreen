"""Quick Run and Quick Ball checks: py -3 emu/suite/quickball.py <rom.gba> <rom.elf> [pk3_out_dir]

On Route 1 (wild battles) with 10 Poke Balls and 5 Great Balls, and in Pewter Gym (a trainer battle):
  widget        a wild battle's action menu shows the widget, on the pocket's first ball
  cycle         L held + Right shows the Great Ball; releasing L throws nothing
  throw         L tapped throws the shown ball: one fewer in the bag, the last ball remembered (VAR_GUNK_LAST_BALL)
  catch         L until the Pokemon is caught: it joins the party in a Great Ball (written as a .pk3 for PKHeX)
  last ball     the next battle's widget starts on the Great Ball
  quick run     R in a wild battle runs: the field comes back
  help          L and R in the action menu don't open Help (the default button mode)
  L=A           with L=A, tapping L throws a ball and doesn't also choose FIGHT
  trainer       against Brock no widget, and R gets the "no running" refusal: still in the battle
  no balls      with no balls, no widget
Every wait is bounded and checks the main loop is still running (a stall fails the check instead of hanging).
Results: emu/suite/out/<rom>/features/quickball.txt.
"""
import os
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import FLAG_SYS_POKEMON_GET, MAP_ROUTE1, SPECIES, Features  # noqa: E402
from lib import NM  # noqa: E402

ITEM_POKE_BALL, ITEM_GREAT_BALL = 4, 3
SB1_BALLS, BALL_SLOTS = 0x430, 13
VAR_GUNK_LAST_BALL = 0x402B
SB2_BUTTON_MODE = 0x13
WINDOW_NONE = 0xFF


def icon_top_color(png):
    """The icon's upper half on a screenshot: "red" (a Poke Ball's) or "blue" (a Great Ball's), by its strongest
    channel over the pixels that aren't white, black or gray."""
    from PIL import Image
    im = Image.open(png).convert("RGB")
    reds = blues = 0
    for y in range(101, 110):
        for x in range(8, 25):
            r, g, b = im.getpixel((x, y))
            if max(r, g, b) - min(r, g, b) > 60:
                reds += r > b
                blues += b > r
    return "blue" if blues > reds else "red" if reds > blues else "none"


class QuickBall(Features):
    def __init__(self, rom, elf, pk3_dir=None):
        super().__init__(rom, elf)
        self.pk3_dir = pk3_dir
        nm = subprocess.run([NM, elf], capture_output=True, text=True, check=True).stdout.splitlines()
        funcs = {}
        for line in nm:
            parts = line.split()
            if len(parts) == 3:
                funcs.setdefault(parts[2], set()).add(int(parts[0], 16))
        self.choose_action = funcs["HandleInputChooseAction"]
        self.choose_move = funcs["HandleInputChooseMove"]

    def controller(self):
        return self.g.u32(self.g.a("gBattlerControllerFuncs")) & ~1

    def alive(self):
        return int(self.g.cmd(f"alive {self.g.a('gMain') + 0x24} 20")[0].split()[1]) > 0

    def wait_action_menu(self, max_steps=80):
        """B through battle text until the action menu (or the battle's end). Returns True at the action menu."""
        for i in range(max_steps):
            if self.controller() in self.choose_action:
                self.g.cmd("wait 20")
                return True
            if not self.in_battle():
                return False
            if i % 20 == 19 and not self.alive():
                raise RuntimeError("the game stopped while waiting for the action menu")
            self.g.cmd("press B 4", "wait 20")
        raise RuntimeError("no action menu (stalled)")

    def widget(self):
        return self.g.u8(self.g.a("sQuickBallWindowIdPlus1")) != 0, struct.unpack("<H", self.read(self.g.a("sQuickBall"), 2))[0]

    def read(self, addr, n):
        return bytes.fromhex(self.g.cmd(f"read {addr} {n}")[0].replace(" ", ""))

    def balls(self, item):
        return self.bag_count(item, SB1_BALLS, BALL_SLOTS)

    def find_wild(self, spot=(15, 6)):
        g = self.g
        self.walk_to(*spot)
        for i in range(600):
            if i and i % 150 == 0:
                g.cmd("press Down 8", "wait 10")
            g.cmd("press Left 8" if (i // 2) % 2 == 0 else "press Right 8", "wait 6")
            if self.in_battle():
                return self.wait_action_menu()
        raise RuntimeError("no wild encounter (stalled)")

    def back_to_field_after_battle(self, max_steps=120):
        for i in range(max_steps):
            if not self.in_battle() and self.g.field_ready():
                return True
            if i % 20 == 19 and not self.alive():
                raise RuntimeError("the game stopped after the battle")
            self.g.cmd("press B 4", "wait 20")
        return False


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    pk3 = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else None
    q = QuickBall(rom, elf, pk3)
    g = q.g
    t0 = time.time()
    import emu
    try:
        q.new_game(mons=[(SPECIES["PIKACHU"], 5)], items=[(ITEM_POKE_BALL, 10), (ITEM_GREAT_BALL, 5)],
                   flags=[FLAG_SYS_POKEMON_GET], name="quickball")
        q.warp(*MAP_ROUTE1, 15, 6, name="quickball_route1")
        q.find_wild()
        shown, ball = q.widget()
        q.shot("quickball_widget.png")
        q.record("quick ball widget", shown and ball == ITEM_POKE_BALL, f"shown {shown}, ball {ball}")

        # cycle: L and Right together (one press: the bridge releases every button after a press), then L lets go
        pokeballs = q.balls(ITEM_POKE_BALL)
        g.cmd("press L+Right 6", "wait 10")
        shown, ball = q.widget()
        q.shot("quickball_cycled.png")
        before = q.balls(ITEM_GREAT_BALL)
        still = q.controller() in q.choose_action
        top = icon_top_color(q.path("quickball_cycled.png"))
        q.record("quick ball cycle", ball == ITEM_GREAT_BALL and still and before == 5
                 and q.balls(ITEM_POKE_BALL) == pokeballs and top == "blue",
                 f"ball {ball}, icon top {top}, still in the action menu {still}, Great Balls {before}, Poke Balls "
                 f"{pokeballs} -> {q.balls(ITEM_POKE_BALL)}")

        # throw: L tapped (pressed and released); Help (default button mode) must stay closed
        party = g.u8(g.a("gPlayerPartyCount"))
        g.cmd("press L 2", "wait 2")
        help_open = g.u8(g.a("sVideoState") + 0x15)
        g.cmd("wait 30")
        thrown = q.balls(ITEM_GREAT_BALL)
        q.record("quick ball throw", thrown == 4 and q.var(VAR_GUNK_LAST_BALL) == ITEM_GREAT_BALL,
                 f"Great Balls {before} -> {thrown}, last ball {q.var(VAR_GUNK_LAST_BALL)}")
        q.record("help stays closed", help_open == 0, f"help state {help_open}")
        caught = False
        for _ in range(4):
            if not q.wait_action_menu():
                break
            g.cmd("press L 4", "wait 2")
        q.back_to_field_after_battle()
        caught = g.u8(g.a("gPlayerPartyCount")) == party + 1
        if caught and pk3:
            os.makedirs(pk3, exist_ok=True)
            raw = q.read(g.a("gPlayerParty") + party * 100, 100)
            open(os.path.join(pk3, "quickball_catch.pk3"), "wb").write(raw)
        q.record("quick ball catch", caught, f"party {party} -> {g.u8(g.a('gPlayerPartyCount'))}, "
                 f"Great Balls {q.balls(ITEM_GREAT_BALL)}")

        q.find_wild()
        shown, ball = q.widget()
        q.record("quick ball remembers the last ball", shown and ball == ITEM_GREAT_BALL, f"ball {ball}")
        ran = False
        for _ in range(6):
            g.cmd("press R 4", "wait 20")
            if q.back_to_field_after_battle(max_steps=30):
                ran = True
                break
            q.wait_action_menu()
        q.record("quick run", ran, f"back in the field {ran}")

        g.cmd(f"write8 {q.sb2() + SB2_BUTTON_MODE} 2")  # L=A
        q.find_wild()
        before = q.balls(ITEM_GREAT_BALL)
        g.cmd("press L 4", "wait 4")
        move_menu = q.controller() in q.choose_move
        g.cmd("wait 30")
        q.record("quick ball with L=A", q.balls(ITEM_GREAT_BALL) == before - 1 and not move_menu,
                 f"Great Balls {before} -> {q.balls(ITEM_GREAT_BALL)}, move menu opened {move_menu}")
        q.back_to_field_after_battle()
        if q.in_battle():
            for _ in range(6):
                q.wait_action_menu()
                g.cmd("press R 4", "wait 20")
                if q.back_to_field_after_battle(max_steps=30):
                    break
        g.cmd(f"write8 {q.sb2() + SB2_BUTTON_MODE} 0")

        # a trainer battle: Brock
        q.new_game(mons=[(SPECIES["PIKACHU"], 60)], items=[(ITEM_POKE_BALL, 10)], flags=[FLAG_SYS_POKEMON_GET],
                   name="quickball_brock")
        q.warp(6, 2, 6, 6, name="quickball_gym")
        g.cmd("press Up 2", "wait 10", "press A 4", "wait 30")
        for _ in range(60):  # Brock's speech before the battle
            if q.in_battle():
                break
            g.cmd("press A 4", "wait 20")
        if q.in_battle() and q.wait_action_menu(max_steps=150):
            shown, _ = q.widget()
            g.cmd("press R 4", "wait 120")
            still = q.in_battle()
            q.shot("quickball_trainer.png")
            q.record("trainer battle: no widget, R refused", not shown and still,
                     f"widget {shown}, still in the battle after R {still}")
        else:
            q.record("trainer battle: no widget, R refused", False, "Brock's battle never reached the action menu")

        q.new_game(mons=[(SPECIES["PIKACHU"], 5)], flags=[FLAG_SYS_POKEMON_GET], name="quickball_none")
        q.warp(*MAP_ROUTE1, 15, 6, name="quickball_none_route1")
        q.find_wild()
        shown, _ = q.widget()
        q.record("no balls: no widget", not shown, f"widget {shown}")
    except RuntimeError as e:
        q.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in q.results if not r[1]]
    print(f"{len(q.results) - len(failed)}/{len(q.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(q.out, "quickball.txt"), "w") as f:
        for check, ok, detail in q.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
