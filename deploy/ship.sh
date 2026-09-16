#!/usr/bin/env bash
# Publish to ghcr, roll the cluster onto it, and VERIFY what the pod is actually running.
#
#   GHCR_TOKEN=… ./deploy/ship.sh portal
#   GHCR_TOKEN=… ./deploy/ship.sh reminders operations console
#   GHCR_TOKEN=… ./deploy/ship.sh billing-service          # a platform image: rolled, not built
#
# THE RULE THIS SCRIPT NOW OBEYS, AND IT IS THE ONE EVERY SERIOUS SHOP OBEYS. The developer builds
# and pushes to the registry; the server pulls from the registry. Nothing travels from a personal
# machine into production.
#
# WHAT IT USED TO DO, AND WHAT THAT COST. There were two other roads, and both ended on a laptop:
#
#   * `docker save | ssh … ctr images import` — the whole image carried down an ssh pipe, ninety
#     megabytes because one Python file changed;
#   * a registry running HERE, reached by the node through a reverse ssh forward, with the values
#     file REWRITTEN at ship time to say `127.0.0.1:5055/raje3/<svc>`.
#
# The second one is why this rewrite exists. That rewrite happened on the node, so no gate reading
# the repository could see it — `deploy/edge/console.yaml` named ghcr the whole time and was
# correct. But the cluster ran
#
#     127.0.0.1:5055/raje3/console@sha256:865bc154…
#
# in a production Deployment: an address exactly one machine on earth resolves, and only while a
# particular developer holds a tunnel open. Reboot the node at 3am and the console cannot start,
# with nothing anywhere saying why. Every other service ran from ghcr; the console alone had been
# shipped by the fast road, and it had become un-shippable by any road.
#
# So both are gone, and `ci/check_no_image_travels_from_a_laptop.py` keeps them gone.
#
# THE FOUR STEPS, AND WHY THE ORDER IS THE ONLY ONE THAT WORKS.
#
#   1. TESTS, before anything is built. Building from code that fails its own tests wastes four
#      minutes to learn something that took four seconds.
#   2. PUBLISH — `publish-images.sh` builds, pushes to ghcr, and writes the digest THE REGISTRY
#      REPORTED into the values file. Not a digest we intended, and never a tag: a tag is a name,
#      and a name can be moved after review so a pod runs code nobody approved.
#   3. SYNC, THEN ROLL, in that order always. A rollout reads the values file ON THE SERVER;
#      syncing afterwards means helm renders the previous pin and reports success about it.
#   4. VERIFY THE ARTIFACT, NOT THE REPORT. `imageID` is what the kubelet actually resolved. helm
#      reports what it asked for, and the two disagreed for two entire releases once.
#
# WHY IT EXISTS AT ALL. These steps were run by hand for every service, and each failed in a
# different way at least once:
#
#   the image was built before the code was added        -> a route 404ing on a running pod
#   the values file synced after the rollout, not before -> "rolled" against a two-version-old pin
#   rollout restart was used to pick up a new image      -> restarted the OLD image, cleanly
#   the pod was on the old digest and nobody looked      -> a proof that returned yesterday's numbers
#
# None of those is interesting. All of them cost an hour.
#
# NO `set -e`. Each phase reports and the script decides — `set -e` turns a diagnosable failure
# into a silent exit, which is the shape half the list above already has.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

# ── WHERE THE MACHINE IS, AND THE REFUSAL WHEN NOBODY SAID ───────────────────────────────────
# `cluster.sh` above read `deploy/target.env` — not in git, because it names a host, a port and a
# login that differ per operator and per environment. See deploy/target.env.example.
#
# A ship needs the BOX and not merely its cluster: the values file and the chart are copied onto
# it before helm is asked to render them. So REMOTE is required rather than defaulted.
: "${REMOTE:?a ship needs a machine — set REMOTE and PORT in deploy/target.env}"
PORT="${PORT:-22}"
NS="${NS:-base-services}"

# KEEPALIVES, BECAUSE THE VERIFY STEP IS THE LONGEST QUIET MOMENT IN THE RUN. Between the rollout
# and the digest read the connection can sit idle long enough for something in the middle to drop
# it, and the failure surfaces as «Connection closed» during VERIFY — which reads as "the image did
# not take" about an image that took.
SSH=(ssh -o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=30
     -o ConnectTimeout=20 -o TCPKeepAlive=yes -p "$PORT" "$REMOTE")

red(){ printf '\e[31m✗ %s\e[0m\n' "$*" >&2; }
yel(){ printf '\e[33m⚠ %s\e[0m\n' "$*" >&2; }
grn(){ printf '\e[32m✔ %s\e[0m\n' "$*" >&2; }
say(){ printf '\n\e[1m▸ %s\e[0m\n' "$*" >&2; }

# Which of the three kinds a name is. The submodule IS the list of platform services — a service
# added upstream needs no edit here — and the console is the one thing deployed by a raw manifest
# rather than by the chart, because it is a Caddy holding files: no secret, no driver, no database
# for a values file to describe.
kind_of() {
  case "$1" in console) echo console; return;; esac
  [ -d "$ROOT/services/$1" ] && { echo ours; return; }
  [ -d "$ROOT/platform/services/$1" ] && { echo platform; return; }
  echo unknown
}

pinned_digest() {
  sed -n 's/^  digest: *"\([^"]*\)".*/\1/p' "$ROOT/deploy/services/$1.values.yaml" | head -1
}

# ── SYNC, THEN ROLL ───────────────────────────────────────────────────────────────────────────
#
# THE CHART TRAVELS WITH THE VALUES, and forgetting it is why every rollout failed for days: the
# tarball carried the values file, the hooks and our update script, and the chart lives in the
# platform SUBMODULE, which is part of none of them. helm answered "path not found", the run
# reported a failure with no obvious cause, and the cluster kept serving an image from weeks
# earlier. It is 92K; re-sending it on every ship is cheaper than one failed rollout, and it closes
# a second failure nobody had reached yet — the day the platform is upgraded, a chart left on the
# server from an older release renders yesterday's templates against today's values.
sync_and_roll() {
  local svc="$1" digest="$2"
  # `deploy/cluster.sh` IS IN THIS LIST BECAUSE THE ROLL CANNOT START WITHOUT IT. update.sh and
  # both hooks source it on their first executable line, and it was not being uploaded — so every
  # roll died with «No such file or directory» before it rolled anything, on a step whose previous
  # line had just printed a true «✔ declaration synced». The verify step caught the consequence
  # every time; nothing named the cause. ci/check_a_script_we_upload_sources_nothing_we_left_behind.py
  # now compares this list against what these scripts actually read.
  # `deploy/sweep.sh` IS HERE FOR THE SAME REASON `cluster.sh` IS, and it was learned the same way
  # — twice in one night. update.sh calls it before rolling, behind an `[[ -f … ]] || return 0`
  # guard that is correct (a missing sweeper must never fail a rollout) and therefore SILENT. The
  # roll reported success, the seats sixteen dead pods were holding stayed booked, and the node
  # went on refusing to schedule. A file we RUN is as much a dependency as one we READ.
  if ! tar czf - -C "$ROOT" "deploy/services/$svc.values.yaml" deploy/cluster.sh deploy/sweep.sh \
         deploy/hooks deploy/server platform/deploy/chart 2>/dev/null \
       | "${SSH[@]}" "mkdir -p ~/raje3 && cd ~/raje3 && tar xzf - 2>/dev/null \
         && chmod +x deploy/hooks/*.sh && grep -q '$digest' deploy/services/$svc.values.yaml"; then
    red "$svc: the values file on the server does not carry the pinned digest"; return 1
  fi
  grn "declaration synced"

  # OURS, NOT THEIRS. deploy/server/update.sh is our copy of the platform's rollout, and the one
  # thing it adds is fetching the images in parallel before the sequential loop needs them — a
  # single image took 3m50s on this link, and nineteen in single file took over an hour.
  "${SSH[@]}" "cd ~/raje3 && sudo -n PRODUCT_NAME=raje3 CHART=platform/deploy/chart PRUNE_IMAGES=1 \
     VALUES_DIR=deploy/services bash deploy/server/update.sh --only $svc 2>&1 | tail -14"
  # `tail -14`, NOT `tail -2`. Two lines showed the banner and threw away everything that could
  # contradict it — the update summary, the render failures, and now the digest comparison the roll
  # makes for itself. A step whose evidence is trimmed off reports only its own opinion.
}

# ── VERIFY THE ARTIFACT, NOT THE REPORT ───────────────────────────────────────────────────────
#
# `imageID`, never the spec. A digest reference is a NAME until something reads back what the
# kubelet resolved; a pod ran two-version-old code for hours under a correct-looking pin, and only
# this comparison disagreed.
#
# AND THE COMPARISON ITSELF HAD TO LEARN THE SAME LESSON, POINTED THE OTHER WAY. `imageID` and a
# pinned digest are BOTH names, and on a multi-arch image they are names of different things: the
# pin is an index (a manifest list) and `imageID` is whatever index containerd already had
# associated with the content it resolved. Measured on the cluster, loyalty showed
#
#     spec:    …@sha256:225470f1…      the pin
#     imageID: …@sha256:0b9518d3…      a different index
#
# and both resolve to the SAME manifest (1d51c7b9…) and the SAME config (5ca4425a…). Identical
# content published twice; the second index differs only by the attestation entry the builder
# attaches. The ship printed «RUNNING 0b9518… but pinned 225470…» over a shipment that had
# worked perfectly.
#
# A proof that cries wolf is worse than no proof, because the next real drift ships behind it. So
# the question asked here is CONTENT: what config digest does the pin resolve to on this node, and
# what config digest is the pod running. Two names for one manifest agree; two manifests do not.
verify_running() {
  local svc="$1" digest="$2" running="" live=""
  # PLAIN `kubectl`, THROUGH THE SEAM — this function used to build its own remote command
  # strings by hand (`sudo -n KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl` over `"${SSH[@]}"`),
  # a second, hardcoded copy of the exact fix cluster.sh's own ssh kubectl() wrapper already
  # carries (sudo + the node's kubeconfig named explicitly — root:root 600 by k3s's own default,
  # unreadable to the login ssh connects as otherwise). Two copies of one fact drift; `cluster.sh`
  # sourced at the top of this file already exported a `kubectl` that does the identical thing
  # for CLUSTER_VIA=ssh (and is simply the real binary, KUBECONFIG already in the environment,
  # for CLUSTER_VIA=node/local) — so this function now asks it the same way every other script
  # under deploy/ does, instead of answering the question a second time.
  for _ in $(seq 1 40); do
    running="$(kubectl -n "$NS" get pods --no-headers 2>/dev/null \
      | awk -v svc="$svc" '$1 ~ ("^" svc "-[0-9a-f]") && $3=="Running" && $2=="1/1" {print $1; exit}')"
    [ -n "$running" ] && break
    sleep 15
  done
  if [ -z "$running" ]; then
    red "$svc: no ready pod after 10 minutes"
    kubectl -n "$NS" get pods --no-headers | grep "^$svc-"
    kubectl -n "$NS" logs \
      "$(kubectl -n "$NS" get pods --no-headers | awk -v svc="$svc" '$1 ~ ("^" svc "-") {print $1; exit}')" \
      --tail=20 2>&1 | tail -12
    return 1
  fi
  live="$(kubectl -n "$NS" get pod "$running" \
      -o jsonpath='{.status.containerStatuses[0].imageID}' | sed 's/.*@//')"
  if [ "$live" = "$digest" ]; then
    grn "$svc is running the digest its values file names"
    return 0
  fi

  # THE NAMES DIFFER. That is not yet a failure — see the note above — so ask the content store
  # what each name resolves to. Only if the CONTENT differs has the wrong code been rolled.
  local want_config live_config
  want_config="$(resolve_config "$digest")"
  live_config="$(resolve_config "$live")"
  if [ -n "$want_config" ] && [ "$want_config" = "$live_config" ]; then
    grn "$svc is running the pinned content (config ${want_config:7:12}…, reached by two indexes)"
    return 0
  fi
  red "$svc: RUNNING ${live:0:26}… but pinned ${digest:0:26}…"
  if [ -n "$want_config$live_config" ]; then
    red "      and they are different content: ${live_config:0:19}… vs ${want_config:0:19}…"
  else
    # COULD NOT RESOLVE EITHER. Reporting a pass on «I could not tell» is the failure this whole
    # file exists to prevent, so an unreadable content store is a red, not a shrug.
    red "      and the node's content store could not be read, so this is unproven, not fine"
  fi
  return 1
}

# ── WHAT A DIGEST ACTUALLY POINTS AT ──────────────────────────────────────────────────────────
#
# TWO HOPS, NOT ONE, AND THE FIRST DRAFT OF THIS ONLY DID ONE. An INDEX names a list of manifests;
# a MANIFEST names the config that is the running image's identity. The pin is an index, so a
# resolver that only understood manifests returned nothing for it — and «returned nothing» was
# then read as «could not resolve», which would have failed exactly the shipment this fix exists
# to stop failing. The fix has to be exercised against the shape it will actually meet.
#
# Prints the config digest, or nothing when the node cannot tell us. Empty is never read as
# agreement by the caller above: unproven is a red, not a shrug.
resolve_config() {
  local d="$1"
  [ -n "$d" ] || return 0
  # `k3s ctr` reads containerd's own socket — root only, same reason every other node-side read
  # in this file now carries sudo explicitly rather than relying on the login's own permissions.
  "${SSH[@]}" "sudo -n python3 - $d <<'RESOLVE'
import json, subprocess, sys

def blob(digest):
    out = subprocess.run(['k3s', 'ctr', '-n', 'k8s.io', 'content', 'get', digest],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except ValueError:
        return None

doc = blob(sys.argv[1])
if doc is None:
    raise SystemExit(0)

# An index: follow the entry for this machine's platform. Attestation entries carry no platform
# and must not be followed — they are about the image, not the image.
if 'manifests' in doc:
    for entry in doc['manifests']:
        platform = entry.get('platform') or {}
        if platform.get('architecture') == 'amd64' and platform.get('os') == 'linux':
            doc = blob(entry['digest'])
            break
    else:
        raise SystemExit(0)

if doc and 'config' in doc:
    print(doc['config']['digest'])
RESOLVE" 2>/dev/null || true
}

# ── A PLATFORM IMAGE: ROLLED, NEVER BUILT ─────────────────────────────────────────────────────
#
# THE GAP THIS CLOSED, AND IT COST TWO RELEASES. This script used to start at `services/$svc`, so
# `./deploy/ship.sh identity-service` failed at the first line with "no services/identity-service"
# — and nothing else in the repo deployed a platform image at all. `repin-platform.sh` rewrote the
# digests, the submodule moved, git was clean and green, and the cluster went on running v0.16.4
# for two releases. It was found the only way it could be: by asking the running billing-service
# for a route v0.16.7 added, and getting 404.
#
# The code is upstream's and was tested there, and the image is already in the registry. What is
# left is the half that matters, and it is the same half our own services need.
ship_platform_one() {
  local svc="$1" digest
  digest="$(pinned_digest "$svc")"
  [ -n "$digest" ] || { red "$svc: no digest pinned in deploy/services/$svc.values.yaml"; return 1; }
  say "$svc · 1/3 sync (platform image — pulled by digest, not built here)"
  sync_and_roll "$svc" "$digest" || return 1
  say "$svc · 3/3 verify"
  verify_running "$svc" "$digest"
}

# ── THE CONSOLE: A MANIFEST, NOT A CHART RELEASE ──────────────────────────────────────────────
#
# `publish-images.sh` has already built it, pushed it to ghcr and written the digest into
# `deploy/edge/console.yaml` — the tracked file, which is the one a stranger installs from. All
# that remains is to put that same file on the server and apply it.
#
# NOTHING IS REWRITTEN ON THE WAY. The old path pinned `127.0.0.1:5055/raje3/console@…` into the
# server's copy and put the tracked file back afterwards, so git looked right while the cluster
# ran an address only this laptop could resolve.
roll_console() {
  local manifest="$ROOT/deploy/edge/console.yaml" ref digest
  [ -f "$manifest" ] || { red "console: no deploy/edge/console.yaml"; return 1; }
  ref="$(awk '/image: /{print $2; exit}' "$manifest")"
  digest="${ref##*@}"
  case "$ref" in
    ghcr.io/*) ;;
    *) red "console: the manifest names $ref — the server pulls from ghcr and nowhere else"
       return 1 ;;
  esac

  say "console · 3/4 sync + apply"
  if ! tar czf - -C "$ROOT" deploy/edge/console.yaml 2>/dev/null \
       | "${SSH[@]}" "mkdir -p ~/raje3 && cd ~/raje3 && tar xzf - 2>/dev/null \
         && grep -q '$digest' deploy/edge/console.yaml"; then
    red "console: the manifest on the server does not carry the published digest"; return 1
  fi
  "${SSH[@]}" "cd ~/raje3 && sudo -n kubectl apply -n $NS -f deploy/edge/console.yaml >/dev/null \
     && sudo -n kubectl rollout status -n $NS deploy/console --timeout=180s 2>&1 | tail -1"

  say "console · 4/4 verify"
  local running=""
  for _ in $(seq 1 40); do
    running="$("${SSH[@]}" "sudo -n kubectl get pods -n $NS -l app=console \
      -o jsonpath='{.items[*].status.containerStatuses[*].imageID}'" 2>/dev/null)"
    case "$running" in *"$digest"*) break ;; esac
    sleep 5
  done
  case "$running" in
    *"$digest"*) grn "console is RUNNING ${digest:0:26}…"; return 0 ;;
    *) red "console: the running imageID is not the digest that was published"
       red "   running: ${running:-<none>}"
       return 1 ;;
  esac
}

# ── TESTS ─────────────────────────────────────────────────────────────────────────────────────
test_one() {
  case "$1" in
    console) (cd "$ROOT/apps/console" && npx vitest run 2>&1 | tail -2) ;;
    # `uv run`, NOT a bare `python3` — bare `python3` resolves through WHATEVER PATH the calling
    # process happens to have, and that is no longer a safe assumption: ops-mcp's own `uv`-managed
    # venv (created once it switched from an installed exe to `uv run python -m ops_mcp`, after
    # Windows Smart App Control started blocking the exe) can prepend its own `python.exe` onto the
    # PATH this script's child processes inherit — an interpreter with none of a SERVICE's own
    # dependencies installed, so every test import fails. `uv run` here always resolves against
    # THIS service's own pyproject.toml/lock, regardless of what shaped the caller's PATH.
    *)       (cd "$ROOT/services/$1" && uv run --extra dev python -m pytest tests/unit -q 2>&1 | tail -2) ;;
  esac
}

# ── THE WHOLE RUN ─────────────────────────────────────────────────────────────────────────────
ship_many() {
  local svcs=("$@") ours=() rc=0 svc

  # BACKUP-SERVICE GOES LAST, ALWAYS, WHEN IT'S IN THE LIST. It needs real OSS credentials this
  # box does not have yet (AWS today, Alibaba once we're actually on it) — `verify_running`'s own
  # readiness poll has no way to know that and spends its full 10-minute timeout finding out,
  # every single ship, with every OTHER named service queued up behind it in this same sequential
  # loop. Reordering (not skipping — a real credential landing here should still be verified)
  # means that ten minutes costs itself, not everything after it.
  local reordered=() svc2
  for svc2 in "${svcs[@]}"; do
    [ "$svc2" = "backup-service" ] || reordered+=("$svc2")
  done
  for svc2 in "${svcs[@]}"; do
    [ "$svc2" = "backup-service" ] && reordered+=("$svc2")
  done
  svcs=("${reordered[@]}")

  for svc in "${svcs[@]}"; do
    case "$(kind_of "$svc")" in
      unknown) red "$svc: not ours, not the platform's, and not the console"; return 1 ;;
      ours|console) ours+=("$svc") ;;
    esac
  done

  # ── 0. deploy wiring, once for the whole repo ───────────────────────────────────────────────
  # FOUND LIVE, THE DAY THIS WAS ADDED: a new route (GET .../platform/tenants/{id}/capacity) was
  # declared tier=user in its own manifest.py, but api-gateway.values.yaml carried no matching
  # GATEWAY_ROUTES prefix — ci/check_deploy_wiring.py's own tier=user/GATEWAY_ROUTES cross-check
  # would have caught this EXACTLY, and does when run — but nothing ever ran it before a ship. It
  # shipped, "1/1 Running", every unit test green, and 404'd at the gateway anyway. A green pod is
  # not a reachable route; this gate is the one thing that actually checks the second half.
  say "deploy wiring"
  python3 "$ROOT/ci/check_deploy_wiring.py" || {
    red "deploy wiring: problems found above — nothing built, nothing shipped"; return 1; }

  # EVERY SCREEN WITH VISIBLE ARABIC TEXT MUST ROUTE IT THROUGH operator-i18n, IN EVERY DECLARED
  # LOCALE — the owner's own explicit call (2026-09-11), made after the real consequence was
  # stated out loud: at the moment this gate went build-blocking, 87 of 95 screens were not yet
  # migrated, so THIS BLOCKS EVERY SHIP until they are. Confirmed knowingly over a staged
  # alternative that was offered at the time.
  say "operator-i18n coverage"
  python3 "$ROOT/ci/check_operator_i18n_coverage.py" || {
    red "operator-i18n coverage: problems found above — nothing built, nothing shipped"; return 1; }

  # ── 1. tests ────────────────────────────────────────────────────────────────────────────────
  for svc in "${ours[@]}"; do
    say "$svc · 1/4 tests"
    test_one "$svc" || { red "$svc: tests failed — nothing built, nothing shipped"; return 1; }
  done

  # ── 2. publish, all of them at once ─────────────────────────────────────────────────────────
  # ONE PLACE BUILDS AND PUSHES, and it is the same one a release uses. This script used to carry
  # its own build-and-transfer, so there were two answers to "how does an image get made" — and
  # the two drifted, which is how the console ended up addressed under a laptop's registry.
  if [ ${#ours[@]} -gt 0 ]; then
    say "publish → ghcr: ${ours[*]}"
    : "${GHCR_TOKEN:?GHCR_TOKEN is required (write:packages) — the server pulls from ghcr, so a \
ship publishes there first}"
    bash "$HERE/publish-images.sh" "${ours[@]}" || {
      red "publish failed — nothing was rolled"; return 1; }
  fi

  # ── 3+4. roll and verify, one service at a time ─────────────────────────────────────────────
  # SEQUENTIAL ON PURPOSE. Rolling four services at once makes a failure a puzzle: helm, the
  # kubelet and the pod logs all interleave, and the one line that matters is the one you cannot
  # find.
  for svc in "${svcs[@]}"; do
    case "$(kind_of "$svc")" in
      console)  roll_console || { rc=1; FAILED+=("$svc"); } ;;
      platform) ship_platform_one "$svc" || { rc=1; FAILED+=("$svc"); } ;;
      ours)
        local digest
        digest="$(pinned_digest "$svc")"
        if [ -z "$digest" ]; then
          red "$svc: publish reported success but wrote no digest — refusing to roll a guess"
          rc=1; FAILED+=("$svc"); continue
        fi
        say "$svc · 3/4 sync + roll"
        sync_and_roll "$svc" "$digest" || { rc=1; FAILED+=("$svc"); continue; }
        say "$svc · 4/4 verify"
        verify_running "$svc" "$digest" || { rc=1; FAILED+=("$svc"); }
        ;;
    esac
  done
  return "$rc"
}

if [ "$#" -eq 0 ]; then
  red "usage: GHCR_TOKEN=… ./deploy/ship.sh <service> [service…]"
  exit 1
fi

# WHAT FAILED, AND NOTHING ELSE. This used to close with «did not ship: $*» — every service the
# operator named. One shipment verified six services green and one red, and the last line called
# all seven failures. The last line is the one line everybody reads.
FAILED=()

if ship_many "$@"; then
  echo
  grn "shipped: $* — every one running the digest its declaration names"
  exit 0
fi
echo
if [ ${#FAILED[@]} -gt 0 ]; then
  red "did not ship: ${FAILED[*]}"
  shipped=()
  for svc in "$@"; do
    case " ${FAILED[*]} " in *" $svc "*) ;; *) shipped+=("$svc") ;; esac
  done
  [ ${#shipped[@]} -gt 0 ] && grn "shipped: ${shipped[*]}"
else
  # A FAILURE NOBODY ATTRIBUTED — publish died before any service was rolled, most likely. Naming
  # the whole list is correct here and only here, because none of them got as far as a rollout.
  red "did not ship: $* (failed before any rollout)"
fi
exit 1
