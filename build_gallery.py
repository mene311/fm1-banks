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


def load_provenance() -> dict:
    """Read banks/provenance.json, written by fm1_banks.py.

    Absent on a checkout that has not been rebuilt; that degrades to no
    attribution rather than a hard failure.
    """
    p = BANKS / "provenance.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


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

    Each patch also carries its source collection, joined from the provenance
    sidecar written by fm1_banks.py. The name is stored once per patch as an
    index into a collections table rather than repeated inline: 832 patches
    x a 13-character name is real weight on a file the page fetches on load.
    """
    import base64

    prov = load_provenance()
    collections: list[str] = []
    col_index: dict[str, int] = {}

    rows = []
    for src in sorted(BANKS.glob("*.syx")):
        key = src.stem[len("FM-1_"):] if src.stem.startswith("FM-1_") else src.stem
        body = src.read_bytes()[6:6 + 4096]
        bank_prov = prov.get(key, [])
        for i in range(32):
            voice = body[i * 128:(i + 1) * 128]
            if not voice:
                continue
            name = voice[118:128].split(b"\x00")[0].decode("latin-1").rstrip()
            if not name:
                continue
            row = {
                "k": key,
                "i": i,
                "n": name,
                "d": base64.b64encode(voice).decode("ascii"),
            }
            if i < len(bank_prov):
                col = bank_prov[i]["collection"]
                if col not in col_index:
                    col_index[col] = len(collections)
                    collections.append(col)
                row["c"] = col_index[col]
                row["f"] = bank_prov[i]["file"]
                row["s"] = bank_prov[i]["index"]
            rows.append(row)

    (DOCS / "patches.json").write_text(
        json.dumps({"collections": collections, "patches": rows},
                   separators=(",", ":")) + "\n"
    )
    print(f"[+] docs/patches.json: {len(rows)} patches "
          f"({len(collections)} collections, "
          f"{(DOCS / 'patches.json').stat().st_size / 1024:.0f} KB)")


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
        entry = {
            "key": key,
            "title": meta["title"],
            "desc": meta["desc"],
            "file": src.name,
            "slots": voice_names(src),
        }
        # attach a demo preview if one has been rendered
        audio = DOCS / "audio" / f"FM-1_{key}.mp3"
        if audio.exists():
            entry["audio"] = audio.name
        entries.append(entry)

    (DOCS / "banks.json").write_text(json.dumps(entries, indent=2) + "\n")
    print(f"[+] docs/banks.json: {len(entries)} banks, "
          f"{len(entries) * 32} patches")
    print(f"[+] docs/banks/: {len(list(DOCS_BANKS.glob('*.syx')))} files")
    write_patch_index()


if __name__ == "__main__":
    main()
