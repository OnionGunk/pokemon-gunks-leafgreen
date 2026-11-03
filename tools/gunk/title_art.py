"""The title screen logo as one editable image, and back.

    py -3 tools/gunk/title_art.py export <out_dir>      writes <out_dir>/title_logo.png and SPEC.txt
    py -3 tools/gunk/title_art.py import <title_logo.png>

The game keeps the logo as 8bpp tiles (graphics/title_screen/<game>/game_title_logo.png, a 32x8-tile sheet), a
32x20 tilemap (game_title_logo.bin) and a palette (game_title_logo.pal). export draws the tilemap into a 256x160
indexed image, as the logo sits on screen (BG0, no scroll). import cuts an edited image back into 8x8 tiles,
merges repeats (also mirrored ones, with the tilemap's flip bits), and writes the three files; the build makes the
.8bpp/.lz/.gbapal from them.
"""
import os
import struct
import sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# FireRed and LeafGreen keep their logos the same way; this checkout's game is the one its folder is named for
GAME = "leafgreen" if "leafgreen" in os.path.basename(REPO).lower() else "firered"
GFX = os.path.join(REPO, "graphics", "title_screen", GAME)
NAME, BEHIND = {"firered": ("FireRed", "the sky, flames and Charizard behind"),
                "leafgreen": ("LeafGreen", "the sky, leaves and Venusaur behind")}[GAME]
BACKGROUND = {"firered": "the flames and Charizard (sprites and BG2)",
              "leafgreen": "the leaves and Venusaur (sprites and BG2)"}[GAME]
SHEET, MAP, PAL = (os.path.join(GFX, "game_title_logo" + ext) for ext in (".png", ".bin", ".pal"))
MAP_W, MAP_H = 32, 20
MAX_TILES = 256  # BG0's character block (16 KB) holds 256 8bpp tiles
USABLE_COLORS = 13 * 16  # the title screen loads 13 palettes' worth (208 colors) for the logo; the rest are BG1-3's
SPEC = f"""Gunk's {NAME} title logo
=========================

title_logo.png: the title screen's logo (BG0) exactly as on screen.

Size:        256 x 160 pixels (the GBA screen shows x 0-239; columns 240-255 are off screen).
Format:      indexed (paletted) PNG, 8 bits per pixel. Keep it indexed; don't convert to RGB.
Palette:     colors 1-{USABLE_COLORS - 1} are yours to use and change. Color 0 is transparent ({BEHIND}
             show through it). Colors {USABLE_COLORS}-255 are not loaded for the
             logo: don't use them. GBA colors are 15-bit: each channel is rounded to a multiple of 8.
Tiles:       the image is cut into 8x8 tiles; at most {MAX_TILES} different tiles after repeats (and mirror
             images) are merged, including the empty one. The original uses {{original}}. Large flat or empty areas cost
             one tile each, so detail anywhere costs tiles everywhere.
Editable:    the whole image. The logo can move or grow; keep important parts inside x 0-239.
Not in this image: {BACKGROUND}, the border, PRESS START and the copyright line.

Give the edited title_logo.png back as it is; tools/gunk/title_art.py import builds it into the game.
"""


def read_pal(path):
    lines = open(path).read().split()
    n = int(lines[2])
    return [tuple(int(v) for v in lines[3 + i * 3:6 + i * 3]) for i in range(n)]


def export(out_dir):
    sheet = Image.open(SHEET)
    tiles = [sheet.crop((x * 8, y * 8, x * 8 + 8, y * 8 + 8)) for y in range(sheet.height // 8) for x in range(32)]
    entries = struct.unpack(f"<{MAP_W * MAP_H}H", open(MAP, "rb").read())
    out = Image.new("P", (MAP_W * 8, MAP_H * 8), 0)
    out.putpalette([c for rgb in read_pal(PAL) for c in rgb])
    for i, e in enumerate(entries):
        t = tiles[e & 0x3FF]
        if e & 0x400:
            t = t.transpose(Image.FLIP_LEFT_RIGHT)
        if e & 0x800:
            t = t.transpose(Image.FLIP_TOP_BOTTOM)
        out.paste(t, ((i % MAP_W) * 8, (i // MAP_W) * 8))
    os.makedirs(out_dir, exist_ok=True)
    out.save(os.path.join(out_dir, "title_logo.png"), transparency=0)
    original = len({e & 0x3FF for e in entries} | {0})
    open(os.path.join(out_dir, "SPEC.txt"), "w", newline="\r\n").write(SPEC.replace("{original}", str(original)))


def import_(path):
    im = Image.open(path)
    if im.mode != "P" or im.size != (MAP_W * 8, MAP_H * 8):
        sys.exit(f"title_logo.png must be an indexed {MAP_W * 8}x{MAP_H * 8} PNG (it is {im.mode} {im.size})")
    px = im.load()
    used = {px[x, y] for x in range(im.width) for y in range(im.height)}
    if max(used) >= USABLE_COLORS:
        sys.exit(f"colors {sorted(c for c in used if c >= USABLE_COLORS)} are past {USABLE_COLORS - 1}")
    tiles, index, entries = [], {}, []
    blank = bytes(64)
    tiles.append(blank)
    index[blank] = (0, 0)
    for ty in range(MAP_H):
        for tx in range(MAP_W):
            t = bytes(px[tx * 8 + x, ty * 8 + y] for y in range(8) for x in range(8))
            if t not in index:
                rows = [t[r * 8:r * 8 + 8] for r in range(8)]
                variants = {(0, 0): t,
                            (1, 0): b"".join(r[::-1] for r in rows),
                            (0, 1): b"".join(rows[::-1]),
                            (1, 1): b"".join(r[::-1] for r in rows[::-1])}
                tiles.append(t)
                for flips, v in variants.items():
                    index.setdefault(v, (len(tiles) - 1, flips[0] | flips[1] << 1))
            n, flips = index[t]
            entries.append(n | flips << 10)
    if len(tiles) > MAX_TILES:
        sys.exit(f"{len(tiles)} different 8x8 tiles; the limit is {MAX_TILES}")
    sheet = Image.new("P", (256, 64), 0)
    sheet.putpalette(im.getpalette()[:768])
    for i, t in enumerate(tiles):
        sheet.paste(Image.frombytes("P", (8, 8), t), ((i % 32) * 8, (i // 32) * 8))
    sheet.save(SHEET)
    open(MAP, "wb").write(struct.pack(f"<{len(entries)}H", *entries))
    pal = im.getpalette()[:768] + [0] * max(0, 768 - len(im.getpalette()))
    with open(PAL, "w", newline="\r\n") as f:
        f.write("JASC-PAL\n0100\n256\n" + "".join(f"{pal[i * 3]} {pal[i * 3 + 1]} {pal[i * 3 + 2]}\n" for i in range(256)))
    print(f"{len(tiles)} tiles, {len(used)} colors: wrote {SHEET}, {MAP}, {PAL}")


if __name__ == "__main__":
    {"export": export, "import": import_}[sys.argv[1]](sys.argv[2])
