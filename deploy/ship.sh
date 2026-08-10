#!/usr/bin/env bash
# Build, ship, pin, deploy and VERIFY one service — in one command.
#
#   ./deploy/ship.sh portal
#   ./deploy/ship.sh reminders operations       # several, in order
#
# WHY THIS EXISTS. The same six steps were run by hand for every service, and each one failed in a
# different way at least once:
#
#   the image was built before the code was added        -> a route 404ing on a running pod
#   the import was piped to /dev/null                    -> "imported" printed, nothing imported
#   containerd stored it by TAG, not by digest           -> ImagePullBackOff on a pinned deploy
#   the values file synced after the rollout, not before -> "rolled" against a two-version-old pin
#   rollout restart was used to pick up a new image      -> restarted the OLD image, cleanly
#   the pod was on the old digest and nobody looked      -> a proof that returned yesterday's numbers
#
# None of those is interesting. All of them cost an hour. This script does the steps in the only
# order that works and refuses to continue when one of them did not happen.
#
# NO `set -e`. Each phase reports and the script decides — `set -e` turns a diagnosable failure
# into a silent exit, which is the shape half the list above already has.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
REMOTE="${REMOTE:-tamam@127.0.0.1}"
PORT="${PORT:-2224}"
NS="${NS:-base-services}"
SSH=(ssh -o BatchMode=yes -p "$PORT" "$REMOTE")

red(){ printf '\e[31m✗ %s\e[0m\n' "$*" >&2; }
yel(){ printf '\e[33m⚠ %s\e[0m\n' "$*"; }
grn(){ printf '\e[32m✔ %s\e[0m\n' "$*"; }
say(){ printf '\n\e[1m▸ %s\e[0m\n' "$*"; }

ship_one() {
  local svc="$1"
  local dir="$ROOT/services/$svc"
  local values="$ROOT/deploy/services/$svc.values.yaml"
  [ -d "$dir" ]    || { red "$svc: no services/$svc"; return 1; }
  [ -f "$values" ] || { red "$svc: no deploy/services/$svc.values.yaml"; return 1; }

  # ── 1. tests, before anything is built ───────────────────────────────────────────────────────
  # Cheapest gate first. Building an image from code that does not pass its own tests wastes four
  # minutes to discover something that took four seconds.
  say "$svc · 1/6 tests"
  if ! (cd "$dir" && python3 -m pytest tests/unit -q 2>&1 | tail -2); then
    red "$svc: unit tests failed — nothing built, nothing shipped"; return 1
  fi

  # ── 2. build ─────────────────────────────────────────────────────────────────────────────────
  say "$svc · 2/6 build"
  local digest
  digest="$(cd "$dir" && docker build -q -t "raje3/$svc:ship" . 2>&1 | tail -1)"
  case "$digest" in
    sha256:*) grn "built ${digest:0:26}…" ;;
    *) red "$svc: build failed: $digest"; return 1 ;;
  esac

  # ── 3. pin, and run OUR guards against the pin ───────────────────────────────────────────────
  # Before the image travels: a values file that fails a guard is a rollout that should not happen,
  # and finding that out after a 90-second transfer is 90 seconds wasted every time.
  say "$svc · 3/6 pin + guards"
  local old
  old="$(grep -m1 'digest:' "$values" | sed -E 's/.*"([^"]*)".*/\1/')"
  if [ "$old" = "$digest" ]; then
    yel "already pinned to this digest — the code did not change since the last ship"
  fi
  sed -i "s|$old|$digest|" "$values"
  python3 "$ROOT/ci/check_deploy_wiring.py" >/dev/null 2>&1 || {
    red "$svc: deploy-wiring guard failed"
    python3 "$ROOT/ci/check_deploy_wiring.py" 2>&1 | tail -8
    sed -i "s|$digest|$old|" "$values"   # leave the tree as we found it
    return 1
  }
  grn "pinned and guards green"

  # ── 4. ship the image, and PROVE it arrived under its digest ─────────────────────────────────
  # The tag→digest step is what makes a digest-pinned deploy resolvable at all: `ctr images import`
  # stores by TAG, so kubelet tries the registry and fails with "pull access denied".
  say "$svc · 4/6 ship image"
  if ! docker save "raje3/$svc:ship" | "${SSH[@]}" \
        "cat > /tmp/$svc.tar && sudo -n k3s ctr images import /tmp/$svc.tar >/dev/null 2>&1 \
         && sudo -n k3s ctr images tag docker.io/raje3/$svc:ship docker.io/raje3/$svc@$digest \
            >/dev/null 2>&1; sudo -n k3s ctr images ls -q | grep -qx docker.io/raje3/$svc@$digest"; then
    red "$svc: the image is NOT in containerd under $digest — the pod would ImagePullBackOff"
    return 1
  fi
  grn "image present under its digest"

  # ── 5. sync the declaration BEFORE rolling ───────────────────────────────────────────────────
  # In that order, always. A rollout reads the values file on the SERVER; syncing afterwards means
  # helm renders the previous pin and reports success about it.
  say "$svc · 5/6 sync + roll"
  if ! tar czf - -C "$ROOT" "deploy/services/$svc.values.yaml" deploy/hooks deploy/server 2>/dev/null \
       | "${SSH[@]}" "cd ~/raje3 && tar xzf - 2>/dev/null && chmod +x deploy/hooks/*.sh \
         && grep -q '$digest' deploy/services/$svc.values.yaml"; then
    red "$svc: the values file on the server does not carry the new digest"; return 1
  fi
  # OURS, NOT THEIRS. deploy/server/update.sh is our copy of the platform's rollout, and the one
  # thing it adds is fetching the images in parallel before the sequential loop needs them — a single
  # image took 3m50s on this link, and nineteen in single file took over an hour. The rollout logic
  # underneath is unchanged, so a diff against theirs stays short.
  "${SSH[@]}" "cd ~/raje3 && sudo -n PRODUCT_NAME=raje3 CHART=platform/deploy/chart \
     VALUES_DIR=deploy/services bash deploy/server/update.sh --only $svc 2>&1 | tail -2"

  # ── 6. verify the ARTIFACT, not the report ───────────────────────────────────────────────────
  say "$svc · 6/6 verify"
  local running=""
  for _ in $(seq 1 40); do
    running="$("${SSH[@]}" "kubectl -n $NS get pods --no-headers 2>/dev/null \
      | awk '/^$svc-[0-9a-f]/ && \$3==\"Running\" && \$2==\"1/1\" {print \$1; exit}'")"
    [ -n "$running" ] && break
    sleep 15
  done
  if [ -z "$running" ]; then
    red "$svc: no ready pod after 10 minutes"
    "${SSH[@]}" "kubectl -n $NS get pods --no-headers | grep '^$svc-'; \
      kubectl -n $NS logs \$(kubectl -n $NS get pods --no-headers | awk '/^$svc-/{print \$1;exit}') \
      --tail=20 2>&1 | tail -12"
    return 1
  fi
  local live
  live="$("${SSH[@]}" "kubectl -n $NS get pod $running \
      -o jsonpath='{.status.containerStatuses[0].imageID}'" | sed 's/.*@//')"
  if [ "$live" != "$digest" ]; then
    red "$svc: RUNNING ${live:0:26}… but shipped ${digest:0:26}…"
    return 1
  fi
  grn "$svc is running the image this command built"
  return 0
}

failed=0
for svc in "$@"; do
  ship_one "$svc" || { failed=$((failed + 1)); red "$svc: STOPPED"; }
done

echo
if [ "$failed" -eq 0 ]; then
  grn "shipped: $* — every one running the image this command built"
else
  red "$failed of $# did not ship"
fi
exit "$failed"
