#!/usr/bin/env python3
"""Render a demo phrase for one FM-1 bank to MP3.

Measures each candidate patch's true fundamental, picks one that is in tune,
plays a 16-step phrase matched to the bank's theme, levels by RMS, encodes MP3.

Usage:
    python3 render_demo.py --bank banks/FM-1_synthwave_pad.syx \
        --theme pad --out docs/audio/FM-1_synthwave_pad.mp3
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 120.0
STEP = 60.0 / (BPM * 4)          # a 16th note
STEPS = 32                        # 16 steps, duplicated = 2 bars
REF_NOTE = 60                     # C4
REF_HZ = 261.63


# ── phrases, per theme ───────────────────────────────────────────────────────
# A step is (notes, hold):
#   notes = list of (semitone_offset, velocity) -- several notes = a chord
#   hold  = how many 16th-steps the note is HELD (sustained), 1 = a 16th, 4 = a beat,
#           8 = a half bar, 16 = a bar. Chords are held across steps, not retriggered.
# A rest is ([], 1). 16 step-slots make one bar at 16ths; the phrase is doubled.
#
# Chord vocabulary (semitones from root):
#   m   = [0,3,7]      M   = [0,4,7]      m7  = [0,3,7,10]
#   M7  = [0,4,7,11]   sus4= [0,5,7]      add9= [0,4,7,14]
#    7  = [0,4,7,10]   m9  = [0,3,7,10,14]
PHRASES: dict[str, dict] = {
    # ── monophonic: bass lines and acid ──
    "bass": {
        "root": 45,  # A2
        "steps": [([(0,110)],1),([(0,70)],1),([(12,110)],1),([(0,85)],1),
                  ([(3,100)],1),([(0,60)],1),([(0,110)],1),([(15,90)],1),
                  ([(0,100)],1),([(0,75)],1),([(10,110)],1),([(0,80)],1),
                  ([(7,95)],1),([(0,65)],1),([(0,105)],1),([(5,88)],1)],
    },
    "acid": {
        "root": 45,
        "steps": [([(0,110)],1),([(0,70)],1),([(12,110)],1),([(0,85)],1),
                  ([(3,100)],1),([(0,60)],1),([(0,110)],1),([(15,90)],1),
                  ([(0,100)],1),([(0,75)],1),([(10,110)],1),([(0,80)],1),
                  ([(7,95)],1),([(0,65)],1),([(0,105)],1),([(5,88)],1)],
    },
    "lead": {
        "root": 57,
        "steps": [([(0,110)],2),([(2,95)],1),([(4,100)],2),([(7,105)],1),
                  ([(9,95)],2),([(12,110)],2),([(7,90)],1),([(4,85)],1),
                  ([(0,105)],2),([(2,90)],1),([(5,100)],2),([(7,95)],1),
                  ([(12,110)],2),([(10,90)],1),([(7,85)],1),([(4,80)],2)],
    },
    # ── polyphonic: pad chords, changing every HALF BEAT (2 steps) ──
    # i - VI - III - VII - iv - i - V - i  (Am F C G Dm Am E Am)
    "pad": {
        "root": 57,  # A3
        # Am - F - C - G - Dm - Am - E - Am. Each chord HELD a full bar
        # (16 sixteenths), wrapped in a chord voicing with the root up an octave.
        "steps": [
            ([(0,86),(3,84),(7,82),(12,72)], 16),   # Am
            ([(-4,84),(-1,82),(2,80),(7,70)], 16),  # F
            ([(3,86),(7,84),(10,82),(15,72)], 16),  # C
            ([(-2,84),(2,82),(5,80),(10,70)], 16),  # G
            ([(5,84),(8,82),(12,80),(17,72)], 16),  # Dm
            ([(0,86),(3,84),(7,82),(12,74)], 16),   # Am
            ([(7,84),(11,82),(14,80),(19,72)], 16), # E
            ([(0,82),(3,80),(7,78),(12,68)], 16),   # Am (resolve)
        ],
    },
    # ── polyphonic: keys comp with syncopation, chord per beat/half-beat ──
    # Cmaj7 - Am7 - Dm7 - G7, with off-beat stabs.
    "keys": {
        "root": 48,  # C3
        # Cmaj7 - Am7 - Dm7 - G7, one chord per bar, HELD 16 sixteenths.
        # (A comping rhythm was tried first, but a held progression reads clearer
        #  as a demo and avoids retriggering the same chord every 16th.)
        "steps": [
            ([(0,100),(4,92),(7,90),(11,80)], 16),    # Cmaj7
            ([(9,96),(12,90),(16,88),(21,80)], 16),   # Am7
            ([(2,100),(5,94),(9,90),(12,80)], 16),    # Dm7
            ([(-3,96),(0,90),(2,86),(7,76)], 16),     # G7
            ([(0,100),(4,92),(7,90),(11,80)], 16),    # Cmaj7
            ([(9,96),(12,90),(16,88),(21,80)], 16),   # Am7
            ([(2,100),(5,94),(9,90),(12,80)], 16),    # Dm7
            ([(-3,96),(0,90),(2,86),(7,76)], 16),     # G7
        ],
    },
    # ── percussive: chord stabs on beats/half-beats, short hold ──
    "perc": {
        "root": 48,
        "steps": [([(0,116),(7,102)], 2),
                  ([], 2),
                  ([(12,86),(19,78)], 2),
                  ([], 2),
                  ([(3,106),(10,96)], 2),
                  ([], 2),
                  ([(7,92),(12,84)], 2),
                  ([], 2),
                  ([(0,112),(5,100)], 2),
                  ([], 2),
                  ([(15,88)], 2),
                  ([], 2),
                  ([(10,104),(14,94)], 2),
                  ([], 2),
                  ([(5,90)], 2),
                  ([], 2)],
    },
}


def fundamental(patch, note: int = REF_NOTE) -> float:
    """Dominant frequency below 3 kHz for a patch at a reference note."""
    from dexed import DexedSynth
    s = DexedSynth(sample_rate=SR)
    s.load_patch(patch)
    a = s.render(midi_note=note, velocity=100, note_duration=1.2,
                 render_duration=1.4)
    F = np.abs(np.fft.rfft(a * np.hanning(len(a))))
    f = np.fft.rfftfreq(len(a), 1 / SR)
    m = f < 3000
    if not m.any() or F[m].max() <= 0:
        return 0.0
    return float(f[m][np.argmax(F[m])])


def octave_offset(patch) -> float:
    """How many octaves the patch is displaced, rounded to a whole octave."""
    f0 = fundamental(patch)
    if f0 <= 0:
        return 0.0
    off = np.log2(REF_HZ / f0)
    return float(np.round(off))


def pick_patch(patches):
    """Choose the first patch whose offset is a whole octave (i.e. usable)."""
    for i, p in enumerate(patches):
        f0 = fundamental(p)
        if f0 <= 0:
            continue
        err = np.log2(REF_HZ / f0)
        # keep patches that are a whole number of octaves off (correctable)
        if abs(err - round(err)) < 0.15:
            return i, p, float(round(err))
    return 0, patches[0], 0.0


def render_phrase(patch, offset_oct: float, phrase: dict) -> np.ndarray:
    from dexed import DexedSynth
    s = DexedSynth(sample_rate=SR)
    s.load_patch(patch)

    # Repeat the phrase so the loop reads as a loop, but keep the preview short:
    # target ~2 bars of 16ths (STEPS steps) per rep, and at most 2 reps.
    base = phrase["steps"]
    base_len = sum(h for _, h in base) or 1
    reps = max(1, min(2, round(STEPS / base_len) or 1))
    steps = base * reps
    root = phrase["root"] + int(offset_oct * 12)   # correct the patch's offset

    # total length = sum of all holds (in 16th steps), plus a tail
    total_steps = sum(hold for _, hold in steps)
    total = int(SR * STEP * total_steps) + SR
    out = np.zeros(total, dtype=np.float32)

    # per-note gain: chords stack, so keep headroom proportional to chord size
    poly = max((len(notes) for notes, _ in steps), default=1)
    vgain = 1.0 / max(1.0, poly ** 0.65)

    pos = 0                       # running position in 16th steps
    for notes, hold in steps:
        if notes:
            st = int(pos * SR * STEP)
            # a held chord is rendered ONCE and sustained; release just before the
            # next event so chords ring rather than retrigger every 16th
            dur = STEP * hold
            for semi, vel in notes:
                a = s.render(midi_note=root + semi, velocity=vel,
                             note_duration=dur,
                             render_duration=dur + STEP * 0.5)
                en = min(st + len(a), total)
                out[st:en] += a[:en - st] * vgain
        pos += hold

    out -= out.mean()                       # DC block
    rms = float(np.sqrt((out ** 2).mean()))
    if rms > 0:
        out *= 0.30 / rms                   # level by RMS, not peak
    peak = float(np.abs(out).max())
    if peak > 0.95:
        out *= 0.95 / peak
    return out


def write_wav(path: Path, audio: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--theme", required=True, choices=sorted(PHRASES))
    ap.add_argument("--out", required=True, help="output .mp3 path")
    ap.add_argument("--wav-dir", default="/tmp")
    args = ap.parse_args()

    from dexed import Patch

    bank = Path(args.bank)
    patches = Patch.load_bank(str(bank))
    idx, patch, off = pick_patch(patches)
    f0 = fundamental(patch)
    print(f"bank   : {bank.name}")
    print(f"patch  : slot {idx} {patch.name.strip()!r}")
    print(f"tuning : {f0:.1f} Hz at MIDI {REF_NOTE} "
          f"(target {REF_HZ:.1f}), offset {off:+.1f} oct")

    audio = render_phrase(patch, off, PHRASES[args.theme])
    dur = len(audio) / SR
    print(f"audio  : {dur:.2f}s, peak {np.abs(audio).max():.3f}, "
          f"rms {np.sqrt((audio**2).mean()):.3f}")

    wav = Path(args.wav_dir) / (bank.stem + ".wav")
    write_wav(wav, audio)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                    "-codec:a", "libmp3lame", "-b:a", "96k", str(out)], check=True)
    print(f"wrote  : {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
