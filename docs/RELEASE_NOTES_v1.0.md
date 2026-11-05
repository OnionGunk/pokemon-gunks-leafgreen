First release of Pokémon Gunk's LeafGreen Version: LeafGreen with the grind and friction taken out, the story and
difficulty kept as they are.

## Features

- **DexNav**: a key item that lists the grass Pokémon of the place you're in. Pick one and it hides in a patch of
  rustling grass nearby that shakes twice a second; reach it within 10 seconds or it gets away. Search levels and
  chains raise the odds of good IVs and shinies: a chain grows with each DexNav win or catch, is kept by battles
  with the same species, and breaks when a search times out, you run from a DexNav battle, or you meet another
  species. Running also doesn't raise the search level. Every Pokémon it finds is a normal, legal wild roll for that
  spot. Even a long chain's search doesn't stall the game when you reach the
  patch.
- **Following Pokémon**: your lead Pokémon walks behind you, any of the 386 species, shinies in their shiny colors.
  Walk into it to swap places. RETURN in its party menu puts it away, WALK brings it back.
- **Quick Run and Quick Ball**: in a wild battle, R runs and L throws the ball shown bottom left (hold L and press
  Left/Right to pick another). It starts on the last ball you threw.
- **16 PC boxes** instead of 14.
- **Faster play**: instant text, a faster EXP bar, auto-run (hold B to walk), eggs that hatch twice as fast.
- **Items**: reusable TMs, two registered items (SELECT and R), bag sorting (START in the bag), a prompt to use
  another Repel when one runs out, and an Endless Repel you switch on and off.
- **Pokémon**: IV and EV view in the summary (A on the SKILLS page), Exp. All, vitamins up to 252 EVs, trade
  evolutions without trading, HM moves without teaching them, and a free Move Tutor on every Pokémon Center PC.
- **Save safety**: a save slot only loads if all of it comes from one save.

Professor Oak gives the Endless Repel, the Exp. All and the DexNav with the Pokédex, when you bring him his
parcel: before the first gym. On a save that is already past that, Mom has them.

## Patch it

You need your own dump of **Pokémon LeafGreen (USA) 1.0**:

```
sha1: 574fa542ffebb14be69902d1d36f1ec0a4afd71e
```

Apply `pokemon-gunks-leafgreen-v1.0.bps` with [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/), Floating
IPS, or `py tools/patch/bps.py apply`. Patch the clean retail ROM. The patcher refuses any other ROM. The patched
ROM should be:

```
sha1: c387a24e78eea03e7b0f7fb81abecd75da207c2f
```

## Notes

- **Saves from vanilla LeafGreen load.** Their 14 PC boxes are converted to the new 16-box format the first time
  they load, with box names, wallpapers and every Pokémon kept; boxes 15 and 16 start empty. Once you save in Gunk's
  LeafGreen, that save won't load in vanilla LeafGreen any more. Back up your save first.
- **Saves from earlier Gunk's LeafGreen builds load as they are.** Quick Ball keeps its last ball in a spare save
  variable, so the save layout didn't change; the ball shown starts on the Poké Ball until you throw one.
- Tested in the emulator before release:
  - save safety: power cuts across the whole save write, torn writes at every sector, and damaged slots;
  - every feature, Quick Ball and the DexNav search rules;
  - a vanilla save with 420 boxed Pokémon converting byte for byte;
  - every map's arrival, compared with vanilla;
  - all 256 story triggers, compared with vanilla;
  - the eight gyms, each Elite Four member and the Champion, the Hall of Fame and the credits, compared with
    vanilla;
  - a PKHeX legality check: 65 caught Pokémon, from random encounters, DexNav searches and chains to a shiny, Unown
    from all seven Tanoby chambers and a Quick Ball catch, were all legal, and so were their PC-box copies.
- Credits: pret's pokefirered decompilation; the DexNav after ghoulslash's design in pokeemerald-expansion; Quick
  Ball after pokeemerald-expansion's last-used-ball option; following Pokémon from MinimalEffort07's pokefirered,
  with sprites from pokeemerald-expansion.
