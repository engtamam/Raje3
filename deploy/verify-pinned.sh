#!/usr/bin/env bash
# Is every service actually RUNNING the digest its values file names?
#
# update.sh reports what helm told it. This reads what the cluster is running, which is the only
# claim worth making after a rollout — a release can be "deployed" while the pods that matter were
# never replaced, and a rollout can be reported failed while the digest landed correctly.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
NS="${NS:-base-services}"
# Derived from where this script LIVES, not from $HOME — it is run under sudo, and sudo's $HOME is
# /root, so a home-relative default silently resolves to a directory that does not exist and the
# loop then reports every service as "never deployed".
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${ROOT:-$(cd "$HERE/.." && pwd)}"
VALUES_DIR="${VALUES_DIR:-$ROOT/deploy/services}"
[ -d "$VALUES_DIR" ] || { echo "  ✗ no values directory at $VALUES_DIR" >&2; exit 2; }
# THIS SCRIPT IS NODE-ONLY, AND OFF THE NODE IT USED TO ACCUSE THE WHOLE FLEET. The KUBECONFIG above
# exists only on the k3s node; run anywhere else, every kubectl fails, every `got` comes back empty,
# and the loop below prints "NOT DEPLOYED" 24 times at a cluster that is serving perfectly. An
# unreachable API server is not evidence about deployments. Prove the connection, or say nothing.
if ! kubectl -n "$NS" get ns "$NS" >/dev/null 2>&1; then
  echo "  ✗ cannot reach the cluster (namespace $NS, KUBECONFIG=$KUBECONFIG)" >&2
  echo "    this script reads the live cluster and must run ON the node." >&2
  echo "    from a workstation use: bash deploy/verify-fleet.sh   (it goes over ssh)" >&2
  exit 2
fi
ok=0; bad=0; missing=0
for f in "$VALUES_DIR"/*.values.yaml; do
  svc=$(basename "$f" .values.yaml)
  want=$(grep -m1 'digest:' "$f" | sed -E 's/.*"([^"]*)".*/\1/')
  got=$(kubectl -n "$NS" get deploy "$svc" -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null | sed 's/.*@//')
  ready=$(kubectl -n "$NS" get deploy "$svc" -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
  if   [ -z "$got"    ]; then printf '  \e[31m✗ %-22s NOT DEPLOYED\e[0m\n' "$svc"; missing=$((missing+1))
  elif [ "$want" != "$got" ]; then printf '  \e[31m✗ %-22s running %s, values say %s\e[0m\n' "$svc" "${got:0:19}…" "${want:0:19}…"; bad=$((bad+1))
  elif [ "${ready:-0}" -lt 1 ]; then printf '  \e[33m⚠ %-22s right digest, 0 ready\e[0m\n' "$svc"; bad=$((bad+1))
  else printf '  \e[32m✔ %-22s\e[0m\n' "$svc"; ok=$((ok+1)); fi
done
echo
echo "  on their pinned digest and ready: $ok · wrong or unready: $bad · never deployed: $missing"
[ $((bad+missing)) -eq 0 ]
