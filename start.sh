#!/usr/bin/env bash
set -euo pipefail

# Activate virtualenv if present
if [ -f .venv/bin/activate ]; then
  # shellcheck source=/dev/null
  . .venv/bin/activate
fi

export PYTHONUNBUFFERED=1

echo "Starting VibeMind (Streamlit)..."
streamlit run app.py
