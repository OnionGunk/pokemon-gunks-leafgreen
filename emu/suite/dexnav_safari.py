"""DexNav and the Safari Zone: py -3 emu/suite/dexnav_safari.py <rom.gba> <rom.elf>

A DexNav battle in the Safari Zone would be an ordinary wild battle with the player's own balls, a catch no real
game can make there (the Safari Zone's met location with another ball). The DexNav refuses at every step:
- the item: FieldUseFunc_DexNav (src/item_use.c) gives Oak's "This isn't the time to use that!", as for other
  items in the Safari Zone (the Bag and SELECT both use it), so the DexNav's script never runs and no screen or
  search starts. Gunk_DexNavPrepareList and Gunk_DexNavStartSearch refuse it again, should anything else start it;
- a search already running (written into sSearch for this check, on the tile ahead) is ended instead of battled
  when the player steps onto it (Gunk_DexNavTryStartBattle checks GetSafariZoneFlag);
- the control: out of Safari mode, the same spot opens the screen with the area's Pokemon.
Every wait is bounded. Results: emu/suite/out/<rom>/features/dexnav_safari.txt.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dexnav_screen import Screen  # noqa: E402
from features import FLAG_SYS_POKEDEX_GET, FLAG_SYS_POKEMON_GET, ITEM, SB1_REGISTERED_ITEM, SPECIES  # noqa: E402

MAP_SAFARI_ZONE_CENTER = (1, 63)
INSIDE = (26, 29)  # just inside the entrance
FLAG_SYS_SAFARI_MODE = 0x800
FLAG_GUNK_ENDLESS_REPEL_ON = 0x4A7
MAP_OFFSET = 7  # sSearch keeps the map's own coordinates, which start 7 tiles in
SPECIES_VENONAT = 48  # in the Safari Zone center's grass in both games
MAX_SPRITES = 64


class Safari(Screen):
    def watch(self):
        """Count calls to the item's refusal and to the DexNav script's first special from now."""
        g = self.g
        g.cmd("lua NT = 0 PL = 0 local reg = event.on_bus_exec or event.onmemoryexecute "
              f"reg(function() NT = NT + 1 end, {g.a('PrintNotTheTimeToUseThat') & ~1}, 'gunk_nt') "
              f"reg(function() PL = PL + 1 end, {g.a('Gunk_DexNavPrepareList') & ~1}, 'gunk_pl') return 1")

    def calls(self):
        nt, pl = self.g.cmd("lua return NT .. ',' .. PL")[0][4:].split(",")
        return int(nt), int(pl)


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    t = Safari(rom, elf)
    g = t.g
    t0 = time.time()
    import emu
    try:
        t.new_game(mons=[(SPECIES["PIKACHU"], 100)], items=[(ITEM["DEXNAV"], 1)],
                   flags=[FLAG_SYS_POKEMON_GET, FLAG_SYS_POKEDEX_GET, FLAG_GUNK_ENDLESS_REPEL_ON], name="safari")
        t.warp(*MAP_SAFARI_ZONE_CENTER, *INSIDE, name="safari_center")
        g.wait_field(press="B", max_steps=60)
        # Safari mode as the entrance sets it, with steps left (after the warp: Continue starts out of Safari mode)
        t.set_flag(FLAG_SYS_SAFARI_MODE)
        g.cmd(f"write16 {g.a('gSafariZoneStepCounter')} 500")
        t.seen_all()
        g.cmd(f"write16 {t.sb1() + SB1_REGISTERED_ITEM} {ITEM['DEXNAV']}")

        # SELECT: Oak's refusal, the DexNav's script never runs, no screen, no search
        t.watch()
        g.cmd("press Select 4")
        opened = False
        for _ in range(30):
            g.cmd("wait 6")
            if t.callback2() == g.a("CB2_DexNavScreen"):
                opened = True
        t.shot("dexnav_safari_refused.png")
        refused, ran = t.calls()
        back = g.wait_field(press="B", max_steps=40)
        search = g.a("sSearch")
        active = g.u8(search + 11)
        t.record("SELECT in the Safari Zone: Oak's refusal, no DexNav script, screen or search",
                 refused == 1 and ran == 0 and not opened and active == 0 and back,
                 f"refusals {refused}, DexNav script runs {ran}, screen opened {opened}, search active {active}, "
                 f"field {back}")

        # a search on the tile ahead (as if one had started), then a step onto it: ended, no battle. The Endless
        # Repel goes off first: with it, a Lv. 100 lead keeps the search's Pokemon away before the Safari check
        # is reached. A DexNav battle sets sSearch.inBattle; a random Safari encounter doesn't
        t.clear_flag(FLAG_GUNK_ENDLESS_REPEL_ON)
        x, y = t.pos()
        g.cmd(f"write16 {search} {SPECIES_VENONAT}", f"write16 {search + 2} {x + MAP_OFFSET}",
              f"write16 {search + 4} {y - 1 + MAP_OFFSET}", f"write8 {search + 6} {MAP_SAFARI_ZONE_CENTER[0]}",
              f"write8 {search + 7} {MAP_SAFARI_ZONE_CENTER[1]}", f"write16 {search + 8} 600",
              f"write8 {search + 10} {MAX_SPRITES}", f"write8 {search + 12} 0", f"write8 {search + 14} 0",
              f"write8 {search + 11} 1")
        for _ in range(4):
            if t.pos() == (x, y - 1):
                break
            g.cmd("press Up 8", "wait 10")
        dexnav_battle = False
        for _ in range(20):
            g.cmd("wait 10")
            dexnav_battle = dexnav_battle or g.u8(search + 12) == 1
        t.record("a search running in the Safari Zone ends instead of battling", t.pos() == (x, y - 1)
                 and not dexnav_battle and g.u8(search + 11) == 0,
                 f"stepped to {t.pos()} (patch {(x, y - 1)}), DexNav battle {dexnav_battle}, "
                 f"search active {g.u8(search + 11)}")
        g.wait_field(press="B", max_steps=40)  # a random Safari encounter on that step: run from it

        # the control: out of Safari mode, the same map lists the center's Pokemon
        t.clear_flag(FLAG_SYS_SAFARI_MODE)
        screen = t.open_screen("dexnav_safari_control.png")
        count = screen["count"] if screen else 0
        refused, ran = t.calls()
        g.cmd("press B 4")
        t.back_in_field()
        t.record("the control: out of Safari mode the screen opens with the area's Pokemon",
                 bool(screen) and count > 0 and ran >= 1,
                 f"screen {bool(screen)}, {count} Pokemon listed, DexNav script runs {ran}")
    except RuntimeError as e:
        t.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [r for r in t.results if not r[1]]
    print(f"{len(t.results) - len(failed)}/{len(t.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(t.out, "dexnav_safari.txt"), "w") as f:
        for check, ok, detail in t.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
