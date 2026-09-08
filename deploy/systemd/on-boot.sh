#!/usr/bin/env bash
# ==================================================================================================
#  on-boot.sh — the three things a reboot does not do by itself.
# --------------------------------------------------------------------------------------------------
#  k3s comes back enabled, and every pod restarts. That is not the product being up.
#
#  WHAT WE ACTUALLY SAW: the node returned, `systemctl status k3s` said active, every deployment
#  said Running — and twenty-two services sat at 0/1 for half an hour behind a postgres that was
#  being killed mid-recovery by a probe that allowed sixty seconds for a job that needed minutes.
#  A boot that "succeeded" and a product that was down, with nothing anywhere saying so.
#
#  So: apply what lives outside base-services' manifests, then WAIT for ready and fail loudly if it
#  never comes. Everything here is idempotent — this runs on every boot, not on the first one.
# ==================================================================================================
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"
NS="${NS:-base-services}"
ROOT="${ROOT:-/home/deploy/raje3}"
export PATH="$PATH:/usr/local/bin:/usr/bin"

say(){ echo "raje3-up: $*"; }

# ── 1. the API server has to answer before anything else is meaningful ────────────────────────
for _ in $(seq 1 60); do
  kubectl get --raw='/readyz' >/dev/null 2>&1 && break
  sleep 5
done
kubectl get --raw='/readyz' >/dev/null 2>&1 || { say "k3s API never became ready"; exit 1; }
say "k3s is answering"

# ── 2. the probe patch, because a rebuilt statefulset carries upstream's manifest again ───────
# It is applied at install too; applying it here as well is what makes it survive a `kubectl apply`
# of base-services' datastores.yaml by anybody, at any time, including their own bring-up.
bash "$ROOT/deploy/patch-datastore-probes.sh" || say "probe patch failed (continuing)"

# ── 3. wait for the fleet, and say which service is holding it up ─────────────────────────────
#
# NAMED, NOT COUNTED. «19/22 ready» after ten minutes tells nobody what to look at; the three names
# do — and on the morning this was written, the one name would have been postgres.
deadline=$(( $(date +%s) + 600 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  notready="$(kubectl -n "$NS" get pods --no-headers 2>/dev/null \
    | awk '$3=="Running" && $2 !~ /^([0-9]+)\/\1$/ {print $1}')"
  [ -z "$notready" ] && { say "every pod is ready"; exit 0; }
  sleep 15
done

say "still not ready after ten minutes:"
printf '  %s\n' $notready
# A FAILED UNIT IS THE POINT. It puts the reason in `systemctl status raje3-up` where the next
# person to log in will meet it, instead of leaving a half-running product looking healthy.
exit 1
