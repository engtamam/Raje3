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
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
TAG="${1:?usage: repin.sh <tag> [--dry-run]}"
DRY=0; [[ "${2:-}" == "--dry-run" ]] && DRY=1
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
VALUES_DIR="${VALUES_DIR:-$ROOT/deploy/services}"
NS="${NS:-base-services}"

C_G="\033[32m"; C_R="\033[31m"; C_D="\033[2m"; C_N="\033[0m"

AUTH=$(kubectl -n "$NS" get secret ghcr -o jsonpath='{.data.\.dockerconfigjson}' 2>/dev/null \
  | base64 -d | python3 -c "import sys,json;d=json.load(sys.stdin)['auths'];print(d[list(d)[0]].get('auth',''))" 2>/dev/null)
[[ -n "$AUTH" ]] || echo "  (no ghcr credential in the cluster — anonymous pulls only)"

ACC='application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json'
changed=0; same=0; missing=0; unresolved=0; moved_list=""; pending_list=""

for f in "$VALUES_DIR"/*.values.yaml; do
  svc=$(basename "$f" .values.yaml)
  repo=$(grep -m1 'repository:' "$f" | sed 's/.*repository:[[:space:]]*//' | tr -d '"' | sed 's#^ghcr.io/##')
  tok=$(curl -s -H "Authorization: Basic $AUTH" \
        "https://ghcr.io/token?scope=repository:${repo}:pull&service=ghcr.io" \
        | sed -E 's/.*"token":"([^"]+)".*/\1/')
  # READ THE STATUS, NOT THE ABSENCE OF A HEADER. An empty digest has two causes that mean opposite
  # things: a 404, which is genuinely "not published at this tag", and a timeout or a throttled
  # token request, which means we do not know. Both printed the same reassuring "no $TAG in the
  # registry" — and on the v0.13.5 re-pin four services printed it while the tag was sitting in the
  # registry the whole time. Reported as "15 moved, 10 not published", that run reads as a clean
  # release and would have left four services a version behind, with the summary line agreeing.
  #
  # So: retry a transient failure, and when it still will not resolve, say we do not know.
  # AND THE BACKOFF IS EXPONENTIAL, because what is being retried is a NAME LOOKUP THAT FAILS
  # UNDER LOAD. This was first written down as "ghcr rate-limits the burst", which was a guess
  # that fitted the symptom. The real evidence arrived from a completely different direction — a
  # kubelet on the same node failing to pull an image with
  #
  #     dial tcp: lookup pkg-containers.githubusercontent.com: Try again
  #
  # "Try again" is a resolver refusing a query, not a registry refusing a request. Twenty-five
  # lookups in a burst overwhelm the local stub resolver; asked one at a time, or four at a time
  # from a fresh session, every single one succeeds. curl reports that as HTTP 000, which looks
  # exactly like a throttled API and is not one.
  #
  # The retry is still right, and so is the backoff. The DIAGNOSIS was wrong, and a wrong
  # diagnosis in a comment outlives the bug.
  dig=""; code=""; backoff=3
  for _try in 1 2 3 4; do
    hdr=$(curl -sI -m 20 -w 'HTTPSTATUS:%{http_code}' \
          -H "Authorization: Bearer $tok" -H "Accept: $ACC" \
          "https://ghcr.io/v2/${repo}/manifests/${TAG}" | tr -d '\r')
    code=$(printf '%s' "$hdr" | grep -o 'HTTPSTATUS:[0-9]*' | tail -1 | cut -d: -f2)
    dig=$(printf '%s' "$hdr" | grep -i '^docker-content-digest:' | awk '{print $2}')
    [[ -n "$dig" || "$code" == "404" ]] && break
    sleep "$backoff"; backoff=$((backoff * 2))
    # A throttled token is refused exactly like an expired one; take a fresh one before retrying.
    tok=$(curl -s -m 20 -H "Authorization: Basic $AUTH" \
          "https://ghcr.io/token?scope=repository:${repo}:pull&service=ghcr.io" \
          | sed -E 's/.*"token":"([^"]+)".*/\1/')
  done

  if [[ -z "$dig" && "$code" != "404" ]]; then
    # HELD FOR A SECOND PASS RATHER THAN GIVEN UP ON. See below: this is a burst problem, and the
    # answer is to come back to the stragglers on their own after a real pause.
    echo -e "  ${C_D}? $svc — no answer yet (HTTP ${code:-none}); held for the second pass${C_N}"
    pending_list="$pending_list $f"
    continue
  fi

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

# ── THE SECOND PASS, over the stragglers only ─────────────────────────────────────────────────
# Twenty-five digest lookups in a burst is twenty-five token requests, and ghcr stops answering
# partway through. Four services failed every time — and every one of them resolved on the first
# try when asked in a batch of four. So the failure is the BURST, not the repo.
#
# In-loop retries did not fix it, and the reason is worth writing down: 3, 6 and 12 seconds all
# land inside the same closed window, so three retries are three identical failures with extra
# waiting. What works is leaving the window entirely and coming back to a handful.
#
# If a service still will not answer after this, THE RUN FAILS. "Not published" is a fact about the
# registry that a human can act on; "we could not tell" is not a state a release may exit in.
if [[ -n "${pending_list// /}" ]]; then
  echo
  echo -e "  ${C_D}second pass: waiting out the rate limit, then retrying the stragglers${C_N}"
  sleep 45
  for f in $pending_list; do
    svc=$(basename "$f" .values.yaml)
    repo=$(grep -m1 'repository:' "$f" | sed 's/.*repository:[[:space:]]*//' | tr -d '"' | sed 's#^ghcr.io/##')
    tok=$(curl -s -m 20 -H "Authorization: Basic $AUTH"           "https://ghcr.io/token?scope=repository:${repo}:pull&service=ghcr.io"           | sed -E 's/.*"token":"([^"]+)".*//')
    hdr=$(curl -sI -m 20 -w 'HTTPSTATUS:%{http_code}'           -H "Authorization: Bearer $tok" -H "Accept: $ACC"           "https://ghcr.io/v2/${repo}/manifests/${TAG}" | tr -d '
')
    code=$(printf '%s' "$hdr" | grep -o 'HTTPSTATUS:[0-9]*' | tail -1 | cut -d: -f2)
    dig=$(printf '%s' "$hdr" | grep -i '^docker-content-digest:' | awk '{print $2}')
    if [[ -z "$dig" ]]; then
      if [[ "$code" == "404" ]]; then
        echo -e "  ${C_R}✗ $svc — no $TAG in the registry, LEFT ON ITS CURRENT DIGEST${C_N}"
        missing=$((missing+1))
      else
        echo -e "  ${C_R}? $svc — still could not resolve $TAG (HTTP ${code:-no response})."
        echo -e "     This is NOT 'not published'. Nothing was written.${C_N}"
        # WHAT TO DO ABOUT IT, rather than just "re-run" — because on the v0.13.7 release the
        # same four services failed on every attempt, including a second pass of four after a
        # 45-second wait, while the identical four resolved instantly from a fresh session. We
        # never found the cause; what we found was that it did not matter.
        #
        # Ask the SOURCE instead of the registry: if the service is unchanged between the two
        # tags upstream, its image is unchanged too, and the digest already pinned is already
        # correct. That is a fact you can check in a second and act on with confidence:
        #
        #   git -C platform diff <old-tag>..<new-tag> --stat -- services/<svc>
        #
        # Empty output means this service does not need to move at all, and the release can go
        # ahead without it. The run still FAILS, because that judgement belongs to a person.
        echo -e "     ${C_D}check whether it needs to move at all:"
        echo -e "       git -C platform diff <previous-tag>..$TAG --stat -- services/$svc"
        echo -e "     no output means the service is unchanged and its current pin is correct.${C_N}"
        unresolved=$((unresolved+1))
      fi
      continue
    fi
    cur=$(grep -m1 'digest:' "$f" | sed -E 's/.*digest:[[:space:]]*"([^"]*)".*//')
    if [[ "$cur" == "$dig" ]]; then
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
s=re.sub(r'(
\s*digest:\s*)"[^"]*"', lambda m: m.group(1)+'"'+dig+'"', s, count=1)
io.open(f,"w",encoding="utf-8",newline="
").write(s)
PY
    echo -e "  ${C_G}✔ $svc -> ${dig:0:19}… (second pass)${C_N}"
    changed=$((changed+1)); moved_list="$moved_list,$svc"
  done
fi

echo
echo -e "  moved: $changed · unchanged: $same · not published at $TAG: $missing"
if [[ $unresolved -gt 0 ]]; then
  echo -e "  ${C_R}$unresolved service(s) UNRESOLVED — this run is incomplete, not a release.${C_N}"
fi

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
# A service we could not resolve fails the run. "Not published" is a fact about the registry that a
# human can act on; "we do not know" is not a state a release may exit successfully in.
[[ $missing -eq 0 && $unresolved -eq 0 ]]
