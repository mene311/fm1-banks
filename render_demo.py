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


# ── phrases, per theme (root-relative semitone offsets from the phrase root) ──
# (offset, velocity)  Each is 16 steps; doubled to 32 for the loop.
PHRASES: dict[str, dict] = {
    "bass": {
        "root": 45,  # A2
        "steps": [(0,110),(0,70),(12,110),(0,85),(3,100),(0,60),(0,110),(15,90),
                  (0,100),(0,75),(10,110),(0,80),(7,95),(0,65),(0,105),(5,88)],
    },
    "pad": {
        "root": 57,  # A3, chord tones, slower feel
        "steps": [(0,95),(0,0),(7,90),(0,0),(4,85),(0,0),(0,80),(12,75),
                  (3,90),(0,0),(10,85),(0,0),(7,80),(0,0),(0,75),(5,70)],
    },
    "acid": {
        "root": 45,
        "steps": [(0,110),(0,70),(12,110),(0,85),(3,100),(0,60),(0,110),(15,90),
                  (0,100),(0,75),(10,110),(0,80),(7,95),(0,65),(0,105),(5,88)],
    },
    "lead": {
        "root": 57,
        "steps": [(0,110),(2,95),(4,100),(7,105),(9,95),(12,110),(7,90),(4,85),
                  (0,105),(2,90),(5,100),(7,95),(12,110),(10,90),(7,85),(4,80)],
    },
    "keys": {
        "root": 48,  # C3
        "steps": [(0,100),(4,90),(7,95),(12,100),(7,88),(4,92),(0,100),(0,80),
                  (5,95),(9,90),(12,95),(16,100),(12,88),(9,92),(5,95),(0,85)],
    },
    "perc": {
        "root": 48,
        "steps": [(0,120),(0,0),(12,70),(0,0),(3,100),(0,0),(7,85),(0,0),
                  (0,115),(0,0),(15,75),(0,0),(10,95),(0,0),(5,80),(0,0)],
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

    steps = phrase["steps"] * (STEPS // len(phrase["steps"]))
    root = phrase["root"] + int(offset_oct * 12)   # correct the patch's offset

    total = int(SR * STEP * len(steps)) + SR
    out = np.zeros(total, dtype=np.float32)
    for i, (semi, vel) in enumerate(steps):
        if vel == 0:
            continue
        a = s.render(midi_note=root + semi, velocity=vel,
                     note_duration=STEP * 0.95, render_duration=STEP * 1.0)
        st = int(i * SR * STEP)
        en = min(st + len(a), total)
        out[st:en] += a[:en - st]

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
