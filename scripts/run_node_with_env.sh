#!/usr/bin/env bash
set -euo pipefail

# Load .env into environment (exports variables) and run the Node test
if [ -f .env ]; then
	set -a
	# shellcheck source=/dev/null
	. .env
	set +a
fi

node scripts/groq_test.mjs
