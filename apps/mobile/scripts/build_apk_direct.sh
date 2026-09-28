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
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
cd "$ROOT"

# AUTO-BUMP pubspec.yaml's patch version — found live (2026-09-28): a hand-edited version that
# nobody remembered to bump before v0.1.7 shipped left the account screen's own version footer
# (account_screen.dart) reading v0.1.6 a full release behind reality. This is the ONE place a
# version is decided for a direct-download build, so every other consumer (the version footer,
# mobile_release_publish's own tag) can just read what this script already wrote instead of a
# human keeping two files in sync by hand. Skipped entirely when SKIP_VERSION_BUMP=1 (kept for a
# rebuild of the SAME version — a hotfix retry, a local test build nobody is about to publish).
if [ "${SKIP_VERSION_BUMP:-0}" != "1" ]; then
  CURRENT_VERSION="$(grep -m1 '^version:' pubspec.yaml | sed 's/^version:[[:space:]]*//')"
  # X.Y.Z only, no +build — Android's versionCode is fixed at 1 for this build (owner's own
  # 2026-09-28 call: this channel is direct-download only, never Google Play, so versionCode
  # never needs to increase; see pubspec.yaml's own version line if that ever changes).
  IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"
  NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
  sed -i "s/^version:.*/version: $NEW_VERSION/" pubspec.yaml
  echo "build_apk_direct: version bumped $CURRENT_VERSION -> $NEW_VERSION (pubspec.yaml)"
else
  NEW_VERSION="$(grep -m1 '^version:' pubspec.yaml | sed 's/^version:[[:space:]]*//')"
  echo "build_apk_direct: SKIP_VERSION_BUMP=1 — building $NEW_VERSION as-is"
fi
echo "build_apk_direct: RELEASE_VERSION=v$NEW_VERSION"

# GATED ON THE MOBILE-KB CHECKS — the owner's own explicit call (2026-09-28), after finding these
# gates existed (wired into .github/workflows/guards.yml) but never actually blocked a real build:
# ship.sh has its own pre-flight gate list for base-services, but nothing analogous ever ran before
# a mobile build, so real KB coverage gaps (an anchor used in a screen with no matching
# mobile_kb.json entry, or an interactive widget with no anchor at all — the assistant cannot
# explain either) shipped silently, release after release. Same "nothing built, nothing shipped"
# posture ship.sh's own gates use.
echo "build_apk_direct: mobile KB anchors are covered..."
python3 "$REPO_ROOT/ci/check_mobile_kb_anchors_are_covered.py" || {
  echo "build_apk_direct: KB anchor gaps found above — nothing built." >&2; exit 1; }
echo "build_apk_direct: every mobile screen action is anchored..."
python3 "$REPO_ROOT/ci/check_mobile_screen_actions_are_anchored.py" || {
  echo "build_apk_direct: unanchored interactive widget(s) found above — nothing built." >&2; exit 1; }
echo "build_apk_direct: mobile screen KB granularity..."
python3 "$REPO_ROOT/ci/check_mobile_screen_kb_granularity.py" || {
  echo "build_apk_direct: KB granularity gap(s) found above — nothing built." >&2; exit 1; }

# GATED ON THE SIX-LOCALE i18n CHECKS TOO — same owner call, same day (2026-09-28): these three
# also existed CI-only before now. check_mobile_screen_localized.py's SCREENS list was expanded
# from 28 files to every currently-clean file in lib/ (129), so a new raw-Arabic string in ANY
# already-migrated file is caught immediately, not just in the original hand-picked set.
echo "build_apk_direct: mobile l10n is wired into MaterialApp..."
python3 "$REPO_ROOT/ci/check_mobile_localization_is_wired.py" || {
  echo "build_apk_direct: l10n not wired — nothing built." >&2; exit 1; }
echo "build_apk_direct: no raw Arabic outside S.of(context)..."
python3 "$REPO_ROOT/ci/check_mobile_screen_localized.py" --all || {
  echo "build_apk_direct: raw Arabic string(s) found above — nothing built." >&2; exit 1; }
echo "build_apk_direct: all six locales carry the same keys..."
python3 "$REPO_ROOT/ci/check_mobile_arb_locales_match.py" || {
  echo "build_apk_direct: locale key drift found above — nothing built." >&2; exit 1; }

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
