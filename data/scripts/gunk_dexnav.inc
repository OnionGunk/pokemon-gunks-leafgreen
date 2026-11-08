@ Gunk's DexNav (src/gunk_dexnav.c): pick one of the area's grass or surfing Pokemon on the DexNav screen
@ (src/gunk_dexnav_screen.c), then it hides nearby in rustling grass or rippling water.
EventScript_GunkDexNav::
	lockall
	special Gunk_DexNavPrepareList
	goto_if_eq VAR_RESULT, 255, EventScript_GunkDexNavSafari @ DEXNAV_LIST_SAFARI
	goto_if_eq VAR_RESULT, 0, EventScript_GunkDexNavNoMons
	fadescreen FADE_TO_BLACK
	special Gunk_ShowDexNavScreen
	waitstate
	goto_if_eq VAR_RESULT, 127, EventScript_GunkDexNavEnd
	copyvar VAR_0x8005, VAR_RESULT
	special Gunk_DexNavStartSearch
	goto_if_eq VAR_RESULT, FALSE, EventScript_GunkDexNavNoSpot
	goto_if_eq VAR_0x8006, TRUE, EventScript_GunkDexNavHidingInWater
	goto_if_eq VAR_0x8006, 2, EventScript_GunkDexNavHidingInDust
	msgbox Text_GunkDexNavHiding
	goto EventScript_GunkDexNavEnd

@ a land patch on a cave or building floor (src/gunk_dexnav.c, sSearch.dust)
EventScript_GunkDexNavHidingInDust::
	msgbox Text_GunkDexNavHidingInDust
	goto EventScript_GunkDexNavEnd

EventScript_GunkDexNavHidingInWater::
	msgbox Text_GunkDexNavHidingInWater
EventScript_GunkDexNavEnd::
	closemessage
	releaseall
	end

@ The Safari Zone's Pokemon are caught with Safari Balls only (src/gunk_dexnav.c, Gunk_DexNavPrepareList)
EventScript_GunkDexNavSafari::
	msgbox Text_GunkDexNavSafari
	releaseall
	end

EventScript_GunkDexNavNoMons::
	msgbox Text_GunkDexNavNoMons
	releaseall
	end

EventScript_GunkDexNavNoSpot::
	goto_if_eq VAR_0x8006, TRUE, EventScript_GunkDexNavNoWater
	msgbox Text_GunkDexNavNoGrass
	releaseall
	end

EventScript_GunkDexNavNoWater::
	msgbox Text_GunkDexNavNoWater
	releaseall
	end

@ The search's 10 seconds ran out before the player reached the patch (src/gunk_dexnav.c, Gunk_DexNavUpdate)
EventScript_GunkDexNavGotAway::
	lockall
	msgbox Text_GunkDexNavGotAway
	releaseall
	end

Text_GunkDexNavGotAway::
	.string "The hidden POKéMON got away…$"

Text_GunkDexNavHiding::
	.string "The grass is rustling nearby…\n"
	.string "Something is hiding there!\p"
	.string "{STR_VAR_1}'s search level: {STR_VAR_2}$"

Text_GunkDexNavHidingInDust::
	.string "Dust is stirring nearby…\n"
	.string "Something is hiding there!\p"
	.string "{STR_VAR_1}'s search level: {STR_VAR_2}$"

Text_GunkDexNavHidingInWater::
	.string "The water is rippling nearby…\n"
	.string "Something is hiding there!\p"
	.string "{STR_VAR_1}'s search level: {STR_VAR_2}$"

Text_GunkDexNavSafari::
	.string "DEXNAV: Searches don't work in the\n"
	.string "SAFARI ZONE. Use SAFARI BALLS!$"

Text_GunkDexNavNoMons::
	.string "DEXNAV: No POKéMON live in the\n"
	.string "grass or water here.$"

Text_GunkDexNavNoGrass::
	.string "DEXNAV: There's nowhere close\n"
	.string "enough for POKéMON to hide.$"

Text_GunkDexNavNoWater::
	.string "DEXNAV: There's no water\n"
	.string "close enough to search.$"
