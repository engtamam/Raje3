#!/usr/bin/env bash
# ==================================================================================================
#  install.sh — the monitoring stack: Prometheus Operator, a postgres exporter, and our rules.
# --------------------------------------------------------------------------------------------------
#  Run AFTER the platform is up. Installing it first means the ServiceMonitors have nothing to
#  scrape and every target is red, which teaches the operator that red is normal.
#
#  ORDER MATTERS, and not for tidiness:
#    1. the operator, because ServiceMonitor and PrometheusRule are CUSTOM resources — applying a
#       values file with metrics.serviceMonitor=true before the CRDs exist fails the whole release
#       with an error about an unknown kind, which reads like a broken chart;
#    2. the postgres exporter, because it is the source of the alert that matters most to us;
#    3. our rules;
#    4. only then flip metrics.serviceMonitor to true in the values files and roll.
#
#  SIZING WARNING, honestly stated: this stack wants roughly 1GB before it scrapes anything. On a
#  node already carrying twenty-one services and a database it is a real addition, and monitoring
#  that pressures the workload it watches generates the faults it reports. Run it on a node with
#  headroom, or accept that this box is a test box and this belongs on production.
# ==================================================================================================
set -euo pipefail
NS_MON="${NS_MON:-monitoring}"
NS="${NS:-base-services}"
HERE="$(cd "$(dirname "$0")" && pwd)"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

info(){ echo -e "\e[36m  ▸ $*\e[0m"; }
ok(){   echo -e "\e[32m  ✔ $*\e[0m"; }

command -v helm >/dev/null || { echo "helm is required"; exit 1; }

# ── 1. the operator ───────────────────────────────────────────────────────────────────────────
info "installing kube-prometheus-stack"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update >/dev/null 2>&1
kubectl create namespace "$NS_MON" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# The namespace needs its metadata name label: the chart's NetworkPolicy opens ingress from a
# namespace matched by `kubernetes.io/metadata.name: monitoring`. Kubernetes sets that label
# automatically on recent versions, but asserting it costs nothing and its absence would make every
# scrape time out against a policy nobody thinks to check.
kubectl label namespace "$NS_MON" kubernetes.io/metadata.name="$NS_MON" --overwrite >/dev/null

helm upgrade --install mon prometheus-community/kube-prometheus-stack \
  --namespace "$NS_MON" -f "$HERE/values.yaml" --wait --timeout 900s
ok "operator, prometheus, alertmanager and grafana are up"

# ── 2. the postgres exporter ──────────────────────────────────────────────────────────────────
# It reads the SAME credential the services use. A monitoring account with its own password is one
# more secret to rotate; a read-only view of pg_stat_activity does not justify that.
info "installing the postgres exporter"
DSN=$(kubectl -n "$NS" get secret tenant-service-secrets -o jsonpath='{.data.DATASTORE_DSN}' | base64 -d)
# Point it at `postgres`, not at a service's own database: pg_stat_activity is cluster-wide, and
# connecting to a service's database would have the exporter competing for the very slots it exists
# to measure.
DSN="${DSN%/*}/postgres?sslmode=disable"
kubectl -n "$NS_MON" create secret generic pg-exporter \
  --from-literal=DATA_SOURCE_NAME="$DSN" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

helm upgrade --install pg-exporter prometheus-community/prometheus-postgres-exporter \
  --namespace "$NS_MON" \
  --set config.datasourceSecret.name=pg-exporter \
  --set config.datasourceSecret.key=DATA_SOURCE_NAME \
  --set serviceMonitor.enabled=true \
  --set resources.requests.cpu=20m \
  --set resources.requests.memory=32Mi \
  --set resources.limits.memory=64Mi \
  --wait --timeout 300s
ok "postgres exporter is up — pg_stat_activity_count is now a series"

# ── 3. our rules ──────────────────────────────────────────────────────────────────────────────
info "applying the alert rules"
kubectl apply -f "$HERE/alerts.yaml" >/dev/null
ok "rules applied"

echo
echo "  Next, and NOT done by this script because it restarts pods:"
echo "    set metrics.serviceMonitor: true in deploy/services/*.values.yaml, then roll with"
echo "    platform/deploy/server/update.sh. Until then Prometheus watches the cluster and the"
echo "    database, but not the services' own /metrics."
echo
echo "  Grafana:  kubectl -n $NS_MON port-forward svc/mon-grafana 3000:80"
echo "  Password: kubectl -n $NS_MON get secret mon-grafana -o jsonpath='{.data.admin-password}' | base64 -d"
