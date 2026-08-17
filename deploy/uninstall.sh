#!/usr/bin/env bash
# ==================================================================================================
#  uninstall.sh — take Raje3 off a machine, completely, and say what it removed.
# --------------------------------------------------------------------------------------------------
#  WHY A SCRIPT AND NOT SIX COMMANDS. Removing this product by hand leaves things behind, and every
#  one of them is invisible until it bites:
#
#    * helm release metadata outlives a deleted namespace, and the next install refuses with
#      "cannot re-use a name that is still in use";
#    * a PVC's local-path directory outlives the claim, so the next postgres finds a populated data
#      directory, SKIPS first-time initialisation, and never creates the database — leaving every
#      service 0/1 on a datastore that answers and has no schema;
#    * our systemd units keep starting and keep failing against a namespace that no longer exists;
#    * a port-forward keeps a socket open on 8090 pointing at nothing.
#
#  WHAT IT DOES NOT TOUCH, EVER:
#    * k3s itself — removing a Kubernetes distribution is a different decision, and other things
#      may live on this cluster. `--purge-k3s` is offered and is not the default.
#    * the repository, and anything under it.
#
#  Usage:
#    sudo bash deploy/uninstall.sh                 # ask first, then remove Raje3 from the cluster
#    sudo bash deploy/uninstall.sh --yes           # no prompt (CI, or a machine being recycled)
#    sudo bash deploy/uninstall.sh --keep-data     # remove the workloads, KEEP the volumes
#    sudo bash deploy/uninstall.sh --purge-k3s     # and uninstall k3s itself
# ==================================================================================================
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cluster.sh"
HERE="$(cd "$(dirname "$0")" && pwd)"
NS="${NS:-base-services}"
STORAGE="${STORAGE:-/var/lib/rancher/k3s/storage}"

C_G=$'\e[32m'; C_C=$'\e[36m'; C_Y=$'\e[33m'; C_R=$'\e[31m'; C_B=$'\e[1m'; C_D=$'\e[2m'; C_N=$'\e[0m'
step(){ echo -e "\n${C_C}━━━ $* ━━━${C_N}"; }
ok(){   echo -e "${C_G}  ✔ $*${C_N}"; }
warn(){ echo -e "${C_Y}  ! $*${C_N}"; }

ASSUME_YES=0; KEEP_DATA=0; PURGE_K3S=0
for a in "$@"; do case "$a" in
  --yes|-y) ASSUME_YES=1;;
  --keep-data) KEEP_DATA=1;;
  --purge-k3s) PURGE_K3S=1;;
  -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
  *) echo "unknown flag: $a" >&2; exit 2;;
esac; done

[[ $EUID -eq 0 ]] || { echo "run as root: sudo bash $0"; exit 2; }

# ── what is actually here, counted BEFORE anything is touched ─────────────────────────────────
#
# A CONFIRMATION PROMPT THAT NAMES NOTHING IS A PROMPT PEOPLE SAY YES TO. This one counts the
# tenants and the customers, because those are the numbers that make somebody stop and think —
# «22 pods» does not.
pods=$(kubectl -n "$NS" get pods --no-headers 2>/dev/null | wc -l | tr -d ' ')
pvcs=$(kubectl -n "$NS" get pvc --no-headers 2>/dev/null | wc -l | tr -d ' ')
# THIS QUERY WAS WRONG IN THREE PLACES AT ONCE, AND SAID NOTHING ABOUT ANY OF THEM. It asked for
# role `postgres` (the role is `base_services`), from table `kv` (the table is `kv_store`), for
# collection `tenant_sector` (that collection was removed with the trade a shop is in). Each alone
# is fatal; all three together produced an empty string, `2>/dev/null` ate all three errors, and
# the `-n` test below then quietly skipped the line. So the one number in this prompt that was
# supposed to make a person stop — «you are about to delete N shops and everything they own» —
# has never once been printed. Everybody who ran this saw pods and volumes and typed the namespace.
#
# AND SILENCE IS NOT ZERO. If the count cannot be read the script says so and REFUSES, because
# «the query failed» and «there is nothing here» are the same empty string to a shell and opposite
# facts to the person deciding. An uninstall that cannot see what it is deleting must not proceed.
PGU=$(pg_role) || exit 1
rows=$(kubectl -n "$NS" exec postgres-0 -- psql -U "$PGU" -d base_services -tAc \
        "select count(*) from kv_store where collection='tenants'" 2>&1 | tr -d ' \r')

echo -e "${C_B}Raje3 — uninstall${C_N}"
echo "  namespace : $NS"
echo "  pods      : ${pods:-0}"
echo "  volumes   : ${pvcs:-0}$([[ $KEEP_DATA -eq 1 ]] && echo '  (kept)')"
if [[ "$rows" =~ ^[0-9]+$ ]]; then
  echo "  shops     : $rows  ${C_R}(their customers, visits and points go with them)${C_N}"
elif [[ $KEEP_DATA -ne 1 ]]; then
  echo -e "  ${C_R}✗ cannot count the shops about to be deleted: ${rows:-<no answer>}${C_N}"
  echo    "    Refusing: an uninstall that cannot see what it destroys is not a decision."
  echo    "    Re-run with --keep-data, or fix the read first."
  exit 1
fi

if [[ $ASSUME_YES -ne 1 ]]; then
  # THE WORD, NOT A LETTER. `y` is a reflex; typing the namespace is a decision — the same rule
  # every dangerous action in the product follows (§2.3).
  echo
  read -r -p "Type the namespace to confirm removal [$NS]: " typed
  [[ "$typed" == "$NS" ]] || { echo "not confirmed — nothing was touched"; exit 1; }
fi

# ── 1. our boot units, before the cluster they point at disappears ────────────────────────────
step "systemd"
for unit in raje3-up.service raje3-gateway-forward.service; do
  if systemctl list-unit-files 2>/dev/null | grep -q "^$unit"; then
    systemctl disable --now "$unit" >/dev/null 2>&1 || true
    rm -f "/etc/systemd/system/$unit"
    ok "$unit removed"
  fi
done
systemctl daemon-reload 2>/dev/null || true
# A port-forward started by hand outlives its unit. It holds 8090 open pointing at nothing, and the
# next person to install here spends ten minutes on "the tunnel works but nothing answers".
pkill -f 'port-forward.*8090' >/dev/null 2>&1 || true

# ── 2. helm releases, BEFORE the namespace ────────────────────────────────────────────────────
step "releases"
releases=$(helm list -n "$NS" -q 2>/dev/null | wc -l | tr -d ' ')
helm list -n "$NS" -q 2>/dev/null | xargs -r -n1 helm uninstall -n "$NS" >/dev/null 2>&1 || true
ok "${releases:-0} helm release(s) uninstalled"

# ── 3. the namespace ──────────────────────────────────────────────────────────────────────────
step "namespace"
if [[ $KEEP_DATA -eq 1 ]]; then
  # Everything except the claims — so a reinstall finds its data where it left it.
  kubectl -n "$NS" delete all --all --wait=false >/dev/null 2>&1 || true
  kubectl -n "$NS" delete secret,configmap,cronjob --all --wait=false >/dev/null 2>&1 || true
  ok "workloads removed, volumes kept"
else
  kubectl delete namespace "$NS" --wait=true --timeout=180s >/dev/null 2>&1 || true
  ok "namespace deleted"
fi

# ── 4. the host directories the claims left behind ────────────────────────────────────────────
if [[ $KEEP_DATA -ne 1 ]]; then
  step "volumes on disk"
  # SCOPED TO THIS NAMESPACE'S DIRECTORIES. k3s names them `pvc-<uid>_<namespace>_<claim>`, so a
  # blanket `rm -rf $STORAGE/pvc-*` would take another product's data with it — and this script
  # runs on machines that host more than one thing.
  gone=0
  for dir in "$STORAGE"/pvc-*_"${NS}"_*; do
    [[ -e "$dir" ]] || continue
    rm -rf "$dir" && gone=$((gone+1))
  done
  ok "$gone volume director$([[ $gone -eq 1 ]] && echo y || echo ies) removed"
  left=$(ls -d "$STORAGE"/pvc-*_"${NS}"_* 2>/dev/null | wc -l | tr -d ' ')
  [[ "${left:-0}" -eq 0 ]] || warn "$left directory(ies) still present — a reinstall will reuse stale data"
fi

# ── 5. k3s itself, only when asked ────────────────────────────────────────────────────────────
if [[ $PURGE_K3S -eq 1 ]]; then
  step "k3s"
  if [[ -x /usr/local/bin/k3s-uninstall.sh ]]; then
    /usr/local/bin/k3s-uninstall.sh >/dev/null 2>&1 || true
    ok "k3s uninstalled"
  else
    warn "no k3s-uninstall.sh — k3s was not installed the standard way; left alone"
  fi
fi

echo
echo -e "${C_G}✔ Raje3 removed${C_N}"
echo -e "  ${C_D}reinstall with: sudo bash deploy/bring-up.sh${C_N}"
