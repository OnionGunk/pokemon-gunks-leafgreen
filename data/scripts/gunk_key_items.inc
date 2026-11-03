@ Gunk's: the Endless Repel, the Exp. All and the DexNav. Oak gives them with the Pokedex, after the parcel and
@ before Brock (a step of the story no one can skip). On a save already past that, Mom has them; Oak's aide in
@ Pewter offers them too. Items already in the bag are skipped, so a full bag never loses one: the flag is set
@ only once all three are there.
PalletTown_ProfessorOaksLab_EventScript_GunkOakGivesKeyItems::
	goto_if_set FLAG_GUNK_GOT_KEY_ITEMS, EventScript_GunkKeyItemsEnd
	msgbox Text_GunkOakAlsoGives
	goto EventScript_GunkGiveKeyItems

PewterCity_EventScript_GunkAideGivesKeyItems::
	goto_if_set FLAG_GUNK_GOT_KEY_ITEMS, EventScript_GunkKeyItemsEnd
	msgbox Text_GunkAideAlsoGives
	goto EventScript_GunkGiveKeyItems

PalletTown_PlayersHouse_1F_EventScript_GunkMomGivesKeyItems::
	goto_if_set FLAG_GUNK_GOT_KEY_ITEMS, EventScript_GunkKeyItemsEnd
	msgbox Text_GunkMomHasKeyItems
EventScript_GunkGiveKeyItems::
	checkitem ITEM_ENDLESS_REPEL
	goto_if_eq VAR_RESULT, TRUE, EventScript_GunkGiveExpAll
	giveitem ITEM_ENDLESS_REPEL
	goto_if_eq VAR_RESULT, FALSE, EventScript_GunkKeyItemsEnd
EventScript_GunkGiveExpAll::
	checkitem ITEM_EXP_ALL
	goto_if_eq VAR_RESULT, TRUE, EventScript_GunkGiveDexNav
	giveitem ITEM_EXP_ALL
	goto_if_eq VAR_RESULT, FALSE, EventScript_GunkKeyItemsEnd
	setflag FLAG_GUNK_EXP_ALL_ON
EventScript_GunkGiveDexNav::
	checkitem ITEM_DEXNAV
	goto_if_eq VAR_RESULT, TRUE, EventScript_GunkGotKeyItems
	giveitem ITEM_DEXNAV
	goto_if_eq VAR_RESULT, FALSE, EventScript_GunkKeyItemsEnd
EventScript_GunkGotKeyItems::
	setflag FLAG_GUNK_GOT_KEY_ITEMS
	msgbox Text_GunkExplainKeyItems
EventScript_GunkKeyItemsEnd::
	return

Text_GunkAideAlsoGives::
	.string "PROF. OAK also asked me to give\n"
	.string "you these.$"

Text_GunkOakAlsoGives::
	.string "OAK: And these will help you on\n"
	.string "your journey.$"

Text_GunkMomHasKeyItems::
	.string "Oh, {PLAYER}! PROF. OAK\n"
	.string "left these for you.$"

Text_GunkExplainKeyItems::
	.string "The ENDLESS REPEL keeps weak wild\n"
	.string "POKéMON away for as long as it's on.\p"
	.string "With the EXP. ALL on, POKéMON that\n"
	.string "didn't battle get half the EXP.\p"
	.string "Use either one from the KEY ITEMS\n"
	.string "to switch it on or off.\p"
	.string "The DEXNAV finds the POKéMON that\n"
	.string "live in the grass around you.$"
