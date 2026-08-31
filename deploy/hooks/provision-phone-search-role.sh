#!/usr/bin/env bash
# ==================================================================================================
#  THE SECOND POSTGRES ROLE ON THIS PLATFORM — and the only one, on purpose.
# --------------------------------------------------------------------------------------------------
#  Every other query in the fleet, in every service, runs under the one role gen-secrets mints
#  (see ci/check_a_deploy_script_does_not_invent_a_postgres_role.py — the platform's own rule that
#  a deploy script reads that role, never spells a new one). This script is the one deliberate
#  exception, and it exists for exactly one query: operations' `GET /customers/by-phone`, the
#  human-driven search screen an insider could abuse (checking a number out of curiosity, or
#  probing whether someone is a customer at all — discussed and audited this session, see
#  customer.searched_by_phone in services/operations/app/auditable_actions.py).
#
#  WHAT THIS ROLE CAN SEE, AND NOTHING ELSE. `operations` stores every collection (customers,
#  visits, branches, operators, everything) in one shared table, `kv_store` — a phone number sits
#  in the same column as a visit's note and a branch's address. A role with SELECT on that table
#  could read all of it. So this role gets NO grant on kv_store at all: only SELECT on a narrow
#  VIEW, `customers_phone_search_v`, exposing `tenant, phone, key` for `collection='customers'`
#  rows — not even a customer's own name or subject_ref, and nothing from any other collection.
#  services/operations/app/adapters/datastore/phone_search_ro.py is the one adapter that uses it,
#  and services/operations/app/core/operations.py's `customer_by_phone_searched` is the one caller.
#
#  IDEMPOTENT. Safe to re-run: the view is CREATE OR REPLACE, the role is created only if missing,
#  and re-running rotates the role's password and re-seals the secret — the same "did we already do
#  this" posture as every other hook under deploy/hooks/.
#
#  USAGE
#    bash deploy/hooks/provision-phone-search-role.sh
# ==================================================================================================
set -Eeuo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"
NS="${NS:-base-services}"
DB="operations"
ROLE="operations_search_ro"
VIEW="customers_phone_search_v"

info(){ echo -e "\e[36m  ▸ $*\e[0m"; }
ok(){   echo -e "\e[32m  ✔ $*\e[0m"; }
die(){  echo -e "\e[31m  ✘ $*\e[0m" >&2; exit 1; }

# THE SUPERUSER IS READ, NOT ASSUMED — same rule, same reason, as deploy/hooks/pre-deploy.sh: a
# spelled-out role that does not exist fails silently, not loudly, and the gate this file must pass
# (check_a_deploy_script_does_not_invent_a_postgres_role.py) exists precisely to catch that class
# of bug before it ships again.
BASE_DSN="$(kubectl -n "$NS" get secret operations-secrets -o jsonpath='{.data.DATASTORE_DSN}' 2>/dev/null | base64 -d || true)"
[ -n "$BASE_DSN" ] || die "no DATASTORE_DSN on operations-secrets — run deploy/mint-our-secrets.sh first"
PGUSER_ADMIN="$(printf '%s' "$BASE_DSN" | cut -d/ -f3 | cut -d: -f1)"
HOST_PORT="$(printf '%s' "$BASE_DSN" | cut -d@ -f2 | cut -d/ -f1)"
[ -n "$PGUSER_ADMIN" ] && [ -n "$HOST_PORT" ] || die "could not parse operations' own DSN"

NEW_PASS="$(head -c 24 /dev/urandom | base64 | tr -d '=+/' | cut -c1-32)"

info "provisioning the view + the weaker role (as $PGUSER_ADMIN, in $DB)"
kubectl -n "$NS" exec postgres-0 -- psql -U "$PGUSER_ADMIN" -d "$DB" -v ON_ERROR_STOP=1 <<SQL
-- The narrow window this role is allowed to look through: (tenant, phone, key) for customers
-- ONLY, never the base table every other collection shares.
CREATE OR REPLACE VIEW $VIEW AS
  SELECT value->>'tenant' AS tenant, value->>'phone' AS phone, key
  FROM kv_store WHERE collection = 'customers';

DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$ROLE') THEN
    CREATE ROLE $ROLE LOGIN PASSWORD '$NEW_PASS' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  ELSE
    ALTER ROLE $ROLE PASSWORD '$NEW_PASS';
  END IF;
END
\$\$;

-- NOTHING ELSE. Explicit REVOKE first so a future grant added elsewhere (a default privilege, a
-- PUBLIC grant) cannot silently widen this role — the intent is legible even if Postgres's own
-- defaults ever change under it.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM $ROLE;
GRANT CONNECT ON DATABASE $DB TO $ROLE;
GRANT USAGE ON SCHEMA public TO $ROLE;
GRANT SELECT ON $VIEW TO $ROLE;
SQL
ok "view + role in place, password rotated"

info "sealing DATASTORE_DSN_PHONE_SEARCH into operations-secrets"
NEW_DSN="postgresql://$ROLE:$NEW_PASS@$HOST_PORT/$DB"
kubectl -n "$NS" patch secret operations-secrets --type=merge -p \
  "{\"data\":{\"DATASTORE_DSN_PHONE_SEARCH\":\"$(printf '%s' "$NEW_DSN" | base64 -w0)\"}}" >/dev/null
ok "sealed"

info "restarting operations to pick it up"
kubectl -n "$NS" rollout restart deploy/operations >/dev/null
kubectl -n "$NS" rollout status  deploy/operations --timeout=180s >/dev/null \
  || die "operations did not come back — the role and secret are sealed, the pod is not running"
ok "operations restarted and holding the weaker role for GET /customers/by-phone"
