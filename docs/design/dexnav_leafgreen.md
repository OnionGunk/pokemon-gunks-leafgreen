# LeafGreen's DexNav screen: the skin

The DexNav screen's structure is shared with FireRed (and modelled on Gunk's Platinum, `C:\Projects\gunk-reference\dexnav`):
title bar with the area's caught count, LAND/WATER tabs, a 2x6 grid of the area's species, an info panel and a footer.
LeafGreen gets its own look on that structure. Mockup: `docs/design/dexnav_leafgreen_mockup.png`
(`py -3 tools/gunk/dexnav_mockup.py <out.png>`; grey placeholders stand in for the game's menu icons).

## Layout (240x160)
- **Title bar** (y 0-15): a leaf and DEXNAV on the left, CAUGHT x/y for the shown tab on the right.
- **Tabs** (y 18-31): LAND and WATER, L/R switches. The off tab is a faded green.
- **Grid** (y 31-106): 2 rows x 6 cells of 32x32. Seen: the menu icon. Unseen: a green "?". Caught: a small
  green-topped Poke Ball in the cell's top-left. Cursor: a two-tone orange frame, so it stands out on the greens.
- **Info** (y 110-143): name (or ?????), CAUGHT / SEEN / NOT SEEN, the search level; how it's found and the
  area's level range.
- **Footer** (y 145-159): the current search target; A: SEARCH, B: CLOSE.

## LeafGreen's colours
| Part | Colour | From |
|---|---|---|
| Title bar, footer | #107820, highlight #28B040, text shadow #084810 | the LeafGreen title screen's greens |
| Background | #C8E8B0 with #B8DEA0 stripes | pale leaf |
| Panels | #F8F8E8, edge #289038 | FRLG menu cream, green edge |
| Text | #383838 on shadow #D8D8C8 | FRLG's standard menu text |
| Cells | #E0F0D0, edge #88C078; unseen "?" #78B068 | |
| Cursor | #E86848 outside, #F8B078 inside | the title screen's orange |
| Caught ball | top #28B040 | a LeafGreen-green ball |

FireRed's skin would swap the greens for its reds; the structure, sizes and text stay the same, so each skin is
just palettes, the frame tiles and a few constants.
