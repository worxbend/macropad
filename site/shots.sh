#!/usr/bin/env bash
# Screenshots of the built site with headless Firefox, one instance at a time, at low priority.
#
#   site/shots.sh OUT_DIR                 the standard set (see SHOTS below)
#   site/shots.sh OUT_DIR NAME:W:H:QUERY  only the shots given, e.g. sig-mid:1440:900:?only=signature&frame=signature:0.5
#
# QUERY is appended to index.html and may carry a #fragment. Run `make site` first.
# Firefox screenshots the viewport only, so scroll states are reached with the ?frame= debug hook
# (see site/README.md) and whole pages with ?motion=off, a few sections at a time.
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

# Whole pages are shot in chunks of a few sections each (?only=), so no window is taller than
# 10000 px: one very tall Firefox surface is hundreds of megabytes.
CHUNKS=(
  "a:hero,words,design,light"
  "b:colourways,details,exploded,inside"
  "c:board,firmware,keymap"
  "d:uses,signature,specs"
  "e:status,build,footer"
)
SHOTS=()
for size in 320:10000 768:8000 1024:7000 1440:6000; do
  for chunk in "${CHUNKS[@]}"; do
    SHOTS+=("page-${size%%:*}-${chunk%%:*}:$size:?motion=off&only=${chunk#*:}")
  done
done
SHOTS+=(
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
for p in 0.05 0.3 0.55 0.64 0.75 0.88 1; do
  SHOTS+=("signature-$p:1440:900:?only=signature&frame=signature:$p")
  SHOTS+=("signature-$p-phone:390:844:?only=signature&frame=signature:$p")
done
# The signature's end state on short and narrow screens: a small phone, a phone held sideways
# (the static layout), and a tablet.
for size in 320:568 844:390 768:1024; do
  SHOTS+=("signature-1-${size/:/x}:$size:?only=signature&frame=signature:1")
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

# The page with JavaScript off, from a profile whose user.js turns scripts off. ?only= needs
# JavaScript, so these show the first 12000 px of the page, the most one window should hold.
if [[ $# -eq 0 ]]; then
  for size in 1440:12000 390:12000; do
    profile=$(mktemp -d -p "$work")
    echo 'user_pref("javascript.enabled", false);' >"$profile/user.js"
    timeout 60 nice -n 10 firefox --headless --no-remote --profile "$profile" \
      --window-size="${size/:/,}" --screenshot "$out/nojs-${size%%:*}.png" \
      "file://$work/site/index.html" >/dev/null 2>&1 || echo "shots: nojs-${size%%:*} failed" >&2
    rm -rf "$profile"
    echo "shots: $out/nojs-${size%%:*}.png"
  done
fi
