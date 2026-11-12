#!/bin/sh
# Runs a command inside the pinned KiCad container with the repository mounted at the same path.
set -eu
repo_root=$(cd "$(dirname "$0")/.." && pwd)
exec docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
    -v "$repo_root:$repo_root" -w "$repo_root" kicad/kicad:9.0.9 "$@"
