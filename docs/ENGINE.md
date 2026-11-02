# Engine choice

**Gunk's LeafGreen is built on [pret/pokefirered](https://github.com/pret/pokefirered)**, the decompilation of
FireRed and LeafGreen, with `make leafgreen` (LeafGreen USA 1.0).

## What the project needs

- **Full source.** Every change is a reviewable diff to C, assembly or data, not bytes poked into a ROM.
- **A reproducible build.** The same commit and toolchain give the same ROM, so a release's BPS patch can be
  rebuilt and checked by anyone.
- **A vanilla control build.** The save-safety suite runs every test on the unmodified game and on the hack. If
  the unmodified build is byte-identical to the retail cart, any difference in results is ours.
- **No gameplay changes beyond quality of life.** Battle mechanics, stats, trainers and the story stay as
  they are.

## Options

| Option | Full source | Reproducible | Byte-identical vanilla | Keeps Gen 3 mechanics |
| --- | --- | --- | --- | --- |
| **pret pokefirered** | yes | yes (agbcc + binutils) | yes: `leafgreen.sha1` = `574fa542…d71e` | yes |
| FRLG-capable expansion (pokeemerald-expansion and its FRLG forks) | yes | yes | no | no: modern battle engine, split, new mechanics by default |
| FireRed Engine Upgrade (CFRU) | only the inserted code; the base game stays a binary | partly (needs the base ROM at build time) | n/a | configurable |

- **pokefirered** builds LeafGreen 1.0 byte for byte from source (`make compare_leafgreen`), which is the
  control build the suite needs. Its save code (`src/save.c`) is fully readable, which matters for "save safety
  first". It is the same base Gunk's FireRed uses, so code can be shared between the two hacks.
- **Expansions** replace the battle engine and many systems with later-generation behaviour. Turning that back
  off is a large diff of its own, and the result can't be compared with the retail game byte for byte. Where an
  expansion has a good implementation of a feature (DexNav, following Pokémon), we port that code onto
  pokefirered with credit instead of adopting the whole engine.
- **CFRU** targets the FireRed ROM (BPRE) and inserts compiled code into a binary. It doesn't support LeafGreen,
  and the base game isn't source.

## Toolchain

- `agbcc` (pret/agbcc, the original-compiler rebuild) for C, as pokefirered expects for a matching build.
- `arm-none-eabi` binutils (MSYS2 `mingw-w64-x86_64-arm-none-eabi-*`) for assembling and linking.
- The decomp's own host tools (`tools/`: gbagfx, scaninc, preproc, mapjson, jsonproc, gbafix…), built by its
  Makefile.
- Release patches: `tools/patch/bps.py` (from Gunk's Platinum).

The base ROM is the user's own LeafGreen dump. It is checked against `leafgreen.sha1` and is never committed.
pokefirered doesn't need it to build; it's only the source side of the BPS patch and the retail control for the
emulator suite.
