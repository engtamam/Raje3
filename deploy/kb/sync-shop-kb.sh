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
# VALIDATED BEFORE IT EVER REACHES THE CLUSTER. Every file must parse as JSON and every entry must
# carry a matching id/anchor pair (assistant-service's own parse_kb refuses a bad entry by failing
# the WHOLE load — a single malformed file would take down every anchor across all nine screens,
# not just its own).
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

shopt -s nullglob
FILES=("$KB_DIR"/*.json)
shopt -u nullglob
[ "${#FILES[@]}" -gt 0 ] || { red "no *.json files in $KB_DIR — nothing to sync"; exit 2; }

# Every file must parse, and every entry needs a matching id/anchor and an Arabic title/body — the
# same shape check.py's own reader expects, run here so a bad file is caught before it ever reaches
# the cluster rather than after assistant-service refuses to boot on a malformed KB.
python3 - "${FILES[@]}" <<'PYEOF'
import json, sys
total = 0
seen = {}
for path in sys.argv[1:]:
    with open(path, encoding="utf-8") as fh:
        entries = json.load(fh)
    if not isinstance(entries, list):
        sys.exit(f"{path}: must be a JSON array of entries")
    for e in entries:
        if not isinstance(e, dict):
            sys.exit(f"{path}: entry is not an object: {e!r}")
        if e.get("id") != e.get("anchor"):
            sys.exit(f"{path}: {e.get('id')!r} — id and anchor must match exactly")
        if e["id"] in seen:
            sys.exit(f"{path}: duplicate id {e['id']!r}, already in {seen[e['id']]}")
        seen[e["id"]] = path
        for field in ("title", "body"):
            v = e.get(field)
            if not isinstance(v, dict) or "ar" not in v:
                sys.exit(f"{path}: {e['id']!r} — {field!r} must be an {{'ar': ...}} map")
        total += 1
print(f"{total} entries across {len(sys.argv) - 1} file(s), all valid, no duplicate ids")
PYEOF

CM_YAML=$(kubectl create configmap "$NAME" \
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
