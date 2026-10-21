#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
repository="$PWD"
app="$repository/../current/FOLD STUDIO Metal Dev.app"
python3 scripts/install-current-app.py --destination "$app" --check-only
# One disposable build directory, one installed app. No dated release directories.
export CARGO_TARGET_DIR="$repository/../build-cache/current"
mkdir -p "$CARGO_TARGET_DIR"
if ! mkdir "$repository/../.current-build-lock"; then
  echo 'Another local build is already active.' >&2
  exit 1
fi
if [[ -e "$repository/../runtime-build" ]]; then
  echo 'Runtime staging is occupied. Finish that work before packaging the current app.' >&2
  rmdir "$repository/../.current-build-lock"
  exit 1
fi
cleanup() {
  rm -rf "$CARGO_TARGET_DIR"
  rm -rf "$repository/../runtime-build"
  rmdir "$repository/../.current-build-lock"
}
trap cleanup EXIT
# The current app already owns the complete tested, standalone runtimes.
# Materialize their packaging inputs only for this build, then remove them.
resources="$app/Contents/Resources"
mkdir -p "$repository/../runtime-build"
for mapping in python-jax:runtime python-metaljax:runtime-metal python-boltz:runtime-boltz python-openmm:runtime-openmm; do
  staging="$repository/../runtime-build/${mapping%%:*}"
  if [[ ! -d "$staging" ]]; then
    cp -cR -P "$resources/${mapping#*:}" "$staging"
  fi
done
node node_modules/@tauri-apps/cli/tauri.js build --bundles app
built="$CARGO_TARGET_DIR/release/bundle/macos/FOLD STUDIO Metal Dev.app"
bash scripts/seal-app.sh "$built"
python3 scripts/install-current-app.py --source "$built" --destination "$app"
