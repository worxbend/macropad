#!/usr/bin/env bash
# Screenshots of the built site with headless Firefox, one instance at a time, at low priority.
#
#   site/shots.sh OUT_DIR                 the standard set (see SHOTS below)
#   site/shots.sh OUT_DIR NAME:W:H:QUERY  only the shots given, e.g. sig-mid:1440:900:?only=signature&frame=signature:0.5
#
# QUERY is appended to index.html and may carry a #fragment. Run `make site` first.
# Firefox screenshots the viewport only, so scroll states are reached with the ?frame= debug hook
# (see site/README.md) and whole pages with a tall window and ?motion=off.
# The shots use a copy of _site with font-display set to block, so they show Archivo rather than
# the fallback that display=optional picks on a cold first visit.
set -euo pipefail

out=${1:?usage: site/shots.sh OUT_DIR [NAME:W:H:QUERY ...]}
shift
repo=$(cd "$(dirname "$0")/.." && pwd)
[[ -f "$repo/_site/index.html" ]] || { echo "shots: run make site first" >&2; exit 1; }

mkdir -p "$out"
out=$(cd "$out" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp -r "$repo/_site" "$work/site"
sed -i 's/display=optional/display=block/' "$work/site/index.html"

SHOTS=(
  "page-320:320:9000:?motion=off"
  "page-768:768:9000:?motion=off"
  "page-1024:1024:9000:?motion=off"
  "page-1440:1440:9000:?motion=off"
  "hero-0:1440:900:?only=hero&frame=hero:0"
  "hero-1:1440:900:?only=hero&frame=hero:1"
  "light-0:1440:900:?only=light&frame=light:0"
  "light-0.3:1440:900:?only=light&frame=light:0.3"
  "light-0.5:1440:900:?only=light&frame=light:0.5"
  "light-1:1440:900:?only=light&frame=light:1"
  "exploded-0:1440:900:?only=exploded&frame=exploded:0"
  "exploded-0.5:1440:900:?only=exploded&frame=exploded:0.5"
  "exploded-1:1440:900:?only=exploded&frame=exploded:1"
  "firmware-0:1440:900:?only=firmware&frame=firmware:0"
  "firmware-0.5:1440:900:?only=firmware&frame=firmware:0.5"
  "firmware-1:1440:900:?only=firmware&frame=firmware:1"
)
for p in 0.05 0.3 0.55 0.75 0.88 1; do
  SHOTS+=("signature-$p:1440:900:?only=signature&frame=signature:$p")
  SHOTS+=("signature-$p-phone:390:844:?only=signature&frame=signature:$p")
done
[[ $# -gt 0 ]] && SHOTS=("$@")

for shot in "${SHOTS[@]}"; do
  IFS=: read -r name width height query <<<"$shot"
  profile=$(mktemp -d -p "$work")
  timeout 60 nice -n 10 firefox --headless --no-remote --profile "$profile" \
    --window-size="$width,$height" --screenshot "$out/$name.png" \
    "file://$work/site/index.html$query" >/dev/null 2>&1 || echo "shots: $name failed" >&2
  rm -rf "$profile"
  echo "shots: $out/$name.png"
done

# A page with JavaScript off: a profile whose user.js turns it off.
if [[ $# -eq 0 ]]; then
  profile=$(mktemp -d -p "$work")
  echo 'user_pref("javascript.enabled", false);' >"$profile/user.js"
  timeout 60 nice -n 10 firefox --headless --no-remote --profile "$profile" \
    --window-size=1440,9000 --screenshot "$out/page-nojs-1440.png" \
    "file://$work/site/index.html" >/dev/null 2>&1 || echo "shots: page-nojs-1440 failed" >&2
  echo "shots: $out/page-nojs-1440.png"
fi
