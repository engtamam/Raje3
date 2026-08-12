#!/usr/bin/env bash
# ==================================================================================================
#  repin-platform.sh — put every base-services image on ONE release, resolved to a digest.
# --------------------------------------------------------------------------------------------------
#  WHY THIS EXISTS. Our values pinned eighteen platform images to eighteen digests collected at
#  eighteen different moments — some as far back as v0.12.5, while the chart we render against them
#  is v0.16.4. That drift was invisible for months for the worst possible reason: every one of those
#  images was already in the node's content store, so nothing ever pulled and nothing ever failed.
#  A fresh machine has no cache, and three of the pins — backup, onboarding, ticket — came back
#  `not found`: upstream had pruned the old tags out of the registry. The images did not break, they
#  ceased to exist, and only a from-nothing install could tell us.
#
#  THE PIN STAYS A DIGEST. A tag is a name and a name can be moved — a pod can run code you never
#  approved under a tag that looks right. So this resolves the tag ONCE, here, where a human is
#  choosing a release, and writes the immutable digest into the values file. What ships is a digest;
#  what a person types is a version.
#
#  Usage:
#    GHCR_TOKEN=… bash deploy/repin-platform.sh v0.16.4          # rewrite the files
#    GHCR_TOKEN=… bash deploy/repin-platform.sh v0.16.4 --check  # report drift, change nothing (CI)
# ==================================================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OWNER="${GHCR_OWNER:-engtamam}"
TAG="${1:-}"
CHECK=0; [ "${2:-}" = "--check" ] && CHECK=1

C_G=$'\e[32m'; C_Y=$'\e[33m'; C_R=$'\e[31m'; C_D=$'\e[2m'; C_N=$'\e[0m'
[ -n "$TAG" ] || { echo "usage: GHCR_TOKEN=… bash $0 <tag> [--check]" >&2; exit 2; }
: "${GHCR_TOKEN:?GHCR_TOKEN is required — the packages are private and a digest lookup is a pull}"

# ghcr wants a bearer token; for a PAT that bearer is the PAT itself, base64'd. Reading a manifest
# by tag returns the digest in a header, so no image is transferred to learn its identity.
BEARER="$(printf '%s' "$GHCR_TOKEN" | base64 -w0)"
ACCEPT='application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json'

CHANGED=0; MISSING=0; SAME=0
for f in "$HERE"/services/*.values.yaml; do
  repo="$(sed -n 's/^  repository: *//p' "$f" | head -1)"
  case "$repo" in
    ghcr.io/"$OWNER"/*) ;;                 # a platform image, ours to repin
    *) continue;;                          # our own services live elsewhere — a different pipeline
  esac
  img="${repo##*/}"
  cur="$(sed -n 's/^  digest: *"\([^"]*\)".*/\1/p' "$f" | head -1)"
  new="$(curl -sI -H "Authorization: Bearer $BEARER" -H "Accept: $ACCEPT" \
          "https://ghcr.io/v2/$OWNER/$img/manifests/$TAG" \
        | tr -d '\r' | sed -n 's/^[Dd]ocker-[Cc]ontent-[Dd]igest: *//p')"
  if [ -z "$new" ]; then
    echo -e "${C_R}  ✖ $img: no $TAG in the registry${C_N}"; MISSING=$((MISSING+1)); continue
  fi
  if [ "$new" = "$cur" ]; then SAME=$((SAME+1)); continue; fi
  CHANGED=$((CHANGED+1))
  echo -e "${C_Y}  ▸ $img${C_N}  ${C_D}${cur:0:19}… → ${new:0:19}…${C_N}"
  [ $CHECK -eq 1 ] && continue
  # The comment after the digest is a version note somebody left; it would now be a lie, so the
  # line is replaced whole and re-stamped with the release actually pinned.
  python3 - "$f" "$new" "$TAG" <<'PY'
import re, sys
path, digest, tag = sys.argv[1:4]
src = open(path, encoding='utf-8').read()
src = re.sub(r'^  digest: *"[^"]*".*$', f'  digest: "{digest}"   # {tag}', src, count=1, flags=re.M)
open(path, 'w', encoding='utf-8', newline='\n').write(src)
PY
done

echo
if [ $MISSING -gt 0 ]; then
  echo -e "${C_R}  $MISSING image(s) have no $TAG — the release is incomplete, do not deploy it${C_N}"; exit 1
fi
if [ $CHECK -eq 1 ]; then
  [ $CHANGED -eq 0 ] && { echo -e "${C_G}  ✔ every platform image is on $TAG${C_N}"; exit 0; }
  echo -e "${C_Y}  $CHANGED image(s) drift from $TAG — run without --check to repin${C_N}"; exit 1
fi
echo -e "${C_G}  ✔ $CHANGED repinned to $TAG, $SAME already there${C_N}"
