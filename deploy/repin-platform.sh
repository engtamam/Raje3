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

CHANGED=0; MISSING=0; SAME=0; RESTAMPED=0; MANIFEST_LINES=""
for f in "$HERE"/services/*.values.yaml; do
  repo="$(sed -n 's/^  repository: *//p' "$f" | head -1)"
  case "$repo" in
    ghcr.io/"$OWNER"/*) ;;                 # the right registry and owner — still not proof
    *) continue;;
  esac
  # AND OURS LIVE UNDER A PRODUCT PATH: ghcr.io/OWNER/raje3/campaigns, against the platform's
  # ghcr.io/OWNER/identity-service. The owner glob above matched BOTH — a `*` spans slashes — so
  # every one of our own six services was looked up under the platform's release tag, found
  # missing, and counted. The script then refused the whole upgrade with "the release is
  # incomplete, do not deploy it": a correct release blocked by a check that was reading the
  # wrong images. One depth of path is the whole difference.
  case "${repo#ghcr.io/$OWNER/}" in
    */*) continue;;                        # ours — published by deploy/publish-images.sh
  esac
  img="${repo##*/}"
  cur="$(sed -n 's/^  digest: *"\([^"]*\)".*/\1/p' "$f" | head -1)"
  new="$(curl -sI -H "Authorization: Bearer $BEARER" -H "Accept: $ACCEPT" \
          "https://ghcr.io/v2/$OWNER/$img/manifests/$TAG" \
        | tr -d '\r' | sed -n 's/^[Dd]ocker-[Cc]ontent-[Dd]igest: *//p')"
  if [ -z "$new" ]; then
    echo -e "${C_R}  ✖ $img: no $TAG in the registry${C_N}"; MISSING=$((MISSING+1)); continue
  fi
  # THE IMAGE IS THE TRUTH, NOT THE TAG. A release rebuilds only what changed, so twelve of these
  # images are byte-identical across v0.16.4 and v0.16.16: same digest, same bytes, same running
  # code. Those pins were never wrong, and none of them is redeployed by anything below.
  #
  # BUT THE NOTE BESIDE THEM WAS TWO RELEASES STALE, because this loop used to skip a matching
  # digest entirely. So the file said `# v0.16.4` about an image v0.16.16 ships, and the offline
  # gate — which has no registry token and can only read that note — accused twelve correct pins of
  # drift, with the sentence «the cluster will run v0.16.4 and every route added since answers
  # 404». Twelve false alarms teach whoever runs the gate to scroll past it.
  #
  # TWO SEPARATE FIXES, AND THEY ARE NOT ALTERNATIVES:
  #   · the note is brought up to date — the digest is rewritten identical to itself, so the diff
  #     touches a comment and nothing else, and a human reading the file reads the truth;
  #   · the resolution is recorded in platform-release.json below, digest by digest, which is what
  #     a checker is allowed to read. Nothing may judge a deployment by a comment.
  MANIFEST_LINES="$MANIFEST_LINES$img $new"$'\n'
  if [ "$new" = "$cur" ]; then
    SAME=$((SAME+1))
    [ $CHECK -eq 1 ] && continue
    # THE IMAGE IS UNTOUCHED; ONLY THE NOTE BESIDE IT IS BROUGHT UP TO DATE. The digest is written
    # back identical to what is already there — nothing is redeployed, nothing is pulled, and the
    # pod goes on running the same bytes. What changes is the `# vX` a human reads, which had gone
    # two releases stale on every image the release did not rebuild.
    label="$(sed -n 's/^  digest: *"[^"]*" *# *//p' "$f" | head -1)"
    [ "$label" = "$TAG" ] && continue
    RESTAMPED=$((RESTAMPED+1))
    echo -e "${C_D}  · $img  ${label:-unlabelled} → $TAG   (same image, note only)${C_N}"
  else
    CHANGED=$((CHANGED+1))
    echo -e "${C_Y}  ▸ $img${C_N}  ${C_D}${cur:0:19}… → ${new:0:19}…${C_N}"
    [ $CHECK -eq 1 ] && continue
  fi
  # The comment after the digest is a version note somebody left; it would now be a lie, so the
  # line is replaced whole and re-stamped with the release actually pinned.
  python3 - "$f" "$new" "$TAG" <<'PY'
# BYTES, NOT TEXT — so the file's own line endings survive. Reading as text and writing back with
# newline='\n' rewrote every CRLF in the file to LF: api-gateway.values.yaml came back as a
# 418-line diff for a one-line change, and a review that has to scroll past 418 lines to find the
# pin is a review nobody does. One image, one line.
import re, sys
path, digest, tag = sys.argv[1:4]
with open(path, 'rb') as fh:
    src = fh.read()
line = f'  digest: "{digest}"   # {tag}'.encode()
src, n = re.subn(rb'^  digest: *"[^"]*"[^\r\n]*', line, src, count=1, flags=re.M)
if n != 1:
    sys.exit(f"{path}: no digest line to rewrite")   # silence is not agreement
with open(path, 'wb') as fh:
    fh.write(src)
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

# ── THE RELEASE MANIFEST, WHICH IS WHAT A CHECKER IS ALLOWED TO READ ──────────────────────────────
# The trailing `# vX` beside a digest is a note. It goes stale the moment a release rebuilds only
# some of its images — twelve of ours are byte-identical across v0.16.4 and v0.16.16, so their
# notes still said v0.16.4 while the pins were exactly right. An offline gate reading those notes
# accused twelve correct pins of drift and said the cluster would answer 404. Twelve false alarms
# teach whoever runs the gate to scroll past it, which costs more than the gate ever saved.
#
# THE RESOLUTION IS A FACT AND IS WRITTEN DOWN ONCE, HERE, where the registry was actually asked.
# A gate then compares digest to digest and never has to interpret a comment. And because this file
# is written only on a real repin, a submodule moved without repinning leaves release != submodule
# and is caught — which is the drift that matters.
printf '{\n  "release": "%s",\n  "images": {\n' "$TAG" > "$HERE/platform-release.json"
printf '%s' "$MANIFEST_LINES" | sort | awk 'NF' | awk '{
  printf "%s    \"%s\": \"%s\"", (NR>1 ? ",\n" : ""), $1, $2 }' >> "$HERE/platform-release.json"
printf '\n  }\n}\n' >> "$HERE/platform-release.json"

echo -e "${C_G}  ✔ $CHANGED repinned, $RESTAMPED renoted (same image), $((SAME - RESTAMPED)) untouched — manifest written for $TAG${C_N}"
