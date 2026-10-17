#!/bin/bash
set -euo pipefail
app="${1:-${CARGO_TARGET_DIR:-src-tauri/target}/release/bundle/macos/FOLD STUDIO Metal Dev.app}"
if [[ -d "$app/Contents/Resources" ]]; then
  /usr/bin/find "$app/Contents/Resources" -type d -name __pycache__ -prune -exec /bin/rm -rf {} +
fi
/usr/bin/codesign --force --deep --sign - --identifier org.foldstudio.metalport "$app"
/usr/bin/codesign --verify --deep --strict --verbose=2 "$app"
