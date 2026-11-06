"""The follower through a scripted walk that ends in a warp's fade: py -3 emu/suite/follower_warp_scene.py <rom.gba> <rom.elf>

Platinum froze when a scripted walk ended during a screen effect. In FRLG every scripted walk is waited for before a
fade starts, so the nearest case is a walk straight into a warp: the Safari Zone entrance, coming back in early
(VAR_MAP_SCENE_FUCHSIA_CITY_SAFARI_ZONE_ENTRANCE 2) and answering NO to "leave early?". The attendant says good luck,
the player walks up a tile and the script warps to the Safari Zone's center (fade out, map load, fade in).
The follower goes back into its ball for the walk (a Poke Ball shown), the warp's fades run with it in its ball, the
game is back on the field in the Safari Zone, and the follower comes out (a ball again) and follows the player's first step.
Every wait is bounded. Results: emu/suite/out/<rom>/features/follower_warp_scene.txt.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import FLAG_SYS_POKEMON_GET, SPECIES, Features  # noqa: E402

MAP_SAFARI_ZONE_ENTRANCE = (11, 0)
MAP_SAFARI_ZONE_CENTER = (1, 63)
ARRIVAL = (4, 2)  # under the Safari Zone's door, where coming back from it puts the player
VAR_MAP_SCENE_FUCHSIA_CITY_SAFARI_ZONE_ENTRANCE = 0x406E


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    t = Features(rom, elf)
    g = t.g
    t0 = time.time()
    import emu
    try:
        t.new_game(mons=[(SPECIES["BULBASAUR"], 20)], flags=[FLAG_SYS_POKEMON_GET], name="warpscene")
        t.warp(*MAP_SAFARI_ZONE_ENTRANCE, *ARRIVAL, name="warpscene_entrance")
        g.cmd("press Down 2", "wait 20", "press Up 2", "wait 20")  # turning in place: the follower spawns
        # set after the warp (Continue clears it): the map's frame script starts the scene at once
        t.set_var(VAR_MAP_SCENE_FUCHSIA_CITY_SAFARI_ZONE_ENTRANCE, 2)
        t.watch_follower_ball()
        # "Leave early?" -> NO (B), then A through "Good luck!": the walk up and the warp follow by themselves
        gone = False
        for i in range(120):
            sb1 = t.sb1()
            if (g.u8(sb1 + 4), g.u8(sb1 + 5)) == MAP_SAFARI_ZONE_CENTER:
                break
            if t.follower_pos() is None and g.u8(g.a("sGlobalScriptContextStatus")) == 0:
                gone = True  # in its ball while the scene's script runs
            g.cmd("press B 4" if i < 6 else "press A 4", "wait 12")
        back = g.wait_field(press="A", max_steps=60)
        sb1 = t.sb1()
        where = (g.u8(sb1 + 4), g.u8(sb1 + 5))
        # the arrival is a one-tile gap in the fence: with no free tile beside the player, the follower waits on
        # the player's tile, hidden, until the first step (as at any spawn)
        g.cmd("wait 60", "press Up 16", "wait 40")
        after, pos = t.follower_pos(), t.pos()
        balls, frames = t.follower_balls()
        t.shot("warpscene_after.png")
        t.record("the scene's walk and warp end on the field in the Safari Zone", back and where == MAP_SAFARI_ZONE_CENTER,
                 f"field {back}, map {where}, player {pos}")
        t.record("the follower went back into its ball for the scene", gone and balls[:1] == ["back"],
                 f"in its ball during the script {gone}, balls {balls}")
        t.record("the follower is out beside the player after the warp",
                 after is not None and 1 <= abs(after[0] - pos[0]) + abs(after[1] - pos[1]) <= 2
                 and balls == ["back", "out"] and frames >= 24,
                 f"player {pos}, follower {after}, balls {balls}, {frames} ball frames")
    except RuntimeError as e:
        t.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in t.results if not r[1]]
    print(f"{len(t.results) - len(failed)}/{len(t.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(t.out, "follower_warp_scene.txt"), "w") as f:
        for check, ok, detail in t.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
