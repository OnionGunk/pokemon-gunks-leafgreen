"""The release ROM itself: py -3 emu/suite/release_smoke.py <release.gba> <release.elf>

Every other test runs on a test build, whose new games start from the emulator test hook (src/gunk_test.c). The
release build (make leafgreen_release / firered_release) leaves the hook out, so this test plays it as a player
would, with nothing written to the game's memory:
- the header is Gunk's title with the retail game code, and the hook's symbols are not in the build;
- from power-on with an erased flash, the copyright screen and the Game Freak intro play untouched to the title
  screen;
- NEW GAME from the title: Oak's speech, the default names, to the bedroom with an empty party;
- a step, a save from the Start menu, a power cycle and CONTINUE: back in the same room on the same tile.
Every wait is bounded. Results: emu/suite/out/<rom>/features/release_smoke.txt.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import ERASED, Features  # noqa: E402

HOOK_SYMBOLS = ("gGunkTestMagic", "gGunkTestMons", "gGunkTestItems", "gGunkTestFlags", "Gunk_ApplyTestSetup")
INTRO = ("CB2_InitCopyrightScreenAfterBootup", "CB2_WaitFadeBeforeSetUpIntro", "CB2_SetUpIntro", "CB2_Intro")
TITLE = ("CB2_InitTitleScreen", "CB2_TitleScreenRun")
MAP_PLAYERS_HOUSE_2F = (4, 1)


class Smoke(Features):
    def cb2_name(self):
        cb2 = self.g.u32(self.g.a("gMain") + 4) & ~1
        return self.names.get(cb2, hex(cb2))

    def where(self):
        sb1 = self.sb1()
        return (self.g.u8(sb1 + 4), self.g.u8(sb1 + 5)), self.pos()


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    t = Smoke(rom, elf)
    g = t.g
    t.names = {}
    for name in INTRO + TITLE + ("CB2_MainMenu",):
        t.names[g.a(name) & ~1] = name
    t0 = time.time()
    import emu
    try:
        title = open(rom, "rb").read()[0xA0:0xB0]
        t.record("header: Gunk's title, the retail game code", title[:12].rstrip(b"\0") in (b"GUNK FR", b"GUNK LG")
                 and title[12:16] in (b"BPRE", b"BPGE"), repr(title))
        present = [s for s in HOOK_SYMBOLS if s in g.sym]
        t.record("no test hook in the build", not present, f"hook symbols present: {present or 'none'}")

        # power on with an erased flash and press nothing: the intro plays by itself to the title screen
        g.start()
        g.set_flash(ERASED)
        g.reboot()
        seen = []
        for _ in range(300):
            name = t.cb2_name()
            if not seen or seen[-1] != name:
                seen.append(name)
            if name == "CB2_TitleScreenRun":
                break
            g.cmd("wait 10")
        t.shot("release_smoke_title.png")
        intro = [n for n in seen if n in INTRO]
        t.record("the copyright screen and the intro play untouched to the title screen",
                 "CB2_Intro" in intro and seen[-1] == "CB2_TitleScreenRun", f"screens: {' > '.join(seen)}")

        # START, then NEW GAME (the only entry with an erased flash), Oak's speech with the default names
        for _ in range(40):
            if t.cb2_name() == "CB2_MainMenu":
                break
            g.cmd("press Start 4", "wait 30")
        if not g.wait_field(press="A", max_steps=1500, settle=5):
            raise RuntimeError("NEW GAME never reached the field")
        g.cmd("wait 30")
        room, pos = t.where()
        party = g.u8(g.a("gPlayerPartyCount"))
        t.shot("release_smoke_bedroom.png")
        t.record("NEW GAME: Oak's speech to the bedroom, an empty party", room == MAP_PLAYERS_HOUSE_2F and party == 0,
                 f"map {room}, player {pos}, party {party}")

        # a step, then save, power-cycle and CONTINUE
        g.cmd("press Left 16", "wait 30")
        saved_room, saved_pos = t.where()
        counter = g.save_counter()
        g.save()
        g.cmd("wait 60")
        g.wait_field(press="B", max_steps=60)
        saved = g.save_counter()
        g.reboot()
        status = g.boot_continue()
        g.cmd("wait 30")
        room, pos = t.where()
        t.shot("release_smoke_continue.png")
        t.record("save, power cycle, CONTINUE: the same room and tile",
                 saved > counter and status == 1 and (room, pos) == (saved_room, saved_pos),
                 f"save counter {counter} -> {saved}, save status {status}, saved at {saved_room} {saved_pos}, "
                 f"continued at {room} {pos}")
    except RuntimeError as e:
        t.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in t.results if not r[1]]
    print(f"{len(t.results) - len(failed)}/{len(t.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(t.out, "release_smoke.txt"), "w") as f:
        for check, ok, detail in t.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
