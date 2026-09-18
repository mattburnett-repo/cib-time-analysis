#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required but was not found on PATH" >&2
  exit 1
fi

PYTHON="$(command -v python3)"
echo "Using Python: $PYTHON ($("$PYTHON" --version 2>&1))"

if [[ ! -d .venv ]]; then
  echo "Creating virtual environment in .venv ..."
  "$PYTHON" -m venv .venv
else
  echo "Virtual environment already exists at .venv"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Upgrading pip ..."
python -m pip install --upgrade pip

if [[ ! -f requirements.txt ]]; then
  echo "error: requirements.txt not found in $ROOT" >&2
  exit 1
fi

echo "Installing dependencies from requirements.txt ..."
python -m pip install -r requirements.txt

if [[ ! -d csv_data ]]; then
  echo "warning: csv_data/ not found — datasets expected by the app are missing" >&2
fi

chmod a+x start.sh 2>/dev/null || true

echo
echo "Setup complete."
echo "Run the app with: ./start.sh"
