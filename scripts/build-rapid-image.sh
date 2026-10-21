#!/bin/sh
set -eu
# Explicit path arguments; no credentials, registry login or push.
repository=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
context=${1:?Supply a dedicated build output directory}
python3 "$repository/scripts/build-rapid-release.py" --output "$context"
cp "$repository/remote_worker/containers/startup.sh" "$context/startup.sh"
chmod 755 "$context/startup.sh"
if docker buildx version >/dev/null 2>&1; then
  docker buildx build --platform linux/amd64 --target core -f "$repository/remote_worker/containers/Dockerfile" --tag fold-rapid:0.2.0-core --load --metadata-file "$context/build-metadata.json" "$context"
elif [ -x /opt/homebrew/lib/docker/cli-plugins/docker-buildx ]; then
  /opt/homebrew/lib/docker/cli-plugins/docker-buildx build --platform linux/amd64 --target core -f "$repository/remote_worker/containers/Dockerfile" --tag fold-rapid:0.2.0-core --load --metadata-file "$context/build-metadata.json" "$context"
else
  echo 'Install the official Docker Buildx plugin before building AMD64 images.' >&2
  exit 1
fi
docker image inspect fold-rapid:0.2.0-core > "$context/image-inspect.json"
docker run --rm --platform linux/amd64 --entrypoint fold-rapid fold-rapid:0.2.0-core health > "$context/container-health.json"
# Multi-GB image archives are opt-in; the image is already in Docker's store.
if [ "${RAPID_EXPORT_IMAGE:-0}" = 1 ]; then
  docker save fold-rapid:0.2.0-core -o "$context/fold-rapid-amd64.tar"
fi
