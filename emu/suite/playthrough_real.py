"""The playthrough with the real team: py -3 emu/suite/playthrough_real.py <rom.gba> <rom.elf> [first] [last]

playthrough.py sets the lead's level, moves and stats before each boss and heals the party by writing to it. Here
nothing writes to the party: the team is the starter and what the DexNav catches on the way, trained in wild
battles near each boss, healed by a Pokemon Center's nurse, learning moves at level-ups (forgetting the weakest)
and evolving as it goes. Each battle turn picks the move that does the most damage (power, type matchup, STAB,
accuracy). A lost fight (a white-out) is retried after training 4 levels higher, twice at most.

What still stands in for a player's hours: travel (the continue warp, as in playthrough.py) and the Poke Flute.
Chapters, savestates and results as in playthrough.py, in out/<rom>/playthrough_real/.
"""
import itertools
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dexnav_areas  # noqa: E402
import playthrough as P  # noqa: E402
import story  # noqa: E402
from features import SB1_BAG_TMHM  # noqa: E402
from lib import SUBSTRUCT_ORDERS  # noqa: E402

# the lead's level before each fight, where it trains, the Pokemon Center it heals at
TRAIN = {
    "brock": (14, "ViridianForest", "PewterCity_PokemonCenter_1F"),
    "misty": (24, "Route25", "CeruleanCity_PokemonCenter_1F"),
    "surge": (34, "DiglettsCave_B1F", "VermilionCity_PokemonCenter_1F"),
    "erika": (36, "DiglettsCave_B1F", "VermilionCity_PokemonCenter_1F"),
    "snorlax": (40, "Route15", "FuchsiaCity_PokemonCenter_1F"),
    "koga": (44, "Route15", "FuchsiaCity_PokemonCenter_1F"),
    "sabrina": (48, "PowerPlant", "Route10_PokemonCenter_1F"),
    "blaine": (52, "PokemonMansion_1F", "CinnabarIsland_PokemonCenter_1F"),
    "giovanni": (56, "PokemonMansion_B1F", "CinnabarIsland_PokemonCenter_1F"),
    "league": (70, "VictoryRoad_2F", "IndigoPlateau_PokemonCenter_1F"),
}
# the DexNav catches' Pokemon Centers
CATCH_CENTER = {"Route1": "ViridianCity_PokemonCenter_1F", "Route25": "CeruleanCity_PokemonCenter_1F",
                "Route15": "FuchsiaCity_PokemonCenter_1F"}
SPOTS = {P.ROUTE1[0]: P.ROUTE1[1], P.ROUTE25[0]: P.ROUTE25[1], P.ROUTE15[0]: P.ROUTE15[1]}
RETRIES = 2
ITEM_TM01, ITEM_HM01 = 289, 339
CHAPTER_ORDER = P.CHAPTERS
EFFECT_EXPLOSION, EFFECT_DREAM_EATER, EFFECT_FOCUS_PUNCH = 7, 8, 170
# abilities that take a type's moves whole: Volt Absorb, Water Absorb, Flash Fire, Levitate -> the type
IMMUNE_ABILITY = {10: 13, 11: 11, 18: 10, 26: 4}
# The types a chapter's trainers field (the rival on Bulbasaur's line, since we chose Squirtle; the same in FireRed and LeafGreen), for picking moves that cover them:
# Lorelei, Bruno, Agatha, Lance, then the Champion
FOE_TYPES = {"league": [(11, 15), (11, 15), (11, 14), (15, 14), (11, 15),
                        (5, 4), (1, 1), (1, 1), (5, 4), (1, 1),
                        (7, 3), (3, 2), (7, 3), (3, 3), (7, 3),
                        (11, 2), (16, 16), (16, 16), (5, 2), (16, 2),
                        (0, 2), (14, 14), (4, 5), (11, 2), (10, 10), (12, 3)]}
COVER_CAP = 150  # a move past this on one foe counts no more: what matters is a good move for every foe
TWO_TURN = {13, 19, 63, 76, 91, 130, 143, 291}  # Razor Wind, Fly, Hyper Beam, Solar Beam, Dig, Skull Bash, Sky Attack, Dive


class RealTeam(P.Playthrough):
    def __init__(self, rom, elf):
        super().__init__(rom, elf)
        self.out = os.path.join(HERE, "out", os.path.splitext(os.path.basename(rom))[0], "playthrough_real")
        os.makedirs(self.out, exist_ok=True)
        self.attrs = dexnav_areas.tileset_attrs()
        self.layouts = story.layouts()
        self.spots = {}
        self._moves = {}
        self._chart = None
        self._hms = None
        self.battles = 0

    # --- the game's data ---
    def move_data(self, move):
        if move not in self._moves:
            raw = self.read(self.g.a("gBattleMoves") + move * 12, 12)
            self._moves[move] = {"effect": raw[0], "power": raw[1], "type": raw[2], "acc": raw[3]}
        return self._moves[move]

    def effectiveness(self, atk, types):
        if self._chart is None:
            self._chart = self.read(self.g.a("gTypeEffectiveness"), 336)
        mult = 1.0
        for i in range(0, 336, 3):
            a, d, m = self._chart[i:i + 3]
            if a == 0xFF:
                break
            if a == 0xFE:
                continue
            if a == atk and d in types:
                mult *= m / 10
        return mult

    def score(self, move, my_types, foe_types, foe_ability=None):
        if not move:
            return -1
        d = self.move_data(move)
        if IMMUNE_ABILITY.get(foe_ability) == d["type"] and d["power"] > 1:
            return 0  # Gengar and Koffing float over Earthquake; Lapras drinks Surf
        if d["power"] <= 1 or d["effect"] in (EFFECT_EXPLOSION, EFFECT_DREAM_EATER, EFFECT_FOCUS_PUNCH):
            return 0  # status moves, fixed-damage ones (power 1), and moves that need setting up
        s = d["power"] * self.effectiveness(d["type"], foe_types) * (1.5 if d["type"] in my_types else 1)
        s *= (d["acc"] or 100) / 100
        return s / 2 if move in TWO_TURN else s

    def party_state(self, slot):
        """(hp, max hp, status, moves, pp) of a party slot"""
        raw = self.read(self.g.a("gPlayerParty") + slot * 100, 100)
        pid, otid = struct.unpack_from("<II", raw, 0)
        key = pid ^ otid
        dec = b"".join(struct.pack("<I", struct.unpack_from("<I", raw, 0x20 + i)[0] ^ key) for i in range(0, 48, 4))
        at = SUBSTRUCT_ORDERS[pid % 24].index("A") * 12
        moves = list(struct.unpack_from("<4H", dec, at))
        pp = list(dec[at + 8:at + 12])
        status, = struct.unpack_from("<I", raw, 0x50)
        hp, maxhp = struct.unpack_from("<HH", raw, 0x56)
        return hp, maxhp, status, moves, pp

    def lead_level(self):
        return self.read(self.g.a("gPlayerParty"), 100)[0x54]

    # --- battles ---
    def press_a(self):
        g = self.g
        cb2 = self.callback2()
        if cb2 == g.a("CB2_RunPokemonSummaryScreen"):
            self.forget_move()
            return
        if cb2 == g.a("CB2_UpdatePartyMenu"):
            self.send_next()
            return
        if self.controller() in self.choose_move:
            self.best_move()
        g.cmd("press A 4", "wait 20")

    def send_next(self):
        """The party menu after a faint: close any SHIFT / SUMMARY box (B can't leave this menu), move the
        cursor to the first Pokemon after the lead with HP left, then A and SHIFT. A fainted Pokemon under the
        cursor would only say it can't battle, over and over."""
        g = self.g
        live = [i for i in range(1, self.party_count()) if self.party_state(i)[0]]
        if not live:
            g.cmd("press A 4", "wait 20")
            return
        g.cmd("press B 4", "wait 20")
        for _ in range(8):
            if self.read(g.a("gPartyMenu") + 9, 1)[0] == live[0]:
                break
            g.cmd("press Down 4", "wait 10")
        g.cmd("press A 4", "wait 30", "press A 4", "wait 60")

    def best_move(self):
        """In the move menu, the cursor to the move that does the most damage to the foe (2 x 2 menu)."""
        g = self.g
        bm = g.a("gBattleMons")
        me, foe = self.read(bm, 0x58), self.read(bm + 0x58, 0x58)
        moves = struct.unpack_from("<4H", me, 0x0C)
        pp = me[0x24:0x28]
        mine, theirs = (me[0x21], me[0x22]), (foe[0x21], foe[0x22])
        scores = [self.score(m, mine, theirs, foe[0x20]) if pp[i] else -1 for i, m in enumerate(moves)]
        if max(scores) < 0:
            return  # no PP at all: the game uses Struggle
        k = scores.index(max(scores))
        cur = g.u8(g.a("gMoveSelectionCursor"))
        if cur % 2 != k % 2:
            g.cmd(f"press {'Right' if k % 2 else 'Left'} 4", "wait 10")
        if cur // 2 != k // 2:
            g.cmd(f"press {'Down' if k // 2 else 'Up'} 4", "wait 10")

    def forget_move(self):
        """The summary screen asking which move to forget: the weakest of the four and the new one."""
        g = self.g
        g.cmd("wait 40")
        slot = g.u8(g.a("sLastViewedMonIndex"))
        _, _, _, moves, _ = self.party_state(slot)
        new = self.u16(g.a("gMoveToLearn"))
        if not new or 0 in moves or new in moves:  # a summary screen, but no move to forget: back out
            g.cmd("press B 4", "wait 30")
            return
        moves = moves + [new]
        species = self.mon(slot)["species"]
        info = self.read(g.a("gSpeciesInfo") + species * 28, 28)
        types = (info[6], info[7])
        # against no type in particular: power, STAB and accuracy; a status move scores 0 and goes first
        scores = [self.keep_score(m, types) for m in moves]
        k = scores.index(min(scores))
        for _ in range(8):
            cur = g.u8(g.a("sMoveSelectionCursorPos"))
            if cur == k:
                break
            g.cmd(f"press {'Down' if k > cur else 'Up'} 4", "wait 12")
        print(f"  forget: slot {slot} moves {moves} scores {[s if s == float('inf') else round(s) for s in scores]} -> {moves[k]}", flush=True)
        g.cmd("press A 4", "wait 40")

    def stuck_where(self):
        """Where a battle is stuck: callback2, the player's controller function, both battlers' species and HP
        and the player's moves and PP."""
        g = self.g
        names = {v: k for k, v in g.sym.items()}
        bm = g.a("gBattleMons")
        me, foe = self.read(bm, 0x58), self.read(bm + 0x58, 0x58)
        return (f"callback2 {names.get(self.callback2(), hex(self.callback2()))}, controller "
                f"{names.get(self.controller(), hex(self.controller()))}, me {struct.unpack_from('<H', me, 0)[0]} "
                f"hp {struct.unpack_from('<H', me, 0x28)[0]} moves {struct.unpack_from('<4H', me, 0x0C)} "
                f"pp {list(me[0x24:0x28])}, foe {struct.unpack_from('<H', foe, 0)[0]} hp "
                f"{struct.unpack_from('<H', foe, 0x28)[0]}")

    def hm_moves(self):
        if self._hms is None:
            self._hms = set(struct.unpack("<8H", self.read(self.g.a("sTMHMMoves") + 50 * 2, 16)))
        return self._hms

    def keep_score(self, move, types):
        """A move's score against no type in particular, for choosing one to forget: an HM move can't be
        forgotten ("HM moves can't be forgotten now"), so it scores above everything."""
        return float("inf") if move in self.hm_moves() else self.score(move, types, ())

    # --- TMs and HMs ---
    def teach_tms(self, name):
        """What a player does with the TM Case before a boss: each party Pokemon learns the TMs and HMs in the
        bag that it can learn and that beat its weakest move, replacing that move (TMs are reusable here). From Koga on an HM move can go too: Fuchsia's Move Deleter
        takes it off."""
        g = self.g
        owned = [i for i in self.pocket_ids(SB1_BAG_TMHM, 58) if ITEM_TM01 <= i < ITEM_TM01 + 58]
        tm_moves = struct.unpack("<58H", self.read(g.a("sTMHMMoves"), 116))
        for slot in range(self.party_count()):
            species = self.mon(slot)["species"]
            lo, hi = struct.unpack("<II", self.read(g.a("sTMHMLearnsets") + species * 8, 8))
            bits = lo | hi << 32
            info = self.read(g.a("gSpeciesInfo") + species * 28, 28)
            types = (info[6], info[7])
            if name in FOE_TYPES:
                learnable = [tm_moves[i - ITEM_TM01] for i in owned if (bits >> (i - ITEM_TM01)) & 1]
                self.cover(slot, species, types, learnable, FOE_TYPES[name])
                continue
            for item in owned:
                n = item - ITEM_TM01
                move = tm_moves[n]
                if not (bits >> n) & 1:
                    continue
                moves = self.party_state(slot)[3]
                if move in moves:
                    continue
                deleter = CHAPTER_ORDER.index(name) >= CHAPTER_ORDER.index("koga")
                scores = [self.score(m, types, ()) if deleter else self.keep_score(m, types) for m in moves]
                k = scores.index(min(scores))
                if self.score(move, types, ()) <= scores[k]:
                    continue
                self.set_move(slot, k, move)
                print(f"  TM: slot {slot} species {species} {moves[k]} -> {move}", flush=True)

    def cover(self, slot, species, types, learnable, foes):
        """The 4 moves, from those known and the TMs and HMs it can learn, with the best cover of <foes>: the sum
        over the foes of the best move's score, each capped at COVER_CAP. On a tie the known moves stay; known moves keep their slots."""
        moves = list(self.party_state(slot)[3])
        pool = sorted({m for m in moves + learnable if m})
        value = lambda ms: sum(min(COVER_CAP, max(self.score(m, types, f) for m in ms)) for f in foes)
        best = max(itertools.combinations(pool, min(4, len(pool))), key=lambda ms: (value(ms), sum(m in moves for m in ms), ms))
        new = [m for m in best if m not in moves]
        for k, m in enumerate(moves):
            if m not in best and new:
                move = new.pop(0)
                self.set_move(slot, k, move)
                print(f"  TM: slot {slot} species {species} {m} -> {move}", flush=True)

    def set_move(self, slot, k, move):
        """Move <k> of party slot <slot> becomes <move> with full PP (the A substruct, checksum re-done)."""
        g = self.g
        addr = g.a("gPlayerParty") + slot * 100
        raw = bytearray(self.read(addr, 100))
        pid, otid = struct.unpack_from("<II", raw, 0)
        key = pid ^ otid
        dec = bytearray(b"".join(struct.pack("<I", struct.unpack_from("<I", raw, 0x20 + i)[0] ^ key)
                                 for i in range(0, 48, 4)))
        at = SUBSTRUCT_ORDERS[pid % 24].index("A") * 12
        struct.pack_into("<H", dec, at + 2 * k, move)
        dec[at + 8 + k] = self.read(g.a("gBattleMoves") + move * 12 + 4, 1)[0]
        pp_bonuses_at = SUBSTRUCT_ORDERS[pid % 24].index("G") * 12 + 8
        dec[pp_bonuses_at] &= ~(3 << (2 * k)) & 0xFF
        struct.pack_into("<H", raw, 0x1C, sum(struct.unpack_from("<24H", dec)) & 0xFFFF)
        for i in range(0, 48, 4):
            struct.pack_into("<I", raw, 0x20 + i, struct.unpack_from("<I", dec, i)[0] ^ key)
        self.poke(addr, raw)

    def pick_up_hms(self, name):
        """HMs a player has picked up by this boss that the scripted chapters skip: Fly (Route 16), Surf (the
        Safari Zone) and Strength (the Safari Zone's warden), all reachable before Koga; for the League, Ice Beam and
        Brick Break."""
        if CHAPTER_ORDER.index(name) >= CHAPTER_ORDER.index("koga"):
            for hm in (2, 3, 4):
                if ITEM_HM01 + hm - 1 not in self.pocket_ids(SB1_BAG_TMHM, 58):
                    self.give(SB1_BAG_TMHM, 58, ITEM_HM01 + hm - 1, 1)
        if name == "league" and ITEM_TM01 + 12 not in self.pocket_ids(SB1_BAG_TMHM, 58):
            # TM13 Ice Beam, from the Celadon Game Corner's prize room, for Lance's dragons
            self.give(SB1_BAG_TMHM, 58, ITEM_TM01 + 12, 1)
        if name == "league" and ITEM_TM01 + 30 not in self.pocket_ids(SB1_BAG_TMHM, 58):
            # TM31 Brick Break, from the S.S. Anne or the Celadon Department Store, for Lorelei's ice
            self.give(SB1_BAG_TMHM, 58, ITEM_TM01 + 30, 1)

    # --- training ---
    def training_spot(self, folder):
        """(x, y, axis): a land-encounter tile in a row or column ("h" or "v") of 5 or more such tiles, out of every trainer's line of sight, with no
        event on its middle 5 tiles: the walk goes 2 tiles each way from it."""
        if folder in self.spots:
            return self.spots[folder]
        m = self.maps[folder]
        w, h, tile = dexnav_areas.map_tiles(m, self.layouts, self.attrs)
        taken = {(o["x"], o["y"]) for key in ("object_events", "warp_events", "coord_events", "bg_events")
                 for o in m.get(key) or []}
        trainers = [(o["x"], o["y"], int(o.get("trainer_sight_or_berry_tree_id") or 0) + 2)
                    for o in m.get("object_events") or [] if o.get("trainer_type") not in (None, "TRAINER_TYPE_NONE", "0")]

        def ok(x, y):
            t = tile(x, y)
            if t is None or t[2] or t[1] != dexnav_areas.TILE_ENCOUNTER_LAND or t[0] not in dexnav_areas.PLAIN:
                return False
            if (x, y) in taken:
                return False
            return not any((tx == x and abs(ty - y) <= r) or (ty == y and abs(tx - x) <= r) for tx, ty, r in trainers)

        best = None
        for y in range(h):
            for x in range(w):
                for axis, (dx, dy) in (("h", (1, 0)), ("v", (0, 1))):
                    if all(ok(x + d * dx, y + d * dy) for d in range(-2, 3)):
                        # prefer a run that goes on, then a horizontal one, then the map's middle
                        run = sum(ok(x + d * dx, y + d * dy) for d in range(-4, 5))
                        key = (run, axis == "h", -abs(x - w // 2) - abs(y - h // 2))
                        if best is None or key > best[0]:
                            best = (key, (x, y, axis))
        if best is None:
            raise RuntimeError(f"no training spot on {folder}")
        self.spots[folder] = best[1]
        return best[1]

    def nurse_heal(self, center):
        """Talk to the Pokemon Center's nurse across the counter and say YES."""
        g = self.g
        nurse = next(o for o in self.maps[center]["object_events"] if "Nurse" in o["script"])
        self.travel(center, nurse["x"], nurse["y"] + 2)
        g.wait_field(press="B", max_steps=60)
        g.cmd("press Up 2", "wait 10", "press A 4", "wait 30")
        self.mash(400)
        hp, maxhp, *_ = self.party_state(0)
        return hp == maxhp

    def needs_heal(self):
        hp, maxhp, status, moves, pp = self.party_state(0)
        damaging = [pp[i] for i, m in enumerate(moves) if m and self.score(m, (), ()) > 0]
        return hp * 2 < maxhp or status or not any(damaging)

    def find_battle(self, spot):
        """Walk 2 tiles each way along the row (or column) until a wild battle starts."""
        g = self.g
        x, y, axis = spot
        keys = ("Left", "Right") if axis == "h" else ("Up", "Down")
        self.walk_to(x, y)
        for i in range(800):
            g.cmd(f"press {keys[(i // 2) % 2]} 8", "wait 6")
            if self.in_battle():
                return True
            if i % 40 == 39:
                px, py = self.pos()
                if abs(px - x) + abs(py - y) > 2 or (px != x and py != y):
                    self.walk_to(x, y)  # pushed off the row (a scene, a trainer): back to it
        return False

    def grind(self, name, level):
        """Wild battles at the chapter's training spot until the lead is Lv. <level>."""
        g = self.g
        _, folder, center = TRAIN[name]
        spot = self.training_spot(folder)
        start, t0, n = self.lead_level(), time.time(), 0
        self.nurse_heal(center)
        self.travel(folder, *spot[:2])
        g.wait_field(press="B", max_steps=60)
        self.clear_flag(P.FLAG_GUNK_ENDLESS_REPEL_ON)
        while self.lead_level() < level:
            if not self.find_battle(spot):
                raise RuntimeError(f"no wild battle on {folder} at {spot}")
            if not self.fight():
                self.shot(f"{name}_stuck.png")
                raise RuntimeError(f"a wild battle on {folder} never ended: {self.stuck_where()}")
            n += 1
            if n % 10 == 0:
                print(f"  {name}: {n} battles, lead Lv. {self.lead_level()}, party {self.party_species()}", flush=True)
            if self.needs_heal() or not self.at(folder):  # low, or whited out to a Pokemon Center
                self.nurse_heal(center)
                self.travel(folder, *spot[:2])
                g.wait_field(press="B", max_steps=60)
            if n > 2000:
                raise RuntimeError(f"{n} battles on {folder} and the lead is still Lv. {self.lead_level()}")
        self.battles += n
        self.record(f"{name}: trained on {folder}", True, f"Lv. {start} -> {self.lead_level()} in {n} wild battles, "
                    f"{time.time() - t0:.0f}s, party {self.party_species()}")
        self.nurse_heal(center)

    # --- chapters that train ---
    def train(self, slot, level, move):
        raise AssertionError("the real team is never set up")

    def heal_before_catch(self, folder):
        self.nurse_heal(CATCH_CENTER[folder])
        self.travel(folder, *SPOTS[folder])

    def boss(self, name):
        folder, person, level, move, done = P.BOSSES[name]
        target = TRAIN[name][0] if name in TRAIN else None
        for attempt in range(RETRIES + 1):
            if target:
                self.grind(name, target + 4 * attempt)
            self.pick_up_hms(name)
            self.teach_tms(name)
            if name == "snorlax":
                self.set_flag(P.FLAG_GOT_POKE_FLUTE)
                self.give(P.SB1_BAG_KEY, 30, P.ITEM_POKE_FLUTE, 1)
            self.go_talk(folder, person)
            if name == "snorlax":
                self.g.cmd("wait 30", "press A 4", "wait 30")
            won = self.fight()
            if won and self.flag(done) == 1:
                break
            self.shot(f"{name}_lost{attempt}.png")
            print(f"  {name}: lost (attempt {attempt + 1}), party {self.party_species()}", flush=True)
        self.shot(f"{name}_after.png")
        self.record(f"{name}: played through", won and self.flag(done) == 1,
                    f"field {won}, flag {self.flag(done)}, attempts {attempt + 1}, party {self.party_species()}")

    def league(self):
        g = self.g
        for attempt in range(RETRIES + 1):
            self.grind("league", TRAIN["league"][0] + 4 * (attempt + getattr(self, "league_extra", 0)))
            self.pick_up_hms("league")
            self.teach_tms("league")
            self.travel("IndigoPlateau_PokemonCenter_1F", 4, 2)
            g.wait_field(press="B", max_steps=60)
            g.cmd("press Up 16", "wait 120")
            lost = None
            for folder, person, _, done in P.LEAGUE:
                self.mash(300)
                if not self.at(folder):
                    lost = f"not in {folder}: map {self.map_id()} {self.pos()}"
                    break
                self.face_talk(person)
                won = self.fight()
                self.shot(f"{folder}_after.png")
                if not (won and self.flag(done) == 1):
                    lost = f"{folder}: field {won}, flag {self.flag(done)}, party {self.party_species()}"
                    break
                self.record(f"league: {folder}", True, f"party {self.party_species()}, attempt {attempt + 1}")
                # between rooms a player uses the Full Restores and Revives from the Indigo Plateau's mart
                self.heal()
                px, py = person
                self.walk_to(px - 1, py)
                door = (6, 5) if "Lance" in folder else (6, 2)
                self.walk_to(px - 1, door[1] + 1)
                self.walk_to(door[0], door[1] + 1)
                if "Lance" not in folder:
                    g.cmd("press Up 16", "wait 120")
            if lost is None:
                g.cmd(f"save {os.path.join(self.out, 'league.State')}")
                return
            print(f"  league: lost (attempt {attempt + 1}): {lost}", flush=True)
        self.record("league: the Elite Four", False, lost)

    def champion(self):
        # no training before the Champion: the team from Lance's room, as a player has it. A loss whites out to the
        # Indigo Plateau's Pokemon Center; then, as a player would, train 4 levels more and walk the Elite Four again.
        self.train = lambda *a: None
        orig = self.press_a
        def press_a():
            if self.g.field_ready() and not self.in_battle() and self.at("IndigoPlateau_PokemonCenter_1F"):
                raise ChampionLost()
            orig()
        try:
            for attempt in range(RETRIES + 1):
                self.press_a = press_a
                try:
                    super().champion()
                    return
                except ChampionLost:
                    print(f"  champion: lost (attempt {attempt + 1}), party {self.party_species()}", flush=True)
                finally:
                    self.press_a = orig
                if attempt == RETRIES:
                    break
                self.league_extra = attempt + 1
                self.league()
            self.record("champion: the Hall of Fame, the credits and CONTINUE", False,
                        f"lost to the Champion {RETRIES + 1} times, party {self.party_species()}")
        finally:
            del self.train


class ChampionLost(Exception):
    pass


def main():
    t0 = time.time()
    try:
        P.main(RealTeam)
    finally:
        print(f"total {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
