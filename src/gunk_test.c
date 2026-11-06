#include "global.h"
#include "event_data.h"
#include "constants/items.h"
#include "item.h"
#include "pokemon.h"
#include "script_pokemon_util.h"
#include "gunk_test.h"

// Gunk's emulator test hook (emu/suite). The harness writes a setup here before choosing NEW GAME; at the end of
// NewGameInitData the new save then starts with these Pokemon, items and flags. It does nothing unless the magic
// value is set: EWRAM is cleared at power-on and the game itself never writes these variables. Release builds
// (RELEASE=1, GUNK_TEST_HOOKS 0) leave it out.

#if GUNK_TEST_HOOKS

#define GUNK_TEST_MAGIC 0x4B4E5547 // "GUNK"

EWRAM_DATA u32 gGunkTestMagic = 0;
EWRAM_DATA u16 gGunkTestMons[GUNK_TEST_MAX_MONS * 2] = {0};   // species, level
EWRAM_DATA u16 gGunkTestItems[GUNK_TEST_MAX_ITEMS * 2] = {0}; // item, quantity
EWRAM_DATA u16 gGunkTestFlags[GUNK_TEST_MAX_FLAGS] = {0};

void Gunk_ApplyTestSetup(void)
{
    u8 i;

    if (gGunkTestMagic != GUNK_TEST_MAGIC)
        return;
    for (i = 0; i < GUNK_TEST_MAX_MONS && gGunkTestMons[i * 2] != SPECIES_NONE; i++)
        ScriptGiveMon(gGunkTestMons[i * 2], gGunkTestMons[i * 2 + 1], ITEM_NONE, 0, 0, 0);
    for (i = 0; i < GUNK_TEST_MAX_ITEMS && gGunkTestItems[i * 2] != ITEM_NONE; i++)
        AddBagItem(gGunkTestItems[i * 2], gGunkTestItems[i * 2 + 1]);
    for (i = 0; i < GUNK_TEST_MAX_FLAGS && gGunkTestFlags[i] != 0; i++)
        FlagSet(gGunkTestFlags[i]);
    gGunkTestMagic = 0;
}

#endif // GUNK_TEST_HOOKS
