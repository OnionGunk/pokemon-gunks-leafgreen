"""Game-level helpers for the LeafGreen test suite: symbols from the build's ELF, field and menu navigation,
in-game saving, power cycles and flash (SRAM) images.

Flash layout (src/save.c): 32 sectors of 4 KB. Sectors 0-13 are save slot 1, 14-27 slot 2, 28-29 Hall of Fame,
30-31 Trainer Tower. Each sector ends in a footer: id u16 @0xFF4, checksum u16 @0xFF6, signature u32 @0xFF8
(0x08012025), counter u32 @0xFFC. A save writes the slot `counter % 2`, all 14 sectors, ids 0..13 in order.
"""
import json
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import emu  # noqa: E402

NM = r"C:\msys64\ucrt64\bin\arm-none-eabi-nm.exe"
SECTOR = 0x1000
SLOT_SECTORS = 14
SIGNATURE = 0x08012025
FLASH_SIZE = 0x20000


def symbols(elf):
    """name -> address for every symbol in the ELF (static ones too), cached next to it."""
    cache = elf + ".syms.json"
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(elf):
        return json.load(open(cache))
    out = subprocess.run([NM, elf], capture_output=True, text=True, check=True).stdout
    syms = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3:
            syms.setdefault(parts[2], int(parts[0], 16))
    json.dump(syms, open(cache, "w"))
    return syms


def footers(flash):
    """[(sector, id, counter, signature_ok, checksum_ok)] for sectors 0-27 of a flash image."""
    rows = []
    for s in range(2 * SLOT_SECTORS):
        b = flash[s * SECTOR:(s + 1) * SECTOR]
        sid, chk, sig, cnt = struct.unpack_from("<HHII", b, 0xFF4)
        rows.append((s, sid, cnt, sig == SIGNATURE, chk))
    return rows


class Game:
    def __init__(self, rom, elf):
        self.rom = rom
        self.sym = symbols(elf)

    # --- emulator plumbing ---
    def start(self):
        emu.start(self.rom)
        self.cmd("speed 6400")

    def cmd(self, *cmds, timeout=600):
        out = emu.run(list(cmds), timeout=timeout, echo=False)
        errors = [l for l in out if l.startswith("ERROR")]
        if errors:
            raise RuntimeError("; ".join(errors))
        return out[:-1]  # drop the "frame N" line

    def a(self, name):
        return self.sym[name]

    def u8(self, addr):
        return int(self.cmd(f"read {addr} 1")[0], 16)

    def u32(self, addr):
        b = bytes.fromhex(self.cmd(f"read {addr} 4")[0].replace(" ", ""))
        return struct.unpack("<I", b)[0]

    def frame(self):
        return int(emu.run(["wait 0"], echo=False)[-1].split()[1])

    def flash(self):
        path = os.path.join(emu.DIR, "flash.bin")
        self.cmd(f"dump SRAM 0 {FLASH_SIZE} {path}")
        return open(path, "rb").read()

    def set_flash(self, data):
        assert len(data) == FLASH_SIZE
        path = os.path.join(emu.DIR, "flash_in.bin")
        open(path, "wb").write(data)
        self.cmd(f"poke SRAM 0 {path}")

    # --- game state ---
    def field_ready(self):
        """The player can walk: overworld main loop, no script running, controls unlocked."""
        cb2 = self.u32(self.a("gMain") + 4)
        return (cb2 & ~1) == self.a("CB2_Overworld") and self.u8(self.a("sLockFieldControls")) == 0 \
            and self.u8(self.a("sGlobalScriptContextStatus")) != 0

    def wait_field(self, press="A", max_steps=400, settle=3):
        """Press <press> every 20 frames until the field has been ready for <settle> checks in a row."""
        ok = 0
        for _ in range(max_steps):
            if self.field_ready():
                ok += 1
                if ok >= settle:
                    return True
                self.cmd("wait 20")
            else:
                ok = 0
                self.cmd(f"press {press} 4" if press else "wait 4", "wait 16")
        return False

    def save_counter(self):
        return self.u32(self.a("gSaveCounter"))

    def open_save_dialog(self):
        """Start menu -> SAVE -> 'Would you like to save?' (stops with the yes/no box up)."""
        self.cmd("press Start 4", "wait 30")
        n = self.u8(self.a("sNumStartMenuItems"))
        order = bytes.fromhex(self.cmd(f"read {self.a('sStartMenuOrder')} {n}")[0].replace(" ", ""))
        target = order.index(self.STARTMENU_SAVE)
        for _ in range(16):
            pos = self.u8(self.a("sStartMenuCursorPos"))
            if pos == target:
                break
            self.cmd("press Down 4" if pos < target else "press Up 4", "wait 6")
        assert self.u8(self.a("sStartMenuCursorPos")) == target
        self.cmd("press A 4", "wait 60")

    STARTMENU_SAVE = 4  # enum StartMenuOption in src/start_menu.c

    def dialog_cb(self):
        return self.u32(self.a("sSaveDialogCB")) & ~1

    def save(self, crash_after=None, before_save=None):
        """Save through the Start menu. crash_after=N power-cycles N frames after the flash write starts
        (returns then, without waiting for the save to finish). before_save() runs with the yes/no box up, just
        before the save is confirmed (tests use it to edit what gets saved). Returns the frames the write took."""
        self.open_save_dialog()
        if before_save is not None:
            before_save()
        do_save = self.a("SaveDialogCB_DoSave")
        for _ in range(400):
            if self.dialog_cb() == do_save:
                break
            self.cmd("press A 4", "wait 10")
        else:
            raise RuntimeError("save dialog never reached DoSave")
        start = self.frame()
        if crash_after is not None:
            self.cmd(f"wait {crash_after}", "reboot")
            return None
        # DoSave returns after TrySavingData finishes; the dialog then moves on
        for _ in range(2000):
            if self.dialog_cb() != do_save:
                break
            self.cmd("wait 2")
        took = self.frame() - start
        if not self.wait_field(press="B"):
            raise RuntimeError("field did not come back after saving")
        return took

    def boot_continue(self):
        """From a power-on: skip the intro, CONTINUE on the main menu, wait for the field."""
        for _ in range(60):
            cb2 = self.u32(self.a("gMain") + 4) & ~1
            if cb2 == self.a("CB2_MainMenu"):
                break
            self.cmd("press Start 4", "wait 30")
        else:
            raise RuntimeError("main menu never came up")
        self.cmd("wait 60")
        status = self.u8(self.a("gSaveFileStatus"))
        if not self.wait_field(press="A"):
            raise RuntimeError("Continue did not reach the field")
        return status

    def reboot(self):
        self.cmd("reboot")


# Gen 3 Pokemon data (struct BoxPokemon): personality @0, otId @4, then 48 encrypted bytes @0x20 in four 12-byte
# substructures (growth, attacks, EVs/condition, misc) whose order depends on personality % 24.
SUBSTRUCT_ORDERS = ["GAEM", "GAME", "GEAM", "GEMA", "GMAE", "GMEA", "AGEM", "AGME", "AEGM", "AEMG", "AMGE", "AMEG",
                    "EGAM", "EGMA", "EAGM", "EAMG", "EMGA", "EMAG", "MGAE", "MGEA", "MAGE", "MAEG", "MEGA", "MEAG"]


def decode_mon(raw):
    """dict with species, item, exp, moves, evs, ivs (list) from 80+ bytes of a party/box Pokemon."""
    pid, otid = struct.unpack_from("<II", raw, 0)
    key = pid ^ otid
    enc = raw[0x20:0x50]
    dec = b"".join(struct.pack("<I", struct.unpack_from("<I", enc, i)[0] ^ key) for i in range(0, 48, 4))
    order = SUBSTRUCT_ORDERS[pid % 24]
    sub = {c: dec[i * 12:(i + 1) * 12] for i, c in enumerate(order)}
    species, item, exp = struct.unpack_from("<HHI", sub["G"], 0)
    moves = list(struct.unpack_from("<HHHH", sub["A"], 0))
    evs = list(sub["E"][0:6])
    ivword = struct.unpack_from("<I", sub["M"], 4)[0]
    ivs = [(ivword >> (5 * i)) & 31 for i in range(6)]
    return {"pid": pid, "species": species, "item": item, "exp": exp, "moves": moves, "evs": evs, "ivs": ivs}


def encode_mon_item(raw, item):
    """raw (bytes of a party/box Pokemon) holding <item>, with the checksum fixed."""
    raw = bytearray(raw)
    pid, otid = struct.unpack_from("<II", raw, 0)
    key = pid ^ otid
    dec = bytearray(b"".join(struct.pack("<I", struct.unpack_from("<I", raw, 0x20 + i)[0] ^ key) for i in range(0, 48, 4)))
    gr = SUBSTRUCT_ORDERS[pid % 24].index("G")
    struct.pack_into("<H", dec, gr * 12 + 2, item)
    struct.pack_into("<H", raw, 0x1C, sum(struct.unpack_from("<24H", dec)) & 0xFFFF)
    for i in range(0, 48, 4):
        struct.pack_into("<I", raw, 0x20 + i, struct.unpack_from("<I", dec, i)[0] ^ key)
    return bytes(raw)


def encode_mon_evs(raw, evs):
    """raw (bytes of a party/box Pokemon) with its six EVs replaced and the checksum fixed."""
    raw = bytearray(raw)
    pid, otid = struct.unpack_from("<II", raw, 0)
    key = pid ^ otid
    dec = bytearray(b"".join(struct.pack("<I", struct.unpack_from("<I", raw, 0x20 + i)[0] ^ key) for i in range(0, 48, 4)))
    e = SUBSTRUCT_ORDERS[pid % 24].index("E")
    dec[e * 12:e * 12 + 6] = bytes(evs)
    struct.pack_into("<H", raw, 0x1C, sum(struct.unpack_from("<24H", dec)) & 0xFFFF)
    for i in range(0, 48, 4):
        struct.pack_into("<I", raw, 0x20 + i, struct.unpack_from("<I", dec, i)[0] ^ key)
    return bytes(raw)
