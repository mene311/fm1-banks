# FM-1 Bank Collection

Thematic 32-voice DX7 banks for the **M-VAVE FM-1** (and any DX7-compatible synth).

The FM-1 stores 128 presets as **4 banks × 32**. Drop one of these banks into
each of slots A/B/C/D and you have a coherent, evenly-spread instrument instead
of 128 random patches.

## Banks

| Bank | Theme | Contents |
|---|---|---|
| [`FM-1_synthwave_bass`](banks/FM-1_synthwave_bass.syx) | Synthwave Bass | Jupiter/Juno/Prophet/Oberheim/Moog analog basses, FM + sequenced bass |
| [`FM-1_synthwave_pad`](banks/FM-1_synthwave_pad.syx) | Synthwave Pad | Warm analog pads, strings, brass stabs, poly synths, sweeps, choirs |
| [`FM-1_acid_techno`](banks/FM-1_acid_techno.syx) | Acid / Techno | TB-303 derivatives, acid, tech bass, rave, square/sync leads |
| [`FM-1_drums_perc`](banks/FM-1_drums_perc.syx) | Drums & Percussion | Kicks, snares, claps, hats, toms, Simmons, hand percussion |
| [`FM-1_bells_marimba`](banks/FM-1_bells_marimba.syx) | Bells & Mallets | FM bells, chimes, marimba, vibes, steel drum, glass |
| [`FM-1_piano_ep`](banks/FM-1_piano_ep.syx) | Piano & Electric Piano | Acoustic piano, DX7 E-pianos (Rhodes/Wurly/Tines), clavs |
| [`FM-1_lead_solo`](banks/FM-1_lead_solo.syx) | Leads & Solos | Monosynth leads, solos, sync leads, expressive brass leads |
| [`FM-1_organ`](banks/FM-1_organ.syx) | Organ | Hammond drawbars, church, combo, rotary |
| [`FM-1_ambient_texture`](banks/FM-1_ambient_texture.syx) | Ambient & Texture | Evolving pads, drones, cinematic textures, soundscapes |
| [`FM-1_bass_funk_slap`](banks/FM-1_bass_funk_slap.syx) | Funk & Slap Bass | Slap, thumb, picked and fretless basses |
| [`FM-1_brass_section`](banks/FM-1_brass_section.syx) | Brass Section | Trumpets, trombones, horns, big ensembles, stabs |
| [`FM-1_strings_orchestral`](banks/FM-1_strings_orchestral.syx) | Strings & Orchestral | Solo and ensemble strings, orchestral beds, pizzicato |
| [`FM-1_vocal_choir`](banks/FM-1_vocal_choir.syx) | Vocal & Choir | Choirs, ooohs/aahs, vocal pads, synth voice textures |
| [`FM-1_misc_fx`](banks/FM-1_misc_fx.syx) | Effects & Experimental | Zaps, risers, noise hits, experimental textures |

**Gallery:** <https://mene311.github.io/fm1-banks/>

## Install

1. Connect the FM-1 over USB-C and open the [FM-1 Editor](https://fm1-editor.com/)
   in **Chrome or Edge** (Firefox/Safari WebMIDI is unreliable or unsupported).
2. Enable MIDI and select the FM-1 as output.
3. **Import DX7 bank** → choose a bank file → pick destination **A / B / C / D**.
4. **Hold SAVE** on the FM-1 to write it to flash.

> Load four banks and you have all 128 slots filled. Slot 1 of bank A, slot 33
> of bank B, and so on.

## Format notes

These are standard **Yamaha DX7 32-voice bulk dumps** (4104 bytes):
`F0 43 00 09 20 00 <4096 voice bytes> <checksum> F7`.

Two things that trip up hand-built banks, both handled here:

- **Checksum rule.** M-VAVE's own dumps use
  `(-sum(the 4096 voice bytes)) & 0x7F` — the **6-byte header is excluded**.
  A "correct" Yamaha-standard checksum (header included) is *rejected* by
  fm1-editor.com as "This file looks damaged."
- **Control characters in names.** Some original DX7 authors padded names with
  `0x7F` (DEL). Strict parsers reject those banks, so all names here are scrubbed
  to printable ASCII.

## Regenerating

`fm1_banks.py` builds the banks from any local DX7 `.syx` collection
(e.g. a Dexed cartridge folder). Voices are scored by name against per-theme
categories, de-duplicated by name *and* family stem, and spread across
sub-categories with quotas so one patch family can't dominate a bank.

```bash
python3 fm1_banks.py --library /path/to/dx7cartridges --out ./banks
python3 fm1_banks.py --library /path/to/dx7cartridges --out ./banks --only organ vocal_choir
```

## Credits

Patches are drawn from public DX7 collections (Dexed cartridges, Yamaha Black
Boxes, Bobby Blues, and community archives). Individual patch authorship is
credited to the original DX7 programmers; this repository only curates and
repackages them into FM-1-sized thematic banks.

## License

The generator script is MIT (see `LICENSE`). The patch data is derived from
public-domain / freely-distributed DX7 SysEx collections; if you are the author
of a patch and want it removed, open an issue.
