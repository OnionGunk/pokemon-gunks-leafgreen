#include "global.h"
#include "gflib.h"
#include "battle.h"
#include "battle_setup.h"
#include "event_data.h"
#include "event_object_movement.h"
#include "field_effect.h"
#include "field_effect_helpers.h"
#include "field_player_avatar.h"
#include "fieldmap.h"
#include "gunk_dexnav.h"
#include "metatile_behavior.h"
#include "pokedex.h"
#include "pokemon.h"
#include "random.h"
#include "field_specials.h"
#include "safari_zone.h"
#include "script.h"
#include "string_util.h"
#include "wild_encounter.h"
#include "constants/battle.h"
#include "constants/field_effects.h"
#include "data.h"
#include "constants/species.h"
#include "constants/items.h"
#include "constants/abilities.h"

// Gunk's DexNav (key item). Pick one of the area's grass or surfing Pokemon on the DexNav screen
// (src/gunk_dexnav_screen.c) and it hides nearby, in a patch of rustling grass or of rippling water; step (or surf)
// into the patch to battle it. Every Pokemon it finds is a normal wild
// roll for that map slot (same species, level range and RNG method as a random encounter). The search level
// (one per species, raised by every DexNav battle) and the chain (DexNav battles in a row against the same
// species that end in a win or a catch) only decide how many of those normal rolls are made: the best one is
// kept, a shiny first, otherwise the one with the highest IV total.
//
// Saved data: SaveBlock1's unused 400 bytes (vanilla never writes them, so old saves read as all zero):
// bytes 0-385 are the search level of each National Dex number 1-386, 386-387 the chain species, 388 the chain.

#define SEARCH_LEVELS_COUNT 386
#define CHAIN_SPECIES_OFFSET 386
#define CHAIN_COUNT_OFFSET 388
#define MAX_SEARCH_LEVEL 255
#define MAX_CHAIN 255

#define PATCH_MIN_DIST 2
#define PATCH_MAX_DIST 5
#define SEARCH_FRAMES 600 // a search lasts 10 seconds of the player being free to walk
#define PATCH_SHAKE_FRAMES 30 // the patch shakes twice a second

#define LIST_MAX DEXNAV_LIST_MAX

struct DexNavSearch
{
    u16 species;
    s16 x, y;
    u8 mapGroup;
    u8 mapNum;
    u16 framesLeft;
    u8 spriteId;
    bool8 active;
    bool8 inBattle;
    bool8 gotAwayPending; // timed out: say so once the player can be told
    u8 area; // WILD_AREA_LAND or WILD_AREA_WATER
    u8 rippleTimer;
    u32 seed; // the RNG state the chosen roll starts from
    struct GunkDexNavRoll roll; // the Pokemon the patch holds (the field search bar shows it)
    u16 heldItem; // what it holds (ChooseHeldItem); SetWildMonHeldItem gives it this instead of its own roll
};

static EWRAM_DATA struct DexNavSearch sSearch = {0};
static EWRAM_DATA u16 sListSpecies[LIST_MAX] = {0};
static EWRAM_DATA u8 sListArea[LIST_MAX] = {0};
static EWRAM_DATA u8 sListMethod[LIST_MAX] = {0}; // DEXNAV_METHOD_*
static EWRAM_DATA u8 sListCount = 0;

static const u8 sText_Unseen[] = _("?????");

#define HELD_ITEM_COMMON_MAX 75
#define HELD_ITEM_RARE_MAX   20
// with a Compound Eyes lead, as in Gen 4 (and Gunk's Platinum): 60% and 20% to start, each cap 10 higher
#define HELD_ITEM_COMPOUND_EYES_COMMON 60
#define HELD_ITEM_COMPOUND_EYES_RARE   20
#define HELD_ITEM_COMPOUND_EYES_CAP    10

// The patch: the grass rustle (FLDEFF_UNUSED_GRASS's frames), replayed from the start every PATCH_SHAKE_FRAMES:
// 6 frames still, then the 8 rustle frames at 3 frames each. (The field effect's own animation shakes once, then
// only wiggles its last two frames.)
static const union AnimCmd sAnim_PatchShake[] =
{
    ANIMCMD_FRAME(0, 6),
    ANIMCMD_FRAME(1, 3),
    ANIMCMD_FRAME(2, 3),
    ANIMCMD_FRAME(3, 3),
    ANIMCMD_FRAME(4, 3),
    ANIMCMD_FRAME(5, 3),
    ANIMCMD_FRAME(6, 3),
    ANIMCMD_FRAME(7, 3),
    ANIMCMD_FRAME(8, 3),
    ANIMCMD_JUMP(0),
};

static const union AnimCmd *const sAnims_PatchShake[] = {sAnim_PatchShake};

extern const u8 EventScript_GunkDexNavGotAway[];

static u8 *SearchData(void)
{
    return gSaveBlock1Ptr->gunkDexNav;
}

static u8 GetSearchLevel(u16 species)
{
    u16 dexNum = SpeciesToNationalPokedexNum(species);

    if (dexNum == 0 || dexNum > SEARCH_LEVELS_COUNT)
        return 0;
    return SearchData()[dexNum - 1];
}

static void RaiseSearchLevel(u16 species)
{
    u16 dexNum = SpeciesToNationalPokedexNum(species);

    if (dexNum != 0 && dexNum <= SEARCH_LEVELS_COUNT && SearchData()[dexNum - 1] < MAX_SEARCH_LEVEL)
        SearchData()[dexNum - 1]++;
}

static u16 GetChainSpecies(void)
{
    return SearchData()[CHAIN_SPECIES_OFFSET] | (SearchData()[CHAIN_SPECIES_OFFSET + 1] << 8);
}

static void SetChain(u16 species, u8 count)
{
    SearchData()[CHAIN_SPECIES_OFFSET] = species & 0xFF;
    SearchData()[CHAIN_SPECIES_OFFSET + 1] = species >> 8;
    SearchData()[CHAIN_COUNT_OFFSET] = count;
}

static u8 GetChain(u16 species)
{
    if (GetChainSpecies() != species)
        return 0;
    return SearchData()[CHAIN_COUNT_OFFSET];
}

// How many normal wild rolls a search makes: 1, plus 1 per 10 search levels (up to 10), plus 1 per 4 links of
// the chain (up to 10). At most 21 rolls: shiny odds about 1 in 390, and the best IVs of 21 Pokemon.
static u8 GetRollCount(u16 species)
{
    u8 level = GetSearchLevel(species);
    u8 chain = GetChain(species);

    if (level > 100)
        level = 100;
    if (chain > 40)
        chain = 40;
    return 1 + level / 10 + chain / 4;
}

static void StopPatchSprite(void)
{
    struct Sprite *sprite = &gSprites[sSearch.spriteId];

    if (sSearch.area == WILD_AREA_WATER)
    {
        sSearch.spriteId = MAX_SPRITES; // the ripples end by themselves
        return;
    }
    if (sSearch.spriteId < MAX_SPRITES && sprite->inUse && sprite->data[0] == FLDEFF_UNUSED_GRASS
     && sprite->callback == WaitFieldEffectSpriteAnim)
        FieldEffectStop(sprite, FLDEFF_UNUSED_GRASS);
    sSearch.spriteId = MAX_SPRITES;
}

static bool8 IsPatchSpriteAlive(void)
{
    struct Sprite *sprite = &gSprites[sSearch.spriteId];

    if (sSearch.area == WILD_AREA_WATER) // ripples end by themselves: a new one twice a second
        return ++sSearch.rippleTimer < PATCH_SHAKE_FRAMES;

    return sSearch.spriteId < MAX_SPRITES && sprite->inUse && sprite->data[0] == FLDEFF_UNUSED_GRASS
        && sprite->callback == WaitFieldEffectSpriteAnim;
}

static void SpawnPatchSprite(void)
{
    if (sSearch.area == WILD_AREA_WATER)
    {
        s16 x = sSearch.x, y = sSearch.y;

        SetSpritePosToOffsetMapCoords(&x, &y, 8, 8);
        gFieldEffectArguments[0] = x;
        gFieldEffectArguments[1] = y + 4;
        gFieldEffectArguments[2] = 151; // subpriority, as a surfer's own ripples
        gFieldEffectArguments[3] = 3;
        FieldEffectStart(FLDEFF_RIPPLE);
        sSearch.spriteId = MAX_SPRITES;
        sSearch.rippleTimer = 0;
        return;
    }
    gFieldEffectArguments[0] = sSearch.x;
    gFieldEffectArguments[1] = sSearch.y;
    gFieldEffectArguments[2] = 0; // subpriority
    gFieldEffectArguments[3] = 2; // OAM priority, as the grass the player walks through
    sSearch.spriteId = FieldEffectStart(FLDEFF_UNUSED_GRASS);
    if (sSearch.spriteId < MAX_SPRITES)
    {
        gSprites[sSearch.spriteId].anims = sAnims_PatchShake;
        StartSpriteAnim(&gSprites[sSearch.spriteId], 0);
    }
}

static void EndSearch(void)
{
    StopPatchSprite();
    sSearch.active = FALSE;
}

static bool8 IsOnSearchMap(void)
{
    return sSearch.mapGroup == gSaveBlock1Ptr->location.mapGroup && sSearch.mapNum == gSaveBlock1Ptr->location.mapNum;
}

static u8 AreaSlotCount(u8 area)
{
    switch (area)
    {
    case WILD_AREA_WATER:   return WATER_WILD_COUNT;
    case WILD_AREA_ROCKS:   return ROCK_WILD_COUNT;
    case WILD_AREA_FISHING: return FISH_WILD_COUNT;
    default:                return LAND_WILD_COUNT;
    }
}

// How the Pokemon in <area>'s <slot> is found. The fishing table is shared by the rods: slots 0-1 the Old Rod's, 2-4
// the Good Rod's, 5-9 the Super Rod's (ChooseWildMonIndex_Fishing).
static u8 SlotMethod(u8 area, u8 slot)
{
    switch (area)
    {
    case WILD_AREA_WATER:   return DEXNAV_METHOD_SURF;
    case WILD_AREA_ROCKS:   return DEXNAV_METHOD_ROCK_SMASH;
    case WILD_AREA_FISHING: return slot < 2 ? DEXNAV_METHOD_OLD_ROD : slot < 5 ? DEXNAV_METHOD_GOOD_ROD : DEXNAV_METHOD_SUPER_ROD;
    default:                return DEXNAV_METHOD_GRASS;
    }
}

static void AddAreaToList(u8 area)
{
    const struct WildPokemonInfo *info = Gunk_GetWildMonsInfo(area);
    u8 count = AreaSlotCount(area);
    u8 i, j;

    if (info == NULL)
        return;
    for (i = 0; i < count; i++)
    {
        u16 species = info->wildPokemon[i].species;

        if (species == SPECIES_NONE)
            continue;
        for (j = 0; j < sListCount; j++)
        {
            if (sListSpecies[j] == species && sListArea[j] == area)
                break;
        }
        if (j == sListCount)
        {
            sListSpecies[sListCount] = species;
            sListArea[sListCount] = area;
            sListMethod[sListCount] = SlotMethod(area, i); // a Pokemon on more than one rod: the first it's on
            sListCount++;
        }
    }
}

// special: lists the map's grass Pokemon, then its surfing Pokemon, then its fishing and Rock Smash Pokemon (the
// OTHER tab: shown, not searched for), for the DexNav screen; VAR_RESULT = how many
void Gunk_DexNavPrepareList(void)
{
    sListCount = 0;
    if (!GetSafariZoneFlag())
    {
        AddAreaToList(WILD_AREA_LAND);
        AddAreaToList(WILD_AREA_WATER);
        AddAreaToList(WILD_AREA_FISHING);
        AddAreaToList(WILD_AREA_ROCKS);
    }
    gSpecialVar_Result = sListCount;
}

u8 Gunk_DexNavListCount(void)
{
    return sListCount;
}

u16 Gunk_DexNavListSpecies(u8 i)
{
    return i < sListCount ? sListSpecies[i] : SPECIES_NONE;
}

u8 Gunk_DexNavListArea(u8 i)
{
    return i < sListCount ? sListArea[i] : WILD_AREA_LAND;
}

// The screen's tab for list row <i>: LAND, WATER, or OTHER (fishing and Rock Smash)
u8 Gunk_DexNavListTab(u8 i)
{
    switch (Gunk_DexNavListArea(i))
    {
    case WILD_AREA_LAND:  return DEXNAV_TAB_LAND;
    case WILD_AREA_WATER: return DEXNAV_TAB_WATER;
    default:              return DEXNAV_TAB_OTHER;
    }
}

u8 Gunk_DexNavListMethod(u8 i)
{
    return i < sListCount ? sListMethod[i] : DEXNAV_METHOD_GRASS;
}

// The levels list row <i>'s Pokemon comes at in its area: the lowest and highest of its encounter slots
void Gunk_DexNavLevelRange(u8 i, u8 *minLevel, u8 *maxLevel)
{
    const struct WildPokemonInfo *info;
    u8 slot, count;

    *minLevel = *maxLevel = 0;
    if (i >= sListCount)
        return;
    info = Gunk_GetWildMonsInfo(sListArea[i]);
    count = AreaSlotCount(sListArea[i]);
    if (info == NULL)
        return;
    for (slot = 0; slot < count; slot++)
    {
        const struct WildPokemon *mon = &info->wildPokemon[slot];

        // a fishing Pokemon's levels on its rod only
        if (mon->species != sListSpecies[i] || SlotMethod(sListArea[i], slot) != sListMethod[i])
            continue;
        if (*minLevel == 0 || mon->minLevel < *minLevel)
            *minLevel = mon->minLevel;
        if (mon->maxLevel > *maxLevel)
            *maxLevel = mon->maxLevel;
    }
}

u16 Gunk_DexNavChainSpecies(void)
{
    return GetChainSpecies();
}

u8 Gunk_DexNavSearchLevel(u16 species)
{
    return GetSearchLevel(species);
}

u8 Gunk_DexNavChain(u16 species)
{
    return GetChain(species);
}

// The row the screen's cursor starts on: the chained species if it is listed, else the first row
u8 Gunk_DexNavDefaultRow(void)
{
    u8 i;

    for (i = 0; i < sListCount; i++)
    {
        if (sListSpecies[i] == GetChainSpecies())
            return i;
    }
    return 0;
}

// The Pokemon the search finds, chosen as it starts: GetRollCount normal rolls are peeked at (the random numbers a
// roll draws, without making the Pokemon: 21 full ones cost half a second) and the best is kept, a shiny first,
// otherwise the highest IV total. Its RNG state is kept, and stepping onto the patch replays that roll for real.
static bool8 ChooseSearchRoll(void)
{
    u8 rolls, i;
    u32 bestScore = 0, otId = GetPlayerTrainerId();
    bool8 haveBest = FALSE;

    rolls = GetRollCount(sSearch.species);
    gGunkHoldVBlankRandom = TRUE; // no Random() from VBlank between a roll's draws
    for (i = 0; i < rolls; i++)
    {
        u32 seed = gRngValue, score;
        struct GunkDexNavRoll roll;

        if (!Gunk_PeekWildMonOfSpecies(sSearch.species, sSearch.area, &roll))
            break;
        score = roll.ivTotal;
        if (GET_SHINY_VALUE(otId, roll.personality) < SHINY_ODDS)
            score += 0x1000;
        if (!haveBest || score > bestScore)
        {
            sSearch.seed = seed;
            sSearch.roll = roll;
            bestScore = score;
            haveBest = TRUE;
        }
        if (score >= 0x1000)
            break;
    }
    gGunkHoldVBlankRandom = FALSE;
    return haveBest;
}

// A lead (the first party slot, not an egg) with Compound Eyes: in Gen 4 and Gunk's Platinum it makes wild held items
// more likely. Gen 3 has no such effect, so it's only the DexNav's.
static bool8 LeadHasCompoundEyes(void)
{
    return GetMonData(&gPlayerParty[0], MON_DATA_SPECIES, NULL) != SPECIES_NONE
        && !GetMonData(&gPlayerParty[0], MON_DATA_IS_EGG, NULL)
        && GetMonAbility(&gPlayerParty[0]) == ABILITY_COMPOUND_EYES;
}

// What the searched Pokemon holds, chosen as the search starts: the species' own wild items (so it stays a legal wild
// Pokemon), with better odds as the search level and chain grow. Vanilla: 50% the common item, 5% the rare one (always
// the item when both are the same). Each 5 search levels add 1% to both, each link of the chain 2% to both, up to
// 75% and 20%. A Compound Eyes lead starts them at 60% and 20%, up to 85% and 30%.
static u16 ChooseHeldItem(u16 species)
{
    u16 common = gSpeciesInfo[species].itemCommon, rare = gSpeciesInfo[species].itemRare;
    u32 boost = GetSearchLevel(species) / 5 + 2 * GetChain(species);
    u32 commonOdds = 50 + boost, rareOdds = 5 + boost;
    u32 commonMax = HELD_ITEM_COMMON_MAX, rareMax = HELD_ITEM_RARE_MAX;
    u16 rnd;

    if (common == rare)
        return common;
    if (LeadHasCompoundEyes())
    {
        commonOdds = HELD_ITEM_COMPOUND_EYES_COMMON + boost;
        rareOdds = HELD_ITEM_COMPOUND_EYES_RARE + boost;
        commonMax += HELD_ITEM_COMPOUND_EYES_CAP;
        rareMax += HELD_ITEM_COMPOUND_EYES_CAP;
    }
    if (commonOdds > commonMax)
        commonOdds = commonMax;
    if (rareOdds > rareMax)
        rareOdds = rareMax;
    rnd = Random() % 100;
    if (rnd < rareOdds)
        return rare;
    if (rnd < rareOdds + commonOdds)
        return common;
    return ITEM_NONE;
}

// SetWildMonHeldItem, at the start of every wild battle: TRUE and *item = the searched Pokemon's item in a DexNav
// battle, FALSE in any other (which keeps the vanilla roll)
bool8 Gunk_DexNavHeldItem(u16 *item)
{
    if (!sSearch.active || !sSearch.inBattle)
        return FALSE;
    *item = sSearch.heldItem;
    return TRUE;
}

// The field search bar: what the searched Pokemon holds
u16 Gunk_DexNavSearchHeldItem(void)
{
    return sSearch.heldItem;
}

const struct GunkDexNavRoll *Gunk_DexNavSearchRoll(u16 *species)
{
    if (!sSearch.active || sSearch.inBattle)
        return NULL;
    *species = sSearch.species;
    return &sSearch.roll;
}

// special: VAR_0x8005 = the list row chosen. Places the patch; VAR_RESULT = TRUE if it found grass (or water) for it.
// STR_VAR_1 = the species' name (or "?????" if unseen), STR_VAR_2 = its search level, VAR_0x8006 = TRUE if it searches the water.
void Gunk_DexNavStartSearch(void)
{
    s16 px, py, x, y;
    s16 candidatesX[(2 * PATCH_MAX_DIST + 1) * (2 * PATCH_MAX_DIST + 1)];
    s16 candidatesY[(2 * PATCH_MAX_DIST + 1) * (2 * PATCH_MAX_DIST + 1)];
    u16 count = 0, pick;
    u16 species;

    gSpecialVar_Result = FALSE;
    if (gSpecialVar_0x8005 >= sListCount)
        return;
    // only grass and water Pokemon are searched for: the OTHER tab's fishing and Rock Smash ones are shown only
    if (sListArea[gSpecialVar_0x8005] != WILD_AREA_LAND && sListArea[gSpecialVar_0x8005] != WILD_AREA_WATER)
        return;
    species = sListSpecies[gSpecialVar_0x8005];
    gSpecialVar_0x8006 = sListArea[gSpecialVar_0x8005] == WILD_AREA_WATER;
    if (GetSetPokedexFlag(SpeciesToNationalPokedexNum(species), FLAG_GET_SEEN))
        StringCopy(gStringVar1, gSpeciesNames[species]);
    else
        StringCopy(gStringVar1, sText_Unseen);
    ConvertIntToDecimalStringN(gStringVar2, GetSearchLevel(species), STR_CONV_MODE_LEFT_ALIGN, 3);

    if (sSearch.active)
        EndSearch();

    // a tall grass (or surfable water) tile in sight, 2 to 5 tiles away, that the player could walk (or surf) onto
    PlayerGetDestCoords(&px, &py);
    for (y = py - PATCH_MAX_DIST; y <= py + PATCH_MAX_DIST; y++)
    {
        for (x = px - PATCH_MAX_DIST; x <= px + PATCH_MAX_DIST; x++)
        {
            s16 dx = x > px ? x - px : px - x;
            s16 dy = y > py ? y - py : py - y;

            if (dx + dy < PATCH_MIN_DIST || dx > 6 || dy > 4)
                continue;
            if (gSpecialVar_0x8006)
            {
                if (!MetatileBehavior_IsSurfableAndNotWaterfall(MapGridGetMetatileBehaviorAt(x, y)))
                    continue;
            }
            else if (!MetatileBehavior_IsTallGrass(MapGridGetMetatileBehaviorAt(x, y)))
            {
                continue;
            }
            if (MapGridGetCollisionAt(x, y) || GetObjectEventIdByXY(x, y) != OBJECT_EVENTS_COUNT)
                continue;
            candidatesX[count] = x;
            candidatesY[count] = y;
            count++;
        }
    }
    if (count == 0)
        return;

    pick = Random() % count;
    sSearch.species = species;
    sSearch.area = sListArea[gSpecialVar_0x8005];
    sSearch.x = candidatesX[pick];
    sSearch.y = candidatesY[pick];
    sSearch.mapGroup = gSaveBlock1Ptr->location.mapGroup;
    sSearch.mapNum = gSaveBlock1Ptr->location.mapNum;
    sSearch.framesLeft = SEARCH_FRAMES;
    sSearch.inBattle = FALSE;
    sSearch.gotAwayPending = FALSE;
    if (!ChooseSearchRoll())
        return;
    sSearch.heldItem = ChooseHeldItem(species);
    sSearch.active = TRUE;
    SpawnPatchSprite();
    gSpecialVar_Result = TRUE;
}

// Every overworld frame: keep the patch on screen (the field's sprites are rebuilt after menus), drop the search
// when the player leaves the map, and run its 10 seconds: they count only while the player is free to walk (not
// during a message or a script). When they run out the patch clears, the chain is lost, and once the player
// stands still with nothing else going on, a message says the Pokemon got away.
void Gunk_DexNavUpdate(void)
{
    Gunk_DexNavHudUpdate();
    if (sSearch.gotAwayPending && !ArePlayerFieldControlsLocked() && !ScriptContext_IsEnabled()
     && gPlayerAvatar.tileTransitionState == T_NOT_MOVING)
    {
        sSearch.gotAwayPending = FALSE;
        ScriptContext_SetupScript(EventScript_GunkDexNavGotAway);
        return;
    }
    if (!sSearch.active || sSearch.inBattle)
        return;
    if (!IsOnSearchMap())
    {
        sSearch.active = FALSE;
        sSearch.spriteId = MAX_SPRITES;
        return;
    }
    if (!IsPatchSpriteAlive())
        SpawnPatchSprite();
    if (!ArePlayerFieldControlsLocked() && --sSearch.framesLeft == 0)
    {
        EndSearch();
        SetChain(SPECIES_NONE, 0);
        sSearch.gotAwayPending = TRUE;
    }
}

// From the field's step check, before the random encounter roll: on the patch, battle the searched Pokemon.
bool8 Gunk_DexNavTryStartBattle(void)
{
    s16 x, y;
    bool8 haveRoll;

    if (!sSearch.active || sSearch.inBattle || !IsOnSearchMap())
        return FALSE;

    PlayerGetDestCoords(&x, &y);
    if (x != sSearch.x || y != sSearch.y)
        return FALSE;

    // the Pokemon chosen when the search started (ChooseSearchRoll): its roll, replayed from where it started
    gGunkHoldVBlankRandom = TRUE; // VBlank's own Random() would make the replay differ from the peek
    gRngValue = sSearch.seed;
    haveRoll = Gunk_GenerateWildMonOfSpecies(sSearch.species, sSearch.area);
    gGunkHoldVBlankRandom = FALSE;
    if (!haveRoll)
    {
        EndSearch();
        return FALSE;
    }

    StopPatchSprite();
    sSearch.inBattle = TRUE;
    Gunk_DexNavHudHide();
    StartWildBattle();
    return TRUE;
}

// From the end of every wild battle (CB2_EndWildBattle, CB2_EndScriptedWildBattle). The chain: a wild encounter
// with another species than the chain's breaks it (to 0); one with the same species keeps it, and a DexNav battle
// of it that is won or caught adds a link. A DexNav battle also raises the species' search level, unless the player
// ran from it (Run, Teleport, a Poke Doll): that breaks the chain and raises nothing.
void Gunk_DexNavOnBattleEnd(void)
{
    u16 species = sSearch.species;

    if (!sSearch.active || !sSearch.inBattle)
    {
        u16 wild = GetMonData(&gEnemyParty[0], MON_DATA_SPECIES);
        if (wild != SPECIES_NONE && wild != GetChainSpecies())
            SetChain(SPECIES_NONE, 0);
        return;
    }
    if (gBattleOutcome == B_OUTCOME_RAN || gBattleOutcome == B_OUTCOME_PLAYER_TELEPORTED)
        SetChain(SPECIES_NONE, 0);
    else
        RaiseSearchLevel(species);
    if (GetChainSpecies() != species)
        SetChain(species, 0);
    if (gBattleOutcome == B_OUTCOME_WON || gBattleOutcome == B_OUTCOME_CAUGHT)
    {
        u8 chain = GetChain(species);
        SetChain(species, chain < MAX_CHAIN ? chain + 1 : chain);
    }
    sSearch.active = FALSE;
    sSearch.inBattle = FALSE;
    sSearch.spriteId = MAX_SPRITES;
}
