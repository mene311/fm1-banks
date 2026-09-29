# FM-1 Bank Collection

Thematic 32-voice DX7 banks for the **M-VAVE FM-1** (and any DX7-compatible synth).

The FM-1 stores 128 presets as **4 banks x 32**. Drop one of these banks into each
of slots A/B/C/D and you have a coherent instrument instead of 128 random patches.

**26 banks - 832 patches.** Gallery: <https://mene311.github.io/fm1-banks/>

## Banks

| Bank | Theme | Contents |
|---|---|---|
| [`FM-1_synthwave_bass`](banks/FM-1_synthwave_bass.syx) | Synthwave Bass | Jupiter/Juno/Prophet/Oberheim/Moog analog basses, FM + sequenced bass. |
| [`FM-1_synthwave_pad`](banks/FM-1_synthwave_pad.syx) | Synthwave Pad | Warm analog pads, strings, brass stabs, poly synths, sweeps, choirs. |
| [`FM-1_acid_techno`](banks/FM-1_acid_techno.syx) | Acid / Techno | TB-303 derivatives, acid patches, tech bass, rave, square/sync leads. |
| [`FM-1_drums_perc`](banks/FM-1_drums_perc.syx) | Drums & Percussion | Kicks, snares, claps, hats, toms, Simmons, hand percussion. |
| [`FM-1_bells_marimba`](banks/FM-1_bells_marimba.syx) | Bells & Mallets | FM bells, chimes, marimba, vibes, steel drum, glass. |
| [`FM-1_piano_ep`](banks/FM-1_piano_ep.syx) | Piano & Electric Piano | Acoustic piano, DX7 E-pianos (Rhodes/Wurly/Tines), clavs. |
| [`FM-1_lead_solo`](banks/FM-1_lead_solo.syx) | Leads & Solos | Monosynth leads, solos, sync leads, expressive brass leads. |
| [`FM-1_organ`](banks/FM-1_organ.syx) | Organ | Hammond-style drawbar organs, church, combo, rotary. |
| [`FM-1_ambient_texture`](banks/FM-1_ambient_texture.syx) | Ambient & Texture | Evolving pads, drones, cinematic textures, soundscapes. |
| [`FM-1_bass_funk_slap`](banks/FM-1_bass_funk_slap.syx) | Funk & Slap Bass | Slap, thumb, picked and fretless basses for funk and beyond. |
| [`FM-1_brass_section`](banks/FM-1_brass_section.syx) | Brass Section | Trumpets, trombones, horns, big brass ensembles, stabs. |
| [`FM-1_strings_orchestral`](banks/FM-1_strings_orchestral.syx) | Strings & Orchestral | Solo and ensemble strings, orchestral beds, pizzicato. |
| [`FM-1_vocal_choir`](banks/FM-1_vocal_choir.syx) | Vocal & Choir | Choirs, ooohs/aahs, vocal pads, synth voice textures. |
| [`FM-1_misc_fx`](banks/FM-1_misc_fx.syx) | Effects & Experimental | Zaps, sweeps, risers, noise hits, experimental textures. |
| [`FM-1_guitar`](banks/FM-1_guitar.syx) | Guitar | Electric clean and distorted guitars, muted, 12-string, leads. |
| [`FM-1_plucked_world`](banks/FM-1_plucked_world.syx) | Plucked & World | Koto, sitar, banjo, mandolin, plucked and ethnic strings. |
| [`FM-1_woodwinds_sax`](banks/FM-1_woodwinds_sax.syx) | Woodwinds & Sax | Flutes, oboes, clarinets, bassoons, saxophones, whistles. |
| [`FM-1_percussion_tribal`](banks/FM-1_percussion_tribal.syx) | Percussion & Tribal | Tabla, taiko, djembe, timbales, timpani, ethnic hand drums. |
| [`FM-1_chiptune`](banks/FM-1_chiptune.syx) | Chiptune & Retro Game | 8-bit game leads, pulse waves, arcade bleeps and bass. |
| [`FM-1_scifi_horror`](banks/FM-1_scifi_horror.syx) | Sci-Fi & Horror | Space textures, alien leads, screams, drones and dread. |
| [`FM-1_industrial`](banks/FM-1_industrial.syx) | Industrial & Metal | Machine hits, factory clangs, grinding metal, harsh textures. |
| [`FM-1_orchestral_hits`](banks/FM-1_orchestral_hits.syx) | Orchestral Hits & Stabs | The classic Fairlight/DX7 orchestra hit, brass stabs, ensemble punches. |
| [`FM-1_clav_funk`](banks/FM-1_clav_funk.syx) | Clav & Funk Keys | Clavinet, wah clavs, funky electric pianos and comping keys. |
| [`FM-1_vibes_bells`](banks/FM-1_vibes_bells.syx) | Vibes & Tubular Bells | Vibraphones, tubular bells, chimes and struck metal. |
| [`FM-1_electronic_bass`](banks/FM-1_electronic_bass.syx) | Electronic Bass | 808 subs, Reese, wobble, rap and dubstep bass. |
| [`FM-1_church_organ`](banks/FM-1_church_organ.syx) | Church & Cathedral Organ | Pipe organs, cathedral registrations, chapel and processional. |

## Install

1. Connect the FM-1 over USB-C and open the [FM-1 editor](https://fm1-editor.com/)
   in **Chrome or Edge** (Firefox/Safari WebMIDI is unreliable or unsupported).
2. Enable MIDI and select the FM-1 as output.
3. **Import DX7 bank** -> choose a bank file -> pick destination **A / B / C / D**.
4. **Hold SAVE** on the FM-1 to write it to flash.

Load four banks and all 128 slots are filled. Slot 1 of bank A, slot 33 of bank B,
and so on.

## Format notes

These are standard **Yamaha DX7 32-voice bulk dumps** (4104 bytes):
`F0 43 00 09 20 00 <4096 voice bytes> <checksum> F7`.

Two things break hand-built banks. Both are handled here:

- **Checksum rule.** M-VAVE's own dumps use
  `(-sum(the 4096 voice bytes)) & 0x7F` - the **6-byte header is excluded**.
  A textbook Yamaha checksum (header included) is *rejected* by fm1-editor.com
  as "This file looks damaged."
- **Control characters in names.** Some original DX7 authors padded names with
  `0x7F` (DEL). Strict parsers reject those banks, so every name here is scrubbed
  to printable ASCII.

## Regenerating

`fm1_banks.py` builds the banks from any local DX7 `.syx` collection.
Voices are scored by name against per-theme categories, de-duplicated by name
*and* family stem, and spread across sub-categories with quotas so one patch
family cannot dominate a bank.

```bash
python3 fm1_banks.py --library /path/to/dx7cartridges --out ./banks
python3 fm1_banks.py --library /path/to/dx7cartridges --out ./banks --only organ church_organ
```

Then refresh the gallery data:

```bash
python3 build_gallery.py     # rewrites docs/banks.json and docs/banks/
```

## Credits

Patches are drawn from public DX7 collections (Dexed cartridges, Yamaha Black
Boxes, Bobby Blues, and community archives). Patch authorship belongs to the
original DX7 programmers; this repository curates and repackages them into
FM-1-sized thematic banks.

## License

The generator script is MIT (see `LICENSE`). The patch data is derived from
freely-distributed DX7 SysEx collections; if you are the author of a patch and
want it removed, open an issue.
