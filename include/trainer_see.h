#ifndef GUARD_TRAINER_SEE_H
#define GUARD_TRAINER_SEE_H

#include "global.h"

bool8 CheckForTrainersWantingBattle(void);
void MovementAction_RevealTrainer_RunTrainerSeeFuncList(struct ObjectEvent *var);
u8 FldEff_ExclamationMarkIcon1(void);
u8 FldEff_DoubleExclMarkIcon(void);
u8 FldEff_XIcon(void);
u8 FldEff_SmileyFaceIcon(void);
u8 FldEff_QuestionMarkIcon(void);

// Gunk's: the emotes, in the order of their animations (src/trainer_see.c)
enum {
    GUNK_EMOTE_EXCLAMATION,
    GUNK_EMOTE_DOUBLE_EXCL,
    GUNK_EMOTE_X,
    GUNK_EMOTE_SMILE,
    GUNK_EMOTE_QUESTION,
    GUNK_EMOTE_NOTE,
    GUNK_EMOTE_DOTS,
};
void GunkShowEmote(u8 localId, u8 emote);

#endif //GUARD_TRAINER_SEE_H
