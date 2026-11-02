EventScript_RepelWoreOff::
	lockall
	goto_if_eq VAR_LAST_REPEL_USED, ITEM_NONE, EventScript_RepelWoreOffNoMore
	checkitem VAR_LAST_REPEL_USED, 1
	goto_if_eq VAR_RESULT, FALSE, EventScript_RepelWoreOffNoMore
	bufferitemname STR_VAR_1, VAR_LAST_REPEL_USED
	msgbox Text_RepelWoreOffUseAnother, MSGBOX_YESNO
	goto_if_eq VAR_RESULT, NO, EventScript_RepelWoreOffEnd
	special Gunk_UseLastRepel
	playse SE_REPEL
	msgbox Text_UsedAnotherRepel
EventScript_RepelWoreOffEnd:
	closemessage
	releaseall
	end

EventScript_RepelWoreOffNoMore:
	msgbox Text_RepelWoreOff
	goto EventScript_RepelWoreOffEnd

Text_RepelWoreOff::
	.string "REPEL's effect wore off…$"

Text_RepelWoreOffUseAnother:
	.string "REPEL's effect wore off…\n"
	.string "Use another {STR_VAR_1}?$"

Text_UsedAnotherRepel:
	.string "{PLAYER} used the {STR_VAR_1}.$"
