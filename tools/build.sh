#!/usr/bin/env bash
#     ,_,
#    (O,O)
#    (   )   Mïmïr
#  ---"-"---
set -euo pipefail
cd "$(dirname "$0")/.."
export BASE="${BASE:-/dao-arts/}"
MEASURE=1 python3 tools/convert.py
python3 tools/measure.py "${PROCS:-5}" | grep -v '"GET'
python3 tools/convert.py
