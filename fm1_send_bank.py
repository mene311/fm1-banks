#!/usr/bin/env python3
"""Send a DX7 bank (.syx) to the M-VAVE FM-1 over ALSA MIDI, no browser needed.

Protocol (from benny-sparra/fm1-dx7-patch-importer, src/lib/dx7.ts):

    Bank message:  F0 43 <ch-1> 09 20 00 <4096 bytes> <checksum> F7
    checksum    =  (128 - (sum(4096 bytes) & 0x7F)) & 0x7F      # data only

The FM-1 shows a bank-select screen (A/B/C/D) when it receives a valid bank. It
does not reply, so a successful send is silent; confirm on the device.

Usage:
    python3 fm1_send_bank.py banks/FM-1_organ.syx            # auto-detect port
    python3 fm1_send_bank.py banks/FM-1_organ.syx --port 36:0
    python3 fm1_send_bank.py banks/FM-1_organ.syx --dry-run
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import rtmidi

BANK_BYTES = 4096
BANK_VOICES = 32
VOICE_BYTES = 128

# The FM-1's own preset upload is one message at a time. M-UPGRADE and the web
# editor space their writes out; give the device room to absorb each one.
INTER_MESSAGE_MS = 25


def checksum(data: bytes) -> int:
    """Yamaha bulk-dump checksum: two's complement of the data sum, in seven bits."""
    return (128 - (sum(data) & 0x7F)) & 0x7F


def load_bank(path: Path) -> bytes:
    """Return the 4096 data bytes of a 32-voice DX7 bank file."""
    raw = path.read_bytes()
    # F0 43 <ch> 09 20 00 <4096> <chk> F7  -> data sits at 6..4102
    if raw[:1] != b"\xf0" or raw[-1:] != b"\xf7":
        raise ValueError(f"{path.name}: not a SysEx file (needs F0 ... F7)")
    if len(raw) == 4104:
        data = raw[6:6 + BANK_BYTES]
    elif len(raw) == 4102:
        data = raw[6:6 + BANK_BYTES]
    elif len(raw) == BANK_BYTES:
        data = raw
    else:
        raise ValueError(f"{path.name}: unexpected size {len(raw)} bytes")
    if len(data) != BANK_BYTES:
        raise ValueError(f"{path.name}: got {len(data)} data bytes, need {BANK_BYTES}")
    return data


def bank_message(data: bytes, channel: int = 1) -> list[int]:
    """Full SysEx bank message as a list of ints, ready for rtmidi."""
    payload = [(channel - 1) & 0x0F, 0x09, 0x20, 0x00]
    return [0xF0, 0x43, *payload, *data, checksum(data), 0xF7]


def voice_names(data: bytes) -> list[str]:
    out = []
    for i in range(BANK_VOICES):
        v = data[i * VOICE_BYTES:(i + 1) * VOICE_BYTES]
        nm = v[118:128].split(b"\x00")[0].decode("latin-1").rstrip()
        out.append(nm)
    return out


def find_fm1(api) -> int | None:
    """Index of the FM-1 output port, or None."""
    out = rtmidi.MidiOut(api)
    for i, name in enumerate(out.get_ports()):
        low = name.lower()
        if "fm-1" in low or "fm1" in low:
            out.delete()
            return i
    out.delete()
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bank", help="path to a 32-voice DX7 .syx file")
    ap.add_argument("--port", help="ALSA port name, e.g. 36:0 or 'FM-1 MIDI 1'")
    ap.add_argument("--channel", type=int, default=1, choices=range(1, 17))
    ap.add_argument("--dry-run", action="store_true", help="build the message, send nothing")
    ap.add_argument("--wait", action="store_true",
                    help="after sending, wait for Enter (so you can pick a bank and SAVE)")
    args = ap.parse_args()

    path = Path(args.bank)
    data = load_bank(path)
    msg = bank_message(data, args.channel)
    names = voice_names(data)

    print(f"file    : {path.name}")
    print(f"data    : {len(data)} bytes, checksum 0x{checksum(data):02X}")
    print(f"message : {len(msg)} bytes total (F0 43 {args.channel - 1:02X} 09 20 00 ...)")
    print(f"voices  : {', '.join(names[:6])}{' ...' if len(names) > 6 else ''}")

    if args.dry_run:
        print("dry run : nothing sent")
        return 0

    api = rtmidi.API_LINUX_ALSA
    out = rtmidi.MidiOut(api)
    ports = out.get_ports()

    if args.port:
        idx = next((i for i, n in enumerate(ports) if args.port in n), None)
        if idx is None:
            print(f"error   : no port matching {args.port!r}", file=sys.stderr)
            print("ports   : " + " | ".join(ports), file=sys.stderr)
            return 1
    else:
        idx = find_fm1(api)
        if idx is None:
            print("error   : no FM-1 output port found", file=sys.stderr)
            print("ports   : " + " | ".join(ports), file=sys.stderr)
            return 1

    print(f"port    : {ports[idx]}")
    try:
        out.open_port(idx)
    except Exception as exc:
        print(f"error   : could not open port: {exc}", file=sys.stderr)
        print("hint    : something else holds it (Renoise, PipeWire, qpwgraph).",
              file=sys.stderr)
        return 1

    out.send_message(msg)
    print(f"sent    : {len(msg)} bytes to {(ports[idx])}")
    time.sleep(INTER_MESSAGE_MS / 1000.0)
    out.close_port()

    print("waiting : pick the bank on the FM-1 (A/B/C/D), hold SAVE")
    if args.wait:
        try:
            input("          press Enter when saved > ")
        except EOFError:
            pass
    else:
        print("          run with --wait to pause here for the next one")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
