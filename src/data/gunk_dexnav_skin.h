// Gunk's DexNav screen (src/gunk_dexnav_screen.c): each game's look. The screen's layout and logic are shared;
// everything here is the game's own: its palette, text colours, cell and cursor colours, caught mark and strings.
// The window frames are the player's own FRLG menu frame (Options), so they always match the game's other menus.

// Window palette (BG palette 15) indices the screen draws with
enum {
    DXCOL_TRANSPARENT,
    DXCOL_WHITE,
    DXCOL_TEXT,
    DXCOL_SHADOW,
    DXCOL_BACKDROP,
    DXCOL_TITLE,
    DXCOL_TITLE_SHADOW,
    DXCOL_LABEL,
    DXCOL_CELL,
    DXCOL_CELL_EDGE,
    DXCOL_EMPTY,
    DXCOL_CURSOR,
    DXCOL_CURSOR_EDGE,
    DXCOL_TAB_OFF,
    DXCOL_BALL,
    DXCOL_TAB_OFF_TEXT,
};

#ifdef LEAFGREEN
// LeafGreen (docs/design/dexnav_leafgreen.md): the title screen's leaf greens on a pale meadow, FRLG's menu cream for
// the cells, an orange cursor that stands out on the greens, and a green-topped ball for caught
static const u16 sDexNavSkinPalette[16] =
{
    [DXCOL_TRANSPARENT]  = RGB(25, 29, 22),
    [DXCOL_WHITE]        = RGB(31, 31, 29),
    [DXCOL_TEXT]         = RGB(7, 7, 7),
    [DXCOL_SHADOW]       = RGB(27, 27, 25),
    [DXCOL_BACKDROP]     = RGB(25, 29, 22),
    [DXCOL_TITLE]        = RGB(2, 15, 4),
    [DXCOL_TITLE_SHADOW] = RGB(1, 9, 2),
    [DXCOL_LABEL]        = RGB(5, 18, 7),
    [DXCOL_CELL]         = RGB(28, 30, 26),
    [DXCOL_CELL_EDGE]    = RGB(17, 24, 15),
    [DXCOL_EMPTY]        = RGB(15, 22, 13),
    [DXCOL_CURSOR]       = RGB(31, 22, 15),
    [DXCOL_CURSOR_EDGE]  = RGB(29, 13, 9),
    [DXCOL_TAB_OFF]      = RGB(21, 26, 18),
    [DXCOL_BALL]         = RGB(5, 22, 8),
    [DXCOL_TAB_OFF_TEXT] = RGB(9, 14, 8),
};
#else
// FireRed: the Pokedex's red bars on a warm cream backdrop
static const u16 sDexNavSkinPalette[16] =
{
    [DXCOL_TRANSPARENT]  = RGB(30, 28, 23),
    [DXCOL_WHITE]        = RGB(31, 31, 31),
    [DXCOL_TEXT]         = RGB(7, 7, 8),
    [DXCOL_SHADOW]       = RGB(21, 21, 21),
    [DXCOL_BACKDROP]     = RGB(30, 28, 23),
    [DXCOL_TITLE]        = RGB(24, 6, 7),
    [DXCOL_TITLE_SHADOW] = RGB(13, 2, 3),
    [DXCOL_LABEL]        = RGB(20, 7, 6),
    [DXCOL_CELL]         = RGB(31, 31, 29),
    [DXCOL_CELL_EDGE]    = RGB(24, 19, 14),
    [DXCOL_EMPTY]        = RGB(28, 25, 20),
    [DXCOL_CURSOR]       = RGB(31, 24, 12),
    [DXCOL_CURSOR_EDGE]  = RGB(25, 11, 4),
    [DXCOL_TAB_OFF]      = RGB(26, 21, 16),
    [DXCOL_BALL]         = RGB(28, 5, 5),
    [DXCOL_TAB_OFF_TEXT] = RGB(15, 11, 8),
};
#endif

// {background, foreground, shadow}
static const u8 sDexNavColors_Title[]    = {DXCOL_TITLE, DXCOL_WHITE, DXCOL_TITLE_SHADOW};
static const u8 sDexNavColors_TabOn[]    = {DXCOL_WHITE, DXCOL_LABEL, DXCOL_SHADOW};
static const u8 sDexNavColors_TabOff[]   = {DXCOL_TAB_OFF, DXCOL_TAB_OFF_TEXT, DXCOL_TAB_OFF};
static const u8 sDexNavColors_Text[]     = {DXCOL_WHITE, DXCOL_TEXT, DXCOL_SHADOW};
static const u8 sDexNavColors_Label[]    = {DXCOL_WHITE, DXCOL_LABEL, DXCOL_SHADOW};
static const u8 sDexNavColors_Unseen[]   = {DXCOL_CELL, DXCOL_CELL_EDGE, DXCOL_EMPTY};
static const u8 sDexNavColors_Backdrop[] = {DXCOL_BACKDROP, DXCOL_TEXT, DXCOL_SHADOW};

// The caught mark, an 8x8 ball: '.' none, 'o' outline, 'r' top, 'w' bottom
static const u8 sDexNavCaughtMark[8][9] =
{
    "..oooo..",
    ".orrrro.",
    "orrrrrro",
    "oooooooo",
    "owwwwwwo",
    "owwwwwwo",
    ".owwwwo.",
    "..oooo..",
};

static const u8 sDexNavText_Title[]       = _("DEXNAV");
static const u8 sDexNavText_Caught[]      = _("CAUGHT ");
static const u8 sDexNavText_Land[]        = _("LAND");
static const u8 sDexNavText_Water[]       = _("WATER");
static const u8 sDexNavText_Other[]       = _("OTHER");
static const u8 sDexNavText_Unseen[]      = _("?????");
static const u8 sDexNavText_Question[]    = _("?");
static const u8 sDexNavText_StatusCaught[]  = _("Caught");
static const u8 sDexNavText_StatusSeen[]    = _("Seen");
static const u8 sDexNavText_StatusNotSeen[] = _("Not seen yet");
static const u8 sDexNavText_Found[]       = _("Found");
static const u8 sDexNavText_TallGrass[]   = _("Tall grass");
static const u8 sDexNavText_Surfing[]     = _("Surfing");
static const u8 sDexNavText_OldRod[] = _("Old Rod");
static const u8 sDexNavText_GoodRod[] = _("Good Rod");
static const u8 sDexNavText_SuperRod[] = _("Super Rod");
static const u8 sDexNavText_RockSmash[] = _("Rock Smash");
static const u8 sDexNavText_HintOldRod[] = _("Old Rod: fish here.");
static const u8 sDexNavText_HintGoodRod[] = _("Good Rod: fish here.");
static const u8 sDexNavText_HintSuperRod[] = _("Super Rod: fish here.");
static const u8 sDexNavText_HintRockSmash[] = _("Rock Smash: break rocks.");
static const u8 sDexNavText_None[] = _("");
// "Found", by DEXNAV_METHOD_* (include/gunk_dexnav.h)
static const u8 *const sDexNavText_Methods[] =
{
    [DEXNAV_METHOD_GRASS]      = sDexNavText_TallGrass,
    [DEXNAV_METHOD_SURF]       = sDexNavText_Surfing,
    [DEXNAV_METHOD_OLD_ROD]    = sDexNavText_OldRod,
    [DEXNAV_METHOD_GOOD_ROD]   = sDexNavText_GoodRod,
    [DEXNAV_METHOD_SUPER_ROD]  = sDexNavText_SuperRod,
    [DEXNAV_METHOD_ROCK_SMASH] = sDexNavText_RockSmash,
};
// The OTHER tab's hint on A, by DEXNAV_METHOD_*
static const u8 *const sDexNavText_MethodHints[] =
{
    [DEXNAV_METHOD_GRASS]      = sDexNavText_None,
    [DEXNAV_METHOD_SURF]       = sDexNavText_None,
    [DEXNAV_METHOD_OLD_ROD]    = sDexNavText_HintOldRod,
    [DEXNAV_METHOD_GOOD_ROD]   = sDexNavText_HintGoodRod,
    [DEXNAV_METHOD_SUPER_ROD]  = sDexNavText_HintSuperRod,
    [DEXNAV_METHOD_ROCK_SMASH] = sDexNavText_HintRockSmash,
};
static const u8 sDexNavText_Level[]       = _("Level");
static const u8 sDexNavText_Lv[]          = _("Lv. ");
static const u8 sDexNavText_SearchLv[]    = _("Search Lv.");
static const u8 sDexNavText_Chain[]       = _("Chain");
static const u8 sDexNavText_ChainNone[]   = _("CHAIN  none yet");
static const u8 sDexNavText_ChainOf[]     = _("CHAIN  ");
static const u8 sDexNavText_Times[]       = _(" ×");
static const u8 sDexNavText_NotSeenHint[] = _("Not seen yet: can't search for it.");
static const u8 sDexNavText_Footer[]      = _("{A_BUTTON}SEARCH NEARBY  {B_BUTTON}CLOSE");
static const u8 sDexNavText_FooterTabs[]  = _("{L_BUTTON}{R_BUTTON}TABS");
