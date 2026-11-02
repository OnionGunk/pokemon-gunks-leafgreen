-- File-based control bridge for EmuHawk (GBA, mGBA core).
-- emu.py writes commands to cmd.txt; this script runs them frame by frame,
-- then writes done.txt with any output lines.
--
-- Commands (one per line):
--   press <Btn+Btn> <frames>     hold buttons for N frames (then 1 frame released)
--   wait <frames>                advance N frames with no input
--   shot <path>                  save a screenshot (png)
--   save <path> / load <path>    savestate to/from file
--   flushsave                    write the cart save to the SaveRAM folder
--   reboot                       power cycle (the cart save stays)
--   speed <percent>              emulation speed, e.g. 100 or 6400
--   read <addr> <len>            System Bus bytes as hex
--   readdom <domain> <addr> <len>
--   write8/write16/write32 <addr> <value>   System Bus writes
--   dump <domain> <addr> <len> <path> / poke <domain> <addr> <path>
--   alive <addr> <frames>        run N frames, report how far the u32 at <addr> (a frame counter) moved
--   until <addr> <value> <max>   run until the u8 at <addr> equals value (or max frames)
--   lua <code>                   run a Lua chunk; its return value goes to done.txt
--   resume                       leave the game running after this batch

local DIR = "C:/Projects/pokemon-leafgreen-gunk/emu/"
local CMD = DIR .. "cmd.txt"
local DONE = DIR .. "done.txt"
local BUS = "System Bus"

local function file_exists(p)
    local f = io.open(p, "r")
    if f then f:close() return true end
    return false
end

local function write_done(lines)
    local f = io.open(DONE .. ".tmp", "w")
    f:write(table.concat(lines, "\n"), "\n")
    f:close()
    os.remove(DONE)
    os.rename(DONE .. ".tmp", DONE)
end

local function split(s)
    local t = {}
    for w in s:gmatch("%S+") do t[#t + 1] = w end
    return t
end

local function advance(n, buttons)
    for _ = 1, n do
        if buttons then joypad.set(buttons) end
        emu.frameadvance()
    end
end

local function hexbytes(addr, len, dom)
    local hex = {}
    for i = 0, len - 1 do hex[#hex + 1] = string.format("%02X", memory.read_u8(addr + i, dom)) end
    return table.concat(hex, " ")
end

-- record the button names the core exposes, for reference
do
    local names = {}
    for k, _ in pairs(joypad.get()) do names[#names + 1] = k end
    table.sort(names)
    local f = io.open(DIR .. "buttons.txt", "w")
    f:write(table.concat(names, "\n"), "\n")
    f:close()
end

client.SetSoundOn(false)
client.speedmode(100)
client.pause()

while true do
    if file_exists(CMD) then
        local f = io.open(CMD, "r")
        local text = f:read("*a")
        f:close()
        os.remove(CMD)
        client.unpause()

        local out = {}
        local resume = false
        for line in text:gmatch("[^\r\n]+") do
            local a = split(line)
            local op = a[1]
            local ok, err = pcall(function()
                if op == "press" then
                    local b = {}
                    for name in a[2]:gmatch("[^+]+") do b[name] = true end
                    advance(tonumber(a[3] or "6"), b)
                    advance(1)
                elseif op == "wait" then
                    advance(tonumber(a[2]))
                elseif op == "shot" then
                    client.screenshot(a[2])
                elseif op == "save" then
                    savestate.save(a[2])
                elseif op == "load" then
                    savestate.load(a[2])
                elseif op == "flushsave" then
                    client.saveram()
                elseif op == "reboot" then
                    client.saveram()
                    client.reboot_core()
                elseif op == "speed" then
                    client.speedmode(tonumber(a[2]))
                elseif op == "read" then
                    out[#out + 1] = hexbytes(tonumber(a[2]), tonumber(a[3]), BUS)
                elseif op == "readdom" then
                    out[#out + 1] = hexbytes(tonumber(a[3]), tonumber(a[4]), a[2])
                elseif op == "write8" then
                    memory.write_u8(tonumber(a[2]), tonumber(a[3]), BUS)
                elseif op == "write16" then
                    memory.write_u16_le(tonumber(a[2]), tonumber(a[3]), BUS)
                elseif op == "write32" then
                    memory.write_u32_le(tonumber(a[2]), tonumber(a[3]), BUS)
                elseif op == "dump" then
                    local addr, len = tonumber(a[3]), tonumber(a[4])
                    local f2 = io.open(a[5], "wb")
                    local bytes = memory.read_bytes_as_array(addr, len, a[2])
                    local chunk = {}
                    for i = 1, #bytes do
                        chunk[#chunk + 1] = string.char(bytes[i])
                        if #chunk == 4096 then f2:write(table.concat(chunk)); chunk = {} end
                    end
                    f2:write(table.concat(chunk))
                    f2:close()
                elseif op == "poke" then
                    local f2 = io.open(a[4], "rb")
                    local data = f2:read("*a")
                    f2:close()
                    local bytes = {}
                    for i = 1, #data do bytes[i] = string.byte(data, i) end
                    memory.write_bytes_as_array(tonumber(a[3]), bytes, a[2])
                elseif op == "alive" then
                    local addr = tonumber(a[2])
                    local before = memory.read_u32_le(addr, BUS)
                    advance(tonumber(a[3]))
                    out[#out + 1] = "alive " .. ((memory.read_u32_le(addr, BUS) - before) & 0xFFFFFFFF)
                elseif op == "until" then
                    local addr, want, max = tonumber(a[2]), tonumber(a[3]), tonumber(a[4])
                    local n = 0
                    while n < max and memory.read_u8(addr, BUS) ~= want do
                        emu.frameadvance()
                        n = n + 1
                    end
                    out[#out + 1] = "until " .. n
                elseif op == "lua" then
                    local f2 = assert(load(line:sub(5)))
                    out[#out + 1] = "lua " .. tostring(f2())
                elseif op == "regs" then
                    local r = emu.getregisters()
                    local keys = {}
                    for k, _ in pairs(r) do keys[#keys + 1] = k end
                    table.sort(keys)
                    for _, k in ipairs(keys) do out[#out + 1] = k .. "=" .. string.format("%08X", r[k] & 0xFFFFFFFF) end
                elseif op == "domains" then
                    out[#out + 1] = table.concat(memory.getmemorydomainlist(), ", ")
                elseif op == "resume" then
                    resume = true
                else
                    error("unknown command")
                end
            end)
            if not ok then out[#out + 1] = "ERROR " .. line .. ": " .. tostring(err) end
        end
        out[#out + 1] = "frame " .. emu.framecount()
        write_done(out)
        if not resume then client.pause() end
    end
    -- idle without advancing the game so state only changes on command
    emu.yield()
end
