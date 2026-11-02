"""Save-safety suite for Gunk's LeafGreen.

Usage: py -3 emu/suite/suite.py <rom.gba> <rom.elf> [test ...]
Tests: cycles crash torn mixed damaged (default: all). Results go to emu/suite/out/<rom name>/.

The oracle for every power-cut case: after Continue, the game must be in the field, its gSaveCounter must be
the old or the new save's, and every sector of the slot it loaded must carry that counter (no mix of saves).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import FLASH_SIZE, SECTOR, SLOT_SECTORS, Game, footers  # noqa: E402

ERASED = b"\xff" * FLASH_SIZE


def slot_of(counter):
    return counter % 2  # 0 = sectors 0-13, 1 = sectors 14-27


def check_loaded(game, allowed, label):
    """The oracle. Returns (ok, detail)."""
    counter = game.save_counter()
    flash = game.flash()
    slot = slot_of(counter)
    rows = footers(flash)[slot * SLOT_SECTORS:(slot + 1) * SLOT_SECTORS]
    mixed = sorted({cnt for (_, _, cnt, _, _) in rows})
    ok = counter in allowed and mixed == [counter]
    return ok, f"{label}: loaded counter {counter} (allowed {sorted(allowed)}), slot {slot + 1} sector counters {mixed}"


class Suite:
    def __init__(self, rom, elf):
        self.game = Game(rom, elf)
        self.out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out",
                                os.path.splitext(os.path.basename(rom))[0])
        os.makedirs(self.out, exist_ok=True)
        self.results = []

    def path(self, name):
        return os.path.join(self.out, name).replace("\\", "/")

    def record(self, test, ok, detail):
        self.results.append((test, ok, detail))
        print(("PASS " if ok else "FAIL ") + test + ": " + detail, flush=True)

    # --- setup ---
    def fresh(self):
        """Power on with an erased flash and play the intro to the bedroom (savestate start.state)."""
        g = self.game
        g.start()
        g.set_flash(ERASED)
        g.reboot()
        for _ in range(80):
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_MainMenu"):
                break
            g.cmd("press Start 4", "wait 30")
        # NEW GAME, the controls guide, Oak's speech, default names: A all the way
        if not g.wait_field(press="A", max_steps=1500, settle=5):
            raise RuntimeError("intro never reached the field")
        g.cmd("wait 60", f"save {self.path('start.state')}", f"shot {self.path('start.png')}")

    def base_saves(self):
        """Two good saves (counter 1 in slot 2, counter 2 in slot 1) then a savestate just before the third."""
        g = self.game
        g.cmd(f"load {self.path('start.state')}")
        g.set_flash(ERASED)
        for _ in range(2):
            g.save()
            g.cmd("press Right 8", "wait 30")  # move a step so the saves differ
        self.f2 = g.flash()
        g.cmd(f"save {self.path('pre3.state')}")
        self.save3_frames = g.save()
        self.f3 = g.flash()

    # --- tests ---
    def test_cycles(self, n=4):
        g = self.game
        g.cmd(f"load {self.path('start.state')}")
        g.set_flash(ERASED)
        for i in range(1, n + 1):
            g.save()
            g.reboot()
            status = g.boot_continue()
            ok, detail = check_loaded(g, {i}, f"cycle {i}")
            self.record("cycles", ok and status == 1, detail + f", status {status}")
            g.cmd("press Right 8", "wait 30")

    def test_crash(self, points=12):
        g = self.game
        span = self.save3_frames
        for j in range(points):
            k = 1 + j * max(1, span) // points
            g.cmd(f"load {self.path('pre3.state')}")
            g.set_flash(self.f2)
            g.save(crash_after=k)
            g.boot_continue()
            ok, detail = check_loaded(g, {2, 3}, f"power cut {k}/{span} frames into the write")
            self.record("crash", ok, detail)

    def test_torn(self):
        """Synthetic torn writes: the first k sectors (in write order, by id) of save 3 over the flash after save 2."""
        g = self.game
        slot = slot_of(3)
        new_rows = footers(self.f3)[slot * SLOT_SECTORS:(slot + 1) * SLOT_SECTORS]
        order = [s for (s, sid, _, _, _) in sorted(new_rows, key=lambda r: r[1])]
        for k in range(0, SLOT_SECTORS + 1):
            img = bytearray(self.f2)
            for s in order[:k]:
                img[s * SECTOR:(s + 1) * SECTOR] = self.f3[s * SECTOR:(s + 1) * SECTOR]
            g.set_flash(bytes(img))
            g.reboot()
            g.boot_continue()
            want = {3} if k == SLOT_SECTORS else {2}
            ok, detail = check_loaded(g, want, f"{k}/{SLOT_SECTORS} sectors of the new save written")
            self.record("torn", ok, detail)

    def test_mixed(self):
        """A slot with all 14 sectors present and valid, but the first 7 (by position) from the save two before.
        A sequential power cut can't make this (sectors rotate, so a torn slot always lacks one), but vanilla
        would load it as the newest save; Gunk's must take the other slot."""
        g = self.game
        slot = slot_of(3)
        old_by_id = {sid: s for (s, sid, _, _, _) in footers(self.f2)[slot * SLOT_SECTORS:(slot + 1) * SLOT_SECTORS]}
        img = bytearray(self.f3)
        for (s, sid, _, _, _) in footers(self.f3)[slot * SLOT_SECTORS:slot * SLOT_SECTORS + 7]:
            o = old_by_id[sid]
            img[s * SECTOR:(s + 1) * SECTOR] = self.f2[o * SECTOR:(o + 1) * SECTOR]
        g.set_flash(bytes(img))
        g.reboot()
        g.boot_continue()
        ok, detail = check_loaded(g, {2}, "slot with every sector, half from an older save")
        self.record("mixed", ok, detail)

    def test_damaged(self):
        g = self.game
        for label, slots, want in (("newest slot damaged", [slot_of(3)], {2}),
                                   ("older slot damaged", [slot_of(2)], {3})):
            img = bytearray(self.f3)
            for slot in slots:
                s = slot * SLOT_SECTORS + 3
                img[s * SECTOR + 0x100] ^= 0xFF  # one data byte: that sector's checksum fails
            g.set_flash(bytes(img))
            g.reboot()
            g.boot_continue()
            ok, detail = check_loaded(g, want, label)
            self.record("damaged", ok, detail)
        # both slots damaged: no save loads; the game must still boot to its main menu
        img = bytearray(self.f3)
        for slot in (0, 1):
            img[(slot * SLOT_SECTORS + 3) * SECTOR + 0x100] ^= 0xFF
        g.set_flash(bytes(img))
        g.reboot()
        for _ in range(60):
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_MainMenu"):
                break
            g.cmd("press Start 4", "wait 30")
        g.cmd("wait 120", f"shot {self.path('both_damaged.png')}")
        status = g.u8(g.a("gSaveFileStatus"))
        alive = int(g.cmd(f"alive {g.a('gMain') + 0x24} 60")[0].split()[1])
        self.record("damaged", status != 1 and alive > 0,
                    f"both slots damaged: save status {status}, main loop alive ({alive} frames)")


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    tests = sys.argv[3:] or ["cycles", "crash", "torn", "mixed", "damaged"]
    t0 = time.time()
    s = Suite(rom, elf)
    try:
        s.fresh()
        if "cycles" in tests:
            s.test_cycles()
        if any(t in tests for t in ("crash", "torn", "mixed", "damaged")):
            s.base_saves()
            print(f"save 3 took {s.save3_frames} frames", flush=True)
        for t in ("crash", "torn", "mixed", "damaged"):
            if t in tests:
                getattr(s, "test_" + t)()
    finally:
        import emu
        emu.stop()
    failed = [r for r in s.results if not r[1]]
    print(f"{len(s.results) - len(failed)}/{len(s.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(s.out, "results.txt"), "w") as f:
        for test, ok, detail in s.results:
            f.write(("PASS " if ok else "FAIL ") + test + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
