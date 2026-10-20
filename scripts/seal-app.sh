#!/bin/bash
set -euo pipefail
app="${1:-${CARGO_TARGET_DIR:-src-tauri/target}/release/bundle/macos/FOLD STUDIO Metal Dev.app}"
app="$(cd "$app" && pwd -P)"
# Re-sealing changes the ad-hoc identity used by macOS privacy grants. A model
# worker can outlive its window, so check executable paths before any mutation.
while IFS= read -r executable; do
  case "$executable" in
    *.app/Contents/*)
      process_app="${executable%%.app/Contents/*}.app"
      if [[ -d "$process_app" ]] && [[ "$(cd "$process_app" && pwd -P)" == "$app" ]]; then
        printf '%s\n' 'Cannot re-sign a running Fold Studio build. Close its window and finish its scientific jobs first.' >&2
        exit 1
      fi
      ;;
  esac
done < <(/bin/ps -axo comm=)
if [[ -d "$app/Contents/Resources" ]]; then
  /usr/bin/find "$app/Contents/Resources" -type d -name __pycache__ -prune -exec /bin/rm -rf {} +
fi
/usr/bin/codesign --force --deep --sign - --identifier org.foldstudio.metalport "$app"
/usr/bin/codesign --verify --deep --strict --verbose=2 "$app"
