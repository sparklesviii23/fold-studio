#!/bin/bash
set -euo pipefail
app="${1:-src-tauri/target/release/bundle/macos/FOLD STUDIO.app}"
if [[ -d "$app/Contents/Resources/scientific" ]]; then
  /usr/bin/find "$app/Contents/Resources/scientific" -type d -name __pycache__ -prune -exec /bin/rm -rf {} +
fi
/usr/bin/codesign --force --deep --sign - --identifier org.foldstudio.observatory "$app"
/usr/bin/codesign --verify --deep --strict --verbose=2 "$app"
