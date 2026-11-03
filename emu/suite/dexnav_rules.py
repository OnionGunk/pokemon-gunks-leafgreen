"""DexNav rules: py -3 emu/suite/dexnav_rules.py <rom.gba> <rom.elf>

On Route 1 (Pidgey and Rattata), each rule checked in the emulator:
  timeout     a search left alone ends after 10 seconds (600 field frames): the patch clears, the chain drops to 0,
              and "got away" is shown
  shake       the patch's rustle restarts twice a second (its animation back at its first command every 30 frames)
  chain kept  a random encounter of the chain's species keeps the chain
  chain lost  a random encounter of another species drops it to 0
  fled        running from a DexNav battle of the chain's species keeps the chain
Every wait is bounded. Results: emu/suite/out/<rom>/features/dexnav_rules.txt.
"""
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import SB1_GUNK_DEXNAV  # noqa: E402
from legality import PLACES, Catcher  # noqa: E402

SPECIES_PIDGEY = 16
SEARCH_FRAMES = 600
# struct DexNavSearch: species, x, y, mapGroup, mapNum, framesLeft, spriteId, active, inBattle, gotAwayPending
SEARCH_FRAMES_LEFT, SEARCH_SPRITE, SEARCH_ACTIVE = 8, 10, 11
SPRITE_ANIM_CMD = 43  # struct Sprite.animCmdIndex


class Rules(Catcher):
    def search(self):
        return self.read(self.g.a("sSearch"), 14)

    def chain(self):
        raw = self.read(self.sb1() + SB1_GUNK_DEXNAV + 386, 3)
        return raw[0] | raw[1] << 8, raw[2]

    def set_chain(self, species, count):
        sb1 = self.sb1()
        self.g.cmd(f"write16 {sb1 + SB1_GUNK_DEXNAV + 386} {species}", f"write8 {sb1 + SB1_GUNK_DEXNAV + 388} {count}")

    def run_away(self):
        """R (Quick Run) until the field is back."""
        g = self.g
        for _ in range(12):
            for _ in range(60):
                if g.u32(g.a("gBattlerControllerFuncs")) & ~1 in self.choose_action or not self.in_battle():
                    break
                g.cmd("press B 4", "wait 20")
            g.cmd("press R 4", "wait 30")
            for _ in range(30):
                if not self.in_battle() and g.field_ready():
                    return True
                g.cmd("press B 4", "wait 20")
        return False

    def random_battle(self):
        g = self.g
        for i in range(600):
            if i and i % 150 == 0:
                g.cmd("press Down 8", "wait 10")
            g.cmd("press Left 8" if (i // 2) % 2 == 0 else "press Right 8", "wait 6")
            if self.in_battle():
                g.cmd("wait 60")
                return struct.unpack_from("<H", self.decrypted(self.read(g.a("gEnemyParty"), 100)), 0)[0]
        raise RuntimeError("no wild encounter (stalled)")


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    r = Rules(rom, elf, os.path.join(HERE, "out", "dexnav_rules_pk3"))
    g = r.g
    t0 = time.time()
    import emu
    try:
        r.start(PLACES[0])
        # timeout and shake: a search, then the player stands still
        r.set_chain(SPECIES_PIDGEY, 5)
        species, x, y, active = r.dexnav_patch(0)
        s = r.search()
        sprite = g.a("gSprites") + s[SEARCH_SPRITE] * 0x44
        restarts, last = 0, None
        for _ in range(60):
            cmd = g.u8(sprite + SPRITE_ANIM_CMD)
            if last is not None and cmd < last:
                restarts += 1
            last = cmd
            g.cmd("wait 1")
        r.shot("dexnav_rules_patch.png")
        r.record("patch shakes twice a second", restarts == 2, f"rustle restarted {restarts} times in 60 frames")
        left0 = struct.unpack_from("<H", r.search(), SEARCH_FRAMES_LEFT)[0]
        start = g.frame()
        ended = None
        for _ in range(80):
            g.cmd("wait 10")
            if r.search()[SEARCH_ACTIVE] == 0:
                ended = g.frame() - start + (SEARCH_FRAMES - left0)
                break
        g.cmd("wait 20")
        message = not g.field_ready()
        r.shot("dexnav_rules_got_away.png")
        g.wait_field(press="A", max_steps=40)
        chain_species, chain = r.chain()
        r.record("search times out after 10 seconds", ended is not None and abs(ended - SEARCH_FRAMES) <= 12
                 and message and chain == 0,
                 f"ended after about {ended} frames, message {message}, chain {chain}")

        # random encounters: the chain's species keeps it, another species breaks it
        kept = lost = None
        for _ in range(12):
            if kept is not None and lost is not None:
                break
            r.set_chain(SPECIES_PIDGEY, 5)
            wild = r.random_battle()
            r.run_away()
            _, chain = r.chain()
            if wild == SPECIES_PIDGEY:
                kept = chain
            else:
                lost = (wild, chain)
        r.record("same-species encounter keeps the chain", kept == 5, f"chain after a Pidgey: {kept}")
        r.record("other-species encounter breaks the chain", lost is not None and lost[1] == 0,
                 f"chain after species {lost[0] if lost else None}: {lost[1] if lost else None}")

        # running from a DexNav battle of the chain's species keeps the chain
        r.set_chain(SPECIES_PIDGEY, 5)
        fled = None
        for _ in range(6):
            species, x, y, active = r.dexnav_patch(0)
            if not active:
                continue
            if species != SPECIES_PIDGEY:
                r.set_chain(species, 5)
            r.walk_to(x, y)
            g.cmd("wait 60")
            if r.in_battle():
                r.run_away()
                fled = (species, r.chain())
                break
        r.record("fleeing a DexNav battle keeps the chain", fled is not None and fled[1] == (fled[0], 5),
                 f"species {fled[0] if fled else None}, chain after fleeing {fled[1] if fled else None}")
    except RuntimeError as e:
        r.record("stall", False, str(e))
    finally:
        emu.stop()
    failed = [x for x in r.results if not x[1]]
    print(f"{len(r.results) - len(failed)}/{len(r.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(r.out, "dexnav_rules.txt"), "w") as f:
        for check, ok, detail in r.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
