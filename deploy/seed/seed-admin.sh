#!/usr/bin/env bash
# Create the administration account the installer asked for — ours, not an establishment's.
#
#   ADMIN_PHONE=… ADMIN_PASSWORD=… ./deploy/seed/seed-admin.sh
#   ./deploy/seed/seed-admin.sh --dry-run     # say what it would do, change nothing
#
# WHY THIS EXISTS, AND IT IS THE WHOLE DEFECT (ل-2). `install.sh` asks the operator for an
# administration phone number and password. It enforces a twelve-character floor. It generates one when
# the field is left blank. It exports both. It prints the password under «تُعرض مرة واحدة فقط».
#
# And nothing read either value. No account was created — not by bring-up.sh, not by any seeder.
# The operator wrote down a password for an account that did not exist, closed the terminal, and
# found out on the day they first tried to sign in. Every signal the prompt gave said the answer
# mattered; none of them was true.
#
# THE DOOR IS IDENTITY'S BOOTSTRAP PRIMITIVE. A freshly provisioned tenant has nobody holding
# members:write, so no user-tier route can add the first admin — that is the chicken and egg
# `/internal/tenancy/seed-owner` exists to break. It is idempotent, it audits WRITE-AHEAD (an owner
# grant that cannot be recorded must not happen), and `only_if_empty` refuses to seed a DIFFERENT
# owner onto an already-staffed tenant. All three properties are why this script is eight lines of
# decision and not a provisioning engine.
#
# THE TENANT IS `_platform`, the same reserved name seed-roles.sh puts our operator roles under and
# the same one operations uses for its own rows. One reserved name across the product rather than a
# different one per service.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# ONE ANSWER TO «WHERE IS THE CLUSTER», and it is not this script's to invent. Without this a
# `kubectl` here resolves against whatever kubeconfig the operator happens to be holding, and the
# failure reads «connection refused» — a network problem — when the truth is that nobody said which
# cluster. A gate enforces it across every deploy script, and it caught this file.
. "$HERE/../cluster.sh"
NS="${NS:-base-services}"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1

C_G=$'\e[32m'; C_R=$'\e[31m'; C_Y=$'\e[33m'; C_D=$'\e[2m'; C_N=$'\e[0m'
ok(){   echo -e "  ${C_G}✔${C_N} $*"; }
red(){  echo -e "  ${C_R}✖${C_N} $*" >&2; }
warn(){ echo -e "  ${C_Y}!${C_N} $*"; }

# NO ADMIN ASKED FOR IS NOT A FAILURE. install.sh lets the operator skip the phone («بلا حساب
# إدارة — يمكن إنشاؤه لاحقاً»), and a bring-up that refused on that would be refusing a choice we
# offered. But a password with no phone, or a phone with no password, is a HALF answer — that is
# the installer and this script disagreeing about what was collected, and it fails loudly.
if [ -z "${ADMIN_PHONE:-}" ] && [ -z "${ADMIN_PASSWORD:-}" ]; then
  warn "no administration account was asked for — skipping (install.sh said it can be created later)"
  exit 0
fi
if [ -z "${ADMIN_PHONE:-}" ] || [ -z "${ADMIN_PASSWORD:-}" ]; then
  red "half an administration account: phone=${ADMIN_PHONE:+set}${ADMIN_PHONE:-EMPTY}, password=${ADMIN_PASSWORD:+set}${ADMIN_PASSWORD:-EMPTY}"
  red "both or neither — a password with nobody to hold it is the defect this script exists to end"
  exit 1
fi

TENANT="${ADMIN_TENANT:-_platform}"
ROLE="${ADMIN_ROLE:-platform-owner}"

POD=$(kubectl -n "$NS" get pods --no-headers 2>/dev/null \
      | awk '/^identity-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "identity-service is not running — the account cannot be created"; exit 1; }

TOKEN=$(kubectl -n "$NS" get secret identity-service-secrets \
        -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$TOKEN" ] || { red "no INTERNAL_SERVICE_TOKEN in identity-service-secrets"; exit 1; }

if [ $DRY -eq 1 ]; then
  echo -e "${C_D}  would seed owner ${ADMIN_PHONE} on tenant ${TENANT} with role ${ROLE}${C_N}"
  exit 0
fi

# THE PASSWORD TRAVELS ON STDIN, NEVER ON A COMMAND LINE. An argument is visible in `ps` to every
# process on the node for as long as the call runs, and this is the credential that opens every
# establishment we host.
#
# THE SCRIPT ITSELF CANNOT ALSO BE ON STDIN — `python -` reads its ENTIRE stdin as the program's
# own source, to EOF, before running a line of it; a heredoc feeding both the script AND the
# password on one stream leaves nothing for the running script's own `sys.stdin.read()` to see.
# That was this file's actual bug for as long as it existed: `-i` connected fine, the exec
# succeeded, and every single seed attempt still died on "the password did not reach the pod" —
# because it structurally could not, regardless of what ADMIN_PASSWORD held. The fix keeps the
# same guarantee (the credential itself touches no argv, no `ps`, nowhere but a pipe) by moving
# the SCRIPT off stdin instead: base64 is not a secret, so it travels as a `-c` argument, and
# stdin is then free to carry the one thing that actually needs the protection.
PY_B64="$(base64 -w0 <<'PY'
import json
import sys
import urllib.error
import urllib.request

token, tenant, identifier, role = sys.argv[1:5]
password = sys.stdin.read().strip()
if not password:
    sys.exit("the password did not reach the pod — refusing to seed an owner without one")

body = json.dumps({
    "tenant": tenant,
    "identifier": identifier,
    "roles": [role],
    "password": password,
    # NEVER OVERWRITE A STAFFED TENANT. A re-run of bring-up must not hand ownership to whoever
    # happens to be holding the installer's env at the time — that is a grant backdoor wearing an
    # idempotency costume. Identity refuses, and the refusal is the correct outcome.
    "only_if_empty": True,
}).encode()

req = urllib.request.Request("http://127.0.0.1:8000/internal/tenancy/seed-owner",
                             data=body, method="POST",
                             headers={"Content-Type": "application/json",
                                      "X-Internal-Token": token})
try:
    with urllib.request.urlopen(req, timeout=30) as resp:      # nosec B310 - loopback, in-pod
        out = json.loads(resp.read() or b"{}")
except urllib.error.HTTPError as exc:
    detail = exc.read().decode(errors="replace")[:200]
    # 409 IS THE CORRECT, EXPECTED SHAPE OF "ALREADY OWNED" — `only_if_empty` refuses this exact
    # way on a re-run, and that is success, not failure. Before this, only a 200-with-seeded:false
    # response ever reached the ALREADY_OWNED branch below; identity actually answers a genuine
    # conflict with 409, which this treated as a hard failure — burning all three of the bash
    # loop's retries on a call that was never going to succeed differently, then cascading into
    # "admin account: failed" and every downstream seed step refusing with 401 (no token, because
    # nothing above ever printed one) even though the account existed and worked the whole time.
    # Found by hand: the FIRST call of a three-call retry burst actually returned 201 Created, and
    # the next two — retries of an already-done job — got exactly this 409 and were read as proof
    # the whole thing had failed.
    if exc.code == 409:
        print("ALREADY_OWNED")
        sys.exit(0)
    sys.exit(f"identity refused ({exc.code}): {detail}")
except (urllib.error.URLError, OSError) as exc:
    sys.exit(f"could not reach identity in its own pod: {exc}")

# `seeded` false means the tenant already had an owner and identity left them alone. That is a
# correct, quiet outcome on a re-run — and it must not read as "created", because an operator who
# believes a fresh password was set will use one that was never accepted.
print("SEEDED" if out.get("seeded") else "ALREADY_OWNED")
PY
)"
# A FEW RETRIES, BECAUSE THIS RACES A ROLLING RESTART. update.sh gates identity-service on its own
# readiness before this script ever runs, and still: on a freshly wiped, heavily loaded node this
# exec has been seen to die instantly with SIGPIPE and print nothing at all — no kubectl error, no
# python traceback, just the pipe closing under load before either side said anything. Retrying is
# correct here for the same reason preflight-netpol.sh's own header gives: a transport that can
# fail independently of what it is carrying should not be the thing that decides the outcome.
attempt=0
until printf '%s' "$ADMIN_PASSWORD" | kubectl -n "$NS" exec -i "$POD" -- \
  python -c "import base64; exec(base64.b64decode('$PY_B64'))" "$TOKEN" "$TENANT" "$ADMIN_PHONE" "$ROLE"; do
  attempt=$((attempt + 1))
  [ $attempt -ge 3 ] && exit 1
  warn "seed attempt $attempt failed (likely a transient exec hiccup) — retrying"
  sleep 3
done
