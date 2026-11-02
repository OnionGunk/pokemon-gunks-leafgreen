"""Drive EmuHawk through bridge.lua.

Usage:
  py -3 emu.py start <rom>          launch EmuHawk with the bridge loaded
  py -3 emu.py run "<cmd>" ...      run commands (see bridge.lua), wait for completion
  py -3 emu.py stop                 close the EmuHawk this instance started (and no other)
  py -3 emu.py dir                  print this instance's folder

Isolation from other sessions' emulators: this harness has its own BizHawk copy (leafgreen-tools\\bizhawk), with the executable
renamed EmuHawk-fr.exe so another session's "taskkill /IM EmuHawk.exe" cannot reach it, and stop kills only the PID
this instance started. Each instance (env EMU_INSTANCE, default "main") has its own folder inst\\<name>\\ holding the
bridge's command files, a bridge.lua pointed at that folder, the BizHawk config, the GBA SaveRAM / savestate folders
and the PID file, so two instances can also run side by side.

Shorthand inside run: "a" = press A 6, "b" = press B 6, "sel", "start",
"up 16", "down 16", "left 16", "right 16" (frames held).
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
INSTANCE = os.environ.get("EMU_INSTANCE", "main")
DIR = os.path.join(HERE, "inst", INSTANCE)
CMD = os.path.join(DIR, "cmd.txt")
DONE = os.path.join(DIR, "done.txt")
PIDFILE = os.path.join(DIR, "emuhawk.pid")
EMUHAWK = os.environ.get("EMUHAWK", r"C:\Projects\leafgreen-tools\bizhawk\EmuHawk-lg.exe")

SHORTHAND = {
    "a": "press A 6", "b": "press B 6", "x": "press X 6", "y": "press Y 6",
    "sel": "press Select 6", "start": "press Start 6",
}


def expand(cmd):
    parts = cmd.split()
    if cmd in SHORTHAND:
        return SHORTHAND[cmd]
    if parts[0] in ("up", "down", "left", "right"):
        frames = parts[1] if len(parts) > 1 else "16"
        return f"press {parts[0].capitalize()} {frames}"
    if parts[0] == "mash":  # mash <btn> <count>
        btn, count = parts[1], int(parts[2])
        return "\n".join([f"press {btn} 4\nwait 20"] * count)
    return cmd


def run(cmds, timeout=600, echo=True):
    """Run bridge commands; returns done.txt's lines (and prints them unless echo is False)."""
    if os.path.exists(DONE):
        os.remove(DONE)
    with open(CMD + ".tmp", "w") as f:
        f.write("\n".join(expand(c) for c in cmds) + "\n")
    os.replace(CMD + ".tmp", CMD)
    end = time.time() + timeout
    while time.time() < end:
        if os.path.exists(DONE):
            time.sleep(0.05)
            with open(DONE) as f:
                text = f.read().strip()
            os.remove(DONE)
            if echo:
                print(text)
            return text.split("\n")
        time.sleep(0.02)
    raise TimeoutError("timed out waiting for emulator")


def test_config():
    """This instance's copy of BizHawk's config: the GBA folders (SaveRAM,
    savestates) inside the instance folder, no single-instance handoff, and windows off the primary monitor."""
    import json
    src = os.path.join(os.path.dirname(EMUHAWK), "config.ini")
    dst = os.path.join(DIR, "config.ini")
    cfg = json.load(open(src, encoding="utf-8-sig"))
    for entry in cfg["PathEntries"]["Paths"]:
        if entry.get("System") == "GBA" and entry.get("Type") == "Base":
            entry["Path"] = os.path.join(DIR, "GBA")
    cfg["SingleInstanceMode"] = False
    cfg.setdefault("RecentLua", {})["recentlist"] = []
    cfg.setdefault("RecentRoms", {})["recentlist"] = []
    # the Lua console is its own window and ignores the minimized start: open it on the second monitor
    # (right of the 2560-wide primary) so it never lands on the user's game
    lua = cfg.setdefault("CommonToolSettings", {}).setdefault("BizHawk.Client.EmuHawk.LuaConsole", {})
    lua.update({"_wndx": 2600, "_wndy": 100, "SaveWindowPosition": True, "TopMost": False})
    cfg["MainWndx"], cfg["MainWndy"] = 2600, 600
    json.dump(cfg, open(dst, "w", encoding="utf-8"), indent=2)
    return dst


def bridge_script():
    """bridge.lua with its command folder pointed at this instance's folder."""
    src = open(os.path.join(HERE, "bridge.lua"), encoding="utf-8").read()
    old = 'local DIR = "C:/Projects/pokemon-leafgreen-gunk/emu/"'
    assert old in src, "bridge.lua's DIR line changed"
    dst = os.path.join(DIR, "bridge.lua")
    open(dst, "w", encoding="utf-8").write(src.replace(old, 'local DIR = "%s/"' % DIR.replace(os.sep, "/")))
    return dst


def own_pid():
    """PID of the EmuHawk this instance started, while it is still running."""
    try:
        pid = int(open(PIDFILE).read())
    except (OSError, ValueError):
        return None
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return pid if os.path.basename(EMUHAWK) in out else None


def stop():
    pid = own_pid()
    if pid:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        # taskkill returns before the process is gone; a lingering instance would steal bridge commands
        for _ in range(200):
            if not own_pid():
                break
            time.sleep(0.1)
    if os.path.exists(PIDFILE):
        os.remove(PIDFILE)


def window_titles(pid):
    """Titles of the process's visible windows (to report a modal dialog that blocked startup)."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    titles = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            titles.append(buf.value)
        return True

    user32.EnumWindows(each, 0)
    return titles


def minimize_windows(pid):
    """Minimize every visible window of the process (main window and Lua console) without activating them."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(each, 0)
    for hwnd in found:
        user32.ShowWindow(hwnd, 7)  # SW_SHOWMINNOACTIVE


def start(rom):
    """Launch this instance's EmuHawk on <rom> with the bridge loaded (stopping its previous one first)."""
    os.makedirs(DIR, exist_ok=True)
    stop()
    for p in (CMD, DONE, os.path.join(DIR, "buttons.txt")):
        if os.path.exists(p):
            os.remove(p)
    # the harness owns the cart save (tests write it through the SRAM domain): drop BizHawk's own SaveRAM files,
    # or a killed run leaves an autosave behind and the next start waits on "Load autosaved SaveRAM?"
    import shutil
    shutil.rmtree(os.path.join(DIR, "GBA", "SaveRAM"), ignore_errors=True)
    # start minimized and inactive (SW_SHOWMINNOACTIVE) so a test run never takes focus from what the user is
    # doing; set EMU_SHOW=1 to get a normal window
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = int(os.environ.get("EMU_SHOW", "7"))
    proc = subprocess.Popen([EMUHAWK, f"--config={test_config()}", f"--lua={bridge_script()}", rom],
                            cwd=os.path.dirname(EMUHAWK), startupinfo=si)
    open(PIDFILE, "w").write(str(proc.pid))
    for _ in range(600):
        if os.path.exists(os.path.join(DIR, "buttons.txt")):
            minimize_windows(proc.pid)
            return
        time.sleep(0.1)
    raise RuntimeError("emulator did not load the bridge; its windows: " + "; ".join(window_titles(proc.pid)))


def main():
    op = sys.argv[1]
    os.makedirs(DIR, exist_ok=True)
    if op == "start":
        start(sys.argv[2])
        print("ready")
    elif op == "run":
        run(sys.argv[2:])
    elif op == "stop":
        stop()
    elif op == "dir":
        print(DIR)


if __name__ == "__main__":
    main()
