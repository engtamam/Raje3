#!/usr/bin/env bash
# What actually happened — run automatically after every update.sh.
#
# WHY THIS EXISTS. In one afternoon a deploy reported success four times and shipped nothing, four
# different ways. Every individual report was truthful; none of them was about the thing we cared
# about. This hook checks the ARTIFACT rather than the report, and each section below is one of
# those four failures turned into a check.
#
#   1. The values file on this machine is not the one in git.  A sync timed out mid-extract and
#      helm rendered a two-version-old digest. verify-pinned.sh compared the running pod to that
#      same stale file and correctly reported agreement.
#
#   2. The image is not in containerd under its pinned digest.  An import was piped to /dev/null
#      and a success line printed regardless, so the pull failed after a green deploy.
#
#   3. The running pod is not on the pinned digest.  `rollout restart` re-creates pods from the
#      SAME spec, so it restarted the old image cleanly and reported success.
#
#   4. A peer path names a route the peer does not serve.  reminders read zero visits forever
#      because operations had not been deployed with the route yet — both services healthy, both
#      correct, and the product silently doing nothing.
#
# NO `set -e`. A failing check must report and continue: one unreachable service must not hide the
# state of the other twenty. The exit code carries the verdict.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

NS="${NS:-base-services}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${ROOT:-$(cd "$HERE/../.." && pwd)}"
VALUES_DIR="${VALUES_DIR:-$ROOT/deploy/services}"

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*"; }
yel(){ printf '  \e[33m⚠ %s\e[0m\n' "$*"; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }
hdr(){ printf '\n\e[1m%s\e[0m\n' "$*"; }

fail=0

# ── 1. is the declaration we deployed the one we wrote? ────────────────────────────────────────
hdr "1 · the values files match git"
if git -C "$ROOT" rev-parse >/dev/null 2>&1; then
  dirty=$(git -C "$ROOT" status --porcelain -- deploy/services 2>/dev/null)
  if [ -n "$dirty" ]; then
    # UNCOMMITTED IS NOT AUTOMATICALLY WRONG — it is how a digest gets pinned before a commit. But
    # it is exactly the state in which a half-finished sync hides, so it is surfaced rather than
    # judged.
    yel "values differ from git HEAD (fine if you just re-pinned; suspicious otherwise):"
    echo "$dirty" | sed 's/^/      /'
  else
    grn "values match git HEAD"
  fi
else
  yel "not a git checkout here — cannot compare the deployed declaration to the written one"
fi

# ── 2. is the image on this node, under the digest we pinned? ──────────────────────────────────
hdr "2 · every pinned digest exists in containerd"
present=$(k3s ctr images ls -q 2>/dev/null || sudo -n k3s ctr images ls -q 2>/dev/null)
for f in "$VALUES_DIR"/*.values.yaml; do
  svc=$(basename "$f" .values.yaml)
  repo=$(grep -m1 'repository:' "$f" | awk '{print $2}')
  want=$(grep -m1 'digest:' "$f" | sed -E 's/.*"([^"]*)".*/\1/')
  [ -n "$want" ] || { red "$svc: no digest pinned"; fail=1; continue; }
  # Only locally-built images can be checked this way; a registry-hosted one is pulled on demand
  # and its absence here is normal.
  case "$repo" in
    docker.io/raje3/*)
      if printf '%s\n' "$present" | grep -qx "${repo}@${want}"; then
        grn "$svc"
      else
        red "$svc: ${want:0:19}… is NOT in containerd — the pod will ImagePullBackOff"
        fail=1
      fi ;;
    *) : ;;
  esac
done

# ── 3. is the pod running that digest, and ready? ──────────────────────────────────────────────
hdr "3 · every pod runs its pinned digest"
for f in "$VALUES_DIR"/*.values.yaml; do
  svc=$(basename "$f" .values.yaml)
  want=$(grep -m1 'digest:' "$f" | sed -E 's/.*"([^"]*)".*/\1/')
  # imageID off the POD, not `image` off the deployment. The deployment says what was asked for;
  # imageID says what is running, and after a failed pull those differ.
  got=$(kubectl -n "$NS" get pods -l "app.kubernetes.io/name=$svc" \
        -o jsonpath='{.items[0].status.containerStatuses[0].imageID}' 2>/dev/null | sed 's/.*@//')
  [ -n "$got" ] || got=$(kubectl -n "$NS" get pods --no-headers 2>/dev/null \
        | awk -v s="^${svc}-[0-9a-f]" '$1 ~ s && $3=="Running" {print $1; exit}' \
        | xargs -r -I{} kubectl -n "$NS" get pod {} \
          -o jsonpath='{.status.containerStatuses[0].imageID}' 2>/dev/null | sed 's/.*@//')
  if   [ -z "$got" ];        then red "$svc: no running pod"; fail=1
  elif [ "$got" != "$want" ]; then red "$svc: RUNNING ${got:0:19}… but pinned ${want:0:19}…"; fail=1
  else grn "$svc"; fi
done

# ── 4. does every peer path name a route that peer serves? ─────────────────────────────────────
hdr "4 · every peer path resolves to a real route"
tok=$(kubectl -n "$NS" get secret operations-secrets \
      -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
if [ -z "$tok" ]; then
  yel "no internal token available — skipping (a skip is not a pass)"
else
  # Read each service's own *_PATH settings out of its values file, then ask the NAMED peer for its
  # manifest and check the path is declared. This is the check that would have caught reminders
  # reading zero visits for ever: both services healthy, both correct, and nothing happening.
  for f in "$VALUES_DIR"/*.values.yaml; do
    svc=$(basename "$f" .values.yaml)
    while read -r key val; do
      case "$key" in *_PATH:) ;; *) continue ;; esac
      path=$(printf '%s' "$val" | tr -d '"')
      case "$path" in /*) ;; *) continue ;; esac
      # The peer is the service named by the neighbouring *_SERVICE_URL, resolved by prefix.
      prefix="${key%_PATH:}"
      peer_url=$(grep -m1 -E "^\s+(${prefix%%_*}[A-Z_]*_SERVICE_URL|${prefix}_URL):" "$f" \
                 | awk '{print $2}' | tr -d '"')
      [ -n "$peer_url" ] || continue
      peer=$(printf '%s' "$peer_url" | sed -E 's#https?://([^:/]+).*#\1#')
      pod=$(kubectl -n "$NS" get pods --no-headers 2>/dev/null \
            | awk -v s="^${peer}-" '$1 ~ s && $3=="Running" {print $1; exit}')
      [ -n "$pod" ] || { yel "$svc: $prefix names $peer, which has no running pod"; continue; }
      served=$(kubectl -n "$NS" exec "$pod" -- python -c "
import urllib.request,json,sys
r=urllib.request.Request('http://localhost:8000/internal/manifest',
  headers={'X-Internal-Token': sys.argv[1]})
print('\n'.join(e['path'] for e in json.load(urllib.request.urlopen(r,timeout=10))['endpoints']))
" "$tok" 2>/dev/null)
      if [ -z "$served" ]; then
        yel "$svc: could not read $peer's manifest"
      # Path placeholders are rendered as {} in a manifest; compare with those stripped.
      elif printf '%s\n' "$served" | sed 's/{[^}]*}/{}/g' | grep -qxF "$(printf '%s' "$path" | sed 's/{[^}]*}/{}/g')"; then
        grn "$svc → $peer $path"
      else
        red "$svc: $prefix=$path — $peer does not serve it. Every call is a silent 404."
        fail=1
      fi
    done < <(grep -E '^\s+[A-Z_]+_PATH:' "$f" | awk '{print $1, $2}')
  done
fi

echo
if [ "$fail" -eq 0 ]; then
  printf '\e[32m✔ post-deploy: the artifact matches the declaration, and every peer path is real\e[0m\n'
else
  printf '\e[31m✗ post-deploy: the deploy reported success and something above is not true\e[0m\n'
fi
exit "$fail"
