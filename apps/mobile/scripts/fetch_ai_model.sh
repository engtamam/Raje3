#!/usr/bin/env bash
# Fetches the Gemma 4 E4B model file to the exact path AiConfig.gemmaModelAssetPath / pubspec.yaml
# declare as a bundled asset — run this BEFORE `flutter build`/`flutter run`, on every machine
# that builds this app (a dev's own laptop, CI). The file itself is gitignored (assets/models/,
# ~2.77GB) — see AiConfig.gemmaModelAssetPath's own doc comment for why it ships bundled at all
# rather than downloaded per-install, and why the file is never committed regardless.
#
# Idempotent: skips the download if the file already exists at the right size, so re-running this
# on an already-fetched machine (a second `flutter run`) costs nothing.
set -euo pipefail

SOURCE_URL="https://huggingface.co/litert-community/gemma-4-E4B-it-litert-lm/resolve/main/gemma-4-E4B-it-gpu.litertlm"
DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/assets/models/gemma-4-E4B-it-gpu.litertlm"
# ~2.77GiB, confirmed via a real HEAD request when this URL was first chosen (ai_config.dart's own
# note) — used only as a SANITY FLOOR to catch a truncated/failed download, not an exact match (a
# future model revision on the same URL may differ by a few bytes).
MIN_BYTES=2900000000

mkdir -p "$(dirname "$DEST")"

if [ -f "$DEST" ]; then
  SIZE=$(wc -c < "$DEST" | tr -d ' ')
  if [ "$SIZE" -ge "$MIN_BYTES" ]; then
    echo "fetch_ai_model: already present ($((SIZE / 1000000))MB) at $DEST — skipping."
    exit 0
  fi
  echo "fetch_ai_model: existing file is too small ($((SIZE / 1000000))MB) — re-fetching."
  rm -f "$DEST"
fi

echo "fetch_ai_model: downloading ~2.77GB, this takes a while the first time..."
curl -L --fail --retry 3 --retry-delay 5 -o "$DEST.partial" "$SOURCE_URL"
mv "$DEST.partial" "$DEST"

SIZE=$(wc -c < "$DEST" | tr -d ' ')
if [ "$SIZE" -lt "$MIN_BYTES" ]; then
  echo "fetch_ai_model: downloaded file is only $((SIZE / 1000000))MB — refusing to leave a" \
       "truncated model in place." >&2
  rm -f "$DEST"
  exit 1
fi

echo "fetch_ai_model: done — $((SIZE / 1000000))MB at $DEST"
