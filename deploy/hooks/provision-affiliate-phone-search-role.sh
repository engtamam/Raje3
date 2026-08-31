#!/usr/bin/env bash
# ==================================================================================================
#  THE THIRD DELIBERATE POSTGRES ROLE ON THIS PLATFORM — same pattern as
#  deploy/hooks/provision-phone-search-role.sh (operations), same reason, one step more urgent:
#  affiliate-service's `POST /apply` (api/v1/public.py) drives an exact-match phone lookup against
#  `affiliates`/`affiliate_applications` with NO capability gate at all — any caller on the open
#  internet reaches it. See services/affiliate-service/app/config.py's DATASTORE_DSN_PHONE_SEARCH
#  for the full rationale.
#
#  WHAT THIS ROLE CAN SEE, AND NOTHING ELSE. Both collections that hold a raw phone number
#  (`affiliates`, `affiliate_applications` — see Affiliate/Application in core/models.py) share the
#  one `kv_store` table with every other collection this service holds (leads, commissions,
#  withdrawals, payout accounts, message templates — see the inventory this session ran). This
#  role gets NO grant on kv_store: only SELECT on a narrow VIEW,
#  `affiliate_phone_search_v(collection, key, phone, created_at)`, scoped to exactly those two
#  collections — never a name, an address, a decision-maker's own phone, a payout account, or
#  anything from `leads`/`commissions`/`withdrawals`/etc.
#
#  IDEMPOTENT. Safe to re-run: the view is CREATE OR REPLACE, the role is created only if missing,
#  and re-running rotates the role's password and re-seals the secret.
#
#  USAGE
#    bash deploy/hooks/provision-affiliate-phone-search-role.sh
# ==================================================================================================
set -Eeuo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"
NS="${NS:-base-services}"
ROLE="affiliate_search_ro"
VIEW="affiliate_phone_search_v"

info(){ echo -e "\e[36m  ▸ $*\e[0m"; }
ok(){   echo -e "\e[32m  ✔ $*\e[0m"; }
die(){  echo -e "\e[31m  ✘ $*\e[0m" >&2; exit 1; }

# THE SUPERUSER IS READ, NOT ASSUMED — same rule as every deploy/hooks/*.sh script; see
# ci/check_a_deploy_script_does_not_invent_a_postgres_role.py. THE DATABASE NAME IS READ TOO,
# for the identical reason: affiliate-service was assumed to own a same-named database when this
# script was first written, and that assumption was WRONG — it is one of the two services
# deliberately placed on the platform's shared `base_services` database instead (see mint-our-
# secrets.sh's own SHARED_ONLY note), confirmed live against the real secret before this hook
# was ever run for real. A spelled-out "affiliate-service" here would connect to a database that
# does not exist, exactly the class of bug the role rule above already exists to prevent — the
# same fix applies to the database, not just the role.
BASE_DSN="$(kubectl -n "$NS" get secret affiliate-service-secrets -o jsonpath='{.data.DATASTORE_DSN}' 2>/dev/null | base64 -d || true)"
[ -n "$BASE_DSN" ] || die "no DATASTORE_DSN on affiliate-service-secrets — gen-secrets.py must run first (see mint-our-secrets.sh's own note: this service's DSN is theirs to mint, not ours)"
PGUSER_ADMIN="$(printf '%s' "$BASE_DSN" | cut -d/ -f3 | cut -d: -f1)"
HOST_PORT="$(printf '%s' "$BASE_DSN" | cut -d@ -f2 | cut -d/ -f1)"
DB="$(printf '%s' "$BASE_DSN" | sed 's#.*/##')"
[ -n "$PGUSER_ADMIN" ] && [ -n "$HOST_PORT" ] && [ -n "$DB" ] || die "could not parse affiliate-service's own DSN"

NEW_PASS="$(head -c 24 /dev/urandom | base64 | tr -d '=+/' | cut -c1-32)"

info "provisioning the view + the weaker role (as $PGUSER_ADMIN, in $DB)"
# `-i` IS NOT OPTIONAL HERE — see provision-phone-search-role.sh's own note (the operations
# twin), found live the same way this file's own DB-name bug was: this script printed success on
# a cluster where nothing was actually created, because `kubectl exec` without `-i` never
# attaches the heredoc to stdin at all — psql ran against a closed stdin and exited 0 having done
# nothing.
kubectl -n "$NS" exec -i postgres-0 -- psql -U "$PGUSER_ADMIN" -d "$DB" -v ON_ERROR_STOP=1 <<SQL
-- The narrow window this role is allowed to look through: (collection, key, phone, created_at)
-- for 'affiliates' and 'affiliate_applications' ONLY — never any other collection this service
-- holds, and never a name/address/payout field even within those two. (Plain quotes here, not
-- backticks: this heredoc is unquoted for variable interpolation below, so a backtick in a SQL
-- comment is still a real shell command substitution -- found live, the hard way, on this exact
-- line, trying to run two collection names as commands.)
CREATE OR REPLACE VIEW $VIEW AS
  SELECT collection, key, value->>'phone' AS phone,
         COALESCE((value->>'created_at')::bigint, 0) AS created_at
  FROM kv_store WHERE collection IN ('affiliates', 'affiliate_applications');

DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$ROLE') THEN
    CREATE ROLE $ROLE LOGIN PASSWORD '$NEW_PASS' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  ELSE
    ALTER ROLE $ROLE PASSWORD '$NEW_PASS';
  END IF;
END
\$\$;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM $ROLE;
GRANT CONNECT ON DATABASE "$DB" TO $ROLE;
GRANT USAGE ON SCHEMA public TO $ROLE;
GRANT SELECT ON $VIEW TO $ROLE;
SQL
ok "view + role in place, password rotated"

info "sealing DATASTORE_DSN_PHONE_SEARCH into affiliate-service-secrets"
NEW_DSN="postgresql://$ROLE:$NEW_PASS@$HOST_PORT/$DB"
kubectl -n "$NS" patch secret affiliate-service-secrets --type=merge -p \
  "{\"data\":{\"DATASTORE_DSN_PHONE_SEARCH\":\"$(printf '%s' "$NEW_DSN" | base64 -w0)\"}}" >/dev/null
ok "sealed"

info "restarting affiliate-service to pick it up"
kubectl -n "$NS" rollout restart deploy/affiliate-service >/dev/null
kubectl -n "$NS" rollout status  deploy/affiliate-service --timeout=180s >/dev/null \
  || die "affiliate-service did not come back — the role and secret are sealed, the pod is not running"
ok "affiliate-service restarted and holding the weaker role for POST /apply"
