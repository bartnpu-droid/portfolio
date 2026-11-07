#!/bin/bash
# One-click run: installs what's needed and builds the lead report.
set -e
cd "$(dirname "$0")"
echo "== Lead generator =="
PY=$(command -v python3 || true)
[ -z "$PY" ] && { echo "Python 3 is required: https://www.python.org/downloads/"; exit 1; }
# Recreate the virtual environment if the folder was moved (its paths are absolute)
if [ -d .venv ] && ! .venv/bin/python -c "import sys" >/dev/null 2>&1; then rm -rf .venv; fi
if [ -d .venv ] && ! grep -q "$(pwd)/.venv" .venv/bin/activate 2>/dev/null; then rm -rf .venv; fi
[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
python leadgen.py config.json "$@"
open output 2>/dev/null || true
