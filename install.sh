#!/usr/bin/env bash
# Whiteboard Explainer kit installer: Python deps, ffmpeg check, unpack assets.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
command -v "$PY" >/dev/null || { echo "ERROR: $PY not found (Python 3.10+ needed)"; exit 1; }
"$PY" -c 'import sys; assert sys.version_info>=(3,10), sys.version' || { echo "ERROR: Python 3.10+ needed"; exit 1; }
echo "== installing Python packages"
"$PY" -m pip install --upgrade -r requirements.txt || "$PY" -m pip install --break-system-packages -r requirements.txt
echo "== checking ffmpeg"
if ! command -v ffmpeg >/dev/null; then
  echo "ERROR: ffmpeg not found on PATH. Install it first:"
  echo "  macOS: brew install ffmpeg | Debian/Ubuntu: sudo apt install ffmpeg | Windows: winget install ffmpeg"
  exit 1
fi
ffmpeg -version | head -1
echo "== unpacking assets"
"$PY" tools/unpack_assets.py
echo "== done. Try: $PY -m wb.render examples/coached_vs_solo_16x9.json"
