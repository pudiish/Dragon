#!/usr/bin/env bash
set -euo pipefail

# If .venv exists, prefer it
if [ -f .venv/bin/activate ]; then
  # shellcheck source=/dev/null
  . .venv/bin/activate
fi

# If python-dotenv is installed in the venv, python script will load .env; otherwise use dotenv-cli
if python -c 'import dotenv' 2>/dev/null; then
  python scripts/groq_test.py
else
  if [ -f .env ]; then
    set -a
    # shellcheck source=/dev/null
    . .env
    set +a
  fi
  python scripts/groq_test.py
fi
