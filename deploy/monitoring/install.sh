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
# NOT `set -e`. helm --wait on this stack routinely exceeds its timeout while a pod is still
# pulling — the release lands and the pods come up healthy a minute later, but helm returns
# non-zero. Under `set -e` that aborted the script BEFORE the postgres exporter and our alert
# rules were installed, leaving a monitoring stack that watches the cluster and misses the one
# metric it was built for. Each step below reports its own outcome instead.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"
NS_MON="${NS_MON:-monitoring}"
NS="${NS:-base-services}"
HERE="$(cd "$(dirname "$0")" && pwd)"

info(){ echo -e "\e[36m  ▸ $*\e[0m"; }
ok(){   echo -e "\e[32m  ✔ $*\e[0m"; }
warn(){ echo -e "\e[33m  ! $*\e[0m"; }

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
  --namespace "$NS_MON" -f "$HERE/values.yaml" --wait --timeout 900s \
  || warn "helm --wait returned non-zero — on this stack that is usually a slow pull, not a
           failure. Continuing; the verification at the end is what decides."
ok "operator, prometheus, alertmanager and grafana applied"

# ── 2. the postgres exporter ──────────────────────────────────────────────────────────────────
# It reads the SAME credential the services use. A monitoring account with its own password is one
# more secret to rotate; a read-only view of pg_stat_activity does not justify that.
info "installing the postgres exporter"
DSN=$(kubectl -n "$NS" get secret tenant-service-secrets -o jsonpath='{.data.DATASTORE_DSN}' | base64 -d)
# Point it at `postgres`, not at a service's own database: pg_stat_activity is cluster-wide, and
# connecting to a service's database would have the exporter competing for the very slots it exists
# to measure.
DSN="${DSN%/*}/postgres?sslmode=disable"
# A DSN IS NAMESPACE-RELATIVE, and this one is being carried ACROSS a namespace. The services keep
# `@postgres:5432`, a bare name that only resolves inside base-services. Copied as-is into the
# monitoring namespace it fails with "lookup postgres: no such host" — the exporter starts, stays
# Ready, logs the error where nobody reads it, and Prometheus simply has no series. A value that was
# valid where it was written is not valid where it is used.
DSN=$(printf '%s' "$DSN" | sed -E "s#@postgres:#@postgres.${NS}.svc.cluster.local:#")
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
  --wait --timeout 300s || warn "exporter helm wait timed out — verified below instead"
ok "postgres exporter applied"

# ── 3. our rules ──────────────────────────────────────────────────────────────────────────────
info "applying the alert rules"
kubectl apply -f "$HERE/alerts.yaml" >/dev/null
ok "rules applied"

# ── 4. verify, because applying is not the same claim as working ──────────────────────────────
# The stack can be "installed" and still be blind: rules that did not load, or an exporter whose
# series never arrives. Both are silent, and both defeat the entire point of installing it.
step_ok=1
PROM="kubectl -n $NS_MON exec prometheus-mon-prometheus-0 -c prometheus -- wget -qO-"
groups=$($PROM "http://localhost:9090/api/v1/rules" 2>/dev/null | grep -c "raje3\." || true)
if [ "${groups:-0}" -gt 0 ]; then ok "our alert rules are loaded in prometheus"
else warn "rules NOT loaded — check the release label on alerts.yaml"; step_ok=0; fi

series=$($PROM "http://localhost:9090/api/v1/query?query=pg_stat_activity_count" 2>/dev/null | grep -c '"value"' || true)
if [ "${series:-0}" -gt 0 ]; then ok "pg_stat_activity_count is flowing — the connection alert can fire"
else warn "the postgres gauge has no series — the alert that cost us an hour is BLIND"; step_ok=0; fi

echo
echo "  Next, and NOT done by this script because it restarts pods:"
echo "    set metrics.serviceMonitor: true in deploy/services/*.values.yaml, then roll with"
echo "    platform/deploy/server/update.sh. Until then Prometheus watches the cluster and the"
echo "    database, but not the services' own /metrics."
echo
echo "  Grafana:  kubectl -n $NS_MON port-forward svc/mon-grafana 3000:80"
echo "  Password: kubectl -n $NS_MON get secret mon-grafana -o jsonpath='{.data.admin-password}' | base64 -d"
