@ Gunk's DexNav (src/gunk_dexnav.c): pick one of the area's grass Pokemon, then it hides in rustling grass nearby.
EventScript_GunkDexNav::
	lockall
	special Gunk_DexNavPrepareList
	goto_if_eq VAR_RESULT, 0, EventScript_GunkDexNavNoMons
	message Text_GunkDexNavWhich
	waitmessage
	setvar VAR_0x8004, LISTMENU_GUNK_DEXNAV
	special ListMenu
	waitstate
	goto_if_eq VAR_RESULT, 127, EventScript_GunkDexNavEnd
	copyvar VAR_0x8005, VAR_RESULT
	special Gunk_DexNavStartSearch
	goto_if_eq VAR_RESULT, FALSE, EventScript_GunkDexNavNoGrass
	msgbox Text_GunkDexNavHiding
EventScript_GunkDexNavEnd::
	closemessage
	releaseall
	end

EventScript_GunkDexNavNoMons::
	msgbox Text_GunkDexNavNoMons
	releaseall
	end

EventScript_GunkDexNavNoGrass::
	msgbox Text_GunkDexNavNoGrass
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

Text_GunkDexNavWhich::
	.string "DEXNAV: Search for which POKéMON?$"

Text_GunkDexNavHiding::
	.string "The grass is rustling nearby…\n"
	.string "Something is hiding there!\p"
	.string "{STR_VAR_1}'s search level: {STR_VAR_2}$"

Text_GunkDexNavNoMons::
	.string "DEXNAV: No POKéMON live in the\n"
	.string "grass here.$"

Text_GunkDexNavNoGrass::
	.string "DEXNAV: There's no tall grass\n"
	.string "close enough to search.$"
