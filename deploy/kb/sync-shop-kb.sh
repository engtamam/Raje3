#!/usr/bin/env bash
# Sync deploy/kb/shop/*.json into the ConfigMap assistant-service mounts as its hand-authored KB.
#
#   ./deploy/kb/sync-shop-kb.sh                 # validate, then kubectl apply the ConfigMap
#   ./deploy/kb/sync-shop-kb.sh --dry-run       # render the ConfigMap YAML, touch nothing
#
# WHY THIS EXISTS. assistant-service's FileKnowledgeSource (Phase 4 of the assistant rollout) reads
# KB_FILE_PATH off local disk — a file, or a directory of *.json. There is no way to write to a
# pod's disk directly, so the authored content has to arrive as a ConfigMap, mounted read-only via
# the chart's extraVolumes/extraVolumeMounts hook (platform v0.18.33). This script is the one place
# that turns "edited a JSON file in this repo" into "the mounted ConfigMap actually has that byte" —
# without it, an author changes deploy/kb/shop/services.json and the running assistant answers with
# whatever was mounted at the LAST sync, silently.
#
# VALIDATION LIVES IN ci/check_shop_kb_is_valid.py, NOT HERE — it runs on every commit, which is
# where a bad entry needs to be caught (the day it is written, in review), not the day someone
# happens to run this script. This still runs it first and refuses to touch the cluster if it
# fails, but the gate is the authority; this is just deploy-time defence in depth.
#
# THE ~1MiB CONFIGMAP CEILING (etcd's own limit, not ours). 68 entries today sit nowhere near it;
# if the authored KB ever grows past it, kubectl apply fails LOUDLY here rather than the pod
# silently mounting a truncated ConfigMap — at that point, move to a projected volume or an
# init-container fetch (the chart's extraVolumes hook supports either).
set -Eeuo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KB_DIR="$HERE/shop"
NS="${NS:-base-services}"
NAME="assistant-kb-shop"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in --dry-run) DRY_RUN=1 ;; esac
done

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }

[ -d "$KB_DIR" ] || { red "no $KB_DIR"; exit 2; }

ROOT="$(cd "$HERE/../.." && pwd)"
python3 "$ROOT/ci/check_shop_kb_is_valid.py" || { red "refusing to sync — fix the KB files above first"; exit 1; }

# `command kubectl`, NOT `kubectl` — when the cluster is reached over ssh (cluster.sh's own
# CLUSTER_VIA=ssh rung), `kubectl` is a shell FUNCTION that forwards the whole command line,
# `--from-file` and all, to the remote node — which does not have $KB_DIR, a path on THIS machine.
# `--dry-run=client` never talks to the cluster at all; it only needs a real local binary reading a
# real local directory, so `command` (bash's own "ignore any function of this name") is what makes
# that true regardless of which rung cluster.sh resolved. Found live: this exact call failing with
# "error reading $KB_DIR: no such file or directory" — the ssh side genuinely had no such file,
# because there was never meant to be a file there, only a request built from one.
CM_YAML=$(command kubectl create configmap "$NAME" \
  --from-file="$KB_DIR" \
  --dry-run=client -o yaml)

SIZE=$(printf '%s' "$CM_YAML" | wc -c)
grn "rendered ConfigMap $NAME — ${SIZE} bytes (etcd's own ceiling is ~1MiB; see this script's own note if this ever gets close)"

if [ "$DRY_RUN" = "1" ]; then
  printf '%s\n' "$CM_YAML"
  exit 0
fi

printf '%s\n' "$CM_YAML" | kubectl -n "$NS" apply -f -
grn "applied $NAME to namespace $NS"
echo "  kubelet syncs a mounted ConfigMap's files on its own (about a minute) — call"
echo "  POST /api/v1/assistant/admin/kb/reload afterward (platform.assistant) so assistant-service"
echo "  picks it up immediately rather than waiting on its own periodic reload, if it has one."
