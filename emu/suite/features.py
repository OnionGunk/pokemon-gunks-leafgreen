"""Feature checks for Gunk's FireRed, in the emulator.

Usage: py -3 emu/suite/features.py <rom.gba> <rom.elf> [check ...]

Each check starts a new game through the ROM's test hook (src/gunk_test.c: the Pokemon, items and flags the
check needs), plays it with button presses, and reads the result from RAM. Screenshots go to
emu/suite/out/<rom name>/features/.
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import FLASH_SIZE, SUBSTRUCT_ORDERS, Game, decode_mon, encode_mon_evs  # noqa: E402

ERASED = b"\xff" * FLASH_SIZE
GUNK_TEST_MAGIC = 0x4B4E5547

# constants (include/constants/*.h)
SPECIES = {"BULBASAUR": 1, "ONIX": 95, "KADABRA": 64, "ALAKAZAM": 65, "PIKACHU": 25, "CHARMANDER": 4}
ITEM = {"REPEL": 86, "RARE_CANDY": 68, "PROTEIN": 64, "TM01": 289, "HM01": 339, "ENDLESS_REPEL": 52,
        "EXP_ALL": 53, "DEXNAV": 54, "POTION": 13, "POKE_BALL": 4}
FLAG_SYS_B_DASH = 0x82F
FLAG_GUNK_ENDLESS_REPEL_ON = 0x4A7
FLAG_GUNK_EXP_ALL_ON = 0x4A8
MAP_ROUTE1 = (3, 19)
MAP_ROUTE2 = (3, 20)
FLAG_BADGE01_GET = 0x820
FLAG_BADGE02_GET = 0x821
FLAG_SYS_POKEMON_GET = 0x828
FLAG_SYS_POKEDEX_GET = 0x829
ITEM_OAKS_PARCEL = 349
VAR_MAP_SCENE_PALLET_TOWN_PROFESSOR_OAKS_LAB = 0x4055
VAR_MAP_SCENE_VIRIDIAN_CITY_MART = 0x4057
MAP_OAKS_LAB = (4, 3)
ITEM_TM_CASE = 364
ITEM_TM09 = 297
ITEM_HM01 = 339
SB1_BAG_TMHM = 0x0464
MOVE_BULLET_SEED = 331
ITEM_BICYCLE = 360
ITEM_TOWN_MAP = 361
SB1_BAG_KEY = 0x03B8
ITEM_METAL_COAT = 199
SPECIES_STEELIX = 208
FLAG_SYS_NATIONAL_DEX = 0x840
SPECIES_LAPRAS = 131
ITEM_HM03 = 341
FLAG_BADGE05_GET = 0x824
SB1_REGISTERED_ITEM = 0x296
VAR_REPEL_STEP_COUNT = 0x4020
VAR_GUNK_LAST_REPEL = 0x4029
SB1_VARS = 0x1000
SB1_FLAGS = 0x0EE0
SB1_BAG_ITEMS = 0x0310
SB2_OPTIONS = 0x14
SB1_GUNK_DEXNAV = 0x348C  # offsetof(struct SaveBlock1, gunkDexNav)
SB2_ENCRYPTION_KEY = 0xF20
SB1_DAYCARE_STEP_COUNTER = 0x309A  # offsetof(struct SaveBlock1, daycare) + 2 * 140 + 2


class Features:
    def __init__(self, rom, elf):
        self.g = Game(rom, elf)
        self.out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out",
                                os.path.splitext(os.path.basename(rom))[0], "features")
        os.makedirs(self.out, exist_ok=True)
        self.results = []

    def path(self, name):
        return os.path.join(self.out, name).replace("\\", "/")

    def shot(self, name):
        self.g.cmd(f"shot {self.path(name)}")

    def record(self, check, ok, detail):
        self.results.append((check, ok, detail))
        print(("PASS " if ok else "FAIL ") + check + ": " + detail, flush=True)

    # --- RAM helpers ---
    def sb1(self):
        return self.g.u32(self.g.a("gSaveBlock1Ptr"))

    def sb2(self):
        return self.g.u32(self.g.a("gSaveBlock2Ptr"))

    def u16(self, addr):
        return struct.unpack("<H", bytes.fromhex(self.g.cmd(f"read {addr} 2")[0].replace(" ", "")))[0]

    def var(self, var):
        return self.u16(self.sb1() + SB1_VARS + (var - 0x4000) * 2)

    def set_var(self, var, value):
        self.g.cmd(f"write16 {self.sb1() + SB1_VARS + (var - 0x4000) * 2} {value}")

    def flag(self, flag):
        return (self.g.u8(self.sb1() + SB1_FLAGS + flag // 8) >> (flag % 8)) & 1

    def bag_count(self, item, pocket_offset=SB1_BAG_ITEMS, slots=42):
        key = self.u16(self.sb2() + SB2_ENCRYPTION_KEY)
        data = bytes.fromhex(self.g.cmd(f"read {self.sb1() + pocket_offset} {slots * 4}")[0].replace(" ", ""))
        for i in range(slots):
            iid, qty = struct.unpack_from("<HH", data, i * 4)
            if iid == item:
                return qty ^ key
        return 0

    # --- setup ---
    def new_game(self, mons=(), items=(), flags=(), name="new"):
        """Power on with an erased flash, set the test hook, play the intro to the bedroom."""
        g = self.g
        g.start()
        g.set_flash(ERASED)
        g.reboot()
        g.cmd("wait 30")
        g.cmd(f"write32 {g.a('gGunkTestMagic')} {GUNK_TEST_MAGIC}")
        for i, (species, level) in enumerate(mons):
            g.cmd(f"write16 {g.a('gGunkTestMons') + i * 4} {species}", f"write16 {g.a('gGunkTestMons') + i * 4 + 2} {level}")
        for i, (item, qty) in enumerate(items):
            g.cmd(f"write16 {g.a('gGunkTestItems') + i * 4} {item}", f"write16 {g.a('gGunkTestItems') + i * 4 + 2} {qty}")
        for i, flag in enumerate(flags):
            g.cmd(f"write16 {g.a('gGunkTestFlags') + i * 2} {flag}")
        for _ in range(80):
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_MainMenu"):
                break
            g.cmd("press Start 4", "wait 30")
        if not g.wait_field(press="A", max_steps=1500, settle=5):
            raise RuntimeError("intro never reached the field")
        g.cmd("wait 30")
        self.shot(f"{name}_bedroom.png")

    def warp(self, map_group, map_num, x, y, name="warp"):
        """Save with the game's own "continue game warp" set to (map, x, y), power-cycle and Continue: the game
        then warps there as it does after a white-out (SaveBlock1 continueGameWarp, SaveBlock2 flag bit 0)."""
        g = self.g

        def edit():
            sb1, sb2 = self.sb1(), self.sb2()
            g.cmd(f"write8 {sb1 + 0xC} {map_group}", f"write8 {sb1 + 0xD} {map_num}", f"write8 {sb1 + 0xE} 255",
                  f"write16 {sb1 + 0x10} {x}", f"write16 {sb1 + 0x12} {y}",
                  f"write8 {sb2 + 9} {g.u8(sb2 + 9) | 1}")
        g.save(before_save=edit)
        g.reboot()
        g.boot_continue()
        g.cmd("wait 30")
        self.shot(f"{name}.png")

    # --- checks ---
    def check_header(self):
        title = bytes.fromhex(self.g.cmd("read 0x080000A0 16")[0].replace(" ", ""))
        self.record("header", title[:12] == b"GUNK FR\0\0\0\0\0" and title[12:16] == b"BPRE", repr(title))

    def check_text_speed_default(self):
        speed = self.g.u8(self.sb2() + SB2_OPTIONS) & 7
        self.record("text speed", speed == 2, f"new game text speed {speed} (2 = FAST)")

    def check_follower(self):
        """The lead (Bulbasaur) walks behind the player."""
        g = self.g
        g.cmd("press Left 40", "wait 20", "press Down 8", "wait 30")
        self.shot("follower.png")
        objs = g.a("gObjectEvents")
        found = None
        for i in range(16):
            raw = bytes.fromhex(g.cmd(f"read {objs + i * 0x24} 12")[0].replace(" ", ""))
            active = raw[0] & 1
            gfx, local_id = raw[5], raw[8]
            if active and local_id == 254:
                found = (i, gfx)
        self.record("follower", found is not None and found[1] == 152, f"follower object {found}")

    def check_auto_run(self):
        g = self.g
        flags_addr = g.a("gPlayerAvatar")
        g.cmd("press Right 3")
        running = g.u8(flags_addr) & 0x80
        g.cmd("wait 20", "press Right+B 3")
        walking = g.u8(flags_addr) & 0x80
        g.cmd("wait 20")
        self.record("auto-run", running != 0 and walking == 0,
                    f"dash flag {running:#x} without B, {walking:#x} holding B")

    def check_repel_prompt(self):
        g = self.g
        before = self.bag_count(ITEM["REPEL"])
        self.set_var(VAR_REPEL_STEP_COUNT, 1)
        self.set_var(VAR_GUNK_LAST_REPEL, ITEM["REPEL"])
        g.cmd("press Left 16", "wait 40")
        self.shot("repel_prompt.png")
        g.cmd("press A 4", "wait 60")
        self.shot("repel_used.png")
        g.cmd("press A 4", "wait 30", "press A 4", "wait 30")
        steps = self.var(VAR_REPEL_STEP_COUNT)
        after = self.bag_count(ITEM["REPEL"])
        self.record("repel prompt", steps == 100 and after == before - 1,
                    f"Repels {before} -> {after}, steps {steps}")

    def pos(self):
        sb1 = self.sb1()
        return struct.unpack("<hh", bytes.fromhex(self.g.cmd(f"read {sb1} 4")[0].replace(" ", "")))

    def in_battle(self):
        return (self.g.u32(self.g.a("gMain") + 4) & ~1) == self.g.a("BattleMainCB2")

    def walk_to(self, tx, ty, max_steps=60):
        """Walk (map coords) one tile at a time, stopping early if a battle starts."""
        for _ in range(max_steps):
            x, y = self.pos()
            if (x, y) == (tx, ty) or self.in_battle():
                return
            if x != tx:
                d = "Right" if tx > x else "Left"
            else:
                d = "Down" if ty > y else "Up"
            self.g.cmd(f"press {d} 8", "wait 10")

    def check_auto_run_outdoors(self):
        """Tiles covered holding a direction for 32 frames on open ground: 4 running (8 frames a tile), 2 walking."""
        g = self.g
        x0, _ = self.pos()
        g.cmd("press Right 32", "wait 20")
        x1, _ = self.pos()
        g.cmd("press Right+B 32", "wait 20")
        x2, _ = self.pos()
        ran, walked = x1 - x0, x2 - x1
        self.record("auto-run", ran >= 3 and 1 <= walked <= 2, f"{ran} tiles without B, {walked} holding B")

    def check_endless_repel(self):
        """Lead at level 100 and the Endless Repel on: 30 steps in tall grass, no wild battle."""
        x, y = self.pos()
        battles = 0
        for i in range(30):
            self.g.cmd("press Left 8" if i % 2 == 0 else "press Right 8", "wait 10")
            if self.in_battle():
                battles += 1
                break
        self.record("endless repel", battles == 0 and self.flag(FLAG_GUNK_ENDLESS_REPEL_ON) == 1,
                    f"{battles} wild battles in 30 steps of grass")

    def check_dexnav(self):
        g = self.g
        g.cmd(f"write16 {self.sb1() + SB1_REGISTERED_ITEM} {ITEM['DEXNAV']}")
        g.cmd("press Select 4", "wait 60")
        self.shot("dexnav_list.png")
        g.cmd("press A 4", "wait 60")
        self.shot("dexnav_hiding.png")
        search = g.a("sSearch")
        raw = bytes.fromhex(g.cmd(f"read {search} 12")[0].replace(" ", ""))
        species, sx, sy = struct.unpack_from("<Hhh", raw, 0)
        active = raw[11]  # struct DexNavSearch.active (after the u16 framesLeft and spriteId)
        g.cmd("press A 4", "wait 30", "press A 4", "wait 30")
        self.shot("dexnav_patch.png")
        self.walk_to(sx - 7, sy - 7)
        g.cmd("wait 200")
        self.shot("dexnav_battle.png")
        enemy = struct.unpack("<H", bytes.fromhex(g.cmd(f"read {g.a('gEnemyParty') + 0x20} 2")[0].replace(" ", "")))[0]
        battle = self.in_battle()
        self.record("dexnav", active == 1 and battle, f"searched species {species} at ({sx - 7},{sy - 7}); "
                    f"battle {battle}")

    def finish_battle(self, max_presses=80):
        """FIGHT, first move, then A through the messages until the field is back."""
        g = self.g
        g.cmd("wait 250", "press A 4", "wait 40", "press A 4", "wait 20")
        for i in range(max_presses):
            if not self.in_battle() and g.field_ready():
                return True
            g.cmd("press A 4", "wait 20")
            if i == 6:
                self.shot("battle_text.png")
        return False

    def party_level(self, slot):
        return self.g.u8(self.g.a("gPlayerParty") + slot * 100 + 0x54)

    def check_exp_all_battle(self):
        """A DexNav battle with INSTANT text; the Bulbasaur in slot 2 never battles and still gets EXP."""
        g = self.g
        g.cmd(f"write8 {self.sb2() + SB2_OPTIONS} {(g.u8(self.sb2() + SB2_OPTIONS) & ~7) | 3}")
        before = self.mon(1)["exp"]
        done = self.finish_battle()
        after = self.mon(1)["exp"]
        self.shot("after_battle.png")
        self.record("exp all", done and after > before, f"slot 2 EXP {before} -> {after}, back in the field {done}")
        dex = bytes.fromhex(g.cmd(f"read {self.sb1() + SB1_GUNK_DEXNAV} 389")[0].replace(" ", ""))
        level, chain_species, chain = dex[16 - 1], dex[386] | (dex[387] << 8), dex[388]
        self.record("dexnav search level", level == 1 and chain_species == 16 and chain == 1,
                    f"Pidgey search level {level}, chain species {chain_species} x{chain}")

    # --- menus ---
    def startmenu(self, option):
        """Open the Start menu and choose an entry (enum StartMenuOption: 1 POKEMON, 2 BAG, 4 SAVE...)."""
        g = self.g
        g.cmd("press Start 4", "wait 30")
        n = g.u8(g.a("sNumStartMenuItems"))
        order = bytes.fromhex(g.cmd(f"read {g.a('sStartMenuOrder')} {n}")[0].replace(" ", ""))
        target = order.index(option)
        for _ in range(10):
            pos = g.u8(g.a("sStartMenuCursorPos"))
            if pos == target:
                break
            g.cmd("press Down 4" if pos < target else "press Up 4", "wait 6")
        g.cmd("press A 4", "wait 90")

    def back_to_field(self, button="B", max_presses=40):
        for _ in range(max_presses):
            if self.g.field_ready():
                return True
            self.g.cmd(f"press {button} 4", "wait 30")
        return False

    def mon(self, slot):
        raw = bytes.fromhex(self.g.cmd(f"read {self.g.a('gPlayerParty') + slot * 100} 100")[0].replace(" ", ""))
        return decode_mon(raw)

    def set_evs(self, slot, evs):
        addr = self.g.a("gPlayerParty") + slot * 100
        raw = bytes.fromhex(self.g.cmd(f"read {addr} 100")[0].replace(" ", ""))
        path = self.path("_mon.bin")
        open(path, "wb").write(encode_mon_evs(raw, evs))
        self.g.cmd(f"poke EWRAM {addr - 0x02000000} {path}")

    def make_egg(self, slot):
        """Party slot <slot> becomes an egg of its species with no egg cycles left (friendship 0)."""
        addr = self.g.a("gPlayerParty") + slot * 100
        raw = bytearray(bytes.fromhex(self.g.cmd(f"read {addr} 100")[0].replace(" ", "")))
        pid, otid = struct.unpack_from("<II", raw, 0)
        key = pid ^ otid
        dec = bytearray(b"".join(struct.pack("<I", struct.unpack_from("<I", raw, 0x20 + i)[0] ^ key)
                                 for i in range(0, 48, 4)))
        order = SUBSTRUCT_ORDERS[pid % 24]
        g, m = order.index("G") * 12, order.index("M") * 12
        dec[g + 9] = 0  # friendship = egg cycles left
        struct.pack_into("<I", dec, m + 4, struct.unpack_from("<I", dec, m + 4)[0] | 1 << 30)  # isEgg
        raw[19] |= 0b100  # the header's isEgg bit, as SetMonData(MON_DATA_IS_EGG) sets it
        struct.pack_into("<H", raw, 0x1C, sum(struct.unpack_from("<24H", dec)) & 0xFFFF)
        for i in range(0, 48, 4):
            struct.pack_into("<I", raw, 0x20 + i, struct.unpack_from("<I", dec, i)[0] ^ key)
        path = self.path("_mon.bin")
        open(path, "wb").write(bytes(raw))
        self.g.cmd(f"poke EWRAM {addr - 0x02000000} {path}")

    def is_egg(self, slot):
        raw = bytes.fromhex(self.g.cmd(f"read {self.g.a('gPlayerParty') + slot * 100} 100")[0].replace(" ", ""))
        pid, otid = struct.unpack_from("<II", raw, 0)
        m = SUBSTRUCT_ORDERS[pid % 24].index("M") * 12
        return (struct.unpack_from("<I", raw, 0x20 + m + 4)[0] ^ pid ^ otid) >> 30 & 1

    def check_egg_hatch(self):
        """An egg with no cycles left hatches on the next egg cycle: 128 steps on Gunk's (256 in vanilla)."""
        g = self.g
        self.make_egg(0)
        counter = self.sb1() + SB1_DAYCARE_STEP_COUNTER
        g.cmd(f"write8 {counter} 0")
        steps, x0 = 0, self.pos()[0]
        for i in range(400):
            g.cmd("press Left 8" if (i // 3) % 2 == 0 else "press Right 8", "wait 4")
            if not g.field_ready():
                break
            steps = g.u8(counter)
        self.shot("egg_hatching.png")
        hatching = not g.field_ready()
        for _ in range(80):  # the hatch scene; B declines the nickname
            if g.field_ready():
                break
            g.cmd("press B 4", "wait 30")
        hatched = g.field_ready() and not self.is_egg(0) and self.mon(0)["species"] == SPECIES["BULBASAUR"]
        self.shot("egg_hatched.png")
        self.record("egg hatching", hatching and hatched and steps <= 128,
                    f"hatch scene after {steps + 1} steps, hatched {hatched}, species {self.mon(0)['species']}")

    def use_first_item_on(self, slot, name):
        """BAG (ITEMS pocket, first item) -> USE -> party slot; then A through its messages."""
        g = self.g
        self.startmenu(2)
        g.cmd("wait 60")
        for _ in range(8):  # A on the item opens its menu, A on USE opens the party menu
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_UpdatePartyMenu"):
                break
            g.cmd("press A 4", "wait 40")
        g.cmd("wait 30")
        for _ in range(8):  # the party menu remembers its cursor: move until gPartyMenu.slotId is the slot
            cur = g.u8(g.a("gPartyMenu") + 9)
            if cur == slot:
                break
            g.cmd("press Down 4" if cur < slot else "press Up 4", "wait 10")
        g.cmd("press A 4", "wait 60")
        self.shot(name)

    def check_kadabra(self):
        g = self.g
        self.use_first_item_on(0, "candy.png")
        for _ in range(60):
            g.cmd("press A 4", "wait 30")
            if g.field_ready():
                break
        self.back_to_field()
        species = self.mon(0)["species"]
        self.record("trade evolution by level", species == SPECIES["ALAKAZAM"],
                    f"Kadabra 35 + Rare Candy -> species {species} (65 = Alakazam)")

    def check_vitamins(self):
        """Bulbasaur (slot 1) with 240 Attack EVs: Protein -> 250, Protein -> 252, a third one does nothing."""
        g = self.g
        self.set_evs(1, [0, 240, 0, 0, 0, 0])
        seen = []
        for i in range(3):
            self.use_first_item_on(1, f"protein{i}.png")
            g.cmd("press A 4", "wait 30", "press A 4", "wait 30")
            self.back_to_field()
            seen.append(self.mon(1)["evs"][1])
        left = self.bag_count(ITEM["PROTEIN"])
        self.record("vitamins to 252", seen == [250, 252, 252] and left == 1,
                    f"Attack EVs after each Protein {seen}, Proteins left {left}")

    def check_tm_reusable(self):
        """TM Case -> TM09 (HM01 is listed first) -> teach Bulbasaur Bullet Seed; TM09 stays in the case."""
        g = self.g
        self.startmenu(2)
        g.cmd("wait 60", "press Right 4", "wait 40", "press A 4", "wait 40", "press A 4", "wait 90",
              "press Down 4", "wait 20", "press A 4", "wait 40", "press A 4", "wait 90")
        for _ in range(6):
            g.cmd("press A 4", "wait 60")
        self.back_to_field()
        moves = self.mon(0)["moves"]
        left = self.bag_count(ITEM_TM09, SB1_BAG_TMHM, 58)
        self.record("reusable TMs", MOVE_BULLET_SEED in moves and left == 1, f"moves {moves}, TM09 left {left}")

    def check_hm_without_teaching(self):
        """Route 2's Cut tree: Bulbasaur doesn't know Cut, but HM01 is in the bag and the badge is set."""
        g = self.g
        before = self.mon(0)["moves"]
        g.cmd("press Up 2", "wait 20", "press A 4", "wait 60")
        self.shot("cut_prompt.png")
        for _ in range(8):
            g.cmd("press A 4", "wait 60")
        self.back_to_field()
        g.cmd("press Up 16", "wait 20")
        x, y = self.pos()
        self.shot("cut_done.png")
        self.record("HM without teaching", y == 62 and 15 not in before, f"stood at ({x},{y}) after cutting (tree at 16,62)")

    def follower_palette_slot(self):
        g = self.g
        objs = g.a("gObjectEvents")
        for i in range(16):
            raw = bytes.fromhex(g.cmd(f"read {objs + i * 0x24} 12")[0].replace(" ", ""))
            if raw[0] & 1 and raw[8] == 254:
                sprite = g.a("gSprites") + raw[4] * 0x44
                return self.u16(sprite + 4) >> 12
        return None

    def check_pc_move_tutor(self):
        """A Pokemon Center PC: MOVE TUTOR -> remember -> Bulbasaur 20 (Tackle and Growl forgotten) -> Tackle."""
        g = self.g
        g.cmd("press Up 2", "wait 20", "press A 4", "wait 60", "press A 4", "wait 60",
              "press Down 4", "wait 10", "press Down 4", "wait 10")
        self.shot("pc_menu.png")
        g.cmd("press A 4", "wait 60", "press A 4", "wait 60", "press A 4", "wait 60", "press A 4", "wait 120",
              "press A 4", "wait 120")
        self.shot("pc_relearner.png")
        before = self.mon(0)["moves"]
        g.cmd("press A 4", "wait 60")  # Tackle, the first move on the list
        for _ in range(20):  # "forget a move?" YES, the first move, the messages (they take A only)
            if (g.u32(g.a("gMain") + 4) & ~1) == g.a("CB2_Overworld"):
                break
            g.cmd("press A 4", "wait 60")
        back = self.back_to_field()  # B on the PC menu logs off
        g.cmd("wait 60")
        after = self.mon(0)["moves"]
        slot = self.follower_palette_slot()
        self.shot("pc_after.png")
        self.record("PC move tutor", 33 in after and 33 not in before, f"moves {before} -> {after}")
        self.record("follower palette after a menu", back and slot is not None and slot >= 12,
                    f"back in the field {back}, follower palette slot {slot}")

    def pocket_ids(self, offset, slots):
        data = bytes.fromhex(self.g.cmd(f"read {self.sb1() + offset} {slots * 4}")[0].replace(" ", ""))
        return [struct.unpack_from("<H", data, i * 4)[0] for i in range(slots)]

    def check_bag_sort(self):
        """ITEMS pocket holds REPEL then POTION (the order they were added); START sorts it to POTION, REPEL."""
        g = self.g
        before = [i for i in self.pocket_ids(SB1_BAG_ITEMS, 4) if i]
        self.startmenu(2)
        g.cmd("wait 60", "press Start 4", "wait 30")
        self.shot("bag_sorted.png")
        after = [i for i in self.pocket_ids(SB1_BAG_ITEMS, 4) if i]
        self.back_to_field()
        self.record("bag sort", before == [ITEM["REPEL"], ITEM["POTION"]] and after == [ITEM["POTION"], ITEM["REPEL"]],
                    f"ITEMS pocket {before} -> {after}")

    def check_two_registered_items(self):
        """Register the BICYCLE, then the TOWN MAP: SELECT has the TOWN MAP, R the BICYCLE (it mounts it)."""
        g = self.g
        self.startmenu(2)
        g.cmd("wait 60", "press Right 4", "wait 40")
        for _ in range(2):  # first row (BICYCLE), then the second (TOWN MAP): A, REGISTER
            g.cmd("press A 4", "wait 40", "press Down 4", "wait 10", "press A 4", "wait 40")
            g.cmd("press Down 4", "wait 20")
        self.shot("registered.png")
        self.back_to_field()
        sel = self.u16(self.sb1() + SB1_REGISTERED_ITEM)
        second = self.var(0x402A)
        g.cmd("press R 4", "wait 90")
        self.shot("r_button.png")
        on_bike = g.u8(g.a("gPlayerAvatar")) & 0x06
        self.record("two registered items", sel == ITEM_TOWN_MAP and second == ITEM_BICYCLE and on_bike != 0,
                    f"SELECT {sel}, R {second}, on the bike after R: {on_bike != 0}")

    def set_flag(self, flag):
        a = self.sb1() + SB1_FLAGS + flag // 8
        self.g.cmd(f"write8 {a} {self.g.u8(a) | (1 << (flag % 8))}")

    def check_trade_item_as_stone(self):
        """Onix + Metal Coat used from the bag: no effect before the National Dex (vanilla's rule for Gen 2
        targets); after it, Onix becomes Steelix and the Coat is used up."""
        g = self.g
        self.use_first_item_on(0, "coat_no_dex.png")
        for _ in range(6):
            g.cmd("press A 4", "wait 40")
        self.back_to_field()
        before = (self.mon(0)["species"], self.bag_count(ITEM_METAL_COAT))
        g.cmd(f"write8 {self.sb2() + 0x18 + 3} 185")
        self.set_var(0x404E, 0x6258)
        self.set_flag(FLAG_SYS_NATIONAL_DEX)
        self.use_first_item_on(0, "coat_dex.png")
        for _ in range(60):
            g.cmd("press A 4", "wait 30")
            if g.field_ready():
                break
        self.back_to_field()
        after = (self.mon(0)["species"], self.bag_count(ITEM_METAL_COAT))
        self.record("trade item as a stone", before == (SPECIES["ONIX"], 1) and after == (SPECIES_STEELIX, 0),
                    f"without the National Dex (species, coats) {before}, with it {after}")

    def check_options_instant(self):
        """OPTION: the TEXT SPEED row goes SLOW, MID, FAST, INSTANT; picking INSTANT saves speed 3."""
        g = self.g
        self.startmenu(5)
        g.cmd("wait 60", "press Right 4", "wait 20")
        self.shot("options_instant.png")
        g.cmd("press B 4", "wait 60")
        self.back_to_field()
        speed = g.u8(self.sb2() + SB2_OPTIONS) & 7
        self.record("INSTANT text option", speed == 3, f"text speed after FAST + Right: {speed}")

    def check_story_opening(self):
        """A real new game (no test setup): bedroom, Pallet Town, Oak's scene on Route 1, the starter in his lab
        and the rival battle. Afterwards the lab's scene var is 4 and the starter follows the player."""
        g = self.g

        def mash(n):
            return g.wait_field(press="A", max_steps=n, settle=4)
        self.walk_to(10, 3)
        g.cmd("press Up 16", "wait 60")          # stairs down
        self.walk_to(4, 8)
        g.cmd("press Down 16", "wait 120")       # out of the door
        self.walk_to(12, 2)
        g.cmd("press Up 16", "wait 60")          # Oak's trigger at the north edge
        mash(900)
        self.shot("story_lab.png")
        self.walk_to(6, 5)
        self.walk_to(8, 5)
        g.cmd("press Up 2", "wait 20", "press A 4", "wait 40")  # Bulbasaur's ball
        mash(1500)
        g.cmd("press Down 16", "wait 30")
        self.walk_to(6, 8)                       # the rival battle trigger
        g.cmd("press Down 16", "wait 30")
        for _ in range(3):
            mash(1500)
        self.shot("story_after_rival.png")
        scene = self.var(0x4055)
        slot = self.follower_palette_slot()
        species = self.mon(0)["species"]
        self.record("story opening", scene == 4 and slot is not None and species == SPECIES["BULBASAUR"],
                    f"lab scene var {scene}, starter species {species}, follower palette slot {slot}")

    def clear_flag(self, flag):
        a = self.sb1() + SB1_FLAGS + flag // 8
        self.g.cmd(f"write8 {a} {self.g.u8(a) & ~(1 << (flag % 8)) & 0xFF}")

    def key_items_given(self):
        return [self.bag_count(i, SB1_BAG_KEY, 30) for i in (ITEM["ENDLESS_REPEL"], ITEM["EXP_ALL"], ITEM["DEXNAV"])]

    def check_oak_gift(self):
        """The parcel delivered (the Mart's scene var 1, the parcel in the bag, Oak and the rival in the lab): Oak's
        Pokedex scene also hands over the three key items, before Brock."""
        g = self.g
        g.cmd("press Up 2", "wait 20", "press A 4", "wait 40")
        g.wait_field(press="A", max_steps=900, settle=4)
        items = self.key_items_given()
        self.shot("oak_after.png")
        self.record("Oak gives the key items with the Pokedex", items == [1, 1, 1] and self.flag(FLAG_SYS_POKEDEX_GET) == 1
                    and self.flag(0x4A9) == 1, f"Endless Repel, Exp. All, DexNav {items}, "
                    f"Pokedex {self.flag(FLAG_SYS_POKEDEX_GET)}, Boulder Badge {self.flag(FLAG_BADGE01_GET)}")

    def check_pewter_aide_gift(self):
        """After Brock (scene var 1, the aide shown): the Running Shoes scene also hands over the three key items."""
        g = self.g
        g.cmd("press Right 16", "wait 30")
        self.shot("pewter_aide.png")
        g.wait_field(press="A", max_steps=600, settle=4)
        items = self.key_items_given()
        self.shot("pewter_after.png")
        self.record("Pewter aide gives the key items", items == [1, 1, 1] and self.flag(FLAG_SYS_B_DASH) == 1
                    and self.flag(0x4A9) == 1 and self.flag(FLAG_GUNK_EXP_ALL_ON) == 1,
                    f"Endless Repel, Exp. All, DexNav {items}, Running Shoes {self.flag(FLAG_SYS_B_DASH)}")

    def check_mom_gift(self):
        """A save past the Pokedex without the key items (made before Gunk's): Mom heals, then gives them."""
        g = self.g
        g.cmd("press Up 2", "wait 20", "press A 4", "wait 40")
        g.wait_field(press="A", max_steps=600, settle=4)
        items = self.key_items_given()
        self.shot("mom_after.png")
        self.record("Mom gives the key items", items == [1, 1, 1], f"Endless Repel, Exp. All, DexNav {items}")

    def follower_pos(self):
        g = self.g
        objs = g.a("gObjectEvents")
        for i in range(16):
            raw = bytes.fromhex(g.cmd(f"read {objs + i * 0x24} 0x14")[0].replace(" ", ""))
            if raw[0] & 1 and raw[8] == 254:
                x, y = struct.unpack_from("<hh", raw, 0x10)
                return x - 7, y - 7
        return None

    def check_follower_surf(self):
        """Lapras (no Surf; HM03 in the bag) surfs off Pallet Town's shore: the follower stays on land, and
        is back beside the player after landing."""
        g = self.g
        g.cmd("press Down 2", "wait 20", "press A 4", "wait 60")
        g.wait_field(press="A", max_steps=60, settle=4)
        g.cmd("wait 60", "press Down 16", "wait 20", "press Down 16", "wait 30")
        surfing = g.u8(g.a("gPlayerAvatar")) & 0x08
        on_water = self.pos()
        follower_while = self.follower_pos()
        self.shot("surf.png")
        g.cmd("press Up 16", "wait 20", "press Up 16", "wait 60", "press Up 16", "wait 120")
        landed = self.pos()
        follower_after = self.follower_pos()
        self.shot("surf_landed.png")
        ok = surfing and follower_while is not None and follower_while[1] <= 16 and landed[1] <= 16             and follower_after is not None and abs(follower_after[0] - landed[0]) + abs(follower_after[1] - landed[1]) <= 3
        self.record("follower and Surf", ok, f"surfing {surfing != 0} at {on_water}, follower at {follower_while}; "
                    f"landed at {landed}, follower at {follower_after}")

    def check_follower_map_edge(self):
        """Walk north out of Pallet Town into Route 1: the follower crosses the map edge behind the player."""
        g = self.g
        self.set_var(0x4050, 3)  # VAR_MAP_SCENE_PALLET_TOWN_OAK: Oak's Route 1 scene is over
        self.walk_to(12, 2)
        for _ in range(8):
            g.cmd("press Up 16", "wait 10")
        g.cmd("wait 60")
        sb1 = self.sb1()
        where = (g.u8(sb1 + 4), g.u8(sb1 + 5))
        p, fp = self.pos(), self.follower_pos()
        self.shot("map_edge.png")
        near = fp is not None and abs(fp[0] - p[0]) + abs(fp[1] - p[1]) <= 3
        self.record("follower across a map edge", where == MAP_ROUTE1 and near, f"map {where}, player {p}, follower {fp}")

    def count_follower_objects(self):
        g = self.g
        objs = g.a("gObjectEvents")
        n = 0
        for i in range(16):
            raw = bytes.fromhex(g.cmd(f"read {objs + i * 0x24} 12")[0].replace(" ", ""))
            if raw[0] & 1 and (raw[8] == 254 or raw[5] == 152):
                n += 1
        return n

    def check_follower_save_cycle(self):
        """Save with the follower out, power-cycle, Continue: one follower, made fresh (it is never saved)."""
        g = self.g
        before = self.count_follower_objects()
        g.save()
        sb1 = self.sb1()
        saved = 0
        for i in range(16):
            raw = bytes.fromhex(g.cmd(f"read {sb1 + 0x6A0 + i * 0x24} 12")[0].replace(" ", ""))
            if raw[0] & 1 and (raw[8] == 254 or raw[5] == 152):
                saved += 1
        g.reboot()
        g.boot_continue()
        g.cmd("wait 60")
        after = self.count_follower_objects()
        self.shot("follower_continue.png")
        self.record("follower and saving", before == 1 and saved == 0 and after == 1,
                    f"follower objects before {before}, in the save block {saved}, after Continue {after}")

    def check_follower_door(self):
        """Through Oak's lab door (Pallet Town 16,13): inside, the follower is next to the player."""
        g = self.g
        self.walk_to(16, 14)
        g.cmd("press Up 16", "wait 120")
        sb1 = self.sb1()
        where = (g.u8(sb1 + 4), g.u8(sb1 + 5))
        g.cmd("press Up 16", "wait 30")
        p, fp = self.pos(), self.follower_pos()
        self.shot("door.png")
        near = fp is not None and abs(fp[0] - p[0]) + abs(fp[1] - p[1]) <= 3
        self.record("follower through a door", where == (4, 3) and near, f"map {where}, player {p}, follower {fp}")

    def check_follower_switch(self):
        """Party menu on the lead: RETURN puts the follower away (and it stays away), WALK brings it back."""
        g = self.g

        def lead_action(row):
            self.startmenu(1)
            g.cmd("wait 40", "press A 4", "wait 40")
            for _ in range(row):
                g.cmd("press Down 4", "wait 10")
            self.shot(f"follower_switch_{row}.png")
            g.cmd("press A 4", "wait 120")
            self.back_to_field()
            g.cmd("wait 60")
        lead_action(1)  # SUMMARY, RETURN, ...
        off = self.count_follower_objects()
        g.cmd("press Left 16", "wait 10", "press Right 16", "wait 40")
        still_off = self.count_follower_objects()
        lead_action(1)  # SUMMARY, WALK, ...
        on = self.count_follower_objects()
        self.record("follower on/off switch", off == 0 and still_off == 0 and on == 1,
                    f"follower objects after RETURN {off}, after a walk {still_off}, after WALK {on}")


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    f = Features(rom, elf)
    t0 = time.time()
    try:
        f.new_game(mons=[(SPECIES["BULBASAUR"], 10)], items=[(ITEM["REPEL"], 3)], flags=[FLAG_SYS_B_DASH],
                   name="basic")
        f.check_header()
        f.check_text_speed_default()
        f.check_options_instant()
        f.check_follower()
        f.check_repel_prompt()
        f.new_game(mons=[(SPECIES["PIKACHU"], 100), (SPECIES["BULBASAUR"], 1)],
                   items=[(ITEM["DEXNAV"], 1), (ITEM["EXP_ALL"], 1)],
                   flags=[FLAG_SYS_B_DASH, FLAG_GUNK_ENDLESS_REPEL_ON, FLAG_GUNK_EXP_ALL_ON], name="route1")
        f.warp(*MAP_ROUTE1, 4, 18, name="route1_warp")
        f.check_auto_run_outdoors()
        f.walk_to(15, 23)
        f.walk_to(15, 25)
        f.check_endless_repel()
        f.walk_to(15, 23)
        f.check_dexnav()
        f.check_exp_all_battle()
        f.new_game(mons=[(SPECIES["BULBASAUR"], 5)], flags=[FLAG_GUNK_ENDLESS_REPEL_ON], name="egg")
        f.warp(*MAP_ROUTE1, 4, 18, name="egg_warp")
        f.check_egg_hatch()
        f.new_game(mons=[(SPECIES["KADABRA"], 35), (SPECIES["BULBASAUR"], 5)],
                   items=[(ITEM["RARE_CANDY"], 1), (ITEM["PROTEIN"], 3)], name="menus")
        f.check_kadabra()
        f.check_vitamins()
        f.new_game(mons=[(SPECIES["BULBASAUR"], 5)], items=[(ITEM_TM_CASE, 1), (ITEM_TM09, 1), (ITEM_HM01, 1)],
                   flags=[FLAG_BADGE01_GET, FLAG_BADGE02_GET, FLAG_SYS_POKEMON_GET], name="tmhm")
        f.check_tm_reusable()
        f.warp(*MAP_ROUTE2, 16, 63, name="route2_warp")
        f.check_hm_without_teaching()
        f.new_game(mons=[(SPECIES["BULBASAUR"], 20)], flags=[FLAG_SYS_POKEMON_GET], name="pc")
        f.warp(5, 4, 11, 2, name="pc_warp")
        f.check_pc_move_tutor()
        f.new_game(mons=[(SPECIES["BULBASAUR"], 5)],
                   items=[(ITEM["REPEL"], 1), (ITEM["POTION"], 1), (ITEM_BICYCLE, 1), (ITEM_TOWN_MAP, 1)],
                   flags=[FLAG_SYS_POKEMON_GET], name="bag")
        f.check_bag_sort()
        f.warp(*MAP_ROUTE1, 4, 18, name="bag_warp")
        f.check_two_registered_items()
        f.new_game(mons=[(SPECIES["ONIX"], 20)], items=[(ITEM_METAL_COAT, 1)], flags=[FLAG_SYS_POKEMON_GET],
                   name="coat")
        f.check_trade_item_as_stone()
        f.new_game(name="story")
        f.check_story_opening()
        f.new_game(mons=[(SPECIES["BULBASAUR"], 5)], items=[(ITEM_OAKS_PARCEL, 1)],
                   flags=[FLAG_SYS_POKEMON_GET, 0x028, 0x029, 0x02A], name="oak")
        f.set_var(VAR_MAP_SCENE_PALLET_TOWN_PROFESSOR_OAKS_LAB, 4)  # after the first rival battle
        f.set_var(VAR_MAP_SCENE_VIRIDIAN_CITY_MART, 1)  # the parcel picked up
        for flag in (0x02B, 0x02D, 0x03A):  # show Oak, the rival and the Pokedexes in the lab
            f.clear_flag(flag)
        f.warp(*MAP_OAKS_LAB, 6, 4, name="oak_warp")
        f.check_oak_gift()
        f.new_game(mons=[(SPECIES["BULBASAUR"], 12)], flags=[FLAG_SYS_POKEMON_GET, FLAG_BADGE01_GET], name="pewter")
        f.set_var(0x406C, 1)
        f.clear_flag(0x092)
        f.warp(3, 2, 45, 22, name="pewter_warp")
        f.check_pewter_aide_gift()
        f.new_game(mons=[(SPECIES["BULBASAUR"], 12)], flags=[FLAG_SYS_POKEMON_GET, FLAG_SYS_POKEDEX_GET, FLAG_SYS_B_DASH, 0x258],
                   name="mom")  # a save past Pewter has the Pokedex, which Mom's gift now checks
        f.warp(4, 0, 8, 5, name="mom_warp")
        f.check_mom_gift()
        f.new_game(mons=[(SPECIES_LAPRAS, 30)], items=[(ITEM_HM03, 1)],
                   flags=[FLAG_SYS_POKEMON_GET, FLAG_BADGE05_GET], name="surf")
        f.warp(3, 0, 8, 16, name="surf_warp")
        f.check_follower_surf()
        f.check_follower_map_edge()
        f.check_follower_save_cycle()
        f.warp(3, 0, 16, 15, name="door_warp")
        f.check_follower_door()
        f.check_follower_switch()
    finally:
        import emu
        emu.stop()
    failed = [r for r in f.results if not r[1]]
    print(f"{len(f.results) - len(failed)}/{len(f.results)} passed in {time.time() - t0:.0f}s")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
