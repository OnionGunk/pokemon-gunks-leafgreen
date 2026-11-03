#ifndef GUARD_GUNK_QUICK_BALL_H
#define GUARD_GUNK_QUICK_BALL_H

// Gunk's Quick Run and Quick Ball (src/gunk_quick_ball.c): in a battle's action menu, R runs (exactly as RUN) and
// L throws the ball shown in a small widget; L held with Left/Right picks another ball.

enum {
    QUICK_BALL_NONE,     // not an input of Quick Ball's: the action menu handles it as usual
    QUICK_BALL_CONSUMED, // taken by Quick Ball (L pressed or held, a ball cycled): the action menu ignores it
    QUICK_BALL_THROW,    // L tapped and released: choose "use item"; PlayerHandleChooseItem then throws the ball
};

void Gunk_QuickBall_Show(void);
void Gunk_QuickBall_Hide(void);
u8 Gunk_QuickBall_HandleInput(void);
bool8 Gunk_QuickBall_TakePending(u16 *ball);
void Gunk_QuickBall_NoteItemUsed(u16 itemId);
bool8 Gunk_QuickBall_IsShown(void);
bool8 Gunk_IsChoosingBattleAction(void); // src/battle_controller_player.c

#endif // GUARD_GUNK_QUICK_BALL_H
