# FM-1 banks

26 themed banks of 32 DX7 patches each, for the M-VAVE FM-1.

The FM-1 holds 128 presets, split into four banks of 32. Fill each bank from a
different file here and the whole instrument is coherent instead of 128 random
patches. Works on any DX7-compatible synth too, since the file format is the same.

Gallery with audio: <https://mene311.github.io/fm1-banks/>

## Banks

| File | Theme |
|---|---|
| [`FM-1_synthwave_bass`](banks/FM-1_synthwave_bass.syx) | Synthwave Bass |
| [`FM-1_synthwave_pad`](banks/FM-1_synthwave_pad.syx) | Synthwave Pad |
| [`FM-1_acid_techno`](banks/FM-1_acid_techno.syx) | Acid / Techno |
| [`FM-1_drums_perc`](banks/FM-1_drums_perc.syx) | Drums & Percussion |
| [`FM-1_bells_marimba`](banks/FM-1_bells_marimba.syx) | Bells & Mallets |
| [`FM-1_piano_ep`](banks/FM-1_piano_ep.syx) | Piano & Electric Piano |
| [`FM-1_lead_solo`](banks/FM-1_lead_solo.syx) | Leads & Solos |
| [`FM-1_organ`](banks/FM-1_organ.syx) | Organ |
| [`FM-1_ambient_texture`](banks/FM-1_ambient_texture.syx) | Ambient & Texture |
| [`FM-1_bass_funk_slap`](banks/FM-1_bass_funk_slap.syx) | Funk & Slap Bass |
| [`FM-1_brass_section`](banks/FM-1_brass_section.syx) | Brass Section |
| [`FM-1_strings_orchestral`](banks/FM-1_strings_orchestral.syx) | Strings & Orchestral |
| [`FM-1_vocal_choir`](banks/FM-1_vocal_choir.syx) | Vocal & Choir |
| [`FM-1_misc_fx`](banks/FM-1_misc_fx.syx) | Effects & Experimental |
| [`FM-1_guitar`](banks/FM-1_guitar.syx) | Guitar |
| [`FM-1_plucked_world`](banks/FM-1_plucked_world.syx) | Plucked & World |
| [`FM-1_woodwinds_sax`](banks/FM-1_woodwinds_sax.syx) | Woodwinds & Sax |
| [`FM-1_percussion_tribal`](banks/FM-1_percussion_tribal.syx) | Percussion & Tribal |
| [`FM-1_chiptune`](banks/FM-1_chiptune.syx) | Chiptune & Retro Game |
| [`FM-1_scifi_horror`](banks/FM-1_scifi_horror.syx) | Sci-Fi & Horror |
| [`FM-1_industrial`](banks/FM-1_industrial.syx) | Industrial & Metal |
| [`FM-1_orchestral_hits`](banks/FM-1_orchestral_hits.syx) | Orchestral Hits & Stabs |
| [`FM-1_clav_funk`](banks/FM-1_clav_funk.syx) | Clav & Funk Keys |
| [`FM-1_vibes_bells`](banks/FM-1_vibes_bells.syx) | Vibes & Tubular Bells |
| [`FM-1_electronic_bass`](banks/FM-1_electronic_bass.syx) | Electronic Bass |
| [`FM-1_church_organ`](banks/FM-1_church_organ.syx) | Church & Cathedral Organ |

## Loading them

1. Plug the FM-1 in over USB-C and open [fm1-editor.com](https://fm1-editor.com/)
   in Chrome or Edge. Firefox WebMIDI is unreliable on Linux, Safari has none.
2. Turn MIDI on and point it at the FM-1.
3. Import a bank file, then choose which of A, B, C or D to write it to.
4. Hold SAVE on the FM-1. Without this the bank is lost when it powers off.

Four banks fill the instrument: slots 1-32, 33-64, 65-96, 97-128. A bank you
write to replaces whatever was in that slot.

## Format notes

Standard Yamaha DX7 32-voice bulk dump, 4104 bytes:
`F0 43 00 09 20 00 <4096 voice bytes> <checksum> F7`.

Two details caught us while making these:

**Checksum.** M-VAVE's own dumps compute
`(-sum(the 4096 voice bytes)) & 0x7F`, with the 6-byte header left out. Using the
textbook Yamaha checksum, which includes the header, gets the file rejected by
the editor with "This file looks damaged."

**Names.** Some original DX7 patches pad the patch name with `0x7F` bytes. Parsers
that validate strictly reject a bank containing those, so every name here is
reduced to printable ASCII before the file is written.

## Rebuilding

`fm1_banks.py` takes any local collection of DX7 `.syx` files and produces the
banks. Voices are scored by patch name against per-theme categories, deduplicated
by name and by family stem, and spread across sub-categories using quotas, so a
single patch family cannot swallow a whole bank.

```bash
python3 fm1_banks.py --library /path/to/dx7cartridges --out ./banks
python3 fm1_banks.py --library /path/to/dx7cartridges --out ./banks --only organ church_organ
python3 build_gallery.py      # refresh docs/banks.json and docs/banks/
```

Audio previews are rendered with `render_demo.py`, which uses
[`dexed-py`](https://pypi.org/project/dexed-py/) — the real Dexed engine, the same
one the FM-1's FM side is built on.

```bash
python3 -m venv ~/.venv-fm1 && ~/.venv-fm1/bin/pip install dexed-py
~/.venv-fm1/bin/python render_demo.py --bank banks/FM-1_organ.syx \
    --theme keys --out docs/audio/FM-1_organ.mp3
```

## Credit and licence

The patches come from public DX7 collections — Dexed cartridge dumps, Yamaha Black
Boxes, Bobby Blues, and assorted community archives. Whoever programmed each patch
originally still owns it; this repo only sorts them into banks and reformats them.

The scripts are MIT, see `LICENSE`.
