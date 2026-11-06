"""Mockup of LeafGreen's DexNav screen skin (240x160, shown 3x), in the game's own text font.

Usage: py -3 tools/gunk/dexnav_mockup.py <out.png>

A design sketch for the skin only: the colours, frames, tabs, cursor and caught mark on the shared layout
(docs/design/dexnav_leafgreen.md). Species cells are grey placeholders; the game draws the real menu icons.
"""
import os
import re
import sys

from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")

# LeafGreen's skin: leaf greens from its title screen, on the cream of FRLG's menus
SKIN = {
    "bg": (200, 232, 176), "bg_stripe": (184, 222, 160),
    "bar": (16, 120, 32), "bar_hi": (40, 176, 64), "bar_text": (248, 248, 248), "bar_shadow": (8, 72, 16),
    "panel": (248, 248, 232), "panel_edge": (40, 144, 56), "panel_shadow": (120, 176, 104),
    "tab_off": (168, 208, 144), "tab_off_text": (72, 112, 64),
    "text": (56, 56, 56), "text_shadow": (216, 216, 200), "dim": (96, 136, 88),
    "cell": (224, 240, 208), "cell_edge": (136, 192, 120), "unseen": (120, 176, 104),
    "cursor": (232, 104, 72), "cursor_in": (248, 176, 120),
    "ball_top": (40, 176, 64), "ball_bottom": (248, 248, 248), "ball_line": (32, 56, 32),
    "placeholder": (176, 184, 176),
}


def load_font():
    sheet = Image.open(os.path.join(ROOT, "graphics/fonts/latin_normal.png"))
    src = open(os.path.join(ROOT, "src/text.c")).read()
    table = src[src.index("sFontNormalLatinGlyphWidths[] ="):]
    widths = [int(w) for w in re.findall(r"\d+", table[table.index("{"):table.index("}")])]
    charmap = {}
    for line in open(os.path.join(ROOT, "charmap.txt"), encoding="utf-8"):
        m = re.match(r"^'(.)'\s*=\s*([0-9A-F]{2})\s*$", line)
        if m:
            charmap.setdefault(m.group(1), int(m.group(2), 16))
    return sheet, widths, charmap


FONT = load_font()


def text(img, x, y, s, fg, shadow):
    sheet, widths, charmap = FONT
    for ch in s:
        g = charmap[ch]
        cell = sheet.crop(((g % 16) * 16, (g // 16) * 16, (g % 16) * 16 + 16, (g // 16) * 16 + 16))
        for py in range(14):
            for px in range(widths[g]):
                v = cell.getpixel((px, py))
                if v == 1:
                    img.putpixel((x + px, y + py), fg)
                elif v == 2:
                    img.putpixel((x + px, y + py), shadow)
        x += widths[g]
    return x


def width(s):
    _, widths, charmap = FONT
    return sum(widths[charmap[c]] for c in s)


def panel(d, x0, y0, x1, y1):
    d.rectangle((x0 + 1, y0 + 1, x1 + 1, y1 + 1), fill=SKIN["panel_shadow"])
    d.rectangle((x0, y0, x1, y1), fill=SKIN["panel"], outline=SKIN["panel_edge"])
    for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):  # rounded corners
        d.point((cx, cy), fill=SKIN["bg"])


def leaf(d, x, y, col):
    d.polygon(((x, y + 6), (x + 3, y), (x + 7, y + 1), (x + 5, y + 5)), fill=col)
    d.line((x, y + 6, x + 5, y + 2), fill=SKIN["bar_shadow"])


def ball(d, x, y):
    d.ellipse((x, y, x + 6, y + 6), fill=SKIN["ball_bottom"], outline=SKIN["ball_line"])
    d.chord((x, y, x + 6, y + 6), 180, 360, fill=SKIN["ball_top"], outline=SKIN["ball_line"])
    d.line((x, y + 3, x + 6, y + 3), fill=SKIN["ball_line"])
    d.point((x + 3, y + 3), fill=SKIN["ball_bottom"])


def draw(cells, cursor, tab, info, target):
    img = Image.new("RGB", (240, 160), SKIN["bg"])
    d = ImageDraw.Draw(img)
    for y in range(0, 160, 8):  # LeafGreen's soft stripes
        if (y // 8) % 2:
            d.rectangle((0, y, 239, y + 3), fill=SKIN["bg_stripe"])

    # title bar: DEXNAV and a leaf on the left, the area's caught count on the right
    d.rectangle((0, 0, 239, 15), fill=SKIN["bar"])
    d.line((0, 15, 239, 15), fill=SKIN["bar_hi"])
    leaf(d, 4, 4, SKIN["bar_hi"])
    text(img, 14, 1, "DEXNAV", SKIN["bar_text"], SKIN["bar_shadow"])
    caught = sum(1 for c in cells[tab] if c and c[1] == "caught")
    s = f"CAUGHT {caught}/{len(cells[tab])}"
    text(img, 236 - width(s), 1, s, SKIN["bar_text"], SKIN["bar_shadow"])

    # LAND / WATER tabs
    for i, name in enumerate(("LAND", "WATER")):
        x0 = 6 + i * 56
        on = (name.lower() == tab)
        d.rectangle((x0, 18, x0 + 52, 31), fill=SKIN["panel"] if on else SKIN["tab_off"],
                    outline=SKIN["panel_edge"])
        if on:
            d.line((x0 + 1, 31, x0 + 51, 31), fill=SKIN["panel"])
        text(img, x0 + 26 - width(name) // 2, 18, name, SKIN["text"] if on else SKIN["tab_off_text"],
             SKIN["text_shadow"] if on else SKIN["tab_off"])
    hint = "L/R: TAB"
    text(img, 234 - width(hint), 18, hint, SKIN["dim"], SKIN["bg"])

    # the grid: 2 rows of 6 cells
    panel(d, 4, 31, 235, 106)
    for i in range(12):
        x0, y0 = 11 + (i % 6) * 37, 36 + (i // 6) * 35
        d.rectangle((x0, y0, x0 + 33, y0 + 32), fill=SKIN["cell"], outline=SKIN["cell_edge"])
        if i < len(cells[tab]):
            name, state = cells[tab][i]
            if state == "unseen":
                text(img, x0 + 14, y0 + 9, "?", SKIN["unseen"], SKIN["cell"])
            else:  # the game's menu icon goes here
                d.rounded_rectangle((x0 + 5, y0 + 4, x0 + 28, y0 + 28), 6, fill=SKIN["placeholder"])
                text(img, x0 + 17 - width(name[:2]) // 2, y0 + 9, name[:2], SKIN["text"], SKIN["placeholder"])
                if state == "caught":
                    ball(d, x0 + 2, y0 + 2)
        if i == cursor:
            d.rectangle((x0 - 1, y0 - 1, x0 + 34, y0 + 33), outline=SKIN["cursor"], width=2)
            d.rectangle((x0 + 1, y0 + 1, x0 + 32, y0 + 31), outline=SKIN["cursor_in"])

    # info: name and status, how it's found, level range, search level
    panel(d, 4, 110, 235, 143)
    name, state, found, levels, search = info
    text(img, 9, 112, name, SKIN["text"], SKIN["text_shadow"])
    status = {"caught": "CAUGHT", "seen": "SEEN", "unseen": "NOT SEEN"}[state]
    x = text(img, 9 + 64, 112, status, SKIN["text"], SKIN["text_shadow"])
    if state == "caught":
        ball(d, x + 2, 116)
    text(img, 9, 127, found, SKIN["dim"], SKIN["text_shadow"])
    text(img, 9 + 64, 127, levels, SKIN["text"], SKIN["text_shadow"])
    s = f"SEARCH LV. {search}"
    text(img, 230 - width(s), 112, s, SKIN["text"], SKIN["text_shadow"])

    # footer: the search target, then the buttons
    d.rectangle((0, 145, 239, 159), fill=SKIN["bar"])
    text(img, 4, 145, f"TARGET {target}" if target else "NO TARGET", SKIN["bar_text"], SKIN["bar_shadow"])
    s = "A: SEARCH  B: CLOSE"
    text(img, 236 - width(s), 145, s, SKIN["bar_text"], SKIN["bar_shadow"])
    return img


def main():
    cells = {"land": [("CATERPIE", "caught"), ("METAPOD", "seen"), ("WEEDLE", "seen"), ("KAKUNA", "unseen"),
                      ("PIKACHU", "unseen")], "water": []}
    img = draw(cells, 1, "land", ("METAPOD", "seen", "TALL GRASS", "LV. 4-6", 3), "CATERPIE")
    img.resize((720, 480), Image.NEAREST).save(sys.argv[1])


if __name__ == "__main__":
    main()
