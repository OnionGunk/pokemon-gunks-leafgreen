#include "global.h"
#include "gflib.h"
#include "data.h"
#include "event_data.h"
#include "gunk_dexnav.h"
#include "help_system.h"
#include "menu.h"
#include "new_menu_helpers.h"
#include "overworld.h"
#include "pokedex.h"
#include "pokemon_icon.h"
#include "quest_log.h"
#include "region_map.h"
#include "scanline_effect.h"
#include "script.h"
#include "string_util.h"
#include "task.h"
#include "text_window.h"
#include "wild_encounter.h"
#include "constants/songs.h"

// Gunk's DexNav screen, on Gunk's Platinum's plan fitted to one 240x160 screen:
//  - a title bar: DEXNAV, the area's name, and how many of its Pokemon are caught;
//  - LAND and WATER tabs (L/R, or Up/Down past the grid's edge), each a 4x3 grid of cells: the Pokemon's menu
//    icon once seen, "?" before that, a ball mark once caught, the cursor's cell highlighted;
//  - a framed info panel for the highlighted Pokemon: name and status, where it's found, its level range, search
//    level and chain;
//  - the current chain under the grid, and the buttons in a footer.
// A starts a search for the highlighted Pokemon (src/gunk_dexnav.c places it nearby), B goes back.
//
// Opened by the script special Gunk_ShowDexNavScreen (data/scripts/gunk_dexnav.inc) after the screen fades to
// black; it returns to the field and goes on with the script, with VAR_RESULT = the list row picked, or 127.
//
// Each game's look (palette, colours, caught mark, strings) is in src/data/gunk_dexnav_skin.h; the frames are the
// player's own menu frame. No graphics files: the layout, the list getters of gunk_dexnav.h and the menu icons
// are all it needs, so the file fits any pret Gen 3 decomp. Porting: pokeemerald and pokeruby have no
// new_menu_helpers.h (DoScheduledBgTilemapCopiesToVram is in menu.h there) and no quest log (drop
// QuestLog_CutRecording).

#ifndef JOY_REPEAT
#define JOY_REPEAT(button) JOY_REPT(button) // pokefirered's name for it
#endif

#include "data/gunk_dexnav_skin.h"

#define GRID_COLUMNS 4
#define GRID_ROWS 3
#define CELL_SIZE 32
#define LIST_MAX (LAND_WILD_COUNT + WATER_WILD_COUNT)
#define NO_ROW 127
#define NUM_TABS 2 // WILD_AREA_LAND, WILD_AREA_WATER

#define FRAME_BASE_TILE 0x3E0
#define FRAME_PAL 14

enum {
    WIN_TITLE,
    WIN_TABS,
    WIN_GRID,
    WIN_CHAIN,
    WIN_INFO,
    WIN_FOOTER,
    WIN_COUNT,
};

// The emulator tests (emu/suite/dexnav_screen.py) read this struct: keep its layout or update them
struct DexNavScreen
{
    u8 count;
    u8 cursor; // list row
    u8 tab;    // WILD_AREA_LAND or WILD_AREA_WATER
    u8 state;
    u8 iconSpriteIds[LIST_MAX];
    u8 cellX[LIST_MAX]; // pixels, in the grid window
    u8 cellY[LIST_MAX];
    u8 row[LIST_MAX]; // in its tab's grid
    u8 col[LIST_MAX];
    u8 tabCount[NUM_TABS];
    bool8 helpWasEnabled; // FRLG's L/R Help is off while the screen uses L and R for its tabs
};

static EWRAM_DATA struct DexNavScreen *sDexNavScreen = NULL;

static void CB2_InitDexNavScreen(void);
static void CB2_DexNavScreen(void);
static void VBlankCB_DexNavScreen(void);
static void Task_DexNavScreen(u8 taskId);

static const struct BgTemplate sBgTemplates[] =
{
    {
        .bg = 0,
        .charBaseIndex = 0,
        .mapBaseIndex = 31,
        .screenSize = 0,
        .paletteMode = 0,
        .priority = 1,
        .baseTile = 0,
    },
};

static const struct WindowTemplate sWindowTemplates[] =
{
    [WIN_TITLE] = {
        .bg = 0,
        .tilemapLeft = 0,
        .tilemapTop = 0,
        .width = 30,
        .height = 2,
        .paletteNum = 15,
        .baseBlock = 1,
    },
    [WIN_TABS] = {
        .bg = 0,
        .tilemapLeft = 0,
        .tilemapTop = 2,
        .width = 16,
        .height = 2,
        .paletteNum = 15,
        .baseBlock = 61,
    },
    [WIN_GRID] = {
        .bg = 0,
        .tilemapLeft = 0,
        .tilemapTop = 4,
        .width = 16,
        .height = 12,
        .paletteNum = 15,
        .baseBlock = 93,
    },
    [WIN_CHAIN] = {
        .bg = 0,
        .tilemapLeft = 0,
        .tilemapTop = 16,
        .width = 16,
        .height = 2,
        .paletteNum = 15,
        .baseBlock = 285,
    },
    [WIN_INFO] = { // inside a frame: columns 16-29, rows 2-17
        .bg = 0,
        .tilemapLeft = 17,
        .tilemapTop = 3,
        .width = 12,
        .height = 14,
        .paletteNum = 15,
        .baseBlock = 317,
    },
    [WIN_FOOTER] = {
        .bg = 0,
        .tilemapLeft = 0,
        .tilemapTop = 18,
        .width = 30,
        .height = 2,
        .paletteNum = 15,
        .baseBlock = 485,
    },
    [WIN_COUNT] = DUMMY_WIN_TEMPLATE,
};

static bool8 IsSeen(u16 species)
{
    return GetSetPokedexFlag(SpeciesToNationalPokedexNum(species), FLAG_GET_SEEN);
}

static bool8 IsCaught(u16 species)
{
    return GetSetPokedexFlag(SpeciesToNationalPokedexNum(species), FLAG_GET_CAUGHT);
}

// special: open the screen (the script has faded to black)
void Gunk_ShowDexNavScreen(void)
{
    QuestLog_CutRecording();
    LockPlayerFieldControls();
    SetMainCallback2(CB2_InitDexNavScreen);
}

// Each tab's Pokemon fill its grid left to right, top to bottom
static void LayOutCells(void)
{
    u8 i;

    for (i = 0; i < sDexNavScreen->count; i++)
    {
        u8 tab = Gunk_DexNavListArea(i);
        u8 n = sDexNavScreen->tabCount[tab]++;

        sDexNavScreen->row[i] = n / GRID_COLUMNS;
        sDexNavScreen->col[i] = n % GRID_COLUMNS;
        sDexNavScreen->cellX[i] = sDexNavScreen->col[i] * CELL_SIZE;
        sDexNavScreen->cellY[i] = sDexNavScreen->row[i] * CELL_SIZE;
    }
}

static void CreateIcons(void)
{
    u8 i;

    LoadMonIconPalettes();
    for (i = 0; i < sDexNavScreen->count; i++)
    {
        u16 species = Gunk_DexNavListSpecies(i);

        sDexNavScreen->iconSpriteIds[i] = MAX_SPRITES;
        if (!IsSeen(species))
            continue;
        sDexNavScreen->iconSpriteIds[i] = CreateMonIcon(species, SpriteCallbackDummy,
                                    sDexNavScreen->cellX[i] + CELL_SIZE / 2,
                                    sWindowTemplates[WIN_GRID].tilemapTop * 8 + sDexNavScreen->cellY[i] + CELL_SIZE / 2 - 2,
                                    0, 0, FALSE);
    }
}

static void DrawCaughtMark(u8 windowId, u16 x, u16 y)
{
    u8 i, j;

    for (i = 0; i < 8; i++)
    {
        for (j = 0; j < 8; j++)
        {
            u8 color;

            switch (sDexNavCaughtMark[i][j])
            {
            case 'o': color = DXCOL_TEXT; break;
            case 'r': color = DXCOL_BALL; break;
            case 'w': color = DXCOL_WHITE; break;
            default: continue;
            }
            FillWindowPixelRect(windowId, color, x + j, y + i, 1, 1);
        }
    }
}

// A cell: a rounded box with a one-pixel edge
static void DrawCellBox(u16 x, u16 y, u8 fill, u8 edge)
{
    FillWindowPixelRect(WIN_GRID, PIXEL_FILL(edge), x + 2, y + 1, CELL_SIZE - 4, CELL_SIZE - 2);
    FillWindowPixelRect(WIN_GRID, PIXEL_FILL(edge), x + 1, y + 2, CELL_SIZE - 2, CELL_SIZE - 4);
    FillWindowPixelRect(WIN_GRID, PIXEL_FILL(fill), x + 2, y + 2, CELL_SIZE - 4, CELL_SIZE - 4);
}

static u8 CountCaught(u8 *total)
{
    u8 i, j, caught = 0;

    *total = 0;
    for (i = 0; i < sDexNavScreen->count; i++)
    {
        u16 species = Gunk_DexNavListSpecies(i);

        for (j = 0; j < i; j++)
        {
            if (Gunk_DexNavListSpecies(j) == species)
                break;
        }
        if (j < i)
            continue; // found both on land and on water: counted once
        (*total)++;
        if (IsCaught(species))
            caught++;
    }
    return caught;
}

static void DrawTitle(void)
{
    u8 mapName[32];
    u8 *end;
    u8 caught, total;
    s32 width;

    FillWindowPixelBuffer(WIN_TITLE, PIXEL_FILL(DXCOL_TITLE));
    AddTextPrinterParameterized3(WIN_TITLE, FONT_NORMAL, 6, 1, sDexNavColors_Title, TEXT_SKIP_DRAW, sDexNavText_Title);

    caught = CountCaught(&total);
    end = StringCopy(gStringVar4, sDexNavText_Caught);
    end = ConvertIntToDecimalStringN(end, caught, STR_CONV_MODE_LEFT_ALIGN, 2);
    *end++ = CHAR_SLASH;
    ConvertIntToDecimalStringN(end, total, STR_CONV_MODE_LEFT_ALIGN, 2);
    width = GetStringWidth(FONT_NORMAL, gStringVar4, 0);
    AddTextPrinterParameterized3(WIN_TITLE, FONT_NORMAL, 240 - 6 - width, 1, sDexNavColors_Title, TEXT_SKIP_DRAW, gStringVar4);

    GetMapName(mapName, gMapHeader.regionMapSectionId, 0);
    AddTextPrinterParameterized3(WIN_TITLE, FONT_SMALL, 56, 3, sDexNavColors_Title, TEXT_SKIP_DRAW, mapName);
    PutWindowTilemap(WIN_TITLE);
    CopyWindowToVram(WIN_TITLE, COPYWIN_FULL);
}

static void DrawTabs(void)
{
    u8 tab;

    FillWindowPixelBuffer(WIN_TABS, PIXEL_FILL(DXCOL_BACKDROP));
    for (tab = 0; tab < NUM_TABS; tab++)
    {
        bool8 on = tab == sDexNavScreen->tab;
        u16 x = 2 + tab * 50;
        const u8 *name = tab == WILD_AREA_WATER ? sDexNavText_Water : sDexNavText_Land;

        FillWindowPixelRect(WIN_TABS, PIXEL_FILL(on ? DXCOL_WHITE : DXCOL_TAB_OFF), x, 2, 48, 14);
        FillWindowPixelRect(WIN_TABS, PIXEL_FILL(on ? DXCOL_LABEL : DXCOL_TAB_OFF), x, 2, 48, 2);
        AddTextPrinterParameterized3(WIN_TABS, FONT_SMALL, x + (48 - GetStringWidth(FONT_SMALL, name, 0)) / 2, 4,
                                     on ? sDexNavColors_TabOn : sDexNavColors_TabOff, TEXT_SKIP_DRAW, name);
    }
    PutWindowTilemap(WIN_TABS);
    CopyWindowToVram(WIN_TABS, COPYWIN_FULL);
}

static void DrawGrid(void)
{
    u8 i, slot;

    FillWindowPixelBuffer(WIN_GRID, PIXEL_FILL(DXCOL_BACKDROP));
    // every slot of the grid, used or not, as Platinum's screen shows them
    for (slot = 0; slot < GRID_COLUMNS * GRID_ROWS; slot++)
        DrawCellBox((slot % GRID_COLUMNS) * CELL_SIZE, (slot / GRID_COLUMNS) * CELL_SIZE, DXCOL_EMPTY, DXCOL_CELL_EDGE);
    for (i = 0; i < sDexNavScreen->count; i++)
    {
        u16 species = Gunk_DexNavListSpecies(i);
        u16 x = sDexNavScreen->cellX[i], y = sDexNavScreen->cellY[i];

        if (Gunk_DexNavListArea(i) != sDexNavScreen->tab)
            continue;
        if (i == sDexNavScreen->cursor)
            DrawCellBox(x, y, DXCOL_CURSOR, DXCOL_CURSOR_EDGE);
        else
            DrawCellBox(x, y, DXCOL_CELL, DXCOL_CELL_EDGE);
        if (!IsSeen(species))
            AddTextPrinterParameterized3(WIN_GRID, FONT_NORMAL, x + 13, y + 8,
                                         i == sDexNavScreen->cursor ? sDexNavColors_Backdrop : sDexNavColors_Unseen,
                                         TEXT_SKIP_DRAW, sDexNavText_Question);
        if (IsCaught(species))
            DrawCaughtMark(WIN_GRID, x + CELL_SIZE - 11, y + 3);
    }
    PutWindowTilemap(WIN_GRID);
    CopyWindowToVram(WIN_GRID, COPYWIN_FULL);
}

// The line under the grid: a hint in place of the chain until the cursor moves
static void DrawHint(const u8 *text)
{
    FillWindowPixelBuffer(WIN_CHAIN, PIXEL_FILL(DXCOL_BACKDROP));
    AddTextPrinterParameterized3(WIN_CHAIN, FONT_SMALL, 4, 3, sDexNavColors_Backdrop, TEXT_SKIP_DRAW, text);
    CopyWindowToVram(WIN_CHAIN, COPYWIN_GFX);
}

static void DrawChain(void)
{
    u16 species = Gunk_DexNavChainSpecies();
    u8 *end;

    FillWindowPixelBuffer(WIN_CHAIN, PIXEL_FILL(DXCOL_BACKDROP));
    if (species == SPECIES_NONE || Gunk_DexNavChain(species) == 0)
    {
        StringCopy(gStringVar4, sDexNavText_ChainNone);
    }
    else
    {
        end = StringCopy(gStringVar4, sDexNavText_ChainOf);
        end = StringCopy(end, gSpeciesNames[species]);
        end = StringCopy(end, sDexNavText_Times);
        ConvertIntToDecimalStringN(end, Gunk_DexNavChain(species), STR_CONV_MODE_LEFT_ALIGN, 3);
    }
    AddTextPrinterParameterized3(WIN_CHAIN, FONT_SMALL, 4, 3, sDexNavColors_Backdrop, TEXT_SKIP_DRAW, gStringVar4);
    PutWindowTilemap(WIN_CHAIN);
    CopyWindowToVram(WIN_CHAIN, COPYWIN_FULL);
}

static void PrintInfoLine(u8 y, const u8 *label, const u8 *value)
{
    AddTextPrinterParameterized3(WIN_INFO, FONT_SMALL, 2, y, sDexNavColors_Label, TEXT_SKIP_DRAW, label);
    AddTextPrinterParameterized3(WIN_INFO, FONT_SMALL, 44, y, sDexNavColors_Text, TEXT_SKIP_DRAW, value);
}

static void DrawInfo(void)
{
    u16 species = Gunk_DexNavListSpecies(sDexNavScreen->cursor);
    bool8 seen = IsSeen(species);
    const u8 *status;
    u8 minLevel, maxLevel;
    u8 *end;

    FillWindowPixelBuffer(WIN_INFO, PIXEL_FILL(DXCOL_WHITE));
    AddTextPrinterParameterized3(WIN_INFO, FONT_NORMAL, 2, 1, sDexNavColors_Text, TEXT_SKIP_DRAW,
                                 seen ? gSpeciesNames[species] : sDexNavText_Unseen);
    if (IsCaught(species))
    {
        status = sDexNavText_StatusCaught;
        DrawCaughtMark(WIN_INFO, 96 - 10, 4);
    }
    else if (seen)
    {
        status = sDexNavText_StatusSeen;
    }
    else
    {
        status = sDexNavText_StatusNotSeen;
    }
    AddTextPrinterParameterized3(WIN_INFO, FONT_SMALL, 2, 17, sDexNavColors_Label, TEXT_SKIP_DRAW, status);
    FillWindowPixelRect(WIN_INFO, PIXEL_FILL(DXCOL_SHADOW), 2, 31, 92, 1);

    PrintInfoLine(36, sDexNavText_Found,
                  Gunk_DexNavListArea(sDexNavScreen->cursor) == WILD_AREA_WATER ? sDexNavText_Surfing : sDexNavText_TallGrass);

    Gunk_DexNavLevelRange(sDexNavScreen->cursor, &minLevel, &maxLevel);
    end = StringCopy(gStringVar4, sDexNavText_Lv);
    end = ConvertIntToDecimalStringN(end, minLevel, STR_CONV_MODE_LEFT_ALIGN, 3);
    if (maxLevel != minLevel)
    {
        *end++ = CHAR_HYPHEN;
        ConvertIntToDecimalStringN(end, maxLevel, STR_CONV_MODE_LEFT_ALIGN, 3);
    }
    PrintInfoLine(52, sDexNavText_Level, gStringVar4);

    ConvertIntToDecimalStringN(gStringVar4, Gunk_DexNavSearchLevel(species), STR_CONV_MODE_LEFT_ALIGN, 3);
    AddTextPrinterParameterized3(WIN_INFO, FONT_SMALL, 2, 72, sDexNavColors_Label, TEXT_SKIP_DRAW, sDexNavText_SearchLv);
    AddTextPrinterParameterized3(WIN_INFO, FONT_NORMAL, 2, 84, sDexNavColors_Text, TEXT_SKIP_DRAW, gStringVar4);

    ConvertIntToDecimalStringN(gStringVar4, Gunk_DexNavChain(species), STR_CONV_MODE_LEFT_ALIGN, 3);
    AddTextPrinterParameterized3(WIN_INFO, FONT_SMALL, 62, 72, sDexNavColors_Label, TEXT_SKIP_DRAW, sDexNavText_Chain);
    AddTextPrinterParameterized3(WIN_INFO, FONT_NORMAL, 62, 84, sDexNavColors_Text, TEXT_SKIP_DRAW, gStringVar4);
    CopyWindowToVram(WIN_INFO, COPYWIN_GFX);
}

static void DrawFooter(void)
{
    FillWindowPixelBuffer(WIN_FOOTER, PIXEL_FILL(DXCOL_TITLE));
    AddTextPrinterParameterized3(WIN_FOOTER, FONT_SMALL, 4, 3, sDexNavColors_Title, TEXT_SKIP_DRAW, sDexNavText_Footer);
    if (sDexNavScreen->tabCount[WILD_AREA_LAND] != 0 && sDexNavScreen->tabCount[WILD_AREA_WATER] != 0)
        AddTextPrinterParameterized3(WIN_FOOTER, FONT_SMALL, 240 - 4 - GetStringWidth(FONT_SMALL, sDexNavText_FooterTabs, 0), 3,
                                     sDexNavColors_Title, TEXT_SKIP_DRAW, sDexNavText_FooterTabs);
    PutWindowTilemap(WIN_FOOTER);
    CopyWindowToVram(WIN_FOOTER, COPYWIN_FULL);
}

// Only the open tab's icons show; the highlighted one hops (the menu icon's own animation)
static void UpdateIcons(void)
{
    u8 i;

    for (i = 0; i < sDexNavScreen->count; i++)
    {
        struct Sprite *sprite;

        if (sDexNavScreen->iconSpriteIds[i] >= MAX_SPRITES)
            continue;
        sprite = &gSprites[sDexNavScreen->iconSpriteIds[i]];
        sprite->invisible = Gunk_DexNavListArea(i) != sDexNavScreen->tab;
        if (i == sDexNavScreen->cursor)
        {
            sprite->callback = SpriteCB_MonIcon;
        }
        else
        {
            sprite->callback = SpriteCallbackDummy;
            sprite->y2 = 0;
        }
    }
}

static void Redraw(void)
{
    DrawChain();
    DrawTabs();
    DrawGrid();
    DrawInfo();
    UpdateIcons();
}

static void CB2_InitDexNavScreen(void)
{
    switch (gMain.state)
    {
    case 0:
        SetVBlankCallback(NULL);
        SetGpuReg(REG_OFFSET_DISPCNT, 0);
        ScanlineEffect_Stop();
        ResetTasks();
        ResetSpriteData();
        ResetPaletteFade();
        FreeAllSpritePalettes();
        gMain.state++;
        break;
    case 1:
        sDexNavScreen = AllocZeroed(sizeof(*sDexNavScreen));
        sDexNavScreen->helpWasEnabled = gHelpSystemEnabled;
        HelpSystem_Disable();
        sDexNavScreen->count = Gunk_DexNavListCount();
        if (sDexNavScreen->count > LIST_MAX)
            sDexNavScreen->count = LIST_MAX;
        sDexNavScreen->cursor = Gunk_DexNavDefaultRow();
        if (sDexNavScreen->cursor >= sDexNavScreen->count)
            sDexNavScreen->cursor = 0;
        sDexNavScreen->tab = Gunk_DexNavListArea(sDexNavScreen->cursor);
        LayOutCells();
        ResetBgsAndClearDma3BusyFlags(FALSE);
        InitBgsFromTemplates(0, sBgTemplates, ARRAY_COUNT(sBgTemplates));
        SetBgTilemapBuffer(0, AllocZeroed(BG_SCREEN_SIZE));
        InitWindows(sWindowTemplates);
        DeactivateAllTextPrinters();
        ChangeBgX(0, 0, BG_COORD_SET);
        ChangeBgY(0, 0, BG_COORD_SET);
        gMain.state++;
        break;
    case 2:
        LoadPalette(sDexNavSkinPalette, BG_PLTT_ID(15), PLTT_SIZE_4BPP);
        LoadPalette(&sDexNavSkinPalette[DXCOL_BACKDROP], BG_PLTT_ID(0), PLTT_SIZEOF(1));
        LoadUserWindowGfx(WIN_INFO, FRAME_BASE_TILE, BG_PLTT_ID(FRAME_PAL));
        FillBgTilemapBufferRect(0, 0, 0, 0, 32, 32, 15);
        DrawStdFrameWithCustomTileAndPalette(WIN_INFO, FALSE, FRAME_BASE_TILE, FRAME_PAL);
        DrawTitle();
        DrawChain();
        DrawFooter();
        CreateIcons();
        Redraw();
        CopyBgTilemapBufferToVram(0);
        gMain.state++;
        break;
    default:
        BeginNormalPaletteFade(PALETTES_ALL, 0, 16, 0, RGB_BLACK);
        SetVBlankCallback(VBlankCB_DexNavScreen);
        SetGpuReg(REG_OFFSET_DISPCNT, DISPCNT_OBJ_ON | DISPCNT_OBJ_1D_MAP);
        ShowBg(0);
        CreateTask(Task_DexNavScreen, 0);
        SetMainCallback2(CB2_DexNavScreen);
        gMain.state = 0;
        break;
    }
}

static void CB2_DexNavScreen(void)
{
    RunTasks();
    RunTextPrinters();
    AnimateSprites();
    BuildOamBuffer();
    DoScheduledBgTilemapCopiesToVram();
    UpdatePaletteFade();
}

static void VBlankCB_DexNavScreen(void)
{
    LoadOam();
    ProcessSpriteCopyRequests();
    TransferPlttBuffer();
}

// The cell of <tab> at (row, col), or the closest one in that row; NO_ROW if the row is empty
static u8 FindCell(u8 tab, u8 row, u8 col)
{
    u8 i, best = NO_ROW, bestDist = 0xFF;

    for (i = 0; i < sDexNavScreen->count; i++)
    {
        u8 dist;

        if (Gunk_DexNavListArea(i) != tab || sDexNavScreen->row[i] != row)
            continue;
        dist = sDexNavScreen->col[i] > col ? sDexNavScreen->col[i] - col : col - sDexNavScreen->col[i];
        if (dist < bestDist)
        {
            best = i;
            bestDist = dist;
        }
    }
    return best;
}

static void MoveDexNavCursor(u8 newCursor)
{
    if (newCursor == NO_ROW || newCursor >= sDexNavScreen->count || newCursor == sDexNavScreen->cursor)
        return;
    PlaySE(SE_SELECT);
    sDexNavScreen->cursor = newCursor;
    sDexNavScreen->tab = Gunk_DexNavListArea(newCursor);
    Redraw();
}

// To the other tab, if it has any Pokemon: the cell in its first (or last) row closest to the cursor's column
static void SwitchTab(bool8 toTop)
{
    u8 tab = sDexNavScreen->tab == WILD_AREA_LAND ? WILD_AREA_WATER : WILD_AREA_LAND;
    u8 row;

    if (sDexNavScreen->tabCount[tab] == 0)
        return;
    row = toTop ? 0 : (sDexNavScreen->tabCount[tab] - 1) / GRID_COLUMNS;
    MoveDexNavCursor(FindCell(tab, row, sDexNavScreen->col[sDexNavScreen->cursor]));
}

static void ExitScreen(u16 result)
{
    gSpecialVar_Result = result;
    BeginNormalPaletteFade(PALETTES_ALL, 0, 0, 16, RGB_BLACK);
    sDexNavScreen->state = 1;
}

static void Task_DexNavScreen(u8 taskId)
{
    u8 i, cursor, tab, row, col;

    if (sDexNavScreen->state == 1)
    {
        if (gPaletteFade.active)
            return;
        for (i = 0; i < sDexNavScreen->count; i++)
        {
            if (sDexNavScreen->iconSpriteIds[i] < MAX_SPRITES)
                DestroyMonIcon(&gSprites[sDexNavScreen->iconSpriteIds[i]]);
        }
        FreeMonIconPalettes();
        if (sDexNavScreen->helpWasEnabled)
            HelpSystem_Enable();
        FreeAllWindowBuffers();
        Free(GetBgTilemapBuffer(0));
        FREE_AND_SET_NULL(sDexNavScreen);
        DestroyTask(taskId);
        SetMainCallback2(CB2_ReturnToFieldContinueScript);
        return;
    }
    if (gPaletteFade.active)
        return;

    cursor = sDexNavScreen->cursor;
    tab = sDexNavScreen->tab;
    row = sDexNavScreen->row[cursor];
    col = sDexNavScreen->col[cursor];
    if (JOY_NEW(A_BUTTON))
    {
        if (!IsSeen(Gunk_DexNavListSpecies(cursor)))
        {
            // as on Platinum, only a Pokemon already seen can be searched for
            PlaySE(SE_FAILURE);
            DrawHint(sDexNavText_NotSeenHint);
            return;
        }
        PlaySE(SE_SELECT);
        ExitScreen(cursor);
    }
    else if (JOY_NEW(B_BUTTON))
    {
        PlaySE(SE_SELECT);
        ExitScreen(NO_ROW);
    }
    else if (JOY_NEW(L_BUTTON | R_BUTTON))
    {
        SwitchTab(TRUE);
    }
    else if (JOY_REPEAT(DPAD_LEFT))
    {
        if (col > 0)
            MoveDexNavCursor(FindCell(tab, row, col - 1));
    }
    else if (JOY_REPEAT(DPAD_RIGHT))
    {
        u8 next = FindCell(tab, row, col + 1);

        if (next != NO_ROW && sDexNavScreen->col[next] == col + 1)
            MoveDexNavCursor(next);
    }
    else if (JOY_REPEAT(DPAD_UP))
    {
        if (row > 0)
            MoveDexNavCursor(FindCell(tab, row - 1, col));
        else if (tab == WILD_AREA_WATER)
            SwitchTab(FALSE);
    }
    else if (JOY_REPEAT(DPAD_DOWN))
    {
        u8 next = FindCell(tab, row + 1, col);

        if (next != NO_ROW)
            MoveDexNavCursor(next);
        else if (tab == WILD_AREA_LAND)
            SwitchTab(TRUE);
    }
}
