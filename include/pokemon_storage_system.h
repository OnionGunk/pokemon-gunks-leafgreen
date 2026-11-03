#ifndef GUARD_POKEMON_STORAGE_SYSTEM_H
#define GUARD_POKEMON_STORAGE_SYSTEM_H

#include "global.h"
#include "pokemon.h"

#define TOTAL_BOXES_COUNT       16 // Gunk's: 14 in vanilla; boxed Pokémon are packed to fit (see Gunk_PackBoxMon)
#define IN_BOX_ROWS             5 // Number of rows, 6 Pokémon per row
#define IN_BOX_COLUMNS          6 // Number of columns, 5 Pokémon per column
#define IN_BOX_COUNT            (IN_BOX_ROWS * IN_BOX_COLUMNS)
#define BOX_NAME_LENGTH         8

/*
            COLUMNS
ROWS        0   1   2   3   4   5
            6   7   8   9   10  11
            12  13  14  15  16  17
            18  19  20  21  22  23
            24  25  26  27  28  29
*/

enum
{
    WALLPAPER_FOREST,
    WALLPAPER_CITY,
    WALLPAPER_DESERT,
    WALLPAPER_SAVANNA,
    WALLPAPER_CRAG,
    WALLPAPER_VOLCANO,
    WALLPAPER_SNOW,
    WALLPAPER_CAVE,
    WALLPAPER_BEACH,
    WALLPAPER_SEAFLOOR,
    WALLPAPER_RIVER,
    WALLPAPER_SKY,
    WALLPAPER_STARS,
    WALLPAPER_POKECENTER,
    WALLPAPER_TILES,
    WALLPAPER_SIMPLE,
    WALLPAPER_COUNT
};
#define MAX_DEFAULT_WALLPAPER WALLPAPER_SAVANNA

// Gunk's: vanilla stores 14 boxes of 80-byte BoxPokemon (0x83D0 bytes). Gunk's stores 16 boxes of
// GUNK_PACKED_BOX_MON_SIZE-byte packed Pokémon in the same 9 save sectors. gunkFormat lies past the end of the
// vanilla layout, where a vanilla save has zeros, so a vanilla save is recognized and converted on load.
#define GUNK_BOX_FORMAT 0x31584247 // "GBX1"
#define VANILLA_TOTAL_BOXES_COUNT 14

struct PokemonStorage
{
    /*0x0000*/ u8 currentBox;
    /*0x0001*/ u8 gunkPadding[3]; // the vanilla struct's alignment padding: boxes stay at the same offset
    /*0x0004*/ u8 boxes[TOTAL_BOXES_COUNT][IN_BOX_COUNT][GUNK_PACKED_BOX_MON_SIZE];
    /*0x8344*/ u8 boxNames[TOTAL_BOXES_COUNT][BOX_NAME_LENGTH + 1];
    /*0x83D4*/ u8 boxWallpapers[TOTAL_BOXES_COUNT];
    /*0x83E4*/ u32 gunkFormat;
};

u8 *GetBoxNamePtr(u8 boxNumber);
void Gunk_UpgradeBoxStorage(void);
void CopyBoxMonAt(u8 boxId, u8 boxPosition, struct BoxPokemon * dst);
void SetBoxMonAt(u8 boxId, u8 boxPosition, struct BoxPokemon * src);
void SetBoxMonNickAt(u8 boxId, u8 monPosition, const u8 *newNick);
s16 CompactPartySlots(void);
u32 GetBoxMonDataAt(u8 boxId, u8 monPosition, s32 request);
void ZeroBoxMonAt(u8 boxId, u8 monPosition);
void CB2_ReturnToPokeStorage(void);
void ResetPokemonStorageSystem(void);
u8 StorageGetCurrentBox(void);
void DrawTextWindowAndBufferTiles(const u8 *string, void *dst, u8 zero1, u8 zero2, u8 *buffer, s32 bytesToBuffer);

#endif // GUARD_POKEMON_STORAGE_SYSTEM_H
