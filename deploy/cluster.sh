#!/usr/bin/env bash
# WHERE IS THE CLUSTER? ONE ANSWER, IN ONE FILE, FOR EVERY SCRIPT UNDER deploy/.
#
# WHAT HAPPENED, AND IT WAS INVISIBLE UNTIL SOMEBODY RAN THEM ALL. Thirty-two scripts here carried
# the same line, copied forward each time a new one was written:
#
#     export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
#
# That is the path k3s writes ON THE NODE. It is right in exactly one place — the node — and the
# scripts that carry it are run from an operator's laptop, where the file does not exist. kubectl
# with a KUBECONFIG pointing at nothing does not complain about the path; it falls back to
# localhost:8080 and reports «connection refused».
#
# So the eighteen proofs did not fail with «I have no cluster». They failed eighteen times with a
# refused connection to a port nobody serves, which reads like a fleet on fire. Run right after a
# ship — which is when they ARE run — they say exactly that about a perfectly healthy fleet. That
# is the worst answer a proof can give: it makes the operator distrust the thing being proved
# instead of the proof.
#
# Meanwhile `verify-fleet.sh` read `deploy/target.env` and `ship.sh` read it and then defaulted to
# `<ssh-user>@127.0.0.1:2224`, an address whose ssh tunnel was retired months ago. Three answers to one
# question, and moving the cluster updated one of them, because nothing tied the other two to it.
#
#   . "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
#
# THE LADDER, AND IT IS ORDERED SO THAT THE MORE SPECIFIC ANSWER WINS.
#
#   1. A KUBECONFIG the operator exported himself. He said it out loud; we do not argue.
#   2. A local kubectl that answers — a laptop k3s, CI's kind.
#   3. The node's own kubeconfig, if that file is really here. This is the line that used to live
#      in thirty-two scripts, and it belongs in one: it is the right answer ON the node, where
#      `install.sh` and the boot unit run, and it is silent nonsense anywhere else. Existence of
#      the file — not reachability of the API — decides, because a script running at boot has its
#      own wait loop and «the cluster is not up YET» is not «I do not know where the cluster is».
#   4. REMOTE from `target.env`: `kubectl` becomes a function that runs the real one on the node
#      over ssh. Nothing else in a caller changes — the pipes, the heredocs, `exec -i` — because
#      ssh forwards stdin and exit status faithfully.
#   5. Nothing. Said out loud, and the script stops. A missing target is a setup fault with
#      exactly one sentence, and it is said here, once, so no caller has to remember to say it and
#      none of them can disagree about what «reachable» means.
#
# There is no sixth rung and in particular no hardcoded host: a default target is how a script
# reaches confidently for a machine nobody has run in months.
# `ci/check_every_deploy_script_finds_the_cluster.py` refuses to let either shape back in.
set -uo pipefail

_CLUSTER_HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# REMOTE ALREADY EXPORTED WINS, SAME "HE SAID IT OUT LOUD" RULE RUNG 1 ABOVE GIVES KUBECONFIG —
# ops-mcp's own deploy_ops.py derives REMOTE/PORT from its config.toml and exports them before
# running this script, so a caller sourcing target.env on top would silently overwrite the one
# real address with a second, hand-maintained copy of it (found live, 2026-10-05: a server moved,
# ops-mcp's config followed, this file still read the old one for a solid hour). target.env stays
# the right answer for an operator running ship.sh by hand, outside ops-mcp entirely.
# shellcheck disable=SC1091
[ -z "${REMOTE:-}" ] && [ -f "$_CLUSTER_HERE/target.env" ] && . "$_CLUSTER_HERE/target.env"

_NODE_KUBECONFIG="/etc/rancher/k3s/k3s.yaml"

if [ -n "${KUBECONFIG:-}" ]; then
  CLUSTER_VIA="kubeconfig"
elif command -v kubectl >/dev/null 2>&1 && kubectl cluster-info >/dev/null 2>&1; then
  CLUSTER_VIA="local"
  # A WORKING `kubectl` IS NOT EVIDENCE THAT `helm` WORKS, and this line is what that cost.
  #
  # On a k3s node the shipped `kubectl` finds the cluster with no KUBECONFIG at all — the wrapper
  # carries the path itself — so this branch matched and the variable stayed unset. `helm` has no
  # such wrapper: it fell back to localhost:8080, failed with «Kubernetes cluster unreachable»,
  # and every `helm upgrade` in update.sh failed for a reason that had nothing to do with the
  # release. The rollout fallback beneath it then read `kubectl rollout status` — which passes
  # trivially for a deployment nobody changed — and reported ok. Six services were «rolled» and
  # the release revision on the node had not moved since the previous day.
  #
  # So the seam serves every tool, not only the one it happened to test with.
  # An `if`, not `[ … ] && …`: this file is sourced by scripts running under `set -e`, where a
  # trailing test that is simply FALSE ends the caller. The guard must not be able to kill a run
  # whose only news is «there is no node kubeconfig here», which is the normal case off the node.
  if [ -r "$_NODE_KUBECONFIG" ]; then export KUBECONFIG="$_NODE_KUBECONFIG"; fi
elif [ -r "$_NODE_KUBECONFIG" ]; then
  CLUSTER_VIA="node"
  export KUBECONFIG="$_NODE_KUBECONFIG"
elif [ -n "${REMOTE:-}" ]; then
  CLUSTER_VIA="ssh"
  # QUOTED ONE ARGUMENT AT A TIME. `kubectl -n ns exec pod -- python -c 'x = 1'` has to survive a
  # trip through a remote shell with its quoting intact; joining the arguments with spaces would
  # let the far side re-split them, and a jsonpath or a python snippet is nothing but characters a
  # shell would love to interpret.
  kubectl() {
    # SUDO, AND KUBECONFIG NAMED EXPLICITLY — the node's kubeconfig
    # (/etc/rancher/k3s/k3s.yaml) is root:root 600 by k3s's own default install, unreadable to
    # the ordinary login this ssh connects as. Without both, kubectl finds nothing, falls back
    # to localhost:8080, and every caller of this wrapper — rollout waits included — reads
    # "connection refused" as if the cluster were down. `ship.sh`'s own 4/4 verify step waited
    # out a full ten-minute rollout timeout per service against exactly this, eight times in a
    # row, before the real cause (this line, not the fleet) was found.
    # `-i "$KEY"`, SAME FIX AS ship.sh's OWN `SSH=(...)` ARRAY (its own comment above) — FOUND
    # MISSING HERE TOO, LIVE (2026-09-28): this bare `ssh` call has no identity flag at all, so it
    # depends entirely on an ssh-agent/`~/.ssh/config` identity being loaded — which an automated
    # caller (ops-mcp's own `deploy_ship`, which sets `KEY`) never has. Every earlier ship still
    # LOOKED like it worked because the FIRST ssh connection this run made (via ship.sh's own
    # correctly-keyed SSH=(...) array, opened before this wrapper's own first call) multiplexes
    # over the same ControlMaster socket when both calls share ssh_config's ControlPath — so this
    # wrapper's key-less call silently rode along on someone else's already-authenticated
    # connection. `verify_running`'s own 15-second-interval, up-to-10-minute poll loop outlives
    # that socket's idle timeout: the moment it lapses, every following bare call here opens a
    # FRESH connection with no key and fails, which is exactly why every "no ready pod after 10
    # minutes" this session traced back to "Permission denied (publickey)" rather than a real
    # unhealthy pod — the pod was fine; this ssh call could no longer prove it.
    local cmd="sudo KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl" a
    for a in "$@"; do cmd+=" $(printf '%q' "$a")"; done
    ssh ${KEY:+-i "$KEY"} -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=15 \
        -p "${PORT:-22}" "$REMOTE" "$cmd"
  }
  export -f kubectl 2>/dev/null || true
else
  printf '\033[31m✗ no cluster: nothing local answers, and deploy/target.env names no host.\033[0m\n' >&2
  printf '\033[2m  Set REMOTE (and PORT) in deploy/target.env — see target.env.example.\033[0m\n' >&2
  exit 2
fi
export CLUSTER_VIA

# WHO ASKS POSTGRES? ONE ANSWER, HERE, FOR THE SAME REASON THE CLUSTER HAS ONE.
#
# Three scripts spelled the role out and all three were wrong, in two different ways. pre-deploy
# said `-U platform` and provisioned nothing while announcing «databases present». check-posture
# said `-U platform` and has reported «postgres does not serve TLS» on every run since it was
# written, including on clusters that serve it. uninstall said `-U postgres` and so the count of
# shops it was about to destroy — the one number in that prompt meant to stop a person — has never
# printed. None of them errored: a psql that cannot connect writes to stderr and returns nothing,
# and nothing reads as «no TLS», «no shops», «no databases».
#
# The role is minted by gen-secrets and written into every DATASTORE_DSN. It is a fact about the
# cluster, so it is read from the cluster, once.
pg_role() {
  if [ -z "${_PG_ROLE:-}" ]; then
    _PG_ROLE="$(kubectl -n "${NS:-base-services}" get secret tenant-service-secrets \
                -o jsonpath='{.data.DATASTORE_DSN}' 2>/dev/null \
                | base64 -d 2>/dev/null | cut -d/ -f3 | cut -d: -f1)"
    # A READER THAT CANNOT READ SAYS SO. Returning an empty role would put every caller back in the
    # silence this function exists to end.
    [ -n "$_PG_ROLE" ] || {
      printf '\033[31m  ✗ cannot read the postgres role from tenant-service-secrets.\033[0m\n' >&2
      printf '\033[2m    Has gen-secrets run? Without it no database question can be asked.\033[0m\n' >&2
      return 1
    }
  fi
  printf '%s' "$_PG_ROLE"
}
