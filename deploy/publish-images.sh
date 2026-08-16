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
#  ALL SEVEN AT ONCE, EACH WITH ITS OWN LOG. Building one at a time left the machine half idle: a
#  push is network and a build is CPU, so while campaigns sent ninety megabytes nothing compiled.
#  The reason it was serial first is exactly the reason the logs are now separated — seven builds
#  writing into one terminal interleave, and the failure you most need to read is the one you cannot
#  find. So each image writes to its own file, and a failure prints ITS log and nothing else. The
#  gain is smaller than sevenfold and always will be: six of these share python:3.12-slim, and
#  seven builds on one daemon share the same cores.
#
#  Usage:
#    GHCR_TOKEN=… bash deploy/publish-images.sh              # all seven, in parallel
#    GHCR_TOKEN=… bash deploy/publish-images.sh operations   # one, after a fix
#    JOBS=2 GHCR_TOKEN=… bash deploy/publish-images.sh       # fewer at a time, on a small machine
#
#  The token needs write:packages — a read:packages token pulls fine and fails at the push, which is
#  a twenty-minute build discovering its problem at the last second.
# ==================================================================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

# META'S THREE VALUES REACH THE CONSOLE AT BUILD TIME OR NOT AT ALL.
#
# Vite inlines `import.meta.env.*` into the bundle, so these cannot be set on the pod the way every
# service setting is: an image built without them cannot be configured later, and the screen
# correctly says «الربط غير مُفعَّل بعد» for ever. They were declared in the Dockerfile and passed
# by nothing — a setting nobody could supply, which is the shape this repo keeps finding.
#
# NOT IN GIT, and read from the same file the ship already reads: they are an operator's own
# application credentials. Absent is a valid state — the button then says so honestly.
[ -f "$ROOT/deploy/target.env" ] && . "$ROOT/deploy/target.env"
META_ARGS=()
for v in VITE_META_APP_ID VITE_META_CONFIG_ID VITE_META_GRAPH_VERSION; do
  [ -n "${!v:-}" ] && META_ARGS+=(--build-arg "$v=${!v}")
done
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
JOBS="${JOBS:-${#TARGETS[@]}}"

docker version >/dev/null 2>&1 || die "docker is not running — start Docker Desktop and try again"
: "${GHCR_TOKEN:?GHCR_TOKEN is required (write:packages)}"
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:-$OWNER}" --password-stdin >/dev/null 2>&1 \
  || die "ghcr login refused — the token needs write:packages, not only read"

# THE TAG IS THE COMMIT, and a dirty tree says so out loud. «Which build is that pod running» must
# have an answer that survives the week; `latest` never did.
COMMIT="$(git -C "$ROOT" rev-parse --short HEAD)"
git -C "$ROOT" diff --quiet || echo -e "${C_Y}  note: building from a tree with uncommitted changes${C_N}"

LOGS="$(mktemp -d)"; trap 'rm -rf "$LOGS"' EXIT

# ONE IMAGE, BUILD TO DIGEST, IN ITS OWN PROCESS. It writes the digest to a file rather than printing
# it: seven of these run at once, and stdout is not a place two processes can share a sentence.
one(){
  local name="$1" d=""
  {
    # `${META_ARGS[@]+"${META_ARGS[@]}"}` — empty-array expansion that survives `set -u`, which is
    # on. Every other image ignores the args it was not asked about.
    docker build ${META_ARGS[@]+"${META_ARGS[@]}"}       -t "$REG/$name:$COMMIT" -t "$REG/$name:latest" -f "$(dfl "$name")" "$(ctx "$name")" || exit 1
    docker push "$REG/$name:$COMMIT" || exit 1
    docker push "$REG/$name:latest"  || true
    # ASK THE REGISTRY, DO NOT READ THE LOCAL IMAGE. RepoDigests is empty for an image built from
    # cache, and reading it there is how a pin silently keeps its previous value while every line
    # printed success.
    d="$(docker buildx imagetools inspect "$REG/$name:$COMMIT" --format '{{.Manifest.Digest}}' 2>/dev/null || true)"
    [ -n "$d" ] || d="$(docker inspect --format '{{index .RepoDigests 0}}' "$REG/$name:$COMMIT" 2>/dev/null | sed 's/.*@//')"
    [ -n "$d" ] || { echo "pushed, but the registry reported no digest — refusing to pin a guess"; exit 1; }
    printf '%s' "$d" > "$LOGS/$name.digest"
  } > "$LOGS/$name.log" 2>&1
}

echo -e "${C_C}  ${#TARGETS[@]} image(s), $JOBS at a time — commit $COMMIT${C_N}"
declare -A PID
RUNNING=0
for name in "${TARGETS[@]}"; do
  # A CAP, because a laptop running seven docker builds with a browser open is a laptop that stops
  # answering its owner. The default is all of them; JOBS=2 exists for the machine that cannot.
  while [ "$RUNNING" -ge "$JOBS" ]; do wait -n 2>/dev/null || true; RUNNING=$((RUNNING-1)); done
  one "$name" & PID[$name]=$!
  RUNNING=$((RUNNING+1))
  echo -e "${C_D}  ▸ $name${C_N}"
done

FAILED=()
for name in "${TARGETS[@]}"; do
  if wait "${PID[$name]}"; then
    d="$(cat "$LOGS/$name.digest")"
    ok "$name  ${d:0:19}…"
    # THE CONSOLE IS PINNED SOMEWHERE ELSE, because it is deployed by a plain manifest rather than
    # by the service chart — it is a Caddy holding files, with no secret, no driver and no database
    # for a values file to describe.
    if [ "$name" = "console" ]; then
      python3 - "$HERE/edge/console.yaml" "$d" "$REG" <<'PYCON'
import re, sys
# THE REPOSITORY MOVES WITH THE DIGEST. Keeping whatever repository the line already carried and
# swapping only the digest is how ghcr content came to be addressed under `127.0.0.1:5055` — a
# name a fresh host resolves to nothing, after every step in the run reported success (ل-3).
path, digest, repo = sys.argv[1:4]
src = open(path, encoding="utf-8").read()
old = re.search(r"image: \S+/console@sha256:[0-9a-f]+", src)
if not old:
    sys.exit("no console image line to pin — the manifest changed shape")
open(path, "w", encoding="utf-8", newline="\n").write(
    src[:old.start()] + "image: " + repo + "/console@" + digest + src[old.end():])
PYCON
      ok "pinned in edge/console.yaml"
      continue
    fi
    values="$HERE/services/$name.values.yaml"
    if [ ! -f "$values" ]; then
      echo -e "${C_Y}  ! $name: no values file — the image is published and nothing deploys it${C_N}"
      continue
    fi
    # PINNED HERE IN THE PARENT, ONE AT A TIME. Seven children rewriting seven files is safe right
    # up until two of them share one, and the day that happens the loss is silent.
    python3 - "$values" "$d" "$REG/$name" "$COMMIT" <<'PYEOF'
import re, sys
path, digest, repo, commit = sys.argv[1:5]
src = open(path, encoding='utf-8').read()
src = re.sub(r'^  repository: .*$', f'  repository: {repo}', src, count=1, flags=re.M)
src = re.sub(r'^  digest: *"[^"]*".*$',
             f'  digest: "{digest}"   # {commit}, published by publish-images.sh',
             src, count=1, flags=re.M)
open(path, 'w', encoding='utf-8', newline='\n').write(src)
PYEOF
  else
    FAILED+=("$name")
    echo -e "${C_R}  ✖ $name${C_N}"
    # ONLY THE FAILURE'S OWN LOG. That is the whole point of separating them: this paragraph is
    # about one image and contains not a line from the six that worked.
    tail -25 "$LOGS/$name.log" | sed 's/^/      /'
  fi
done

echo
[ ${#FAILED[@]} -gt 0 ] && die "${#FAILED[@]} did not publish: ${FAILED[*]} — the pins for the rest are written"
echo -e "${C_D}  next: commit the pins, then  bash deploy/pack.sh --to root@HOST  and re-run the installer${C_N}"
