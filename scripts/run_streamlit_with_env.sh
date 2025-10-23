#!/usr/bin/env bash
set -euo pipefail

# Prefer venv python if available
PY_CMD=python3
if [ -f .venv/bin/activate ]; then
  # shellcheck source=/dev/null
  . .venv/bin/activate
  PY_CMD=.venv/bin/python
fi

# Ensure streamlit installed
if ! $PY_CMD -c "import streamlit" 2>/dev/null; then
  echo "streamlit not found in current python environment. Install requirements first." >&2
  exit 2
fi

if [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  . .env
  set +a
fi

$PY_CMD -m streamlit run app.py
