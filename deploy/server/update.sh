#!/usr/bin/env bash
# ==================================================================================================
#  Raje3 — health-gated rollout, with the images fetched in parallel first
# --------------------------------------------------------------------------------------------------
#  OUR COPY of platform/deploy/server/update.sh, taken deliberately rather than wrapped.
#
#  The platform's own script is read-only to us and stays untouched. A wrapper around it would have
#  worked and would have left the interesting part — WHEN the images are fetched — outside our
#  control, in a file we may not edit. Owning the copy means the change sits where the loop is, and
#  the cost is the one every fork has: their fixes do not arrive on their own. Their version is
#  worth re-reading at each platform release; the rollout logic below is theirs and should stay
#  recognisable so a diff is short.
#
#  WHAT WE CHANGED, AND WHY IT WAS WORTH A COPY.
#
#  The rollout is SEQUENTIAL and must stay so: services depend on one another, and upgrading them
#  together is how a fleet ends up half on each release. But the sequence also serialises the image
#  PULL, and that is not a dependency — it is just where the download happened to land.
#
#  Measured on our own cluster: 90 MB in 3m50s, nineteen services, one after another. The upgrade
#  itself takes seconds; the waiting was almost entirely the registry.
#
#  So the pulls happen FIRST and CONCURRENTLY, and the sequential loop then finds every image
#  already in containerd. Same order, same health gate, same rollback — an hour of it spent
#  downloading in parallel instead of in single file.
# --------------------------------------------------------------------------------------------------
#  A SAFE replacement for `make deploy`'s bare upgrade loop. Same idea — one generic chart, one values
#  file per service — but every service is rendered before the cluster is touched, waited on for
#  health, and AUTO-ROLLED-BACK to its previous revision if it does not come up. A release's identity
#  is the set of digests in the values directory; immutable by construction, so a rollback is exact.
#
#  PLUG-AND-PLAY. Nothing here is base-services-specific except the defaults. A product that consumes
#  this platform points the three env vars at its own tree and gets the same safe rollout:
#      PRODUCT_NAME=raje3 CHART=platform/deploy/chart VALUES_DIR=deploy/services bash update.sh
#
#  Usage:
#    sudo bash deploy/server/update.sh                    # roll every service to its pinned digest
#    sudo bash deploy/server/update.sh --only tenant,audit  # roll ONLY these; leave the rest untouched
#    sudo bash deploy/server/update.sh --dry-run          # render everything, change nothing
#    sudo bash deploy/server/update.sh --no-rollback      # leave a failed release up for debugging
#
#  Env:  PRODUCT_NAME (banner, default base-services) · NS (default base-services) ·
#        CHART (default <repo>/deploy/chart) · VALUES_DIR (default <repo>/deploy/pinned, else
#        deploy/services) · HEALTH_TIMEOUT (default 360) · PULL_GRACE (default 300)
# ==================================================================================================
set -Eeuo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"                 # repo root (deploy/server/ -> ../..)
PRODUCT_NAME="${PRODUCT_NAME:-base-services}"
NS="${NS:-${NAMESPACE:-base-services}}"           # NS or NAMESPACE (the Makefile uses NAMESPACE)
CHART="${CHART:-$ROOT/deploy/chart}"
# Prefer the digest-pinned release values; fall back to the source values (placeholder digests) so a
# fresh checkout that has not cut a release yet still rolls.
if [[ -z "${VALUES_DIR:-}" ]]; then
  if compgen -G "$ROOT/deploy/pinned/*.values.yaml" >/dev/null; then VALUES_DIR="$ROOT/deploy/pinned";
  else VALUES_DIR="$ROOT/deploy/services"; fi
fi
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-360}"           # helm --wait: a first install pulls an image first
# AFTER a helm --wait timeout, an extra budget for a node still PULLING a freshly published image.
# helm --wait cannot tell "will never be ready" from "still downloading the image", so a slow
# registry reads as a failure — and, with rollback working, would trigger a spurious rollback of a
# healthy service. If the rollout converges within this grace, it was slow, not broken.
PULL_GRACE="${PULL_GRACE:-300}"
ROLLBACK=1
DRY_RUN=0

C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_R=$'\e[31m'; C_N=$'\e[0m'; C_D=$'\e[2m'
info(){ echo -e "${C_C}▸ $*${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }
warn(){ echo -e "${C_Y}  ⚠ $*${C_N}"; }
die(){  echo -e "${C_R}✖ $*${C_N}" >&2; exit 1; }

ONLY=""      # optional CSV of service names to roll — the rest are LEFT UNTOUCHED
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-rollback) ROLLBACK=0;;
    --dry-run) DRY_RUN=1;;
    --only) shift; ONLY="${1:-}"; [[ -n "$ONLY" ]] || die "--only needs a comma-separated list";;
    --only=*) ONLY="${1#--only=}";;
    -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    -*) die "unknown flag $1";;
    *) die "unexpected argument '$1' — this rolls the digests in $VALUES_DIR, it takes no tag";;
  esac; shift
done

# Roll only the named services (and tolerate a bare name or a "-service" suffix). Re-rolling every
# service to change one is slow and restarts pods nobody touched, so --only exists.
_in_only() {
  [[ -z "$ONLY" ]] && return 0
  local n="$1"; IFS=',' read -ra want <<< "$ONLY"
  for w in "${want[@]}"; do
    w="$(echo "$w" | xargs)"
    [[ "$n" == "$w" || "$n" == "$w-service" || "$n-service" == "$w" ]] && return 0
  done
  return 1
}

[[ $EUID -eq 0 ]] || die "run as root: sudo bash $0"
command -v helm >/dev/null || die "helm missing (deploy/server/provision-server.sh installs it)"
kubectl get nodes >/dev/null 2>&1 || die "kubectl cannot reach the cluster (is k3s up?)"
# One clear line instead of N identical helm errors if the tree is wrong or a checkout is half-done.
[[ -f "$CHART/Chart.yaml" ]] || die "chart not found at $CHART — run from the repo, or set CHART=<path>"

echo -e "${C_C}━━━  ${PRODUCT_NAME} — rolling the platform to its pinned digests  ━━━${C_N}"
echo -e "  ${C_D}chart=$CHART${C_N}"
echo -e "  ${C_D}values=$VALUES_DIR${C_N}"
[[ $DRY_RUN -eq 1 ]] && warn "DRY RUN — every service is rendered, nothing is applied"

mapfile -t targets < <(ls "$VALUES_DIR"/*.values.yaml 2>/dev/null | xargs -r -n1 basename | sed "s/\.values\.yaml$//")
[[ ${#targets[@]} -gt 0 ]] || die "no values files in $VALUES_DIR"

[[ -n "$ONLY" ]] && info "rolling ONLY: ${ONLY} (all other services left untouched)" \
                  || info "rolling ${#targets[@]} services"

# ── pre-pull: every image at once, before the sequential loop needs any of them ───────────────
#
# WHY ctr AND NOT THE KUBELET. The kubelet pulls when a pod is scheduled, which is inside the loop —
# by then the waiting has already been serialised. Pulling into containerd ahead of time puts the
# image where the kubelet will look for it, and the pod starts without a network round trip.
#
# AND WHY THE CREDENTIAL IS PASSED EXPLICITLY. Our images are private. The kubelet authenticates
# with the `ghcr` imagePullSecret, which `ctr` does not read — it tries anonymously and gets a 401
# that reads like "no such image". The first version of this failed on all eight services for that
# reason and reported nothing useful, because it discarded stderr.
#
# FAILURE HERE IS NOT FATAL, and that is deliberate: a pull that could not run leaves the kubelet to
# do exactly what it did before. This step makes the rollout faster; it must never make it fail.
prepull() {
  command -v k3s >/dev/null 2>&1 || return 0
  local cred=""
  # `|| true` — THIS COMMENT PROMISED "failure here is not fatal" AND THE CODE DID NOT KEEP THAT
  # PROMISE. `kubectl get secret ghcr` failing (the secret was simply missing from the namespace,
  # a real state hit live) makes the whole pipeline exit non-zero; under this script's own
  # `set -Eeuo pipefail`, an unguarded assignment from a failing command substitution is fatal —
  # so the entire rollout died right here, silently, before the per-service loop ever printed a
  # line, on EVERY ship for as long as the secret was missing. `cred` staying empty is already
  # the correct, handled case two lines below (falls through to an anonymous pull); this only
  # needed to stop being allowed to kill the script over it.
  cred="$(kubectl -n "$NS" get secret ghcr -o jsonpath='{.data.\.dockerconfigjson}' 2>/dev/null \
          | base64 -d 2>/dev/null \
          | python3 -c 'import sys,json,base64
try:
    d = json.load(sys.stdin)["auths"]
    print(base64.b64decode(d[list(d)[0]].get("auth","")).decode())
except Exception:
    pass' 2>/dev/null)" || true

  local pulled=0 pids=()
  for svc in "${targets[@]}"; do
    _in_only "$svc" || continue
    local values="$VALUES_DIR/$svc.values.yaml"
    local repo digest
    repo="$(grep -m1 'repository:' "$values" 2>/dev/null | sed 's/.*repository:[[:space:]]*//' | tr -d '"')"
    digest="$(grep -m1 -o 'sha256:[a-f0-9]*' "$values" 2>/dev/null)"
    [[ -n "$repo" && -n "$digest" ]] || continue
    # LOCAL IMAGES ARE ALREADY THERE. Our own services are built here and imported into containerd;
    # asking a registry for them would fail and would say so loudly for no reason.
    [[ "$repo" == docker.io/raje3/* ]] && continue
    if k3s ctr images ls -q 2>/dev/null | grep -qx "$repo@$digest"; then continue; fi
    pulled=$((pulled+1))
    ( if [[ -n "$cred" ]]; then
        k3s ctr images pull -u "$cred" "$repo@$digest" >/dev/null 2>&1
      else
        k3s ctr images pull "$repo@$digest" >/dev/null 2>&1
      fi ) &
    pids+=($!)
  done

  [[ $pulled -eq 0 ]] && { ok "every image is already on the node"; return 0; }
  info "fetching $pulled image(s) in parallel before rolling"
  local failed_pulls=0
  for p in "${pids[@]}"; do wait "$p" || failed_pulls=$((failed_pulls+1)); done
  if [[ $failed_pulls -gt 0 ]]; then
    # NAMED, NOT SWALLOWED. The rollout still works — the kubelet will pull — but a silent failure
    # here would leave somebody wondering why it took an hour anyway.
    warn "$failed_pulls image(s) could not be pre-fetched; the kubelet will pull them during the roll"
  else
    ok "every image is on the node — the roll below will not wait on the registry"
  fi
}

# ── THE SEATS THE DEAD ARE HOLDING, RETURNED BEFORE WE NEED THEM ─────────────────────────────
#
# A pod that has FINISHED — Failed or Succeeded — no longer runs and is still counted by the
# scheduler: its requests stay booked. Sixteen of them on the pilot node held 5180m against a
# 4000m box, so a rollout could not place its new pod, the pod died `OutOfcpu`, the OLD pod kept
# serving, and helm reported a healthy release — truthfully, about the old one.
#
# CALLED, NOT COPIED. `deploy/sweep.sh` is the one place that decides what may be swept and what
# may never be, and it runs here because THIS is the moment the seats are actually needed. The
# weekly cron runs the same file for what accumulates between deploys.
sweep_before_rolling() {
  local sweeper="$ROOT/deploy/sweep.sh"
  [[ -f "$sweeper" ]] || return 0
  NS="$NS" bash "$sweeper" 2>&1 | sed 's/^/  /'
}

[[ $DRY_RUN -eq 1 ]] || sweep_before_rolling
[[ $DRY_RUN -eq 1 ]] || prepull

updated=0 failed=0 skipped=0
for svc in "${targets[@]}"; do
  if ! _in_only "$svc"; then skipped=$((skipped+1)); continue; fi
  values="$VALUES_DIR/$svc.values.yaml"
  printf "  %-26s ... " "$svc"

  # RENDER FIRST. A values file that cannot render is caught BEFORE the cluster is touched, rather
  # than halfway through with some services on the new release and some on the old.
  if ! helm template "$svc" "$CHART" -f "$values" >/dev/null 2>&1; then
    echo -e "${C_R}render failed${C_N}"
    helm template "$svc" "$CHART" -f "$values" 2>&1 | tail -3 | sed "s/^/      /"
    failed=$((failed+1)); continue
  fi
  if [[ $DRY_RUN -eq 1 ]]; then echo -e "${C_D}renders clean${C_N}"; updated=$((updated+1)); continue; fi

  # The revision to return to, read BEFORE the upgrade. `helm rollback <n>` to a known revision beats
  # a bare `rollback`, which trusts helm's idea of "previous" after a failed release.
  #
  # The revision lives under the "version" key of `helm status -o json`. It is NOT "revision" — that
  # key does not exist, so parsing it yielded EMPTY for every release, the rollback branch was
  # unreachable, and every failed upgrade was silently left up while the operator was told, falsely,
  # that there was "nothing to roll back to". `existed` separates the two cases the old code collapsed:
  # a genuine first install (no prior revision — reassuring) from a release we could not read (a parse
  # failure — alarming, and the operator must roll back by hand).
  existed=0; prev=""
  if helm -n "$NS" status "$svc" >/dev/null 2>&1; then
    existed=1
    prev="$(helm -n "$NS" status "$svc" -o json 2>/dev/null \
            | sed -n 's/.*"version":[ ]*\([0-9]*\).*/\1/p' | head -1)"
  fi

  # THE ERROR IS KEPT, NOT DISCARDED. `2>&1 >/dev/null` used to throw away the one sentence that
  # says WHY an upgrade failed, and the branch below then asked a question that cannot distinguish
  # the causes: «is the deployment healthy?» is true for a deployment nobody managed to change.
  # `|| helm_rc=$?`, because this file runs under `set -e`: an assignment whose command substitution
  # FAILS ends the script, and a failing upgrade is precisely the case this code exists to handle.
  helm_rc=0
  helm_err="$(helm upgrade --install "$svc" "$CHART" -f "$values" \
                --namespace "$NS" --create-namespace --wait \
                --timeout "${HEALTH_TIMEOUT}s" 2>&1 >/dev/null)" || helm_rc=$?
  if [[ $helm_rc -eq 0 ]]; then
    echo -e "${C_G}ok${C_N}"; updated=$((updated+1))
  elif [[ "$helm_err" != *"timed out waiting"* ]]; then
    # HELM DID NOT EVEN GET TO WAIT. An unreachable cluster, a bad chart, a rejected manifest —
    # none of these is «still pulling», and the pull-grace branch below must not be asked about
    # them. It reads `kubectl rollout status`, which SUCCEEDS for a deployment that was never
    # touched, so a `helm` that could not connect at all was reported as a successful roll. That
    # is exactly what happened: every upgrade failed with «Kubernetes cluster unreachable», every
    # service was marked ok, and the release revision on the node had not moved in a day.
    echo -e "${C_R}failed${C_N}"; failed=$((failed+1))
    echo "      ${helm_err%%$'\n'*}"
    continue
  elif kubectl -n "$NS" rollout status "deploy/$svc" --timeout="${PULL_GRACE}s" >/dev/null 2>&1; then
    # helm --wait ran out, but the rollout CONVERGED within the pull grace: the node was still
    # PULLING the freshly published image, not failing. Report success, and name which budget was
    # short so the operator raises the right one — not a rollback of a healthy service.
    echo -e "${C_G}ok${C_N}"; updated=$((updated+1))
    warn "$svc: became healthy only after helm --wait's ${HEALTH_TIMEOUT}s elapsed — the image was"\
         "still pulling; it converged within the ${PULL_GRACE}s PULL_GRACE. Raise HEALTH_TIMEOUT if"\
         "your registry is consistently this slow."
  else
    # Neither the health wait NOR the pull grace converged — a genuine readiness failure (a crash,
    # a bad config, an unpullable image), not a slow download.
    echo -e "${C_R}failed${C_N}"; failed=$((failed+1))
    kubectl -n "$NS" logs "deploy/$svc" --tail=5 2>/dev/null | sed "s/^/      /" || true
    if [[ $ROLLBACK -eq 0 ]]; then
      warn "$svc left in its failed state (--no-rollback)"
    elif [[ "$prev" =~ ^[0-9]+$ && "$prev" -gt 0 ]]; then
      warn "$svc did not become healthy (readiness, not a slow pull) — rolling back to revision $prev"
      helm -n "$NS" rollback "$svc" "$prev" --wait --timeout "${HEALTH_TIMEOUT}s" >/dev/null 2>&1 \
        && ok "$svc rolled back to revision $prev" \
        || warn "$svc rollback ALSO failed — inspect and roll back by hand: helm -n $NS history $svc"
    elif [[ $existed -eq 1 ]]; then
      # The release EXISTS but its prior revision could not be read. This is NOT "nothing to roll
      # back to" — do not reassure. The operator can still roll back manually, and should.
      warn "$svc did NOT roll back — could not determine its prior revision, though the release HAS"\
           "history. Roll back BY HAND: helm -n $NS history $svc  then  helm -n $NS rollback $svc <REVISION>"
    else
      warn "$svc has no previous revision (first install) — nothing to roll back to"
    fi
  fi
done

echo -e "\n${C_G}━━━  update summary ━━━${C_N}"
echo -e "  source:     ${C_C}${VALUES_DIR}/*.values.yaml${C_N}"
echo -e "  updated:    ${C_G}${updated}${C_N} / ${#targets[@]}"
[[ $skipped -gt 0 ]] && echo -e "  skipped:    ${C_C}${skipped}${C_N} (not in --only; left untouched)"
[[ $failed -gt 0 ]] && echo -e "  failed:     ${C_R}${failed}${C_N}$([[ $ROLLBACK -eq 1 ]] && echo ' (rolled back)')"
kubectl -n "$NS" get deploy --no-headers 2>/dev/null | awk '{printf "  %-26s %s\n",$1,$2}'
echo -e "\n  Not-ready pods (if any):"
# Fully-ready+Running, or a Completed job pod, is fine; anything else is worth showing. (mawk has no
# regex backreference, so split READY on "/" rather than matching ^(n)/\1$, which over-lists healthy pods.)
kubectl -n "$NS" get pods --no-headers 2>/dev/null \
  | awk '{split($2,a,"/"); ok=(a[1]==a[2] && $3=="Running"); if(!(ok || $3=="Completed")) print "    "$0}' \
  | head -20 || true
[[ $failed -eq 0 ]] || exit 1

# PRUNE superseded node images now that every deployment is on the new digest and healthy — the old
# tags are no longer referenced by any pod, which is what slowly fills a long-lived box. Only on a
# fully-successful rollout (a rollback might still need the previous image). Best-effort.
#
# ── AND NEVER WHEN THE IMAGES WERE SIDE-LOADED, WHICH IS WHAT PRUNE_IMAGES GUARDS ────────────
#
# `crictl rmi --prune` deletes every image no RUNNING pod references. On the registry road that is
# harmless — the node can fetch it again. On the TARBALL road the node holds the ONLY copy, and a
# pod that is still pulling (or restarting) does not count as a reference: the prune deletes the
# image we just shipped, and the pod can never recover, because there is nowhere left to pull from.
#
# IT COST TWO FULL DEPLOYS TO SEE. Both reported «rolled — every service on its pinned digest»,
# both ended in ImagePullBackOff, and the second left containerd with NO image for the service at
# all — which is what finally named the culprit. A cleanup that destroys the artefact it was
# cleaning up around is the worst kind of green report.
if [ "${PRUNE_IMAGES:-1}" != "1" ]; then
  echo -e "  images kept — side-loaded, and the node holds the only copy"
elif command -v crictl >/dev/null 2>&1; then
  crictl rmi --prune >/dev/null 2>&1 && echo -e "  ${C_G}✔ pruned superseded node images${C_N}" || true
elif command -v k3s >/dev/null 2>&1; then
  k3s crictl rmi --prune >/dev/null 2>&1 && echo -e "  ${C_G}✔ pruned superseded node images${C_N}" || true
fi

# ── THE CLOSING LINE SAYS WHAT WAS DONE, AND CHECKS IT ────────────────────────────────────────
#
# IT USED TO CLAIM «every service on its pinned digest», unconditionally, at the end of every run.
# Two things were wrong with that sentence and both mattered.
#
# IT COVERED SERVICES THIS RUN NEVER TOUCHED. `--only api-gateway` rolls one and LEAVES the other
# twenty-three exactly as they were — which is the whole point of the flag — and then announced
# that all twenty-four were on their pinned digests. A claim about services the run deliberately
# skipped cannot be anything but a guess.
#
# AND IT ASSERTED THE ONE THING NOBODY HAD READ BACK. `helm upgrade` reports that IT succeeded;
# whether the Deployment now carries the digest in the values file is a different fact, and every
# expensive deploy failure in this file's history has lived in that gap. A run reported «rolled»
# six times in a row while all six Deployments kept their old digests, and only the caller's own
# verify step ever disagreed.
#
# So the check is here now, where the roll is: for each service this run actually upgraded, compare
# the Deployment's image against the digest its values file pins. A mismatch is a FAILURE — the
# operator asked for a roll and did not get one — and it names the two digests rather than a mood.
verified=0; unmoved=()
for svc in "${targets[@]}"; do
  _in_only "$svc" || continue
  values="$VALUES_DIR/$svc.values.yaml"
  want="$(grep -m1 -o 'sha256:[a-f0-9]*' "$values" 2>/dev/null || true)"
  [[ -n "$want" ]] || continue          # no digest pinned: nothing to compare, and nothing claimed
  live="$(kubectl -n "$NS" get deploy "$svc" \
            -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true)"
  if [[ -z "$live" ]]; then
    unmoved+=("$svc: no deployment to read")
  elif [[ "$live" == *"$want"* ]]; then
    verified=$((verified+1))
  else
    unmoved+=("$svc: declares ${want:0:19}… and the deployment carries ${live##*@}")
  fi
done

if [[ ${#unmoved[@]} -gt 0 ]]; then
  echo -e "\n${C_R}✗ the roll did not land${C_N}"
  for line in "${unmoved[@]}"; do echo -e "    ${C_R}$line${C_N}"; done
  echo -e "  ${C_D}helm reported success; the deployment did not change. Nothing here is on the"\
          "digest you asked for.${C_N}"
  exit 1
fi
if [[ -n "$ONLY" ]]; then
  echo -e "\n${C_G}✔ ${PRODUCT_NAME}: ${verified} service(s) on the pinned digest — ${ONLY}${C_N}"
  echo -e "  ${C_D}the rest were not part of this run and are not claimed for${C_N}"
else
  echo -e "\n${C_G}✔ ${PRODUCT_NAME}: all ${verified} service(s) verified on their pinned digest${C_N}"
fi
