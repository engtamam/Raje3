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
# `tamam@127.0.0.1:2224`, an address whose ssh tunnel was retired months ago. Three answers to one
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
# shellcheck disable=SC1091
[ -f "$_CLUSTER_HERE/target.env" ] && . "$_CLUSTER_HERE/target.env"

_NODE_KUBECONFIG="/etc/rancher/k3s/k3s.yaml"

if [ -n "${KUBECONFIG:-}" ]; then
  CLUSTER_VIA="kubeconfig"
elif command -v kubectl >/dev/null 2>&1 && kubectl cluster-info >/dev/null 2>&1; then
  CLUSTER_VIA="local"
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
    local cmd="kubectl" a
    for a in "$@"; do cmd+=" $(printf '%q' "$a")"; done
    ssh -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=15 \
        -p "${PORT:-22}" "$REMOTE" "$cmd"
  }
  export -f kubectl 2>/dev/null || true
else
  printf '\033[31m✗ no cluster: nothing local answers, and deploy/target.env names no host.\033[0m\n' >&2
  printf '\033[2m  Set REMOTE (and PORT) in deploy/target.env — see target.env.example.\033[0m\n' >&2
  exit 2
fi
export CLUSTER_VIA
