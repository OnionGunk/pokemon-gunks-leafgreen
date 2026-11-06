#ifndef GUARD_GUNK_DEXNAV_H
#define GUARD_GUNK_DEXNAV_H

// Gunk's DexNav, see src/gunk_dexnav.c
struct GunkDexNavRoll;

void Gunk_DexNavPrepareList(void);
u8 Gunk_DexNavListCount(void);
u16 Gunk_DexNavListSpecies(u8 i);
u8 Gunk_DexNavListArea(u8 i);
// The screen's tabs, and how each Pokemon is found (the OTHER tab's are shown, not searched for)
enum {
    DEXNAV_TAB_LAND,
    DEXNAV_TAB_WATER,
    DEXNAV_TAB_OTHER,
    DEXNAV_TAB_COUNT,
};
enum {
    DEXNAV_METHOD_GRASS,
    DEXNAV_METHOD_SURF,
    DEXNAV_METHOD_OLD_ROD,
    DEXNAV_METHOD_GOOD_ROD,
    DEXNAV_METHOD_SUPER_ROD,
    DEXNAV_METHOD_ROCK_SMASH,
};
#define DEXNAV_LIST_MAX (LAND_WILD_COUNT + WATER_WILD_COUNT + ROCK_WILD_COUNT + FISH_WILD_COUNT)
u8 Gunk_DexNavListTab(u8 i);
u8 Gunk_DexNavListMethod(u8 i);
void Gunk_DexNavLevelRange(u8 i, u8 *minLevel, u8 *maxLevel);
u16 Gunk_DexNavChainSpecies(void);
u8 Gunk_DexNavSearchLevel(u16 species);
u8 Gunk_DexNavChain(u16 species);
u8 Gunk_DexNavDefaultRow(void);
void Gunk_DexNavStartSearch(void);
const struct GunkDexNavRoll *Gunk_DexNavSearchRoll(u16 *species);
bool8 Gunk_DexNavHeldItem(u16 *item);
u16 Gunk_DexNavSearchHeldItem(void);
void Gunk_DexNavUpdate(void);
bool8 Gunk_DexNavTryStartBattle(void);
void Gunk_DexNavOnBattleEnd(void);

// Gunk's DexNav screen, see src/gunk_dexnav_screen.c
void Gunk_ShowDexNavScreen(void);

// Gunk's DexNav search bar, see src/gunk_dexnav_hud.c
void Gunk_DexNavHudReset(void);
void Gunk_DexNavHudUpdate(void);
void Gunk_DexNavHudHide(void);

#endif // GUARD_GUNK_DEXNAV_H
