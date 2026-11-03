@ Gunk's: A on the following Pokemon (src/field_control_avatar.c sends it here; src/gunk_follower.c picks the line).
@ VAR_RESULT from Gunk_FollowerTalkPrepare: 0 tired, 1 wary, 2 shy, 3 steady, 4 happy, 5 devoted (FOLLOWER_TALK_*).
EventScript_GunkFollowerTalk::
	lock
	faceplayer
	special Gunk_FollowerTalkPrepare
	switch VAR_RESULT
	case 0, EventScript_GunkFollowerTired
	case 1, EventScript_GunkFollowerWary
	case 2, EventScript_GunkFollowerShy
	case 3, EventScript_GunkFollowerSteady
	case 4, EventScript_GunkFollowerHappy
	msgbox Text_GunkFollowerDevoted
	release
	end

EventScript_GunkFollowerTired::
	msgbox Text_GunkFollowerTired
	release
	end

EventScript_GunkFollowerWary::
	msgbox Text_GunkFollowerWary
	release
	end

EventScript_GunkFollowerShy::
	msgbox Text_GunkFollowerShy
	release
	end

EventScript_GunkFollowerSteady::
	msgbox Text_GunkFollowerSteady
	release
	end

EventScript_GunkFollowerHappy::
	msgbox Text_GunkFollowerHappy
	release
	end

Text_GunkFollowerTired::
	.string "{STR_VAR_1} is worn out.\n"
	.string "It could use a rest.$"

Text_GunkFollowerWary::
	.string "{STR_VAR_1} keeps a little distance.\n"
	.string "It doesn't quite trust you yet.$"

Text_GunkFollowerShy::
	.string "{STR_VAR_1} glances at you,\n"
	.string "then looks away.$"

Text_GunkFollowerSteady::
	.string "{STR_VAR_1} is keeping pace\n"
	.string "right behind you.$"

Text_GunkFollowerHappy::
	.string "{STR_VAR_1} is following you\n"
	.string "happily.$"

Text_GunkFollowerDevoted::
	.string "{STR_VAR_1} is beaming!\n"
	.string "It would follow you anywhere.$"
