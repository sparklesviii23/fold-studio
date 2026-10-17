#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
: "${FOLD_DEV_TOKEN:?Set FOLD_DEV_TOKEN to a development-only token}"
export VITE_FOLD_DEV_TOKEN="$FOLD_DEV_TOKEN"
python3 scientific/worker.py --root "${FOLD_DATA_DIR:-../../validation/preview-library}" --fixtures fixtures --serve 1425 &
service_pid=$!
trap 'kill "$service_pid" 2>/dev/null || true' EXIT INT TERM
pnpm dev
