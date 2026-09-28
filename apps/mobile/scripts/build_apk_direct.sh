#!/usr/bin/env bash
# Builds a single signed release APK for DIRECT download from our own landing page — no Google
# Play, no Play Asset Delivery (a sideloaded APK has no Play Store underneath it to serve an
# install-time asset pack).
#
# DEFAULTS TO AI_MODEL_SOURCE=download — the model is fetched by the APP ITSELF, post-install,
# from the same public Hugging Face URL scripts/fetch_ai_model.sh already uses at build time (see
# GemmaAiModel's own doc comment). NOT the original design: this build first shipped with the
# model BUNDLED IN (mode 'asset', below), and mobile_release_publish (ops-mcp) refused the
# resulting 2.6GB APK outright — GitHub Releases caps a single release asset at 2GB. Switching to
# 'download' is a flag, not a rewrite, exactly so 'asset' stays one build-arg away if a future
# distribution channel has no such cap and bundling is worth it again: `MODE=asset
# scripts/build_apk_direct.sh`.
#
# --target-platform=android-arm64 only, deliberately — the overwhelming majority of real devices,
# and (in 'asset' mode) a single-ABI APK keeps the download at the model's own size instead of
# doubling it for arm32 as well.
#
# API_BASE_URL IS PASSED EXPLICITLY, NOT LEFT TO ApiConstants' OWN DEFAULT — found live
# (2026-09-28): every release build until now (this script AND the Play bundle) never set it, so
# ApiConstants.baseUrl fell back to its own emulator-only default (http://10.0.2.2:3000, "map to
# the host machine's localhost") — unreachable from any real phone. A real, signed, installable
# APK that could never reach the server shipped and was never caught because nobody had tested it
# against the actual production network until now.
set -euo pipefail

MODE="${MODE:-download}"
if [ "$MODE" != "download" ] && [ "$MODE" != "asset" ]; then
  echo "build_apk_direct: MODE must be 'download' (default) or 'asset', got $MODE" >&2
  exit 1
fi

API_BASE_URL="${API_BASE_URL:-https://kobo-cloud.com}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ASCII FILENAME, NOT "راجع.apk" — found live (2026-09-28): GitHub Releases' own asset-upload API
# silently refuses a non-ASCII asset name (both `gh release upload` and a direct multipart POST
# to uploads.github.com reproduced it — a real platform limitation, not our tooling), storing the
# file as a meaningless "default.apk" instead. The APK's own display name inside Android (the
# owner's actual ask) comes from AndroidManifest.xml's android:label ("راجع"), already set — a
# user only ever sees this on-disk filename transiently in their Downloads folder.
OUT_DIR="$ROOT/build/app/outputs/flutter-apk"
APK="$OUT_DIR/raje3.apk"

if [ "$MODE" = "download" ]; then
  echo "build_apk_direct: building the release APK (AI_MODEL_SOURCE=download — model fetched post-install, not bundled; API_BASE_URL=$API_BASE_URL)..."
  flutter build apk --release \
    --target-platform=android-arm64 \
    --dart-define=AI_MODEL_SOURCE=download \
    --dart-define=API_BASE_URL="$API_BASE_URL"

  mv -f "$OUT_DIR/app-release.apk" "$APK"
  echo "build_apk_direct: done — $APK ($(du -h "$APK" | cut -f1))"
  exit 0
fi

# ── MODE=asset — the model bundled INTO the APK, kept for a distribution channel with no 2GB cap ──
PACK_MODEL="$ROOT/android/ai_model_pack/src/main/assets/gemma-4-E4B-it-gpu.litertlm"
DIRECT_ASSET_DIR="$ROOT/assets/models"
DIRECT_MODEL="$DIRECT_ASSET_DIR/gemma-4-E4B-it-gpu.litertlm"
PUBSPEC="$ROOT/pubspec.yaml"

if [ ! -f "$PACK_MODEL" ]; then
  echo "build_apk_direct: model file missing at $PACK_MODEL — run scripts/fetch_ai_model.sh first." >&2
  exit 1
fi

cleanup() {
  # REMOVES ONLY THE ONE LINE THIS SCRIPT ADDED, NEVER `git checkout -- pubspec.yaml` — that blindly
  # discards ANY uncommitted edit to the file, not just this script's own staged line, and did
  # exactly that live once already (wiped out a whole session's worth of real dependency-version
  # fixes that had not been committed yet).
  echo "build_apk_direct: removing the staged asset line from pubspec.yaml and the asset copy..."
  sed -i '\|assets/models/gemma-4-E4B-it-gpu.litertlm|d' "$PUBSPEC"
  rm -f "$DIRECT_MODEL"
  rmdir "$DIRECT_ASSET_DIR" 2>/dev/null || true
}
trap cleanup EXIT

echo "build_apk_direct: staging the model as a plain asset for this build only..."
mkdir -p "$DIRECT_ASSET_DIR"
cp "$PACK_MODEL" "$DIRECT_MODEL"

python3 - "$PUBSPEC" <<'PY'
import sys
path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    lines = f.readlines()
marker = "    - assets/wakeword/raje_wakeword.tflite\n"
for i, line in enumerate(lines):
    if line == marker:
        lines.insert(i + 1, "    - assets/models/gemma-4-E4B-it-gpu.litertlm\n")
        break
else:
    raise SystemExit("build_apk_direct: could not find the assets: anchor line in pubspec.yaml")
with open(path, "w", encoding="utf-8") as f:
    f.writelines(lines)
PY

echo "build_apk_direct: building the release APK (this takes a while — a ~2.77GB asset to pack; API_BASE_URL=$API_BASE_URL)..."
flutter build apk --release \
  --target-platform=android-arm64 \
  --dart-define=AI_MODEL_SOURCE=asset \
  --dart-define=API_BASE_URL="$API_BASE_URL"

mv -f "$OUT_DIR/app-release.apk" "$APK"
echo "build_apk_direct: done — $APK ($(du -h "$APK" | cut -f1))"
