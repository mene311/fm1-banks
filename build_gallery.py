#!/usr/bin/env python3
"""Refresh the GitHub Pages gallery from the banks in ./banks.

Regenerates docs/banks.json and mirrors banks/*.syx into docs/banks/ (GitHub
Pages does not follow symlinks, so the files must be copied).

Run after `fm1_banks.py` has rebuilt the banks.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BANKS = ROOT / "banks"
DOCS = ROOT / "docs"
DOCS_BANKS = DOCS / "banks"


def load_themes() -> dict:
    spec = importlib.util.spec_from_file_location("fm1_banks", ROOT / "fm1_banks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.THEMES


def voice_names(path: Path) -> list[str]:
    data = path.read_bytes()[6:6 + 4096]
    out = []
    for n in range(32):
        v = data[n * 128:(n + 1) * 128]
        nm = v[118:128].split(b"\x00")[0].decode("latin-1").rstrip()
        out.append(nm)
    return out


def write_patch_index() -> None:
    """Emit docs/patches.json: every patch's raw 128 bytes, base64, for the
    in-browser bank builder.

    This is DERIVED from banks/*.syx. Regenerate it whenever the banks change --
    run this script, or let the CI workflow do it on push.
    """
    import base64
    rows = []
    for src in sorted(BANKS.glob("*.syx")):
        key = src.stem[len("FM-1_"):] if src.stem.startswith("FM-1_") else src.stem
        body = src.read_bytes()[6:6 + 4096]
        for i in range(32):
            voice = body[i * 128:(i + 1) * 128]
            if not voice:
                continue
            name = voice[118:128].split(b"\x00")[0].decode("latin-1").rstrip()
            if not name:
                continue
            rows.append({
                "k": key,
                "i": i,
                "n": name,
                "d": base64.b64encode(voice).decode("ascii"),
            })
    (DOCS / "patches.json").write_text(
        json.dumps(rows, separators=(",", ":")) + "\n"
    )
    print(f"[+] docs/patches.json: {len(rows)} patches "
          f"({(DOCS / 'patches.json').stat().st_size / 1024:.0f} KB)")


def main() -> None:
    themes = load_themes()
    DOCS_BANKS.mkdir(parents=True, exist_ok=True)

    entries = []
    for key, meta in themes.items():
        src = BANKS / f"FM-1_{key}.syx"
        if not src.exists():
            print(f"[!] missing {src.name}, skipping")
            continue
        shutil.copy2(src, DOCS_BANKS / src.name)
        entries.append({
            "key": key,
            "title": meta["title"],
            "desc": meta["desc"],
            "file": src.name,
            "slots": voice_names(src),
        })

    (DOCS / "banks.json").write_text(json.dumps(entries, indent=2) + "\n")
    print(f"[+] docs/banks.json: {len(entries)} banks, "
          f"{len(entries) * 32} patches")
    print(f"[+] docs/banks/: {len(list(DOCS_BANKS.glob('*.syx')))} files")
    write_patch_index()


if __name__ == "__main__":
    main()
