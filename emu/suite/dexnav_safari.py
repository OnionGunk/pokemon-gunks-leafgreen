"""The DexNav refuses the Safari Zone: py -3 emu/suite/dexnav_safari.py <rom.gba> <rom.elf>

The Safari Zone's Pokemon are caught with Safari Balls only. A DexNav battle there would be a normal battle with
normal balls, and its catches illegal (a Safari Zone met location with any ball), so the DexNav refuses it
at the item (src/item_use.c, FieldUseFunc_DexNav: Oak's "This isn't the time to use that!", as for other items in
the Safari Zone; the Bag and SELECT both use it), and again in src/gunk_dexnav.c (Gunk_DexNavPrepareList,
Gunk_DexNavStartSearch, Gunk_DexNavTryStartBattle) should anything else start it. In the Safari Zone's center,
standing still:
- in Safari mode (FLAG_SYS_SAFARI_MODE, with steps left), SELECT (the registered DexNav) gets Oak's refusal, the
  DexNav's script never runs (Gunk_DexNavPrepareList never called), the screen never opens and no search starts;
- the control: the same spot out of Safari mode, the screen opens with the area's Pokemon.
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
STAND = (26, 29)  # just inside the entrance
FLAG_SYS_SAFARI_MODE = 0x800
SPECIES_NIDORAN_F = 29  # one of the center's grass Pokemon, seen so the screen has something to show


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
        t.new_game(mons=[(SPECIES["PIKACHU"], 50)], items=[(ITEM["DEXNAV"], 1)],
                   flags=[FLAG_SYS_POKEMON_GET, FLAG_SYS_POKEDEX_GET], name="safari")
        t.warp(*MAP_SAFARI_ZONE_CENTER, *STAND, name="safari_center")
        g.wait_field(press="B", max_steps=60)
        t.set_dex(SPECIES_NIDORAN_F, False)
        g.cmd(f"write16 {t.sb1() + SB1_REGISTERED_ITEM} {ITEM['DEXNAV']}")
        # Safari mode, as the entrance sets it (set after the warp: Continue would end it), with steps left
        t.set_flag(FLAG_SYS_SAFARI_MODE)
        g.cmd(f"write16 {g.a('gSafariZoneStepCounter')} 500")

        t.watch()
        g.cmd("press Select 4")
        opened = False
        for _ in range(40):
            g.cmd("wait 6")
            if t.callback2() == g.a("CB2_DexNavScreen"):
                opened = True
        t.shot("safari_refused.png")
        refused, ran = t.calls()
        search = t.search()
        g.wait_field(press="B", max_steps=30)
        t.record("in Safari mode the DexNav refuses at the item (Oak's line), its script never runs",
                 refused == 1 and ran == 0 and not opened and not search["active"] and t.flag(FLAG_SYS_SAFARI_MODE),
                 f"refusals {refused}, DexNav script runs {ran}, screen opened {opened}, "
                 f"search active {search['active']}, player {t.pos()}")

        # the control: out of Safari mode, the same spot lists the center's Pokemon
        t.clear_flag(FLAG_SYS_SAFARI_MODE)
        screen = t.open_screen("safari_control.png")
        count = screen["count"] if screen else 0
        refused, ran = t.calls()
        g.cmd("press B 4")
        t.back_in_field()
        t.record("the control: out of Safari mode the screen opens with the area's Pokemon",
                 bool(screen) and count > 0 and ran >= 1, f"screen {bool(screen)}, {count} Pokemon listed, "
                 f"DexNav script runs {ran}")
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
