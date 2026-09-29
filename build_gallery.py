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


if __name__ == "__main__":
    main()
