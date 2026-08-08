#!/usr/bin/env bash
# ==================================================================================================
#  repin.sh — move every values file to a base-services tag, by DIGEST.
# --------------------------------------------------------------------------------------------------
#  Resolves each service's image digest from the registry and rewrites `digest:` in its values file.
#  Nothing else in the file is touched.
#
#  WHY DIGESTS AND NOT THE TAG ITSELF: a tag can be moved. Pinning `:v0.12.8` means a rollback
#  re-pulls whatever that tag points at on the day you roll back, which is not a rollback — it is a
#  hope. A digest names bytes, so `git revert` on a values file is an exact restoration.
#
#  Run it from the deploy host, where the cluster holds the registry credential — this reads the
#  `ghcr` pull secret rather than asking anyone to re-type a token.
#
#  IT PRINTS THE LIST OF SERVICES THAT MOVED, and that list is the point. update.sh takes --only,
#  and its own comment says why: "Re-rolling every service to change one is slow and restarts pods
#  nobody touched". A release that changes one service should take two minutes, not thirty. Feeding
#  this output into --only is the difference, and forgetting to is a mistake I made for three
#  releases in a row.
#
#  Usage:
#    bash deploy/repin.sh v0.13.1              # re-pin, then print the --only line to run
#    bash deploy/repin.sh v0.13.1 --dry-run    # show what would change, touch nothing
#
#  A service with no image at that tag is LEFT ON ITS CURRENT DIGEST and named in the output. That
#  is deliberate: silently leaving it behind while reporting success is how half a fleet ends up on
#  a version nobody meant to keep.
# ==================================================================================================
set -uo pipefail
TAG="${1:?usage: repin.sh <tag> [--dry-run]}"
DRY=0; [[ "${2:-}" == "--dry-run" ]] && DRY=1
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
VALUES_DIR="${VALUES_DIR:-$ROOT/deploy/services}"
NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

C_G="\033[32m"; C_R="\033[31m"; C_D="\033[2m"; C_N="\033[0m"

AUTH=$(kubectl -n "$NS" get secret ghcr -o jsonpath='{.data.\.dockerconfigjson}' 2>/dev/null \
  | base64 -d | python3 -c "import sys,json;d=json.load(sys.stdin)['auths'];print(d[list(d)[0]].get('auth',''))" 2>/dev/null)
[[ -n "$AUTH" ]] || echo "  (no ghcr credential in the cluster — anonymous pulls only)"

ACC='application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json'
changed=0; same=0; missing=0; moved_list=""

for f in "$VALUES_DIR"/*.values.yaml; do
  svc=$(basename "$f" .values.yaml)
  repo=$(grep -m1 'repository:' "$f" | sed 's/.*repository:[[:space:]]*//' | tr -d '"' | sed 's#^ghcr.io/##')
  tok=$(curl -s -H "Authorization: Basic $AUTH" \
        "https://ghcr.io/token?scope=repository:${repo}:pull&service=ghcr.io" \
        | sed -E 's/.*"token":"([^"]+)".*/\1/')
  dig=$(curl -sI -H "Authorization: Bearer $tok" -H "Accept: $ACC" \
        "https://ghcr.io/v2/${repo}/manifests/${TAG}" \
        | tr -d '\r' | grep -i '^docker-content-digest:' | awk '{print $2}')

  if [[ -z "$dig" ]]; then
    echo -e "  ${C_R}✗ $svc — no $TAG in the registry, LEFT ON ITS CURRENT DIGEST${C_N}"
    missing=$((missing+1)); continue
  fi
  cur=$(grep -m1 'digest:' "$f" | sed -E 's/.*digest:[[:space:]]*"([^"]*)".*/\1/')
  if [[ "$cur" == "$dig" ]]; then
    # Not an error and not a no-op worth hiding: upstream re-tags services whose image did not
    # change, so the same digest under a new tag means "this service is genuinely unchanged".
    echo -e "  ${C_D}= $svc already on this digest (unchanged between releases)${C_N}"
    same=$((same+1)); continue
  fi
  if [[ $DRY -eq 1 ]]; then
    echo -e "  ${C_D}~ $svc would move to ${dig:0:19}…${C_N}"; changed=$((changed+1)); continue
  fi
  python3 - "$f" "$dig" <<'PY'
import io,re,sys
f,dig=sys.argv[1],sys.argv[2]
s=io.open(f,encoding="utf-8").read()
s=re.sub(r'(\n\s*digest:\s*)"[^"]*"', lambda m: m.group(1)+'"'+dig+'"', s, count=1)
io.open(f,"w",encoding="utf-8",newline="\n").write(s)
PY
  echo -e "  ${C_G}✔ $svc -> ${dig:0:19}…${C_N}"
  changed=$((changed+1)); moved_list="$moved_list,$svc"
done

echo
echo -e "  moved: $changed · unchanged: $same · not published at $TAG: $missing"

# The whole reason to know WHICH moved. Rolling nineteen services to change one restarts eighteen
# pods for nothing, and on a modest node that is half an hour instead of two minutes.
if [[ -n "$moved_list" ]]; then
  echo
  echo -e "  ${C_G}roll only what changed:${C_N}"
  echo -e "    sudo KUBECONFIG=/etc/rancher/k3s/k3s.yaml PRODUCT_NAME=raje3 \\"
  echo -e "      CHART=\$ROOT/platform/deploy/chart VALUES_DIR=\$ROOT/deploy/services \\"
  echo -e "      bash \$ROOT/platform/deploy/server/update.sh --only ${moved_list#,}"
elif [[ $missing -eq 0 ]]; then
  echo -e "  ${C_D}nothing moved — the fleet is already on $TAG, no rollout needed${C_N}"
fi
[[ $missing -eq 0 ]]
