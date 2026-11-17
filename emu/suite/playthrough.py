"""One game from New Game to the Hall of Fame: py -3 emu/suite/playthrough.py <rom.gba> <rom.elf> [first chapter]

A single save carried through the whole story, played with button presses. Nothing is set up by the test hook, so
the release ROM runs it too. The intro, the starter (Squirtle), the rival in Oak's lab, the parcel, the Pokedex
(and Gunk's key items with it), a Mart, wild battles, DexNav searches, every gym leader, the S.S. Anne's captain,
Snorlax, the Elite Four (walked room to room from the Indigo Plateau's Pokemon Center), the Champion, the Hall of
Fame, the credits and CONTINUE all run the game's own scripts.

What stands in for the parts a player spends hours on:
- travel: the game's own continue warp (the one a white-out uses), then a save, a power cycle and CONTINUE, puts
  the player at the next event. So every chapter also saves and comes back from a power cycle;
- training: before each boss the party is healed and the lead set to a level (its stats worked out as the game
  does, its EXP one short of the next level, so the battle levels it up and evolves it when due) with a move that
  suits the fight in its first slot. Battles are fought with A (FIGHT, first move),
  so EXP, level-ups, evolutions and Gunk's Exp. All happen in the battles themselves;
- the Poke Flute (for Snorlax) is put in the bag, with the flag Mr. Fuji's gift sets.

Gunk's features used along the way: the follower (checked out after every chapter), the DexNav (opened with
SELECT, a search, the battle in the patch) in three places (Routes 1, 25 and 15), Quick Ball (L) for every catch, Quick Run (R) from
wild battles, the Endless Repel toggle, Exp. All and auto-run.

Each chapter ends with a savestate (out/<rom>/playthrough/<chapter>.State), so a run can start at a later
chapter. Results: emu/suite/out/<rom>/playthrough/playthrough.txt.
"""
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import story  # noqa: E402
from dexnav_screen import Screen  # noqa: E402
from features import (FLAG_BADGE01_GET, FLAG_GUNK_ENDLESS_REPEL_ON, FLAG_SYS_POKEDEX_GET, ITEM, SB1_BAG_KEY,  # noqa: E402
                      SB1_REGISTERED_ITEM, SB2_ENCRYPTION_KEY)
from lib import NM, SUBSTRUCT_ORDERS  # noqa: E402

import subprocess  # noqa: E402

ERASED = b"\xff" * 0x20000
ITEM_POKE_BALL, ITEM_GREAT_BALL, ITEM_ULTRA_BALL = 4, 3, 2
ITEM_POKE_FLUTE, ITEM_OAKS_PARCEL = 350, 349
SB1_BALLS, BALL_SLOTS = 0x430, 13
VAR_STARTER_MON, VAR_MAP_SCENE_VIRIDIAN_CITY_MART = 0x4031, 0x4057
FLAG_GOT_HM01, FLAG_GOT_POKE_FLUTE, FLAG_HIDE_ROUTE_12_SNORLAX = 0x237, 0x23D, 0x054
FLAG_DEFEATED_LORELEI, FLAG_SYS_GAME_CLEAR = 0x4B8, 0x82C
LOCALID_FOLLOWER = 254
SPECIES_SQUIRTLE = 7
MOVE = {"TACKLE": 33, "WATER_GUN": 55, "SURF": 57, "ICE_BEAM": 58, "BODY_SLAM": 34, "EARTHQUAKE": 89, "BITE": 44}

# grass tiles in a row of at least 5 (legality.py's): the DexNav searches and the wild battles
ROUTE1, ROUTE25, ROUTE15 = ("Route1", (15, 6)), ("Route25", (5, 3)), ("Route15", (62, 10))

# boss chapters: name, map folder, the person's tile, the lead's level and first move, the flag set afterwards
BOSSES = {
    "brock": ("PewterCity_Gym", (6, 5), 15, "WATER_GUN", FLAG_BADGE01_GET),
    "misty": ("CeruleanCity_Gym", (8, 6), 30, "BITE", FLAG_BADGE01_GET + 1),
    "captain": ("SSAnne_CaptainsOffice", (5, 4), None, None, FLAG_GOT_HM01),
    "surge": ("VermilionCity_Gym", (5, 2), 35, "EARTHQUAKE", FLAG_BADGE01_GET + 2),
    "erika": ("CeladonCity_Gym", (6, 4), 45, "ICE_BEAM", FLAG_BADGE01_GET + 3),
    "snorlax": ("Route12", (14, 70), 50, "BODY_SLAM", FLAG_HIDE_ROUTE_12_SNORLAX),
    "koga": ("FuchsiaCity_Gym", (7, 13), 58, "SURF", FLAG_BADGE01_GET + 4),  # Koffing and Weezing float
    "sabrina": ("SaffronCity_Gym", (14, 11), 62, "SURF", FLAG_BADGE01_GET + 5),
    "blaine": ("CinnabarIsland_Gym", (5, 4), 65, "SURF", FLAG_BADGE01_GET + 6),
    "giovanni": ("ViridianCity_Gym", (2, 2), 70, "SURF", FLAG_BADGE01_GET + 7),
}
# the Elite Four, room by room: the person's tile and the move for them (the lead is Lv. 100 from Lorelei on)
LEAGUE = [("PokemonLeague_LoreleisRoom", (6, 5), "BODY_SLAM", FLAG_DEFEATED_LORELEI),
          ("PokemonLeague_BrunosRoom", (6, 5), "SURF", FLAG_DEFEATED_LORELEI + 1),
          ("PokemonLeague_AgathasRoom", (6, 5), "SURF", FLAG_DEFEATED_LORELEI + 2),
          ("PokemonLeague_LancesRoom", (6, 8), "ICE_BEAM", FLAG_DEFEATED_LORELEI + 3)]
CHAPTERS = ["opening", "parcel", "pokedex", "mart", "route1", "brock", "misty", "route25", "captain", "surge",
            "erika", "snorlax", "route15", "koga", "sabrina", "blaine", "giovanni", "league", "champion"]


class Playthrough(Screen):
    def __init__(self, rom, elf):
        super().__init__(rom, elf)
        self.out = os.path.join(HERE, "out", os.path.splitext(os.path.basename(rom))[0], "playthrough")
        os.makedirs(self.out, exist_ok=True)
        self.maps = story.maps()
        story.neighbour.cache = self.maps
        story.neighbour.layouts = story.layouts()
        nm = subprocess.run([NM, elf], capture_output=True, text=True, check=True).stdout.splitlines()
        self.choose_action = {int(l.split()[0], 16) for l in nm if l.endswith(" HandleInputChooseAction")}
        self.choose_move = {int(l.split()[0], 16) for l in nm if l.endswith(" HandleInputChooseMove")}

    # --- reading and writing ---
    def read(self, addr, n):
        return bytes.fromhex(self.g.cmd(f"read {addr} {n}")[0].replace(" ", ""))

    def poke(self, addr, data):
        path = self.path("_poke.bin")
        open(path, "wb").write(bytes(data))
        self.g.cmd(f"poke EWRAM {addr - 0x02000000} {path}")

    def party_count(self):
        return self.g.u8(self.g.a("gPlayerPartyCount"))

    def party_species(self):
        out = []
        for i in range(self.party_count()):
            raw = self.read(self.g.a("gPlayerParty") + i * 100, 100)
            out.append((self.mon(i)["species"], raw[0x54]))
        return out

    def map_id(self):
        loc = self.read(self.sb1() + 4, 2)
        return loc[0], loc[1]

    def at(self, folder):
        m = self.maps[folder]
        return self.map_id() == (m["group"], m["num"])

    def give(self, pocket, slots, item, qty):
        """Put <qty> of <item> into the first free (or its own) slot of a bag pocket (quantities are encrypted)."""
        key = self.u16(self.sb2() + SB2_ENCRYPTION_KEY)
        base = self.sb1() + pocket
        data = self.read(base, slots * 4)
        for i in range(slots):
            iid, _ = struct.unpack_from("<HH", data, i * 4)
            if iid in (0, item):
                self.poke(base + i * 4, struct.pack("<HH", item, qty ^ key))
                return

    # --- moving around ---
    def mash(self, n=600):
        return self.g.wait_field(press="A", max_steps=n, settle=4)

    def travel(self, folder, x=None, y=None, warp_id=255):
        """The continue warp to (x, y) on the map (or to its warp <warp_id>), saved; power cycle and CONTINUE."""
        g = self.g
        m = self.maps[folder]
        if x is None:
            x = y = 0xFFFF

        def edit():
            sb1, sb2 = self.sb1(), self.sb2()
            g.cmd(f"write8 {sb1 + 0xC} {m['group']}", f"write8 {sb1 + 0xD} {m['num']}", f"write8 {sb1 + 0xE} {warp_id}",
                  f"write16 {sb1 + 0x10} {x}", f"write16 {sb1 + 0x12} {y}", f"write8 {sb2 + 9} {g.u8(sb2 + 9) | 1}")
        g.save(before_save=edit)
        g.reboot()
        g.boot_continue()
        g.cmd("wait 30")

    def go_talk(self, folder, person):
        """Travel next to the person and talk to them."""
        x, y, direction = story.neighbour(folder, *person)
        self.travel(folder, x, y)
        self.g.wait_field(press="B", max_steps=60)
        self.g.cmd(f"press {direction} 2", "wait 10", "press A 4", "wait 30")

    def face_talk(self, person):
        """Walk next to a person on this map (from below, or the side) and talk."""
        px, py = person
        self.walk_to(px, py + 1)
        self.g.cmd("press Up 2", "wait 10", "press A 4", "wait 30")

    # --- the party ---
    def train(self, slot, level, move):
        """Heal the party and set party slot <slot> to <level> with <move> first: EXP from the species' growth
        rate, stats from its base stats, IVs, EVs and nature, as CalculateMonStats works them out."""
        g = self.g
        addr = g.a("gPlayerParty") + slot * 100
        raw = bytearray(self.read(addr, 100))
        pid, otid = struct.unpack_from("<II", raw, 0)
        key = pid ^ otid
        dec = bytearray(b"".join(struct.pack("<I", struct.unpack_from("<I", raw, 0x20 + i)[0] ^ key)
                                 for i in range(0, 48, 4)))
        order = SUBSTRUCT_ORDERS[pid % 24]
        gr, at, ev, mi = (order.index(c) * 12 for c in "GAEM")
        species = struct.unpack_from("<H", dec, gr)[0]
        info = self.read(g.a("gSpeciesInfo") + species * 28, 28)
        # one EXP short of the next level: the next battle's EXP levels it up, and evolves it when due
        exp = struct.unpack("<I", self.read(g.a("gExperienceTables") + (info[19] * 101 + min(level + 1, 100)) * 4, 4))[0]
        exp -= level < 100
        struct.pack_into("<I", dec, gr + 4, exp)
        if move:
            # the fight's move first, then backups for when its PP runs out
            moves = [move] + [m for m in ("SURF", "ICE_BEAM", "BODY_SLAM", "EARTHQUAKE") if m != move][:3]
            for k, name in enumerate(moves):
                mid = MOVE[name]
                struct.pack_into("<H", dec, at + 2 * k, mid)
                dec[at + 8 + k] = self.read(g.a("gBattleMoves") + mid * 12 + 4, 1)[0]
        ivword = struct.unpack_from("<I", dec, mi + 4)[0]
        ivs = [(ivword >> (5 * i)) & 31 for i in range(6)]
        evs = list(dec[ev:ev + 6])
        nature = pid % 25
        stats = [(2 * info[0] + ivs[0] + evs[0] // 4) * level // 100 + level + 10]
        for s in range(1, 6):  # Attack, Defense, Speed, Sp. Atk, Sp. Def
            v = (2 * info[s] + ivs[s] + evs[s] // 4) * level // 100 + 5
            if nature // 5 != nature % 5:
                v = v * 110 // 100 if nature // 5 == s - 1 else v * 90 // 100 if nature % 5 == s - 1 else v
            stats.append(v)
        struct.pack_into("<H", raw, 0x1C, sum(struct.unpack_from("<24H", dec)) & 0xFFFF)
        for i in range(0, 48, 4):
            struct.pack_into("<I", raw, 0x20 + i, struct.unpack_from("<I", dec, i)[0] ^ key)
        struct.pack_into("<IB", raw, 0x50, 0, level)
        struct.pack_into("<7H", raw, 0x56, stats[0], *stats)
        self.poke(addr, raw)
        self.heal()

    def heal(self):
        """Full HP, no status and full PP for the party (a Pokemon Center's work)."""
        g = self.g
        for slot in range(self.party_count()):
            addr = g.a("gPlayerParty") + slot * 100
            raw = bytearray(self.read(addr, 100))
            pid, otid = struct.unpack_from("<II", raw, 0)
            key = pid ^ otid
            dec = bytearray(b"".join(struct.pack("<I", struct.unpack_from("<I", raw, 0x20 + i)[0] ^ key)
                                     for i in range(0, 48, 4)))
            at = SUBSTRUCT_ORDERS[pid % 24].index("A") * 12
            for k in range(4):
                mid = struct.unpack_from("<H", dec, at + 2 * k)[0]
                if mid:
                    dec[at + 8 + k] = self.read(g.a("gBattleMoves") + mid * 12 + 4, 1)[0]
            struct.pack_into("<H", raw, 0x1C, sum(struct.unpack_from("<24H", dec)) & 0xFFFF)
            for i in range(0, 48, 4):
                struct.pack_into("<I", raw, 0x20 + i, struct.unpack_from("<I", dec, i)[0] ^ key)
            struct.pack_into("<I", raw, 0x50, 0)
            raw[0x56:0x58] = raw[0x58:0x5A]
            self.poke(addr, raw)

    # --- battles ---
    def controller(self):
        return self.g.u32(self.g.a("gBattlerControllerFuncs")) & ~1

    def action_menu(self, max_steps=80):
        """B through battle text to the action menu. False if the battle ends first."""
        for _ in range(max_steps):
            if self.controller() in self.choose_action:
                self.g.cmd("wait 20")
                return True
            if not self.in_battle():
                return False
            self.g.cmd("press B 4", "wait 20")
        return False

    def wild_battle(self, spot):
        """Walk back and forth on the grass until a wild battle's action menu."""
        g = self.g
        self.walk_to(*spot)
        for i in range(600):
            if i and i % 150 == 0:
                g.cmd("press Down 8", "wait 10")
            g.cmd("press Left 8" if (i // 2) % 2 == 0 else "press Right 8", "wait 6")
            if self.in_battle():
                return self.action_menu()
        return False

    def back_in_field_after_battle(self, max_steps=150):
        for _ in range(max_steps):
            if not self.in_battle() and self.g.field_ready():
                return True
            self.g.cmd("press B 4", "wait 20")
        return False

    def quick_run(self):
        for _ in range(6):
            self.g.cmd("press R 4", "wait 20")
            if self.back_in_field_after_battle(max_steps=30):
                return True
            self.action_menu()
        return False

    def quick_ball(self):
        """L at each action menu until the Pokemon is caught (or the battle ends). True if the party grew."""
        count = self.party_count()
        for _ in range(15):
            if not self.action_menu(max_steps=120):
                break
            self.g.cmd("press L 2", "wait 2", "wait 60")
        self.back_in_field_after_battle()
        return self.party_count() == count + 1

    def fight(self, presses=3000):
        """A (FIGHT, the first move) through a battle and its scene until the player can walk again."""
        g = self.g
        settled = 0
        for i in range(presses):
            if g.field_ready() and not self.in_battle():
                settled += 1
                if settled >= 3:
                    return True
                g.cmd("wait 20")
                continue
            settled = 0
            self.press_a()
            if i % 200 == 199 and int(g.cmd(f"alive {g.a('gMain') + 0x24} 30")[0].split()[1]) == 0:
                raise RuntimeError("the game stopped")
        return False

    def press_a(self):
        """A, as a player fighting with the first move would: on the party menu after a faint, the next Pokemon;
        in the move menu, a move with PP left."""
        g = self.g
        if self.callback2() == g.a("CB2_UpdatePartyMenu"):
            g.cmd("press Down 4", "wait 10")
        if self.controller() in self.choose_move:
            self.move_with_pp()
        g.cmd("press A 4", "wait 20")

    def move_with_pp(self):
        """In the move menu: if the highlighted move has no PP left, move the cursor to one that has (the menu is
        2 x 2: 0 1 / 2 3). gBattleMons[0].pp is at 0x24; gMoveSelectionCursor[0] is the player's cursor."""
        g = self.g
        pp = self.read(g.a("gBattleMons") + 0x24, 4)
        cur = g.u8(g.a("gMoveSelectionCursor"))
        if pp[cur] or not any(pp):
            return  # (with no PP at all the game uses Struggle by itself)
        k = next(i for i in range(4) if pp[i])
        if cur % 2 != k % 2:
            g.cmd(f"press {'Right' if k % 2 else 'Left'} 4", "wait 10")
        if cur // 2 != k // 2:
            g.cmd(f"press {'Down' if k // 2 else 'Up'} 4", "wait 10")

    def dexnav_catch(self, place, name):
        """On the grass: a wild battle to run from with R (it also marks a species seen), then the DexNav from
        SELECT, a search for the first seen Pokemon, the battle in its patch, and Quick Ball until it's caught."""
        g = self.g
        folder, spot = place
        self.travel(folder, *spot)
        g.wait_field(press="B", max_steps=60)
        self.clear_flag(FLAG_GUNK_ENDLESS_REPEL_ON)
        ran = self.wild_battle(spot) and self.quick_run()
        self.record(f"{name}: Quick Run from a wild battle", ran, f"back in the field {ran}")
        self.walk_to(*spot)
        g.cmd(f"write16 {self.sb1() + SB1_REGISTERED_ITEM} {ITEM['DEXNAV']}")
        s = self.open_screen(f"{name}_dexnav.png")
        listed = self.list() if s else []
        seen = [i for i, (sp, _) in enumerate(listed) if self.dex_seen(sp)]
        if not seen:
            self.record(f"{name}: DexNav search and Quick Ball catch", False, f"screen {bool(s)}, list {listed}, none seen")
            g.cmd("press B 4")
            self.back_in_field()
            return
        self.goto_cell(seen[0], 0)
        g.cmd("press A 4", "wait 150")
        search = self.search()
        g.wait_field(press="B", max_steps=40)  # the search level message
        party = self.party_count()
        caught = False
        if search["active"]:
            self.walk_to(search["x"], search["y"])
            for _ in range(30):
                if self.in_battle():
                    break
                g.cmd("wait 10")
            caught = self.in_battle() and self.quick_ball()
        self.shot(f"{name}_caught.png")
        got = self.party_species()[-1] if self.party_count() > party else None
        self.record(f"{name}: DexNav search and Quick Ball catch", caught and got and got[0] == search["species"],
                    f"searched species {search['species']} (active {search['active']}), caught {got}, "
                    f"Poke Balls left {self.bag_count(ITEM_POKE_BALL, SB1_BALLS, BALL_SLOTS)}")

    def dex_seen(self, species):
        return self.g.u8(self.sb2() + 0x5C + (species - 1) // 8) >> ((species - 1) % 8) & 1

    # --- the follower and the save ---
    def follower_out(self):
        objs = self.g.a("gObjectEvents")
        for i in range(16):
            raw = self.read(objs + i * 0x24, 12)
            if raw[0] & 1 and raw[8] == LOCALID_FOLLOWER:
                return True
        return False

    def end_chapter(self, name):
        """The follower is out; save, power cycle, CONTINUE: the same map and tile, the follower out again."""
        g = self.g
        g.wait_field(press="B", max_steps=60)
        before, pos = self.map_id(), self.pos()
        out_before = self.follower_out()
        g.save()
        g.reboot()
        g.boot_continue()
        g.cmd("wait 60")
        after, pos2 = self.map_id(), self.pos()
        self.shot(f"{name}_end.png")
        self.record(f"{name}: save, power cycle, CONTINUE", (before, pos) == (after, pos2) and out_before
                    and self.follower_out(), f"map {before} {pos} -> {after} {pos2}, follower out {out_before} -> "
                    f"{self.follower_out()}, party {self.party_species()}")
        g.cmd(f"save {os.path.join(self.out, name + '.State')}")

    # --- chapters ---
    def opening(self):
        g = self.g
        g.start()
        g.set_flash(ERASED)
        g.reboot()
        for _ in range(80):
            if self.callback2() == g.a("CB2_MainMenu"):
                break
            g.cmd("press Start 4", "wait 30")
        if not g.wait_field(press="A", max_steps=1500, settle=5):
            raise RuntimeError("the intro never reached the field")
        self.walk_to(10, 3)
        g.cmd("press Up 16", "wait 60")          # stairs down
        self.walk_to(4, 8)
        g.cmd("press Down 16", "wait 120")       # out of the door
        self.walk_to(12, 2)
        g.cmd("press Up 16", "wait 60")          # Oak's scene at the north edge
        self.mash(900)
        self.walk_to(6, 5)
        self.walk_to(9, 5)
        g.cmd("press Up 2", "wait 20", "press A 4", "wait 40")  # Squirtle's ball
        self.mash(1500)
        g.cmd("press Down 16", "wait 30")
        self.walk_to(6, 8)                       # the rival's battle as the player leaves
        g.cmd("press Down 16", "wait 30")
        for _ in range(3):
            self.mash(1500)
        species = self.mon(0)["species"] if self.party_count() else None
        self.record("opening: Squirtle from Oak and the rival's battle", species == SPECIES_SQUIRTLE
                    and self.var(VAR_STARTER_MON) == 1 and self.var(0x4055) == 4,
                    f"starter {species}, VAR_STARTER_MON {self.var(VAR_STARTER_MON)}, lab scene {self.var(0x4055)}")

    def parcel(self):
        self.travel("ViridianCity_Mart", warp_id=0)
        self.mash(900)
        has = self.bag_count(ITEM_OAKS_PARCEL, SB1_BAG_KEY, 30)
        self.record("parcel: the Viridian Mart's clerk", self.var(VAR_MAP_SCENE_VIRIDIAN_CITY_MART) == 1 and has == 1,
                    f"Mart scene var {self.var(VAR_MAP_SCENE_VIRIDIAN_CITY_MART)}, parcel {has}")

    def pokedex(self):
        self.go_talk("PalletTown_ProfessorOaksLab", (6, 3))
        self.mash(1500)
        items = self.key_items_given()
        self.record("pokedex: Oak's Pokedex and Gunk's key items", self.flag(FLAG_SYS_POKEDEX_GET) == 1
                    and items == [1, 1, 1], f"Pokedex {self.flag(FLAG_SYS_POKEDEX_GET)}, Endless Repel, Exp. All, "
                    f"DexNav {items}")

    def mart(self):
        """Poke Balls from the Viridian Mart: BUY, the first item, quantity up, YES."""
        g = self.g
        before = self.bag_count(ITEM_POKE_BALL, SB1_BALLS, BALL_SLOTS)
        self.go_talk("ViridianCity_Mart", (2, 3))
        g.cmd("wait 60", "press A 4", "wait 60")          # the greeting, BUY
        g.cmd("press A 4", "wait 30")                      # the first item: Poke Ball
        for _ in range(9):
            g.cmd("press Up 4", "wait 6")                  # quantity 10
        g.cmd("press A 4", "wait 30", "press A 4", "wait 30", "press A 4", "wait 30")  # buy, YES, thanks
        for _ in range(6):
            g.cmd("press B 4", "wait 30")
        g.wait_field(press="B", max_steps=60)
        after = self.bag_count(ITEM_POKE_BALL, SB1_BALLS, BALL_SLOTS)
        self.record("mart: Poke Balls bought", after > before, f"Poke Balls {before} -> {after} (5 from Oak)")

    def boss(self, name):
        folder, person, level, move, done = BOSSES[name]
        if level:
            self.train(0, level, move)
        if name == "snorlax":
            self.set_flag(FLAG_GOT_POKE_FLUTE)
            self.give(SB1_BAG_KEY, 30, ITEM_POKE_FLUTE, 1)
        self.go_talk(folder, person)
        if name == "snorlax":  # "Play the Poke Flute?" YES
            self.g.cmd("wait 30", "press A 4", "wait 30")
        won = self.fight()
        self.shot(f"{name}_after.png")
        self.record(f"{name}: played through", won and self.flag(done) == 1,
                    f"field {won}, flag {self.flag(done)}, party {self.party_species()}")

    def league(self):
        """From the Pokemon Center's north door, on foot: each room's entry scene, the member, the next door."""
        g = self.g
        self.train(0, 100, LEAGUE[0][2])
        self.travel("IndigoPlateau_PokemonCenter_1F", 4, 2)
        g.wait_field(press="B", max_steps=60)
        g.cmd("press Up 16", "wait 120")
        for folder, person, move, done in LEAGUE:
            self.mash(300)  # the entry scene walks the player in
            if not self.at(folder):
                self.record(f"league: {folder}", False, f"not in the room: map {self.map_id()} {self.pos()}")
                return
            self.train(0, 100, move)
            self.face_talk(person)
            won = self.fight()
            self.shot(f"{folder}_after.png")
            ok = won and self.flag(done) == 1
            self.record(f"league: {folder}", ok, f"field {won}, flag {self.flag(done)}, party {self.party_species()}")
            if not ok:
                return
            # the next door: around the member, up the middle
            px, py = person
            self.walk_to(px - 1, py)
            door = (6, 5) if "Lance" in folder else (6, 2)
            self.walk_to(px - 1, door[1] + 1)
            self.walk_to(door[0], door[1] + 1)
            if "Lance" not in folder:
                g.cmd("press Up 16", "wait 120")
        # in front of the Champion's door: the champion chapter trains, then walks in
        g.cmd(f"save {os.path.join(self.out, 'league.State')}")

    def champion(self):
        """The Champion's room (the rival walks up), the battle, Oak, the Hall of Fame and its save, the credits,
        then CONTINUE from that save."""
        g = self.g
        self.train(0, 100, "ICE_BEAM")
        g.cmd("press Up 16", "wait 120")  # through Lance's room's north door
        title = False
        for i in range(6000):
            if g.field_ready() and not self.in_battle() and title:
                break
            cb2 = self.callback2()
            if cb2 in (g.a("CB2_MainMenu"), g.a("CB2_InitTitleScreen"), g.a("CB2_InitCopyrightScreenAfterBootup")):
                title = True
                g.cmd("wait 60")
                self.shot("champion_title.png")
                g.boot_continue()
                g.cmd("wait 60")
                continue
            self.press_a()
            if i % 500 == 499:
                self.shot(f"champion_{i + 1}.png")
                print(f"champion: {i + 1} presses, cb2 {self.callback2():#x}, map {self.map_id()}", flush=True)
        species = self.party_species()
        self.record("champion: the Hall of Fame, the credits and CONTINUE", title and self.flag(FLAG_SYS_GAME_CLEAR) == 1,
                    f"title screen after the credits {title}, game clear {self.flag(FLAG_SYS_GAME_CLEAR)}, "
                    f"map {self.map_id()}, party {species}")

    def set_options(self):
        """The Options menu's battle style SET (no "will you switch?" when a trainer sends out the next
        Pokemon) and battle scene OFF, as many players choose: bits 9 and 10 of SaveBlock2's options word."""
        addr = self.sb2() + 0x14
        self.g.cmd(f"write16 {addr} {self.u16(addr) | 1 << 9 | 1 << 10}")

    def chapter(self, name):
        if name != "opening":
            self.set_options()
        if name in BOSSES:
            self.boss(name)
        elif name == "route1":
            self.give(SB1_BALLS, BALL_SLOTS, ITEM_POKE_BALL, self.bag_count(ITEM_POKE_BALL, SB1_BALLS, BALL_SLOTS))
            self.dexnav_catch(ROUTE1, name)
        elif name == "route25":
            self.give(SB1_BALLS, BALL_SLOTS, ITEM_GREAT_BALL, 10)  # Great Balls from the Cerulean Mart
            self.dexnav_catch(ROUTE25, name)
        elif name == "route15":
            self.give(SB1_BALLS, BALL_SLOTS, ITEM_ULTRA_BALL, 10)  # Ultra Balls from the Fuchsia Mart
            self.dexnav_catch(ROUTE15, name)
        else:
            getattr(self, name)()
        if name != "league":
            self.end_chapter(name)


def main():
    rom, elf = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    first = sys.argv[3] if len(sys.argv) > 3 else CHAPTERS[0]
    last = sys.argv[4] if len(sys.argv) > 4 else CHAPTERS[-1]
    p = Playthrough(rom, elf)
    t0 = time.time()
    import emu
    todo = CHAPTERS[CHAPTERS.index(first):CHAPTERS.index(last) + 1]
    try:
        if first != CHAPTERS[0]:
            p.g.start()
            p.g.cmd(f"load {os.path.join(p.out, CHAPTERS[CHAPTERS.index(first) - 1] + '.State')}")
        for name in todo:
            t1 = time.time()
            n = len(p.results)
            p.chapter(name)
            print(f"{name}: {time.time() - t1:.0f}s, " + "; ".join(("PASS " if ok else "FAIL ") + c
                                                                for c, ok, _ in p.results[n:]), flush=True)
    except Exception as e:  # a stalled game or a lost emulator: record it, still write the results
        p.record("stall", False, f"{type(e).__name__}: {e}")
    finally:
        emu.stop()
    failed = [r for r in p.results if not r[1]]
    print(f"{len(p.results) - len(failed)}/{len(p.results)} passed in {time.time() - t0:.0f}s")
    with open(os.path.join(p.out, "playthrough.txt"), "w") as f:
        for check, ok, detail in p.results:
            f.write(("PASS " if ok else "FAIL ") + check + ": " + detail + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
