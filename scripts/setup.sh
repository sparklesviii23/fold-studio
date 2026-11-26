#!/usr/bin/env bash
# Set up a fold workspace on a new Apple Silicon Mac.
#
#   bash scripts/setup.sh              # app dependencies + Python runtimes
#   bash scripts/setup.sh --models     # also download pinned models (~18 GB)
#   bash scripts/setup.sh --only gbcell   # rebuild one runtime
#
# Layout (the workspace is the folder that contains this repository):
#   <workspace>/fold   this repository
#   <workspace>/runtimes      Python venvs built from runtimes-lock/*.txt
#   <workspace>/models        AlphaFold parameters
#   <workspace>/validation    model store and research library
# Override the workspace with FOLD_WORKSPACE=/path.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="${FOLD_WORKSPACE:-$(dirname "$REPO")}"
MODELS=0
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --models) MODELS=1 ;;
    --only) ONLY="$2"; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo "fold needs macOS on Apple Silicon (Metal). Found $(uname -s) $(uname -m)." >&2
  exit 1
fi

PYTHON="${FOLD_PYTHON:-$(command -v python3.12 || true)}"
if [ -z "$PYTHON" ]; then
  echo "Python 3.12 is required. Install it with: brew install python@3.12" >&2
  exit 1
fi
echo "Workspace: $WORKSPACE"
echo "Python:    $PYTHON ($("$PYTHON" -c 'import sys;print(sys.version.split()[0])'))"

if [ -z "$ONLY" ]; then
  command -v pnpm >/dev/null || { echo "pnpm is required: brew install pnpm" >&2; exit 1; }
  command -v cargo >/dev/null || echo "Note: Rust (cargo) is needed to build the desktop app: https://rustup.rs"
  (cd "$REPO" && pnpm install --frozen-lockfile)
fi

mkdir -p "$WORKSPACE/runtimes"
for lock in "$REPO"/runtimes-lock/*.txt; do
  name="$(basename "$lock" .txt)"
  [ -n "$ONLY" ] && [ "$name" != "$ONLY" ] && continue
  venv="$WORKSPACE/runtimes/$name"
  if [ -x "$venv/bin/python" ] && [ -z "$ONLY" ]; then
    echo "runtime $name: exists, skipped (use --only $name to rebuild)"
    continue
  fi
  echo "runtime $name: building"
  rm -rf "$venv"
  "$PYTHON" -m venv "$venv"
  "$venv/bin/python" -m pip install --quiet --upgrade pip
  # The lock is a full pip freeze, so install exactly it without re-resolving.
  "$venv/bin/python" -m pip install --quiet --no-deps -r "$lock"
done

if [ "$MODELS" = 1 ]; then
  FOLD_WORKSPACE="$WORKSPACE" "$PYTHON" "$REPO/scripts/fetch-models.py"
  for model in model_1_ptm model_2_ptm model_1_multimer_v3 model_2_multimer_v3 model_3_multimer_v3 model_4_multimer_v3 model_5_multimer_v3; do
    if [ -f "$WORKSPACE/models/alphafold/params_$model.npz" ]; then
      echo "  ok      models/alphafold/params_$model.npz"
    else
      "$PYTHON" "$REPO/scripts/fetch-af2-parameter.py" --model "$model" --directory "$WORKSPACE/models/alphafold"
    fi
  done
fi

echo
echo "Done. Next:"
echo "  cd $REPO && pnpm test && pnpm desktop"
[ "$MODELS" = 1 ] || echo "  Models were not downloaded. Run: bash scripts/setup.sh --models"
