#!/usr/bin/env bash
# ==================================================================================================
#  راجِع (Raje3) — setup.sh · THE ONE COMMAND
#  Stand up (or re-stand-up) the WHOLE platform on a server, in order, from a single entrypoint.
#  No hand-run steps, no remembering the order.
#
#      sudo bash deploy/server/setup.sh
#
#  Phases (each idempotent; an already-done phase is a fast no-op):
#    1. provision-server.sh          the host: packages, hardening, firewall, k3s   (ours)
#    2. platform/…/bootstrap.sh      Calico + metrics-server + postgres/redis/minio (base-services)
#    3. platform/…/preflight.sh      PROVE default-deny is enforced — FATAL if not  (base-services)
#    4. pull-secret                  registry credential for our private images     (ours, pending)
#    5. helm upgrade --install       every deploy/services/*.values.yaml            (ours)
#    6. boot-heal --install          survive an ungraceful reboot                   (ours, pending)
#
#  Structure adapted from imtithal's setup.sh. Two deliberate differences:
#    * Phase 3 is FATAL here. imtithal warns and continues on a soft failure; a cluster that
#      cannot enforce NetworkPolicy is not a slow start, it is a tenant-isolation hole, and
#      tenant isolation is the one guarantee Raje3 cannot ship without.
#    * Phases 2, 3 and the chart come from platform/ (base-services) and are invoked, never
#      copied and never edited. We own only the values files we feed the chart.
#
#  Env: NAMESPACE (default base-services) · DOMAIN (edge + TLS; skipped when unset) ·
#       SKIP_PROVISION=1 (host already prepared) · DRY_RUN=1 (print the plan, change nothing)
# ==================================================================================================
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PLATFORM="$ROOT/platform/deploy"
OUR_VALUES="$ROOT/deploy/services"
NAMESPACE="${NAMESPACE:-base-services}"
DRY_RUN="${DRY_RUN:-0}"

C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_R=$'\e[31m'; C_D=$'\e[2m'; C_B=$'\e[1m'; C_N=$'\e[0m'
phase(){ echo -e "\n${C_B}${C_C}══════ $* ══════${C_N}"; }
ok(){    echo -e "${C_G}✔ $*${C_N}"; }
warn(){  echo -e "${C_Y}⚠ $*${C_N}"; }
pend(){  echo -e "${C_Y}▸ PENDING — $*${C_N}"; }
die(){   echo -e "${C_R}✖ $*${C_N}" >&2; exit 1; }
run(){   if [ "$DRY_RUN" = "1" ]; then echo -e "${C_D}  [dry-run] $*${C_N}"; else "$@"; fi; }

[ "$(id -u)" = "0" ] || die "run as root: sudo bash $0"
[ "$DRY_RUN" = "1" ] && warn "DRY RUN — nothing will be modified"

# The submodule is sparse-checked-out to the chart + CI harness. If it is empty, the clone was
# never initialised and every phase below would fail in a more confusing way.
[ -d "$PLATFORM/chart" ] || die "platform/deploy/chart missing — run: bash scripts/setup.sh (initialises the base-services submodule)"

export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

# ── 1 · the host ───────────────────────────────────────────────────────────────────────────────────
phase "1 · provision the host"
if [ "${SKIP_PROVISION:-0}" = "1" ]; then
  ok "SKIP_PROVISION=1 — leaving the host alone"
elif kubectl get nodes >/dev/null 2>&1; then
  ok "k3s already answering — skipping provision-server.sh"
else
  [ -f "$HERE/provision-server.sh" ] || die "provision-server.sh missing"
  run bash "$HERE/provision-server.sh" || die "provision-server.sh failed"
fi

# ── 2 · the cluster (base-services owns this) ──────────────────────────────────────────────────────
phase "2 · bootstrap the cluster (Calico + metrics-server + datastores)"
[ -f "$PLATFORM/k3s/bootstrap.sh" ] || die "platform bootstrap.sh missing — is the submodule sparse-checkout complete?"
run bash "$PLATFORM/k3s/bootstrap.sh" || die "platform bootstrap failed"

# ── 3 · PROVE it, do not assume it ─────────────────────────────────────────────────────────────────
# bootstrap INSTALLS Calico. preflight sends an actual packet and proves the policy drops it.
# Presence is not enforcement: a NetworkPolicy on a flannel cluster applies cleanly and fails OPEN.
# Every tenant-isolation claim in the spec (§2.3, §14.1) rests on this passing. So: fatal.
phase "3 · preflight — prove default-deny is enforced"
[ -f "$PLATFORM/k3s/preflight.sh" ] || die "platform preflight.sh missing"
if [ "$DRY_RUN" = "1" ]; then
  echo -e "${C_D}  [dry-run] bash $PLATFORM/k3s/preflight.sh${C_N}"
elif bash "$PLATFORM/k3s/preflight.sh"; then
  ok "cluster enforces what the chart promises"
else
  die "preflight FAILED — this cluster does not enforce NetworkPolicy.
     Do not deploy onto it. Tenant isolation would be decorative.
     Most likely cause: k3s was installed with stock flannel. Fix:
       k3s-uninstall.sh && sudo bash $HERE/provision-server.sh"
fi

# ── 4 · registry credential ────────────────────────────────────────────────────────────────────────
phase "4 · image pull-secret for our private images"
if [ -f "$HERE/pull-images.sh" ]; then
  run bash "$HERE/pull-images.sh" --no-prewarm || die "pull-images.sh failed (registry credential)"
else
  pend "pull-images.sh not built yet. Base-services images are public; our own services have"
  pend "no images to pull until the first one is built. Adapt imtithal's pull-images.sh then."
fi

# ── 5 · deploy the services ────────────────────────────────────────────────────────────────────────
# One generic chart, one values file per service. We never call the platform Makefile's `deploy`
# target: it deploys ITS services list from ITS values directory. Ours live here, in our repo,
# and are the only thing we own in this step.
phase "5 · deploy services (chart from platform/, values from deploy/services/)"
if [ ! -d "$OUR_VALUES" ] || [ -z "$(ls -A "$OUR_VALUES"/*.values.yaml 2>/dev/null)" ]; then
  pend "no values files in deploy/services/ yet — nothing to deploy."
  pend "Wave 1 starts here: tenant → authz → identity → audit."
else
  command -v helm >/dev/null 2>&1 || die "helm missing (provision-server.sh installs it)"
  for f in "$OUR_VALUES"/*.values.yaml; do
    n="$(basename "$f" .values.yaml)"
    echo -e "${C_C}==> $n${C_N}"
    run helm upgrade --install "$n" "$PLATFORM/chart" -f "$f" \
      --namespace "$NAMESPACE" --create-namespace --wait --timeout 5m \
      || die "deploy failed for $n — stopping. Nothing after this point is trustworthy."
  done
  ok "all services rolled out"
fi

# ── 6 · reboot resilience ──────────────────────────────────────────────────────────────────────────
phase "6 · survive an ungraceful reboot"
if [ -f "$HERE/boot-heal.sh" ]; then
  run bash "$HERE/boot-heal.sh" --install || warn "boot-heal install had issues"
else
  pend "boot-heal.sh not built yet (adapt imtithal's)."
fi
# Graceful node shutdown is cheap and independent of boot-heal: a clean reboot drains pods
# instead of stranding them. Applies on the next k3s restart.
if [ "$DRY_RUN" != "1" ]; then
  mkdir -p /etc/rancher/k3s
  if ! grep -q "shutdown-grace-period" /etc/rancher/k3s/config.yaml 2>/dev/null; then
    printf 'kubelet-arg:\n  - "shutdown-grace-period=30s"\n  - "shutdown-grace-period-critical-pods=10s"\n' \
      >> /etc/rancher/k3s/config.yaml
    ok "k3s graceful-shutdown armed (applies on next k3s restart)"
  fi
fi

echo
ok "${C_B}setup complete${C_N}"
kubectl -n "$NAMESPACE" get deploy 2>/dev/null || true
