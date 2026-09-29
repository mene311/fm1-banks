#!/usr/bin/env python3
"""Generate thematic DX7 banks for the M-VAVE FM-1 from a local DX7 library.

This is the standalone, shareable version of the generator. It builds complete
32-voice DX7 SysEx banks (banks of patches), not single voices, because the
FM-1 stores 128 presets as 4 banks x 32.

Key protocol facts baked in (learned the hard way):
  * Bank must be a Yamaha DX7 bulk dump: F0 43 00 09 20 00 <4096 bytes> <chk> F7
  * Checksum = (-sum(the 4096 voice bytes)) & 0x7F  -- the 6-byte HEADER IS EXCLUDED.
    M-VAVE's own dumps use this rule; a Yamaha-standard checksum is REJECTED by
    fm1-editor.com as "damaged".
  * Names must contain no control characters (0x00-0x1F, 0x7F). Some DX7 authors
    used 0x7F as padding; strict parsers reject those banks.

Usage:
    python3 fm1_banks.py --library /path/to/dx7cartridges --out ./banks
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

# --- Themes ----------------------------------------------------------------
# Each theme = list of categories. A category is (label, [(include, exclude, weight)], quota).
# Quotas force spread across sub-categories instead of letting one patch family
# ("Prophet.07..22") consume a whole bank.
THEMES: dict[str, dict] = {
    "synthwave_bass": {
        "title": "Synthwave Bass",
        "desc": "Jupiter/Juno/Prophet/Oberheim/Moog analog basses, FM + sequenced bass.",
        "categories": [
            ("jupiter_juno", [(r"JUPITER|JUNO", r"", 60)], 6),
            ("prophet", [(r"PROPHET", r"", 55)], 6),
            ("oberheim", [(r"OBERHEIM|\bOB-?[X8]\b", r"", 55)], 5),
            ("moog", [(r"MOOG|MINI\s?MOOG|POLYMOOG", r"", 55)], 5),
            ("analog_synth_bass", [(r"ANALOG\s?BASS|ANLG\s?BASS|ANLG\s?BS", r"", 55)], 4),
            ("fm_digi_bass", [(r"FM\s?BASS|DIGI-?BASS|DIGIBASS", r"", 50)], 3),
            ("seq_bass", [(r"SEQ\.?\s?BASS|BASS\s?SEQ", r"", 45)], 3),
        ],
    },
    "synthwave_pad": {
        "title": "Synthwave Pad",
        "desc": "Warm analog pads, strings, brass stabs, poly synths, sweeps, choirs.",
        "categories": [
            ("analog_pad", [(r"\bPAD\b|PADS", r"", 50)], 7),
            ("strings", [(r"STRING|STRGS|\.STR\b|\bSTR\.", r"", 50)], 6),
            ("brass_stab", [(r"\bBRASS\b|\bBRS\b|BRAS\.", r"", 45)], 5),
            ("poly_synth", [(r"POLYSYNTH|POLY\s?SYNTH|POLYSYN", r"", 45)], 4),
            ("analog_sweep", [(r"SWEEP|ANALOG\s?SYN|ANLG\s?SYN", r"", 40)], 4),
            ("fat_detune", [(r"FATSYNTH|FAT\s?SYNTH|DETUNED|DETUNE", r"", 40)], 3),
            ("choir_vox", [(r"CHOIR|VOICE|VOX|VOCAL", r"", 35)], 3),
        ],
    },
    "acid_techno": {
        "title": "Acid / Techno",
        "desc": "TB-303 derivatives, acid patches, tech bass, rave, square/sync leads.",
        "categories": [
            ("tb303", [(r"\bTB\s?303\b|\b303\b", r"", 80)], 5),
            ("acid", [(r"ACID", r"", 70)], 3),
            ("tech_bass", [(r"TECH-?BASS|TECHBASS", r"", 60)], 6),
            ("rave_techno", [(r"RAVE|TECHNO", r"", 55)], 6),
            ("square_sync", [(r"SQUARE|SQR|SYNC-?BASS|ANALOGSYNC|ANLG\s?SYNC", r"", 50)], 5),
            ("house_club", [(r"HOUSE|DANCE|CLUB", r"", 45)], 4),
            ("sub_bass", [(r"SUB-?BASS|SUB\*?BASS|SUB\s?BASS", r"", 45)], 3),
        ],
    },
    "drums_perc": {
        "title": "Drums & Percussion",
        "desc": "Kicks, snares, claps, hats, toms, Simmons, hand percussion.",
        "categories": [
            ("kick", [(r"\bKICK\b|KICK\s?DR|KICKDRM|\bBD\b|BASS\s?DRUM|BASSDRUM", r"", 80)], 6),
            ("snare", [(r"\bSNARE\b|SNR|\bSN\.|\bSD\b", r"", 75)], 5),
            ("clap", [(r"\bCLAP\b|HAND\s?CLAP|HANDCLAP|SPACECLAP", r"", 70)], 4),
            ("hat", [(r"\bHAT\b|HI-?HAT|HIHAT|\bHH\b|OPEN\s?HAT", r"", 65)], 4),
            ("tom", [(r"\bTOM\b|TOM\s?TOM|SIM\s?TOM", r"", 60)], 4),
            ("perc_metal", [(r"PERC|PERCUSSION|PERCUSSIVE", r"", 45)], 4),
            ("world_hand", [(r"CONGA|COWBELL|BONGO|WOOD\s?BLOCK|WOODBLOCK|CLAVE|STEEL\s?DRUM|LOG\s?DRUM|LOGDRUM", r"", 40)], 3),
            ("cymbal_tamb", [(r"CRASH|CYM|RIDE|TAMB|SHAKER|MARACAS", r"", 35)], 2),
        ],
    },
    "bells_marimba": {
        "title": "Bells & Mallets",
        "desc": "FM bells, chimes, marimba, vibes, steel drum, glass.",
        "categories": [
            ("bells", [(r"\bBELL\b|BELLS|CHIME|TUBULAR|GLOCKEN", r"", 70)], 8),
            ("marimba_vibe", [(r"MARIMBA|VIBE|VIBRA|XYLO|CELEST|CALESTA", r"", 65)], 7),
            ("mallet_soft", [(r"KALIMBA|MALLET|WOOD\s?MALLET|STEEL\s?DRUM", r"", 55)], 5),
            ("glass_crystal", [(r"GLASS|CRYSTAL|ICE|FROST", r"", 50)], 4),
            ("harp_pluck", [(r"\bHARP\b|PLUCK|PIZZI", r"", 45)], 4),
            ("music_box", [(r"MUSIC\s?BOX|TOY|CALLIOPE", r"", 45)], 4),
        ],
    },
    "piano_ep": {
        "title": "Piano & Electric Piano",
        "desc": "Acoustic piano, DX7 E-pianos (Rhodes/Wurly/Tines), clavs.",
        "categories": [
            ("acoustic_piano", [(r"\bPIANO\b|GRAND|ACOUS\s?PIA|\bPIA\b", r"E\.?PIANO|EPIANO|RHODES|WURLY|TINES|CLAV", 60)], 8),
            ("e_piano", [(r"RHODES|WURLY|TINES|\bE\.?\s?PIANO\b|EPIANO|\bEP\b", r"", 70)], 8),
            ("clav", [(r"CLAV|CLAVINET", r"", 55)], 5),
            ("piano_bright", [(r"BRIGHT\s?PIA|HONKY|UPRIGHT", r"", 50)], 5),
            ("piano_layers", [(r"PIA.*(STR|PAD|CHOIR)|LAYER", r"", 40)], 3),
            ("harpsi", [(r"HARPSICHORD|HARPSI|CLAVICYMB", r"", 45)], 3),
        ],
    },
    "lead_solo": {
        "title": "Leads & Solos",
        "desc": "Monosynth leads, solos, sync leads, expressive brass leads.",
        "categories": [
            ("synth_lead", [(r"\bLEAD\b|SOLO", r"", 60)], 8),
            ("sync_lead", [(r"SYNC|OSC\s?SYNC", r"", 50)], 5),
            ("brass_lead", [(r"BRASS.*LEAD|LEAD.*BRASS", r"", 50)], 4),
            ("flute_lead", [(r"FLUTE|PAN\s?FLUTE|OBOE|CLARINET", r"", 40)], 4),
            ("whistle_lead", [(r"WHISTLE|OCARINA|RECORDER", r"", 40)], 4),
            ("sax_lead", [(r"SAX|SAXOPHONE", r"", 40)], 4),
            ("guitar_lead", [(r"LEAD\s?GTR|GTR.*LEAD|GUITAR\s?LEAD", r"", 40)], 3),
        ],
    },
    "organ": {
        "title": "Organ",
        "desc": "Hammond-style drawbar organs, church, combo, rotary.",
        "categories": [
            ("hammond", [(r"HAMMOND|DRAWBAR|\bB-?3\b|\bB3\b", r"", 70)], 8),
            ("church", [(r"CHURCH|PIPE\s?ORG|CATHEDRAL|CHAPEL", r"", 65)], 6),
            ("combo_organ", [(r"COMBO\s?ORG|COMBO|FARFISA|VOX\s?ORG", r"", 55)], 6),
            ("organ_generic", [(r"\bORGAN\b|\bORG\b", r"", 45)], 6),
            ("rocks_organ", [(r"ROCK.*ORG|OVERDRIVE.*ORG|DIRTY\s?ORG", r"", 40)], 3),
            ("perc_organ", [(r"PERC.*ORG|ORG.*PERC", r"", 40)], 3),
        ],
    },
    "ambient_texture": {
        "title": "Ambient & Texture",
        "desc": "Evolving pads, drones, cinematic textures, soundscapes.",
        "categories": [
            ("ambient_pad", [(r"AMBIENT|ATMOS|ETHEREAL|SPACE\s?PAD", r"", 65)], 7),
            ("drone", [(r"DRONE|DARK\s?PAD|SUSTAIN.*PAD", r"", 55)], 5),
            ("cinematic", [(r"CINEMA|FILM|SCORE|EPIC|ORCHESTRAL\s?PAD", r"", 55)], 5),
            ("evolving", [(r"EVOLV|MOTION|ANIMAT|SLOW\s?SWEEP", r"", 50)], 5),
            ("crystal_pad", [(r"CRYSTAL|GLASS\s?PAD|ICE\s?PAD|SHIMMER", r"", 50)], 5),
            ("vox_pad", [(r"CHOIR|VOCAL\s?PAD|ANGEL|VOICES", r"", 45)], 5),
        ],
    },
    "bass_funk_slap": {
        "title": "Funk & Slap Bass",
        "desc": "Slap, thumb, picked and fretless basses for funk and beyond.",
        "categories": [
            ("slap", [(r"SLAP|THUMB|\bSLP\b", r"", 70)], 8),
            ("funk", [(r"FUNK", r"", 65)], 6),
            ("picked", [(r"PICK|PLEC|PLK", r"", 50)], 5),
            ("fretless", [(r"FRETLESS|FRET\s?LESS", r"", 50)], 5),
            ("ebass_generic", [(r"E\.?\s?BASS|ELECTRIC\s?BASS|ELEC\.?\s?BASS", r"", 40)], 5),
            ("synth_funk_bass", [(r"SYN.*FUNK|FUNK.*SYN|ACID\s?BASS", r"", 40)], 3),
        ],
    },
    "brass_section": {
        "title": "Brass Section",
        "desc": "Trumpets, trombones, horns, big brass ensembles, stabs.",
        "categories": [
            ("brass_ensemble", [(r"BRASS\s?ENS|ENSEMBLE.*BRASS|HORNS|SECTION", r"", 70)], 8),
            ("trumpet", [(r"TRUMPET|TRMPT|CORNET", r"", 60)], 5),
            ("trombone", [(r"TROMBONE|TROMB", r"", 60)], 5),
            ("french_horn", [(r"FRENCH\s?HORN|\bHORN\b", r"", 55)], 4),
            ("brass_generic", [(r"\bBRASS\b|BRAS\.|\bBRS\b", r"", 45)], 6),
            ("brass_stab", [(r"STAB|HIT|PUNCH.*BRASS", r"", 45)], 4),
        ],
    },
    "strings_orchestral": {
        "title": "Strings & Orchestral",
        "desc": "Solo and ensemble strings, orchestral beds, pizzicato.",
        "categories": [
            ("ensemble_strings", [(r"STRING\s?ENS|ENS.*STRING|ORCH.*STR|STR.*ORCH", r"", 70)], 8),
            ("solo_violin", [(r"VIOLIN|VIOLA|SOLO.*STR|STR.*SOLO", r"", 60)], 5),
            ("cello_bass_str", [(r"CELLO|CONTRAB|UPRIGHT.*STR|STR.*BASS", r"", 55)], 5),
            ("pizzicato", [(r"PIZZ", r"", 55)], 4),
            ("strings_generic", [(r"STRING|STRGS|\bSTR\b", r"", 45)], 6),
            ("orchestral_bed", [(r"ORCHESTRA|SYMPHON|CHAMBER|ENSEMBLE", r"", 45)], 4),
        ],
    },
    "vocal_choir": {
        "title": "Vocal & Choir",
        "desc": "Choirs, ooohs/aahs, vocal pads, synth voice textures.",
        "categories": [
            ("choir", [(r"CHOIR|CHORUS\s?VOX|CHORALE", r"", 70)], 8),
            ("aah_ooh", [(r"\bAAH|\bOOH|\bAHH|\bOHH|VOCAL\s?AAH|VOCAL\s?OOH", r"", 60)], 6),
            ("vox_pad", [(r"VOX\s?PAD|VOICE\s?PAD|VOCAL\s?PAD", r"", 55)], 5),
            ("voice_generic", [(r"\bVOICE\b|\bVOX\b|VOCAL", r"", 45)], 6),
            ("synth_voice", [(r"SYN.*VOICE|VOICE.*SYN|FORMANT", r"", 45)], 4),
            ("whisper_breath", [(r"WHISPER|BREATH|SOFT\s?VOX", r"", 35)], 3),
        ],
    },
    "misc_fx": {
        "title": "Effects & Experimental",
        "desc": "Zaps, sweeps, risers, noise hits, experimental textures.",
        "categories": [
            ("zap_laser", [(r"ZAP|LASER|PHASER\s?HIT|BLAST", r"", 65)], 6),
            ("riser_sweep", [(r"RISE|RISER|SWEEP\s?UP|UPLIFT", r"", 60)], 6),
            ("noise_hit", [(r"NOISE|HIT|IMPACT|CRASH\s?HIT", r"", 55)], 5),
            ("fx_generic", [(r"\bFX\b|EFFECT|SFX", r"", 50)], 6),
            ("weird", [(r"WEIRD|STRANGE|ODD|ALIEN|MUTANT", r"", 45)], 5),
            ("scifi", [(r"SCI-?FI|SPACE|COSMIC|GALAXY|WARP", r"", 45)], 4),
        ],
    },
    "guitar": {
        "title": "Guitar",
        "desc": "Electric clean and distorted guitars, muted, 12-string, leads.",
        "categories": [
            ("gtr_clean", [(r"CLN\s?GTR|CLEAN\s?GTR|E\.?GTR|ELEC.*GTR", r"", 70)], 7),
            ("gtr_dist", [(r"DIST.*GTR|GTR.*DIST|DS\s?GTR|OVERDRIVE|FUZZ", r"", 65)], 7),
            ("gtr_generic", [(r"\bGUITAR\b|\bGTR\b", r"BASS", 50)], 8),
            ("gtr_muted", [(r"MUTE.*GTR|GTR.*MUTE|PALM|CHUNK", r"", 55)], 4),
            ("gtr_12str", [(r"12\s?-?STR|12STRING|DOUBLE\s?NECK", r"", 55)], 3),
            ("gtr_lead", [(r"LEAD\s?GTR|GTR.*LEAD|SOLO.*GTR", r"", 55)], 3),
        ],
    },
    "plucked_world": {
        "title": "Plucked & World",
        "desc": "Koto, sitar, banjo, mandolin, plucked and ethnic strings.",
        "categories": [
            ("koto_sitar", [(r"KOTO|SITAR|SHAMISEN|SANXIAN", r"", 70)], 7),
            ("banjo_mandolin", [(r"BANJO|MANDOLIN|BOUZOUKI|LUTE", r"", 65)], 6),
            ("plucked_generic", [(r"PLUCK|PLK", r"", 55)], 8),
            ("world_strings", [(r"ETHNIC|WORLD|FOLK|CELTIC|ORIENT", r"", 50)], 5),
            ("pizzicato", [(r"PIZZ", r"", 50)], 3),
            ("harp", [(r"\bHARP\b", r"", 50)], 3),
        ],
    },
    "woodwinds_sax": {
        "title": "Woodwinds & Sax",
        "desc": "Flutes, oboes, clarinets, bassoons, saxophones, whistles.",
        "categories": [
            ("flute", [(r"FLUTE|PAN\s?FLUTE|RECORDER", r"", 65)], 7),
            ("sax", [(r"SAX|SAXOPHONE", r"", 65)], 7),
            ("reed", [(r"OBOE|CLARINET|BASSOON|ENGLISH\s?HORN", r"", 60)], 6),
            ("whistle", [(r"WHISTLE|OCARINA|TIN\s?WHIS", r"", 55)], 5),
            ("woodwind_generic", [(r"WOODWIND|WOOD\s?WIND", r"", 50)], 4),
            ("breathy_lead", [(r"BREATH|AIRY|SOFT\s?WIND", r"", 40)], 3),
        ],
    },
    "percussion_tribal": {
        "title": "Percussion & Tribal",
        "desc": "Tabla, taiko, djembe, timbales, timpani, ethnic hand drums.",
        "categories": [
            ("tabla_taiko", [(r"TABLA|TAIKO|DJEMBE|DUMBEK|FRAME\s?DRUM", r"", 70)], 8),
            ("timbale_timpani", [(r"TIMBALE|TIMBALES|TIMPANI|KETTLE", r"", 65)], 6),
            ("tribal_generic", [(r"TRIBAL|AFRICA|ETHNIC|RITUAL", r"", 60)], 6),
            ("hand_perc", [(r"CONGA|BONGO|DJEMBE|SHAKER|CLAVES|WOOD\s?BLOCK", r"", 50)], 6),
            ("metal_perc", [(r"GONG|BELL\s?TREE|TAM-?TAM|RIDE|CRASH", r"", 45)], 3),
            ("log_drum", [(r"LOG\s?DRUM|LOGDRUM|SLIT\s?DRUM", r"", 45)], 3),
        ],
    },
    "chiptune": {
        "title": "Chiptune & Retro Game",
        "desc": "8-bit game leads, pulse waves, arcade bleeps and bass.",
        "categories": [
            ("chip_8bit", [(r"8-?BIT|CHIPTUNE|NES|GAME|ARCADE", r"", 70)], 8),
            ("pulse_square", [(r"PULSE|SQUARE\s?WAVE|SQR\s?WAVE", r"", 60)], 8),
            ("bleep_zap", [(r"BLEEP|BLIP|ZAP|LASER", r"", 55)], 5),
            ("game_bass", [(r"GAME.*BASS|BASS.*GAME|8BIT.*BASS", r"", 55)], 4),
            ("chip_lead", [(r"CHIP.*LEAD|LEAD.*CHIP|PIXEL", r"", 50)], 4),
            ("arcade_drum", [(r"ARCADE.*DRUM|GAME.*DRUM|NOISE\s?HIT", r"", 40)], 3),
        ],
    },
    "scifi_horror": {
        "title": "Sci-Fi & Horror",
        "desc": "Space textures, alien leads, screams, drones and dread.",
        "categories": [
            ("scifi", [(r"SCI-?FI|SPACE|COSMIC|GALAXY|WARP|UFO|ROBOT|ANDROID", r"", 65)], 9),
            ("horror", [(r"HORROR|SCREAM|TERROR|DEMON|EVIL|NIGHTMARE|HAUNT|GHOST", r"", 65)], 7),
            ("theremin_ghost", [(r"THEREMIN|ETHEREAL|SPECTRAL|PHANTOM", r"", 55)], 5),
            ("drone_dark", [(r"DRONE|DARK\s?PAD|OMINOUS|UNDERWORLD", r"", 50)], 5),
            ("alien_vox", [(r"ALIEN|MUTANT|CREATURE|MONSTER", r"", 50)], 4),
            ("siren_alarm", [(r"SIREN|ALARM|WARNING|EMERGENCY", r"", 40)], 2),
        ],
    },
    "industrial": {
        "title": "Industrial & Metal",
        "desc": "Machine hits, factory clangs, grinding metal, harsh textures.",
        "categories": [
            ("industrial", [(r"INDUSTRI|FACTORY|MACHINE", r"", 70)], 8),
            ("metal_hit", [(r"METAL|ANVIL|CLANG|STEEL", r"", 60)], 7),
            ("grind", [(r"GRIND|PISTON|BRUTAL|HARSH|DISTORT", r"", 55)], 6),
            ("noise_impact", [(r"NOISE|IMPACT|SLAM|SMASH|CRUSH", r"", 50)], 6),
            ("dark_brass", [(r"DARK.*BRASS|BRASS.*DARK|DOOM", r"", 45)], 3),
            ("growl_bass", [(r"GROWL|WOBBLE|REESE", r"", 45)], 2),
        ],
    },
    "orchestral_hits": {
        "title": "Orchestral Hits & Stabs",
        "desc": "The classic Fairlight/DX7 orchestra hit, brass stabs, ensemble punches.",
        "categories": [
            ("orch_hit", [(r"ORCH.*HIT|HIT.*ORCH|ENSEMBLE\s?HIT|BRASS\s?HIT", r"", 75)], 9),
            ("stab", [(r"STAB", r"", 70)], 7),
            ("ensemble_punch", [(r"PUNCH|ATTACK\s?ENS|SHORT\s?BRASS", r"", 60)], 6),
            ("fairlight_chord", [(r"FAIRLIGHT|CHORD\s?HIT|SYNTH\s?HIT", r"", 60)], 5),
            ("big_brass", [(r"BIG\s?BRASS|BRASS\s?ENS|HORNS", r"", 50)], 3),
            ("cinematic_punch", [(r"CINEMA.*HIT|HIT.*CINEMA|TRAILER", r"", 45)], 2),
        ],
    },
    "clav_funk": {
        "title": "Clav & Funk Keys",
        "desc": "Clavinet, wah clavs, funky electric pianos and comping keys.",
        "categories": [
            ("clav", [(r"CLAV|CLAVINET", r"", 70)], 9),
            ("wah_clav", [(r"WAH|PHASE.*CLAV|CLAV.*PHASE|FUNK.*KEY", r"", 60)], 6),
            ("ep_funk", [(r"RHODES|WURLY|TINES", r"", 55)], 6),
            ("comp_key", [(r"COMP|CHORD|STACK|LAYER", r"", 50)], 5),
            ("organ_funk", [(r"B-?3|DRAWBAR|COMBO\s?ORG", r"", 45)], 4),
            ("horns_funk", [(r"HORN\s?SECTION|FUNK\s?BRASS|SAX\s?SECTION", r"", 40)], 2),
        ],
    },
    "vibes_bells": {
        "title": "Vibes & Tubular Bells",
        "desc": "Vibraphones, tubular bells, chimes and struck metal.",
        "categories": [
            ("vibes", [(r"VIBE|VIBRA", r"", 70)], 8),
            ("tubular_bell", [(r"TUBULAR|TUBE\s?BELL|CHURCH\s?BELL", r"", 65)], 6),
            ("chime", [(r"CHIME|BELL\s?TREE|WIND\s?CHIME", r"", 60)], 6),
            ("glock_glocken", [(r"GLOCKEN|Glockenspiel|CARILLON", r"", 55)], 5),
            ("marimba_vibe", [(r"MARIMBA|XYLO|CELEST", r"", 50)], 4),
            ("struck_metal", [(r"ANVIL|GONG|STEEL\s?DRUM|SLEIGH", r"", 45)], 3),
        ],
    },
    "electronic_bass": {
        "title": "Electronic Bass",
        "desc": "808 subs, Reese, wobble, rap and dubstep bass.",
        "categories": [
            ("sub_808", [(r"\b808\b|SUB\s?BASS|SUB-?BASS|SUPERBASS", r"", 70)], 7),
            ("reese_dnb", [(r"REESE|JUNGL|D&B|DNB|NEURO", r"", 65)], 6),
            ("wobble_dubstep", [(r"WOBBLE|DUBSTEP|GROWL|GRIME", r"", 65)], 6),
            ("rap_bass", [(r"RAP.*BASS|BASS.*RAP|HIP.?HOP|TRAP", r"", 60)], 6),
            ("synth_sub_generic", [(r"SYNTH.*BASS|SYN.*BASS|ANALOG.*BASS", r"", 50)], 5),
            ("acid_bass", [(r"ACID|303", r"", 45)], 2),
        ],
    },
    "church_organ": {
        "title": "Church & Cathedral Organ",
        "desc": "Pipe organs, cathedral registrations, chapel and processional.",
        "categories": [
            ("pipe_organ", [(r"PIPE\s?ORG|CHURCH\s?ORG|CATHEDRAL", r"", 75)], 9),
            ("chapel", [(r"CHAPEL|PROCESSION|HYMN|LITURG", r"", 60)], 6),
            ("full_registration", [(r"FULL\s?ORG|GRAND\s?ORG|ORGAN\s?FULL|PLENUM", r"", 60)], 6),
            ("church_bell_organ", [(r"CHURCH|CATHEDRAL|MASS", r"", 50)], 5),
            ("reed_organ", [(r"REED|VOX\s?HUMANA|TROMPETTE|CROMORNE", r"", 45)], 4),
            ("positive_organ", [(r"POSITIV|PORTATIV|BAROQUE\s?ORG", r"", 40)], 2),
        ],
    },
}

# Trusted collections, in descending order of quality.
COLLECTION_RANK = {
    "_Best_Of": 100, "BobbyBlues": 95, "Dexed_cart": 90, "YamahaBlackBoxes": 88,
    "DaveBenson": 85, "MiniDexed_Library": 80, "SynprezFM": 75, "TheIntrovert": 70,
    "Musical Artifacts": 60, "Extra Collections": 55, "Magazines": 50,
    "Growl & Bass": 45, "Growl & Bass Picks": 45,
}

JUNK = re.compile(r"^[\s\W]*$|^INIT|^\*?\s*INIT\b|^\s*\.*\s*$", re.I)
CTRL = re.compile(r"[\x00-\x1f\x7f]")


def clean_name(name: str) -> str:
    """Remove control chars and collapse whitespace."""
    s = CTRL.sub(" ", name)
    return re.sub(r"\s+", " ", s).strip()


def norm(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return re.sub(r"(.)\1{2,}", r"\1", s)


def stem(name: str) -> str:
    """Coarse family key so numbered variants collapse together."""
    return re.sub(r"\d+$", "", norm(name))


# --- Library scanning ------------------------------------------------------

def read_voice_body(path: Path) -> bytes:
    data = path.read_bytes()
    if len(data) == 4104 and data[:6] == bytes([0xF0, 0x43, 0x00, 0x09, 0x20, 0x00]):
        return data[6:6 + 4096]
    if len(data) == 4096:
        return data
    raise ValueError(f"unexpected bank size {len(data)} for {path}")


def scan_library(root: Path) -> list[tuple[str, int, str]]:
    """Return (relpath, voice_index, name) for every voice in every 32-voice bank."""
    rows: list[tuple[str, int, str]] = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if not f.lower().endswith(".syx"):
                continue
            p = Path(dirpath) / f
            try:
                data = p.read_bytes()
            except OSError:
                continue
            if len(data) == 4104 and data[:6] == bytes([0xF0, 0x43, 0x00, 0x09, 0x20, 0x00]):
                body = data[6:6 + 4096]
            elif len(data) == 4096:
                body = data
            else:
                continue
            rel = str(p.relative_to(root))
            for n in range(32):
                v = body[n * 128:(n + 1) * 128]
                if len(v) < 128:
                    continue
                nm = v[118:128].split(b"\x00")[0].decode("latin-1")
                nm = clean_name(nm)
                if nm:
                    rows.append((rel, n, nm))
    return rows


def score_voice(name: str, patterns: list[tuple[str, str, int]]) -> int:
    best = 0
    for inc, exc, w in patterns:
        if re.search(inc, name, re.I):
            if exc and re.search(exc, name, re.I):
                continue
            if w > best:
                best = w
    return best


def select(rows, categories, limit=32):
    scored_by_cat: dict[str, list] = {label: [] for label, _, _ in categories}
    for path, idx, name in rows:
        if JUNK.search(name):
            continue
        if not (2 <= len(name) <= 20):
            continue
        cw = COLLECTION_RANK.get(path.split("/", 1)[0], 30)
        for label, patterns, _ in categories:
            w = score_voice(name, patterns)
            if w > 0:
                scored_by_cat[label].append((w * 1000 + cw, name, path, idx))

    for label in scored_by_cat:
        scored_by_cat[label].sort(reverse=True)

    chosen: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    seen_stems: set[str] = set()

    def take(label, quota):
        got = 0
        for _, nm, path, idx in scored_by_cat[label]:
            if got >= quota:
                break
            nk, sk = norm(nm), stem(nm)
            if nk in seen_names or (sk and sk in seen_stems):
                continue
            seen_names.add(nk)
            if sk:
                seen_stems.add(sk)
            chosen.append((nm, path, idx))
            got += 1
        return got

    shortfall = 0
    for label, _, quota in categories:
        shortfall += quota - take(label, quota)

    if shortfall > 0:
        pool = sorted((e for l in scored_by_cat for e in scored_by_cat[l]), reverse=True)
        for _, nm, path, idx in pool:
            if shortfall <= 0:
                break
            nk, sk = norm(nm), stem(nm)
            if nk in seen_names or (sk and sk in seen_stems):
                continue
            seen_names.add(nk)
            if sk:
                seen_stems.add(sk)
            chosen.append((nm, path, idx))
            shortfall -= 1

    return chosen[:limit]


def build_bank(voices, library: Path) -> bytes:
    body = bytearray()
    for i in range(32):
        if i < len(voices):
            _, path, idx = voices[i]
            bank_body = read_voice_body(library / path)
            voice = bytearray(bank_body[idx * 128:(idx + 1) * 128])
            raw = voice[118:128].split(b"\x00")[0].decode("latin-1")
            voice[118:128] = clean_name(raw)[:10].encode("latin-1").ljust(10, b" ")
            body += voice
        else:
            body += bytes(128)
    header = bytes([0xF0, 0x43, 0x00, 0x09, 0x20, 0x00])
    body_b = bytes(body)
    checksum = (-sum(body_b)) & 0x7F  # header EXCLUDED — M-VAVE rule
    return header + body_b + bytes([checksum, 0xF7])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", required=True, help="root of the .syx DX7 collection")
    ap.add_argument("--out", required=True, help="output directory for generated banks")
    ap.add_argument("--only", nargs="*", help="build only these theme keys")
    args = ap.parse_args()

    library = Path(os.path.expanduser(args.library)).resolve()
    out = Path(os.path.expanduser(args.out)).resolve()
    out.mkdir(parents=True, exist_ok=True)

    print(f"[*] scanning {library} ...")
    rows = scan_library(library)
    print(f"[*] {len(rows)} voices indexed")

    themes = THEMES
    if args.only:
        themes = {k: v for k, v in THEMES.items() if k in args.only}

    for key, spec in themes.items():
        voices = select(rows, spec["categories"], limit=32)
        bank = build_bank(voices, library)
        outfile = out / f"FM-1_{key}.syx"
        outfile.write_bytes(bank)
        print(f"[+] {key}: {len(voices)} voices -> {outfile.name}")


if __name__ == "__main__":
    main()
