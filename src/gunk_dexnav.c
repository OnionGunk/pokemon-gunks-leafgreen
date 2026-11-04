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

// Gunk's DexNav (key item). Pick one of the area's grass Pokemon from a list and it hides in a patch of
// rustling grass near the player; step into the patch to battle it. Every Pokemon it finds is a normal wild
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
};

static EWRAM_DATA struct DexNavSearch sSearch = {0};
static EWRAM_DATA u16 sListSpecies[LAND_WILD_COUNT] = {0};
static EWRAM_DATA u8 sListCount = 0;
static EWRAM_DATA u8 sListNames[LAND_WILD_COUNT][POKEMON_NAME_LENGTH + 1] = {0};

static const u8 sText_Unseen[] = _("----------");

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

    if (sSearch.spriteId < MAX_SPRITES && sprite->inUse && sprite->data[0] == FLDEFF_UNUSED_GRASS
     && sprite->callback == WaitFieldEffectSpriteAnim)
        FieldEffectStop(sprite, FLDEFF_UNUSED_GRASS);
    sSearch.spriteId = MAX_SPRITES;
}

static bool8 IsPatchSpriteAlive(void)
{
    struct Sprite *sprite = &gSprites[sSearch.spriteId];

    return sSearch.spriteId < MAX_SPRITES && sprite->inUse && sprite->data[0] == FLDEFF_UNUSED_GRASS
        && sprite->callback == WaitFieldEffectSpriteAnim;
}

static void SpawnPatchSprite(void)
{
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

// special: fills the list menu (LISTMENU_GUNK_DEXNAV) with the map's grass Pokemon; VAR_RESULT = how many
void Gunk_DexNavPrepareList(void)
{
    const struct WildPokemonInfo *info = Gunk_GetLandMonsInfo();
    u8 i, j;

    sListCount = 0;
    if (info != NULL && !GetSafariZoneFlag())
    {
        for (i = 0; i < LAND_WILD_COUNT; i++)
        {
            u16 species = info->wildPokemon[i].species;

            for (j = 0; j < sListCount; j++)
            {
                if (sListSpecies[j] == species)
                    break;
            }
            if (j == sListCount && species != SPECIES_NONE)
            {
                sListSpecies[sListCount] = species;
                if (GetSetPokedexFlag(SpeciesToNationalPokedexNum(species), FLAG_GET_SEEN))
                    StringCopy(sListNames[sListCount], gSpeciesNames[species]);
                else
                    StringCopy(sListNames[sListCount], sText_Unseen);
                sListCount++;
            }
        }
    }
    gSpecialVar_Result = sListCount;
}

u8 Gunk_DexNavListCount(void)
{
    return sListCount;
}

const u8 *Gunk_DexNavListLabel(u8 i)
{
    return sListNames[i];
}

// special: VAR_0x8005 = the list row chosen. Places the patch; VAR_RESULT = TRUE if it found grass for it.
// STR_VAR_1 = the species' name (or the unseen dashes), STR_VAR_2 = its search level.
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
    species = sListSpecies[gSpecialVar_0x8005];
    StringCopy(gStringVar1, sListNames[gSpecialVar_0x8005]);
    ConvertIntToDecimalStringN(gStringVar2, GetSearchLevel(species), STR_CONV_MODE_LEFT_ALIGN, 3);

    if (sSearch.active)
        EndSearch();

    // a tall grass tile in sight, 2 to 5 tiles away, that the player could walk onto
    PlayerGetDestCoords(&px, &py);
    for (y = py - PATCH_MAX_DIST; y <= py + PATCH_MAX_DIST; y++)
    {
        for (x = px - PATCH_MAX_DIST; x <= px + PATCH_MAX_DIST; x++)
        {
            s16 dx = x > px ? x - px : px - x;
            s16 dy = y > py ? y - py : py - y;

            if (dx + dy < PATCH_MIN_DIST || dx > 6 || dy > 4)
                continue;
            if (!MetatileBehavior_IsTallGrass(MapGridGetMetatileBehaviorAt(x, y)))
                continue;
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
    sSearch.x = candidatesX[pick];
    sSearch.y = candidatesY[pick];
    sSearch.mapGroup = gSaveBlock1Ptr->location.mapGroup;
    sSearch.mapNum = gSaveBlock1Ptr->location.mapNum;
    sSearch.framesLeft = SEARCH_FRAMES;
    sSearch.inBattle = FALSE;
    sSearch.gotAwayPending = FALSE;
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
    u8 rolls, i;
    u32 bestScore = 0, bestSeed = 0, otId;
    bool8 haveBest = FALSE;

    if (!sSearch.active || sSearch.inBattle || !IsOnSearchMap())
        return FALSE;

    PlayerGetDestCoords(&x, &y);
    if (x != sSearch.x || y != sSearch.y)
        return FALSE;

    // The rolls are only peeked at (the random numbers a roll draws, without making the Pokemon: 21 full ones cost
    // half a second); then the RNG goes back to where the best one started and that one is made for real.
    rolls = GetRollCount(sSearch.species);
    otId = GetPlayerTrainerId();
    gGunkHoldVBlankRandom = TRUE; // VBlank's own Random() would make the replay differ from the peek
    for (i = 0; i < rolls; i++)
    {
        u32 seed = gRngValue, personality, score;
        u8 ivTotal;

        if (!Gunk_PeekLandMonOfSpecies(sSearch.species, &personality, &ivTotal))
        {
            gGunkHoldVBlankRandom = FALSE;
            EndSearch();
            return FALSE;
        }
        score = ivTotal;
        if (GET_SHINY_VALUE(otId, personality) < SHINY_ODDS)
            score += 0x1000;
        if (!haveBest || score > bestScore)
        {
            bestSeed = seed;
            bestScore = score;
            haveBest = TRUE;
        }
        if (score >= 0x1000)
            break;
    }
    gRngValue = bestSeed;
    haveBest = Gunk_GenerateLandMonOfSpecies(sSearch.species);
    gGunkHoldVBlankRandom = FALSE;
    if (!haveBest)
    {
        EndSearch();
        return FALSE;
    }

    StopPatchSprite();
    sSearch.inBattle = TRUE;
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
