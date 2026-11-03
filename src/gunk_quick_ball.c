// Gunk's Quick Run and Quick Ball, after pokeemerald-expansion's B_LAST_USED_BALL and B_LAST_USED_BALL_CYCLE.
//
// In a battle's action menu (FIGHT / BAG / POKEMON / RUN):
//   R           runs, exactly as choosing RUN does (the same escape odds, messages and refusals).
//   L           throws the ball shown in the widget, through the bag's own path: the same "use item" action, the
//               same room check (no room in the party or the boxes: the bag opens and says so) and the same removal
//               of one ball, then the battle's own throw.
//   L + Left/Right   shows the previous or next ball in the POKe BALLS pocket (L is released without a throw).
// The widget, bottom left above the message box: the ball's icon and "L ×NN" (the count, at most 99). It's shown
// only in a wild battle where a ball can be thrown: not against trainers, in the Safari Zone, link, Trainer Tower,
// e-Reader, the Old Man's and the Poke Dude's tutorials, the ghost before the Silph Scope, double battles, nor
// with no balls. The ball shown is the last one used (VAR_GUNK_LAST_BALL), or the first in the pocket.
// In the action menu L and R belong to these whatever the button mode: Help doesn't open there, and with L=A, L
// doesn't also act as A.
//
// Hooks (src/battle_controller_player.c): Gunk_QuickBall_Show when the action menu comes up,
// Gunk_QuickBall_HandleInput first thing in its input handler, Gunk_QuickBall_Hide whenever it ends,
// Gunk_QuickBall_TakePending in PlayerHandleChooseItem, Gunk_QuickBall_NoteItemUsed when the bag returns an item.
// src/help_system_util.c asks Gunk_IsChoosingBattleAction before opening Help.
#include "global.h"
#include "gunk_quick_ball.h"
#include "battle.h"
#include "event_data.h"
#include "item.h"
#include "item_menu_icons.h"
#include "menu.h"
#include "pokemon.h"
#include "sprite.h"
#include "sound.h"
#include "string_util.h"
#include "text.h"
#include "window.h"
#include "constants/battle.h"
#include "constants/items.h"
#include "constants/songs.h"

#define TAG_QUICK_BALL_ICON 0x6A00
#define BALLS_POCKET (POCKET_POKE_BALLS - 1)
#define WIDGET_X 16  // the icon's centre: screen tiles 0-3, rows 13-14
#define WIDGET_Y 112

// BG0, two rows above the action prompt. While the action menu shows, BG0 is scrolled to rows 20-39, so rows 33-34
// are the screen's 13-14; every other page of BG0 (messages, moves) leaves them off screen. Tiles 0x2D0-0x2FF are
// free in BG0's block (B_WIN_SWITCH_PROMPT ends at 0x2D0, the move names start at 0x300).
static const struct WindowTemplate sWidgetWindow = {
    .bg = 0,
    .tilemapLeft = 4,
    .tilemapTop = 33,
    .width = 4,
    .height = 2,
    .paletteNum = 0,
    .baseBlock = 0x2D0,
};

static const u8 sTextColors[] = {TEXT_COLOR_TRANSPARENT, 1, 6}; // as the battle's own text on BG0
static const u8 sText_Count[] = _("{L_BUTTON}×{STR_VAR_1}");

// EWRAM_DATA starts zeroed (its initializers aren't applied), so the sprite and window ids are kept plus one:
// 0 means none
static EWRAM_DATA u16 sQuickBall = ITEM_NONE;
static EWRAM_DATA u8 sIconSpriteIdPlus1 = 0;
static EWRAM_DATA u8 sQuickBallWindowIdPlus1 = 0;
static EWRAM_DATA bool8 sLDown = FALSE;
static EWRAM_DATA bool8 sCycled = FALSE;
static EWRAM_DATA bool8 sPending = FALSE;

extern u16 GetBagItemQuantity(u16 *quantity);

static u16 BallCount(u16 ball)
{
    u32 total = 0;
    u8 i;

    for (i = 0; i < gBagPockets[BALLS_POCKET].capacity; i++)
    {
        struct ItemSlot *slot = &gBagPockets[BALLS_POCKET].itemSlots[i];
        if (slot->itemId == ball)
            total += GetBagItemQuantity(&slot->quantity);
    }
    return total;
}

static bool8 IsThrowableWildBattle(void)
{
    if (gBattleTypeFlags & (BATTLE_TYPE_DOUBLE | BATTLE_TYPE_LINK | BATTLE_TYPE_TRAINER | BATTLE_TYPE_FIRST_BATTLE
                          | BATTLE_TYPE_SAFARI | BATTLE_TYPE_OLD_MAN_TUTORIAL | BATTLE_TYPE_EREADER_TRAINER
                          | BATTLE_TYPE_POKEDUDE | BATTLE_TYPE_TRAINER_TOWER | BATTLE_TYPE_BATTLE_TOWER))
        return FALSE;
    // the Marowak ghost before the Silph Scope can't be caught
    if ((gBattleTypeFlags & BATTLE_TYPE_GHOST) && !(gBattleTypeFlags & BATTLE_TYPE_GHOST_UNVEILED))
        return FALSE;
    return TRUE;
}

// The pocket slot of the next (step 1) or previous (step -1) ball after <ball> that the player has, wrapping
static u16 StepBall(u16 ball, s8 step)
{
    u8 n = gBagPockets[BALLS_POCKET].capacity;
    s16 start = 0, i;
    u8 k;

    for (i = 0; i < n; i++)
    {
        if (gBagPockets[BALLS_POCKET].itemSlots[i].itemId == ball)
        {
            start = i;
            break;
        }
    }
    for (k = 1; k <= n; k++)
    {
        struct ItemSlot *slot;
        i = (start + step * k + n * 2) % n;
        slot = &gBagPockets[BALLS_POCKET].itemSlots[i];
        if (slot->itemId != ITEM_NONE && slot->itemId <= ITEM_PREMIER_BALL && GetBagItemQuantity(&slot->quantity) != 0)
            return slot->itemId;
    }
    return ITEM_NONE;
}

static u16 ChooseBall(void)
{
    u16 last = VarGet(VAR_GUNK_LAST_BALL);

    if (sQuickBall != ITEM_NONE && BallCount(sQuickBall) != 0)
        return sQuickBall;
    if (last != ITEM_NONE && last <= ITEM_PREMIER_BALL && BallCount(last) != 0)
        return last;
    return StepBall(ITEM_NONE, 1);
}

// AddItemIconObject's sprite template lives on its stack, so the sprite can't free its own tiles and palette
// (DestroySpriteAndFreeResources reads them through that template): they go by tag, or the next ball's icon would
// reuse this one's
static void DestroyIcon(void)
{
    if (sIconSpriteIdPlus1 != 0)
    {
        DestroySprite(&gSprites[sIconSpriteIdPlus1 - 1]);
        sIconSpriteIdPlus1 = 0;
    }
    FreeSpriteTilesByTag(TAG_QUICK_BALL_ICON);
    FreeSpritePaletteByTag(TAG_QUICK_BALL_ICON);
}

static void DrawWidget(void)
{
    u16 count = BallCount(sQuickBall);
    u8 spriteId, windowId = sQuickBallWindowIdPlus1 - 1;

    DestroyIcon();
    spriteId = AddItemIconObject(TAG_QUICK_BALL_ICON, TAG_QUICK_BALL_ICON, sQuickBall);
    if (spriteId != MAX_SPRITES)
    {
        gSprites[spriteId].x = WIDGET_X;
        gSprites[spriteId].y = WIDGET_Y;
        gSprites[spriteId].oam.priority = 0;
        sIconSpriteIdPlus1 = spriteId + 1;
    }
    ConvertIntToDecimalStringN(gStringVar1, count > 99 ? 99 : count, STR_CONV_MODE_LEFT_ALIGN, 2);
    StringExpandPlaceholders(gStringVar4, sText_Count);
    FillWindowPixelBuffer(windowId, PIXEL_FILL(0));
    AddTextPrinterParameterized4(windowId, FONT_SMALL, 1, 2, 0, 0, sTextColors, TEXT_SKIP_DRAW, gStringVar4);
    PutWindowTilemap(windowId);
    CopyWindowToVram(windowId, COPYWIN_FULL);
}

bool8 Gunk_QuickBall_IsShown(void)
{
    return sQuickBallWindowIdPlus1 != 0;
}

void Gunk_QuickBall_Show(void)
{
    u8 windowId;

    sLDown = FALSE;
    sCycled = FALSE;
    if (Gunk_QuickBall_IsShown() || !IsThrowableWildBattle())
        return;
    sQuickBall = ChooseBall();
    if (sQuickBall == ITEM_NONE)
        return;
    windowId = AddWindow(&sWidgetWindow);
    if (windowId == WINDOW_NONE)
        return;
    sQuickBallWindowIdPlus1 = windowId + 1;
    DrawWidget();
}

void Gunk_QuickBall_Hide(void)
{
    sLDown = FALSE;
    DestroyIcon();
    if (sQuickBallWindowIdPlus1 != 0)
    {
        u8 windowId = sQuickBallWindowIdPlus1 - 1;
        FillWindowPixelBuffer(windowId, PIXEL_FILL(0));
        ClearWindowTilemap(windowId);
        CopyWindowToVram(windowId, COPYWIN_FULL);
        RemoveWindow(windowId);
        sQuickBallWindowIdPlus1 = 0;
    }
}

u8 Gunk_QuickBall_HandleInput(void)
{
    if (!Gunk_QuickBall_IsShown())
        return QUICK_BALL_NONE;
    if (JOY_NEW(L_BUTTON))
    {
        sLDown = TRUE; // from here on L's input is Quick Ball's (with L=A, also the A that L made)
        sCycled = FALSE;
    }
    if (!sLDown)
        return QUICK_BALL_NONE;
    if (JOY_HELD(L_BUTTON))
    {
        if (JOY_NEW(DPAD_LEFT | DPAD_RIGHT))
        {
            u16 next = StepBall(sQuickBall, JOY_NEW(DPAD_RIGHT) ? 1 : -1);
            if (next != ITEM_NONE && next != sQuickBall)
            {
                PlaySE(SE_SELECT);
                sQuickBall = next;
                DrawWidget();
            }
            sCycled = TRUE;
        }
        return QUICK_BALL_CONSUMED;
    }
    sLDown = FALSE;
    if (sCycled)
        return QUICK_BALL_CONSUMED;
    sPending = TRUE;
    return QUICK_BALL_THROW;
}

// PlayerHandleChooseItem: after a Quick Ball "use item", the ball to throw, with the bag's own check and removal
// (BattleUseFunc_PokeBallEtc). FALSE: no quick throw, so the bag opens as usual (with no room for a catch, the bag
// itself says the boxes are full).
bool8 Gunk_QuickBall_TakePending(u16 *ball)
{
    if (!sPending)
        return FALSE;
    sPending = FALSE;
    if (sQuickBall == ITEM_NONE || BallCount(sQuickBall) == 0 || IsPlayerPartyAndPokemonStorageFull())
        return FALSE;
    RemoveBagItem(sQuickBall, 1);
    *ball = sQuickBall;
    Gunk_QuickBall_NoteItemUsed(sQuickBall);
    return TRUE;
}

void Gunk_QuickBall_NoteItemUsed(u16 itemId)
{
    if (itemId != ITEM_NONE && itemId <= ITEM_PREMIER_BALL)
        VarSet(VAR_GUNK_LAST_BALL, itemId);
}
