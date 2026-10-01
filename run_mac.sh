#!/usr/bin/env bash
# Runs Desktop Hamster on macOS for testing.
# First run sets up a private Python environment in this folder (~1 min); later runs start instantly.
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Run:  xcode-select --install   then try again."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "First run: installing PyQt6 into ./.venv ..."
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet PyQt6
fi

echo "Starting hamster. Right-click it -> 'Say goodbye' to quit (or Ctrl+C here)."
exec .venv/bin/python hamster.py
