#!/usr/bin/env python3
"""Render a short preview for EVERY patch in every bank.

Bank-level previews (render_demo.py) show what a bank is like. These are
per-patch: a four-note arpeggio so you can hear one voice on its own while
picking patches in the gallery's bank builder.

Written as one small MP3 per patch. They are lazy-loaded by the page, so the
total size matters -- keep them short and low bitrate.

Usage:
    python3 render_patches.py                 # all patches, all banks
    python3 render_patches.py --only organ    # one bank
    python3 render_patches.py --list          # show what would be rendered
"""
from __future__ import annotations

import argparse
import os
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
NOTE_MS = 380               # length of each preview note
GAP_MS = 30
BITRATE = "64k"
PREVIEW_INTERVALS = (0, 4, 7, 12)   # root, third, fifth, octave


def render_patch(patch, note: int = 60) -> np.ndarray:
    """A root-third-fifth-octave arpeggio, so the voice is recognisable."""
    from dexed import DexedSynth
    s = DexedSynth(sample_rate=SR)
    s.load_patch(patch)
    dur = NOTE_MS / 1000.0
    gap = np.zeros(int(SR * GAP_MS / 1000.0), dtype=np.float32)
    chunks = []
    for i, semi in enumerate(PREVIEW_INTERVALS):
        a = s.render(midi_note=note + semi, velocity=100,
                     note_duration=dur * 0.92, render_duration=dur)
        chunks.append(a.astype(np.float32))
        if i < len(PREVIEW_INTERVALS) - 1:
            chunks.append(gap)
    out = np.concatenate(chunks)
    out -= out.mean()
    peak = float(np.abs(out).max())
    if peak > 0:
        out *= 0.85 / peak
    return out


def write_wav(path: Path, audio: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank-dir", default="banks")
    ap.add_argument("--out", default="docs/audio/patches")
    ap.add_argument("--only", help="single bank key, e.g. organ")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    from dexed import Patch

    banks = sorted(Path(args.bank_dir).glob("*.syx"))
    if args.only:
        banks = [b for b in banks if args.only in b.stem]

    outdir = Path(args.out)
    if not args.list:
        outdir.mkdir(parents=True, exist_ok=True)
    tmp = Path("/tmp/_patchprev.wav")

    total = 0
    for bank in banks:
        key = bank.stem[len("FM-1_"):] if bank.stem.startswith("FM-1_") else bank.stem
        patches = Patch.load_bank(str(bank))
        names = []
        for i, p in enumerate(patches):
            nm = p.name.strip()
            names.append(nm)
            if args.list:
                continue
            dst = outdir / f"{key}__{i:02d}.mp3"
            if dst.exists() and dst.stat().st_mtime > bank.stat().st_mtime:
                continue                      # up to date
            audio = render_patch(p)
            write_wav(tmp, audio)
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(tmp),
                 "-codec:a", "libmp3lame", "-b:a", BITRATE, str(dst)],
                check=True,
            )
            total += 1
        if args.list:
            print(f"{key}: {len(names)} patches")
    if not args.list:
        files = list(outdir.glob("*.mp3"))
        size = sum(f.stat().st_size for f in files) / 1024 / 1024
        print(f"rendered {total} new, {len(files)} total, {size:.1f} MB")


if __name__ == "__main__":
    main()
