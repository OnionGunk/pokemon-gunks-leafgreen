Talk to your follower in Pokémon Gunk's LeafGreen Version.

## New

- **Talk to your follower**: face the Pokémon walking behind you and press A. It answers with a line that depends on
  how it feels: worn out when its HP is under a quarter, otherwise by how much it likes you, from wary to devoted.

## Patch it

You need your own dump of **Pokémon LeafGreen (USA) 1.0**:

```
sha1: 574fa542ffebb14be69902d1d36f1ec0a4afd71e
```

Apply `pokemon-gunks-leafgreen-v1.2.bps` with [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/), Floating
IPS, or `py tools/patch/bps.py apply`. Patch the clean retail ROM, not your v1.0 ROM. The patcher refuses any other
ROM. The patched ROM should be:

```
sha1: 7d32e73e109567312e64162ec71c84f9ab036c68
```

## Notes

- Saves from v1.0 carry over: the save layout is unchanged. A vanilla LeafGreen save still loads, with its 14 boxes
  converted to 16. Back up your save anyway.
- Tested in the emulator before release: every story conversation with a person (144), played on both this ROM and
  vanilla LeafGreen, with the same outcomes; the save-safety suite (power cuts, torn writes, damaged slots); every
  feature check; the 16-box tests; Quick Ball and DexNav rule checks; follower talk checks; and a room whose
  objects fill every slot. DexNav catches were checked with PKHeX: all legal.
- In Lorelei's house on Four Island, once all her dolls are out, the room has no space left for your follower: it
  waits outside and is back when you leave.
