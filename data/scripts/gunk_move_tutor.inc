@ Gunk's: a Move Tutor in every Pokémon Center. Remembering a move is free (no mushrooms); forgetting one
@ reuses the Fuchsia City Move Deleter's script.
EventScript_GunkMoveTutor::
	goto_if_questlog EventScript_ReleaseEnd
	special QuestLog_CutRecording
	lock
	faceplayer
	msgbox Text_GunkMoveTutor_RememberMove, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, YES, EventScript_GunkMoveTutor_ChooseMon
	msgbox Text_GunkMoveTutor_ForgetMove, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, YES, FuchsiaCity_House3_EventScript_ChooseMonForMoveDeleter
	goto EventScript_GunkMoveTutor_End
	end

EventScript_GunkMoveTutor_ChooseMon::
	msgbox Text_GunkMoveTutor_WhichMon
	special ChooseMonForMoveRelearner
	waitstate
	goto_if_ge VAR_0x8004, PARTY_SIZE, EventScript_GunkMoveTutor_End
	special IsSelectedMonEgg
	goto_if_eq VAR_RESULT, TRUE, EventScript_GunkMoveTutor_Egg
	goto_if_eq VAR_0x8005, 0, EventScript_GunkMoveTutor_NoMoves
	msgbox Text_GunkMoveTutor_WhichMove
	special TeachMoveRelearnerMove
	waitstate
	goto_if_eq VAR_0x8004, 0, EventScript_GunkMoveTutor_ChooseMon
	goto EventScript_GunkMoveTutor_End
	end

EventScript_GunkMoveTutor_Egg::
	msgbox Text_GunkMoveTutor_Egg
	goto EventScript_GunkMoveTutor_ChooseMon
	end

EventScript_GunkMoveTutor_NoMoves::
	msgbox Text_GunkMoveTutor_NoMoves
	goto EventScript_GunkMoveTutor_ChooseMon
	end

EventScript_GunkMoveTutor_End::
	msgbox Text_GunkMoveTutor_Bye
	release
	end

Text_GunkMoveTutor_RememberMove:
	.string "I'm the MOVE TUTOR.\n"
	.string "Shall I help a POKéMON remember\l"
	.string "a move it has forgotten?$"

Text_GunkMoveTutor_ForgetMove:
	.string "Then shall I make a POKéMON\n"
	.string "forget a move?$"

Text_GunkMoveTutor_WhichMon:
	.string "Which POKéMON?$"

Text_GunkMoveTutor_WhichMove:
	.string "Which move should it remember?$"

Text_GunkMoveTutor_Egg:
	.string "An EGG can't learn moves!$"

Text_GunkMoveTutor_NoMoves:
	.string "This POKéMON has no moves\n"
	.string "to remember.$"

Text_GunkMoveTutor_Bye:
	.string "Come back any time.$"
