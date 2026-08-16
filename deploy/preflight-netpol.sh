#!/usr/bin/env bash
# ==================================================================================================
#  preflight-netpol.sh — prove NetworkPolicy is enforced, WITHOUT depending on `kubectl attach`.
# --------------------------------------------------------------------------------------------------
#  WHY OURS EXISTS BESIDE UPSTREAM'S. base-services' preflight proves the same property and reads
#  its answer over an interactive attach (`kubectl run --rm -i`). On this host that attach fails —
#
#     couldn't attach to pod/client: failed to load task: context deadline exceeded
#
#  — under load, and the probe then reports "the cluster's networking is broken" and refuses the
#  install. IT IS NOT BROKEN: the same client, run by hand, prints REACHABLE. The transport used to
#  READ the result failed, and the message blamed the thing being measured.
#
#  A FALSE NEGATIVE ON A SECURITY GATE IS EXPENSIVE IN BOTH DIRECTIONS. Believed, it blocks an
#  install for a fault that does not exist; disbelieved once, it teaches everybody to pass
#  `--skip-preflight` for ever, and the day enforcement really is off nobody finds out.
#
#  SO THIS READS THE ANSWER FROM LOGS, which do not need a session: the client pod writes one word
#  and exits, and we read it after it has terminated. Same property, same two probes — baseline
#  reachable, then blocked under a default-deny — and no interactive channel anywhere.
#
#  ESCALATED upstream: a probe whose transport can fail independently of what it measures should
#  not be the one that gates an install.
#
#  Usage:  sudo bash deploy/preflight-netpol.sh
# ==================================================================================================
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
NS="${PREFLIGHT_NS:-raje3-preflight}"
IMAGE="${PREFLIGHT_IMAGE:-busybox:1.36}"

C_G=$'\e[32m'; C_R=$'\e[31m'; C_C=$'\e[36m'; C_D=$'\e[2m'; C_N=$'\e[0m'
info(){ echo -e "${C_C}  ▸ $*${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }
die(){  echo -e "${C_R}  ✖ $*${C_N}" >&2; cleanup; exit 1; }

cleanup(){ kubectl delete namespace "$NS" --wait=false >/dev/null 2>&1 || true; }
trap cleanup EXIT

# A namespace still Terminating from a previous run makes `create` fail with AlreadyExists, and the
# re-run then fails for a different reason than the first — which is how a flaky check becomes an
# unreadable one.
while kubectl get namespace "$NS" >/dev/null 2>&1; do sleep 3; done
kubectl create namespace "$NS" >/dev/null

kubectl -n "$NS" run server --image="$IMAGE" --labels=app=server --port=8080 \
  --command -- sh -c 'while true; do echo ok | nc -l -p 8080; done' >/dev/null
kubectl -n "$NS" expose pod server --port=8080 --target-port=8080 >/dev/null
kubectl -n "$NS" wait --for=condition=Ready pod/server --timeout=120s >/dev/null \
  || die "the server pod never became ready — this host cannot run the check"

# ONE WORD, WRITTEN TO STDOUT AND READ FROM THE LOG. `--restart=Never` plus a wait for termination
# means the result is a fact on disk by the time we read it, not a stream we had to stay attached to.
probe() {
  local name="probe-$RANDOM"
  kubectl -n "$NS" run "$name" --image="$IMAGE" --restart=Never --command -- \
    sh -c 'nc -w 3 -z server 8080 && echo REACHABLE || echo BLOCKED' >/dev/null 2>&1
  kubectl -n "$NS" wait --for=jsonpath='{.status.phase}'=Succeeded "pod/$name" --timeout=90s \
    >/dev/null 2>&1
  local out; out="$(kubectl -n "$NS" logs "$name" 2>/dev/null | tr -d '\r\n')"
  kubectl -n "$NS" delete pod "$name" --wait=false >/dev/null 2>&1 || true
  echo "$out"
}

info "baseline: can a pod reach a service with no policy in the way?"
answer=""
for _ in $(seq 1 8); do
  answer="$(probe)"
  [ "$answer" = "REACHABLE" ] && break
  sleep 5
done
[ "$answer" = "REACHABLE" ] || die "baseline connectivity failed — pod networking is genuinely broken"
ok "baseline reachable"

info "applying default-deny and re-testing"
kubectl -n "$NS" apply -f - >/dev/null <<'YAML'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: preflight-default-deny
spec:
  podSelector:
    matchLabels:
      app: server
  policyTypes: [Ingress]
  ingress: []
YAML
sleep 5   # the CNI programmes the dataplane asynchronously

# AND HERE THE RETRY LOGIC INVERTS. Above, a slow dataplane looks like a failure; here it looks like
# a PASS, so a single early probe could report "blocked" before the policy was ever programmed. We
# take the last of several: if it is still reachable after four attempts, enforcement is off.
answer=""
for _ in $(seq 1 4); do
  answer="$(probe)"
  [ "$answer" = "BLOCKED" ] && break
  sleep 5
done
[ "$answer" = "BLOCKED" ] \
  || die "NETWORK POLICY IS NOT ENFORCED — a default-deny is applied and the client still connects.
       Every network policy in this product is decoration until the CNI enforces them."
ok "default-deny is enforced"

echo -e "${C_D}  (read from pod logs, not an attached session — see the header)${C_N}"
