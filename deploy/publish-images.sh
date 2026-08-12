#!/usr/bin/env bash
# ==================================================================================================
#  publish-images.sh — build our images HERE, push them to ghcr, and pin the values to what shipped.
# --------------------------------------------------------------------------------------------------
#  THE BUILD IS LOCAL BY DECISION, NOT BY DEFAULT. GitHub charges for Actions minutes on a private
#  repository, and this build is seven images with a compile step in each — a bill for work a laptop
#  already does. So the laptop builds and pushes, and the registry stays the single place every
#  server pulls from. What we are NOT going back to is the old arrangement, where the images existed
#  only in a registry inside one cluster: a product installable on exactly one machine on earth.
#
#  THE PIN IS WRITTEN FROM WHAT THE REGISTRY ANSWERED, NEVER FROM WHAT WE INTENDED. `docker push`
#  reports the manifest digest it stored; that string, and no other, goes into the values file. A
#  digest typed by a person is a digest that can be one character wrong and still look right — and
#  a tag we could have used instead is a name, which can be moved after review so a pod runs code
#  nobody approved.
#
#  Usage:
#    GHCR_TOKEN=… bash deploy/publish-images.sh              # all seven
#    GHCR_TOKEN=… bash deploy/publish-images.sh operations   # one, after a fix
#
#  The token needs write:packages — a read:packages token pulls fine and fails at the push, which is
#  a twenty-minute build discovering its problem at the last second.
# ==================================================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OWNER="${GHCR_OWNER:-engtamam}"
REG="ghcr.io/$OWNER/raje3"

C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_R=$'\e[31m'; C_D=$'\e[2m'; C_N=$'\e[0m'
ok(){ echo -e "${C_G}  ✔ $*${C_N}"; }
die(){ echo -e "${C_R}  ✖ $*${C_N}" >&2; exit 1; }

# name → build context and dockerfile. The console builds from the repository root because its image
# also carries the landing page, which lives outside apps/console.
ctx(){ case "$1" in console) echo "$ROOT";; *) echo "$ROOT/services/$1";; esac; }
dfl(){ case "$1" in console) echo "$ROOT/apps/console/Dockerfile";; *) echo "$ROOT/services/$1/Dockerfile";; esac; }

ALL=(campaigns insights loyalty operations portal reminders console)
TARGETS=("$@"); [ ${#TARGETS[@]} -eq 0 ] && TARGETS=("${ALL[@]}")

docker version >/dev/null 2>&1 || die "docker is not running — start Docker Desktop and try again"
: "${GHCR_TOKEN:?GHCR_TOKEN is required (write:packages)}"
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:-$OWNER}" --password-stdin >/dev/null 2>&1 \
  || die "ghcr login refused — the token needs write:packages, not only read"

# THE TAG IS THE COMMIT, and a dirty tree says so out loud. «Which build is that pod running» must
# have an answer that survives the week; `latest` never did.
COMMIT="$(git -C "$ROOT" rev-parse --short HEAD)"
git -C "$ROOT" diff --quiet || echo -e "${C_Y}  note: building from a tree with uncommitted changes${C_N}"

for name in "${TARGETS[@]}"; do
  values="$HERE/services/$name.values.yaml"
  echo -e "\n${C_C}━━━ $name ━━━${C_N}"
  docker build -q -t "$REG/$name:$COMMIT" -t "$REG/$name:latest" -f "$(dfl "$name")" "$(ctx "$name")" >/dev/null \
    || die "$name failed to build"
  ok "built"
  docker push -q "$REG/$name:$COMMIT" >/dev/null || die "$name failed to push"
  docker push -q "$REG/$name:latest"  >/dev/null || true
  # ASK THE REGISTRY, DO NOT PARSE THE PUSH. The local `RepoDigests` is populated only after a push
  # and is empty for an image built from cache — reading it there is how a pin silently keeps its
  # previous value while everything prints success.
  digest="$(docker buildx imagetools inspect "$REG/$name:$COMMIT" --format '{{.Manifest.Digest}}' 2>/dev/null || true)"
  [ -n "$digest" ] || digest="$(docker inspect --format '{{index .RepoDigests 0}}' "$REG/$name:$COMMIT" 2>/dev/null | sed 's/.*@//')"
  [ -n "$digest" ] || die "$name pushed but the registry did not report a digest — refusing to pin a guess"
  ok "pushed ${digest:0:19}…"

  [ -f "$values" ] || { echo -e "${C_Y}  ! no values file — the image is published and nothing deploys it${C_N}"; continue; }
  python3 - "$values" "$digest" "$REG/$name" "$COMMIT" <<'PY'
import re, sys
path, digest, repo, commit = sys.argv[1:5]
src = open(path, encoding='utf-8').read()
src = re.sub(r'^  repository: .*$', f'  repository: {repo}', src, count=1, flags=re.M)
src = re.sub(r'^  digest: *"[^"]*".*$', f'  digest: "{digest}"   # {commit}, published by publish-images.sh',
             src, count=1, flags=re.M)
open(path, 'w', encoding='utf-8', newline='\n').write(src)
PY
  ok "pinned in $(basename "$values")"
done

echo
echo -e "${C_D}  next: commit the pins, then  bash deploy/pack.sh --to root@HOST  and re-run the installer${C_N}"
