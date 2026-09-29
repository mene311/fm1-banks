#!/usr/bin/env bash
# Push four banks to the FM-1 in sequence, then prompt for SAVE on each.
#
# Usage:
#   ./fm1_send_set.sh banks/FM-1_synthwave_bass.syx banks/FM-1_synthwave_pad.syx \
#                     banks/FM-1_acid_techno.syx banks/FM-1_drums_perc.syx
#
# The FM-1 shows its A/B/C/D bank-select screen after each file. Choose the bank,
# hold SAVE, then press Enter here to send the next one.
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <bank.syx> [bank.syx ...]" >&2
  exit 1
fi

here="$(cd "$(dirname "$0")" && pwd)"
n=0
for bank in "$@"; do
  n=$((n + 1))
  echo
  echo "── $n/$#  $(basename "$bank") ──"
  python3 "$here/fm1_send_bank.py" "$bank" --wait 10
done

echo
echo "all $# sent. hold SAVE on the last one if you have not yet."
