#include "global.h"
#include "gflib.h"
#include "pokemon_storage_system_internal.h"
#include "strings.h"

void BackupPokemonStorage(struct PokemonStorage * dest)
{
    *dest = *gPokemonStoragePtr;
}

void RestorePokemonStorage(struct PokemonStorage * src)
{
    *gPokemonStoragePtr = *src;
}

// Functions here are general utility functions.
u8 StorageGetCurrentBox(void)
{
    return gPokemonStoragePtr->currentBox;
}

void SetCurrentBox(u8 boxId)
{
    if (boxId < TOTAL_BOXES_COUNT)
        gPokemonStoragePtr->currentBox = boxId;
}

// Gunk's: boxed Pokémon are stored packed (Gunk_PackBoxMon), so every access unpacks a copy and writes repack it.
#define VALID_BOX_SLOT(boxId, boxPosition) ((boxId) < TOTAL_BOXES_COUNT && (boxPosition) < IN_BOX_COUNT)
#define PACKED_MON(boxId, boxPosition) (gPokemonStoragePtr->boxes[boxId][boxPosition])

u32 GetBoxMonDataAt(u8 boxId, u8 boxPosition, s32 request)
{
    struct BoxPokemon mon;

    if (VALID_BOX_SLOT(boxId, boxPosition))
    {
        Gunk_UnpackBoxMon(PACKED_MON(boxId, boxPosition), &mon);
        return GetBoxMonData(&mon, request);
    }
    else
        return 0;
}

void SetBoxMonDataAt(u8 boxId, u8 boxPosition, s32 request, const void *value)
{
    struct BoxPokemon mon;

    if (VALID_BOX_SLOT(boxId, boxPosition))
    {
        Gunk_UnpackBoxMon(PACKED_MON(boxId, boxPosition), &mon);
        SetBoxMonData(&mon, request, value);
        Gunk_PackBoxMon(&mon, PACKED_MON(boxId, boxPosition));
    }
}

u32 GetCurrentBoxMonData(u8 boxPosition, s32 request)
{
    return GetBoxMonDataAt(gPokemonStoragePtr->currentBox, boxPosition, request);
}

void SetCurrentBoxMonData(u8 boxPosition, s32 request, const void *value)
{
    SetBoxMonDataAt(gPokemonStoragePtr->currentBox, boxPosition, request, value);
}

void GetBoxMonNickAt(u8 boxId, u8 boxPosition, u8 *dst)
{
    struct BoxPokemon mon;

    if (VALID_BOX_SLOT(boxId, boxPosition))
    {
        Gunk_UnpackBoxMon(PACKED_MON(boxId, boxPosition), &mon);
        GetBoxMonData(&mon, MON_DATA_NICKNAME, dst);
    }
    else
        *dst = EOS;
}

void SetBoxMonNickAt(u8 boxId, u8 boxPosition, const u8 *nick)
{
    SetBoxMonDataAt(boxId, boxPosition, MON_DATA_NICKNAME, nick);
}

u32 GetAndCopyBoxMonDataAt(u8 boxId, u8 boxPosition, s32 request, void *dst)
{
    struct BoxPokemon mon;

    if (VALID_BOX_SLOT(boxId, boxPosition))
    {
        Gunk_UnpackBoxMon(PACKED_MON(boxId, boxPosition), &mon);
        return GetBoxMonData(&mon, request, dst);
    }
    else
        return 0;
}

void SetBoxMonAt(u8 boxId, u8 boxPosition, struct BoxPokemon * src)
{
    if (VALID_BOX_SLOT(boxId, boxPosition))
        Gunk_PackBoxMon(src, PACKED_MON(boxId, boxPosition));
}

void CopyBoxMonAt(u8 boxId, u8 boxPosition, struct BoxPokemon * dst)
{
    if (VALID_BOX_SLOT(boxId, boxPosition))
        Gunk_UnpackBoxMon(PACKED_MON(boxId, boxPosition), dst);
}

void CreateBoxMonAt(u8 boxId, u8 boxPosition, u16 species, u8 level, u8 fixedIV, u8 hasFixedPersonality, u32 personality, u8 otIDType, u32 otID)
{
    struct BoxPokemon mon;

    if (VALID_BOX_SLOT(boxId, boxPosition))
    {
        CreateBoxMon(&mon,
                     species,
                     level,
                     fixedIV,
                     hasFixedPersonality, personality,
                     otIDType, otID);
        Gunk_PackBoxMon(&mon, PACKED_MON(boxId, boxPosition));
    }
}

void ZeroBoxMonAt(u8 boxId, u8 boxPosition)
{
    // an all-zero packed Pokémon unpacks to an all-zero (empty) BoxPokemon
    if (VALID_BOX_SLOT(boxId, boxPosition))
        memset(PACKED_MON(boxId, boxPosition), 0, GUNK_PACKED_BOX_MON_SIZE);
}

void BoxMonAtToMon(u8 boxId, u8 boxPosition, struct Pokemon * dst)
{
    struct BoxPokemon mon;

    if (VALID_BOX_SLOT(boxId, boxPosition))
    {
        Gunk_UnpackBoxMon(PACKED_MON(boxId, boxPosition), &mon);
        BoxMonToMon(&mon, dst);
    }
}

// Gunk's: a save from vanilla FireRed (or a Gunk's build before 16 boxes) has 14 boxes of 80-byte BoxPokemon.
// Called after a save is loaded: converts that layout to the packed one in place. Packed Pokémon i ends before
// vanilla Pokémon i + 1 starts (70 * (i + 1) <= 80 * (i + 1)), so converting in order never overwrites one unread.
void Gunk_UpgradeBoxStorage(void)
{
    u8 names[VANILLA_TOTAL_BOXES_COUNT][BOX_NAME_LENGTH + 1];
    u8 wallpapers[VANILLA_TOTAL_BOXES_COUNT];
    u8 *base = (u8 *)gPokemonStoragePtr;
    u8 *packed = &gPokemonStoragePtr->boxes[0][0][0];
    struct BoxPokemon mon;
    u16 i;

    if (gPokemonStoragePtr->gunkFormat == GUNK_BOX_FORMAT)
        return;
    memcpy(names, base + 4 + VANILLA_TOTAL_BOXES_COUNT * IN_BOX_COUNT * sizeof(struct BoxPokemon), sizeof(names));
    memcpy(wallpapers, base + 4 + VANILLA_TOTAL_BOXES_COUNT * IN_BOX_COUNT * sizeof(struct BoxPokemon) + sizeof(names), sizeof(wallpapers));
    for (i = 0; i < VANILLA_TOTAL_BOXES_COUNT * IN_BOX_COUNT; i++)
    {
        memcpy(&mon, base + 4 + i * sizeof(struct BoxPokemon), sizeof(mon));
        Gunk_PackBoxMon(&mon, packed + i * GUNK_PACKED_BOX_MON_SIZE);
    }
    memset(packed + VANILLA_TOTAL_BOXES_COUNT * IN_BOX_COUNT * GUNK_PACKED_BOX_MON_SIZE, 0,
           (TOTAL_BOXES_COUNT - VANILLA_TOTAL_BOXES_COUNT) * IN_BOX_COUNT * GUNK_PACKED_BOX_MON_SIZE);
    for (i = 0; i < TOTAL_BOXES_COUNT; i++)
    {
        if (i < VANILLA_TOTAL_BOXES_COUNT)
        {
            memcpy(gPokemonStoragePtr->boxNames[i], names[i], BOX_NAME_LENGTH + 1);
            gPokemonStoragePtr->boxWallpapers[i] = wallpapers[i];
        }
        else
        {
            u8 *dest = StringCopy(gPokemonStoragePtr->boxNames[i], gText_Box);
            ConvertIntToDecimalStringN(dest, i + 1, STR_CONV_MODE_LEFT_ALIGN, 2);
            gPokemonStoragePtr->boxWallpapers[i] = i % (MAX_DEFAULT_WALLPAPER + 1);
        }
    }
    if (gPokemonStoragePtr->currentBox >= TOTAL_BOXES_COUNT)
        gPokemonStoragePtr->currentBox = 0;
    gPokemonStoragePtr->gunkFormat = GUNK_BOX_FORMAT;
}

u8 *GetBoxNamePtr(u8 boxId)
{
    if (boxId < TOTAL_BOXES_COUNT)
        return gPokemonStoragePtr->boxNames[boxId];
    else
        return NULL;
}

u8 GetBoxWallpaper(u8 boxId)
{
    if (boxId < TOTAL_BOXES_COUNT)
        return gPokemonStoragePtr->boxWallpapers[boxId];
    else
        return 0;
}

void SetBoxWallpaper(u8 boxId, u8 wallpaperId)
{
    if (boxId < TOTAL_BOXES_COUNT && wallpaperId < WALLPAPER_COUNT)
        gPokemonStoragePtr->boxWallpapers[boxId] = wallpaperId;
}

s16 SeekToNextMonInBox(struct BoxPokemon * boxMons, s8 curIndex, u8 maxIndex, u8 flags)
{
    // flags:
    // bit 0: Allow eggs
    // bit 1: Search backwards
    s16 i;
    s16 adder;
    if (flags == 0 || flags == 1)
        adder = 1;
    else
        adder = -1;

    if (flags == 1 || flags == 3)
    {
        for (i = curIndex + adder; i >= 0 && i <= maxIndex; i += adder)
        {
            if (GetBoxMonData(&boxMons[i], MON_DATA_SPECIES) != SPECIES_NONE)
                return i;
        }
    }
    else
    {
        for (i = curIndex + adder; i >= 0 && i <= maxIndex; i += adder)
        {
            if (GetBoxMonData(&boxMons[i], MON_DATA_SPECIES) != SPECIES_NONE
                && !GetBoxMonData(&boxMons[i], MON_DATA_IS_EGG))
                return i;
        }
    }

    return -1;
}
