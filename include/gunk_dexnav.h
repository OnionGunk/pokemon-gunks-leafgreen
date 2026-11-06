#ifndef GUARD_GUNK_DEXNAV_H
#define GUARD_GUNK_DEXNAV_H

// Gunk's DexNav, see src/gunk_dexnav.c
struct GunkDexNavRoll;

void Gunk_DexNavPrepareList(void);
u8 Gunk_DexNavListCount(void);
u16 Gunk_DexNavListSpecies(u8 i);
u8 Gunk_DexNavListArea(u8 i);
void Gunk_DexNavLevelRange(u8 i, u8 *minLevel, u8 *maxLevel);
u16 Gunk_DexNavChainSpecies(void);
u8 Gunk_DexNavSearchLevel(u16 species);
u8 Gunk_DexNavChain(u16 species);
u8 Gunk_DexNavDefaultRow(void);
void Gunk_DexNavStartSearch(void);
const struct GunkDexNavRoll *Gunk_DexNavSearchRoll(u16 *species);
bool8 Gunk_DexNavHeldItem(u16 *item);
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
