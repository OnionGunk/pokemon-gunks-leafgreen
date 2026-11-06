#include "global.h"
#include "gflib.h"
#include "battle_main.h"
#include "data.h"
#include "field_player_avatar.h"
#include "field_specials.h"
#include "gunk_dexnav.h"
#include "menu.h"
#include "pokemon.h"
#include "pokemon_summary_screen.h"
#include "script.h"
#include "string_util.h"
#include "wild_encounter.h"
#include "item.h"
#include "constants/abilities.h"
#include "constants/items.h"

// Gunk's DexNav search bar: while a search runs and the player is free to walk, a bar across the top of the field
// shows the Pokemon the patch holds (src/gunk_dexnav.c chooses it when the search starts): its name and level, a
// shiny mark, the species' search level and chain, its nature and ability, and one gold star per perfect IV.
// It hides during menus, messages and scripts, and goes once the search ends.
//
// Its window lives on the field's BG0 at tiles 0x240-0x2B7 (past the message box and frames, below the other BGs'
// tilemaps from 0xE000, tile 0x300) with BG palette 13, the map name pop-up's, reloaded each time the bar is shown.

#define HUD_BASE_TILE 0x240
#define HUD_PAL 13

enum {
    HUDCOL_TRANSPARENT,
    HUDCOL_BG,
    HUDCOL_TEXT,
    HUDCOL_SHADOW,
    HUDCOL_LABEL,
    HUDCOL_SHINY,
    HUDCOL_STAR,
    HUDCOL_STAR_OFF,
    HUDCOL_EDGE,
};

static const u16 sHudPalette[16] =
{
    [HUDCOL_TRANSPARENT] = RGB(0, 0, 0),
    [HUDCOL_BG]          = RGB(31, 31, 30),
    [HUDCOL_TEXT]        = RGB(7, 7, 8),
    [HUDCOL_SHADOW]      = RGB(22, 22, 21),
    [HUDCOL_LABEL]       = RGB(20, 7, 6),
    [HUDCOL_SHINY]       = RGB(29, 4, 4),
    [HUDCOL_STAR]        = RGB(31, 24, 4),
    [HUDCOL_STAR_OFF]    = RGB(24, 24, 23),
    [HUDCOL_EDGE]        = RGB(20, 18, 16),
};

static const u8 sHudColors_Text[]  = {HUDCOL_BG, HUDCOL_TEXT, HUDCOL_SHADOW};
static const u8 sHudColors_Label[] = {HUDCOL_BG, HUDCOL_LABEL, HUDCOL_SHADOW};
static const u8 sHudColors_Shiny[] = {HUDCOL_BG, HUDCOL_SHINY, HUDCOL_SHADOW};

static const u8 sText_Lv[]       = _(" Lv.");
static const u8 sText_Shiny[]    = _("SHINY");
static const u8 sText_SearchLv[] = _("SEARCH LV.");
static const u8 sText_Chain[]    = _("CHAIN");
static const u8 sText_IVs[]      = _("IVs");
static const u8 sText_Holds[]    = _("HOLDS");
static const u8 sText_Nothing[]  = _("nothing");

static const u8 sStar[7][8] =
{
    "...o...",
    "..ooo..",
    "ooooooo",
    ".ooooo.",
    "..ooo..",
    ".oo.oo.",
    "oo...oo",
};

static const struct WindowTemplate sHudWindowTemplate =
{
    .bg = 0,
    .tilemapLeft = 0,
    .tilemapTop = 0,
    .width = 30,
    .height = 5,
    .paletteNum = HUD_PAL,
    .baseBlock = HUD_BASE_TILE,
};

static EWRAM_DATA u8 sHudWindowId = WINDOW_NONE;
static EWRAM_DATA bool8 sHudShown = FALSE;

// From the overworld's BG setup: the field's windows were all just set up afresh, so the bar's is gone
void Gunk_DexNavHudReset(void)
{
    sHudWindowId = WINDOW_NONE;
    sHudShown = FALSE;
}

static void DrawStar(u16 x, u16 y, u8 color)
{
    u8 i, j;

    for (i = 0; i < 7; i++)
    {
        for (j = 0; j < 7; j++)
        {
            if (sStar[i][j] == 'o')
                FillWindowPixelRect(sHudWindowId, color, x + j, y + i, 1, 1);
        }
    }
}

static void PrintRight(u8 fontId, u16 right, u8 y, const u8 *colors, const u8 *str)
{
    AddTextPrinterParameterized3(sHudWindowId, fontId, right - GetStringWidth(fontId, str, 0), y, colors, TEXT_SKIP_DRAW, str);
}

static void DrawHud(u16 species, const struct GunkDexNavRoll *roll, u16 heldItem)
{
    u8 *end;
    u8 i, ability, x;
    s32 width;

    FillWindowPixelBuffer(sHudWindowId, PIXEL_FILL(HUDCOL_BG));
    FillWindowPixelRect(sHudWindowId, PIXEL_FILL(HUDCOL_EDGE), 0, 39, 240, 1);

    // name, level, shiny
    end = StringCopy(gStringVar4, gSpeciesNames[species]);
    end = StringCopy(end, sText_Lv);
    ConvertIntToDecimalStringN(end, roll->level, STR_CONV_MODE_LEFT_ALIGN, 3);
    AddTextPrinterParameterized3(sHudWindowId, FONT_SMALL, 4, 2, sHudColors_Text, TEXT_SKIP_DRAW, gStringVar4);
    width = GetStringWidth(FONT_SMALL, gStringVar4, 0);
    if (GET_SHINY_VALUE(GetPlayerTrainerId(), roll->personality) < SHINY_ODDS)
        AddTextPrinterParameterized3(sHudWindowId, FONT_SMALL, 4 + width + 6, 2, sHudColors_Shiny, TEXT_SKIP_DRAW, sText_Shiny);

    // search level and chain, on the right
    ConvertIntToDecimalStringN(gStringVar4, Gunk_DexNavChain(species), STR_CONV_MODE_LEFT_ALIGN, 3);
    PrintRight(FONT_SMALL, 236, 2, sHudColors_Text, gStringVar4);
    x = 236 - GetStringWidth(FONT_SMALL, gStringVar4, 0) - 3;
    PrintRight(FONT_SMALL, x, 2, sHudColors_Label, sText_Chain);
    x -= GetStringWidth(FONT_SMALL, sText_Chain, 0) + 8;
    ConvertIntToDecimalStringN(gStringVar4, Gunk_DexNavSearchLevel(species), STR_CONV_MODE_LEFT_ALIGN, 3);
    PrintRight(FONT_SMALL, x, 2, sHudColors_Text, gStringVar4);
    x -= GetStringWidth(FONT_SMALL, gStringVar4, 0) + 3;
    PrintRight(FONT_SMALL, x, 2, sHudColors_Label, sText_SearchLv);

    // nature and ability
    ability = gSpeciesInfo[species].abilities[1] != ABILITY_NONE && (roll->personality & 1)
            ? gSpeciesInfo[species].abilities[1] : gSpeciesInfo[species].abilities[0];
    end = StringCopy(gStringVar4, gNatureNamePointers[roll->personality % NUM_NATURES]);
    *end++ = CHAR_SPACE;
    *end++ = CHAR_SPACE;
    StringCopy(end, gAbilityNames[ability]);
    AddTextPrinterParameterized3(sHudWindowId, FONT_SMALL, 4, 17, sHudColors_Text, TEXT_SKIP_DRAW, gStringVar4);

    // one gold star per perfect IV (HP, Atk, Def, Speed, SpAtk, SpDef in the order CreateMon draws them)
    x = 236 - 6 * 9;
    PrintRight(FONT_SMALL, x - 3, 17, sHudColors_Label, sText_IVs);
    for (i = 0; i < 6; i++)
    {
        u8 iv = (roll->ivWords[i / 3] >> (5 * (i % 3))) & MAX_IV_MASK;

        DrawStar(x + i * 9 + 1, 20, iv == MAX_PER_STAT_IVS ? HUDCOL_STAR : HUDCOL_STAR_OFF);
    }

    // what it holds
    AddTextPrinterParameterized3(sHudWindowId, FONT_SMALL, 4, 28, sHudColors_Label, TEXT_SKIP_DRAW, sText_Holds);
    x = 4 + GetStringWidth(FONT_SMALL, sText_Holds, 0) + 4;
    if (heldItem != ITEM_NONE)
        AddTextPrinterParameterized3(sHudWindowId, FONT_SMALL, x, 28, sHudColors_Text, TEXT_SKIP_DRAW, ItemId_GetName(heldItem));
    else
        AddTextPrinterParameterized3(sHudWindowId, FONT_SMALL, x, 28, sHudColors_Text, TEXT_SKIP_DRAW, sText_Nothing);
}

void Gunk_DexNavHudHide(void)
{
    if (sHudWindowId == WINDOW_NONE)
        return;
    ClearWindowTilemap(sHudWindowId);
    CopyWindowToVram(sHudWindowId, COPYWIN_MAP);
    RemoveWindow(sHudWindowId);
    sHudWindowId = WINDOW_NONE;
    sHudShown = FALSE;
}

// Every overworld frame (Gunk_DexNavUpdate): shown while a search runs and the player is free to walk
void Gunk_DexNavHudUpdate(void)
{
    u16 species;
    const struct GunkDexNavRoll *roll = Gunk_DexNavSearchRoll(&species);
    bool8 want = roll != NULL && !ArePlayerFieldControlsLocked() && !ScriptContext_IsEnabled();

    if (want == sHudShown)
        return;
    if (!want)
    {
        Gunk_DexNavHudHide();
        return;
    }
    sHudWindowId = AddWindow(&sHudWindowTemplate);
    if (sHudWindowId == WINDOW_NONE)
        return;
    LoadPalette(sHudPalette, BG_PLTT_ID(HUD_PAL), PLTT_SIZE_4BPP);
    DrawHud(species, roll, Gunk_DexNavSearchHeldItem());
    PutWindowTilemap(sHudWindowId);
    CopyWindowToVram(sHudWindowId, COPYWIN_FULL);
    sHudShown = TRUE;
}
