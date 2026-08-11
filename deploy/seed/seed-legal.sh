#!/usr/bin/env bash
# Publish our legal documents into compliance-service.
#
#   ./deploy/seed/seed-legal.sh              # instantiate each template with our values, publish
#   ./deploy/seed/seed-legal.sh --dry-run    # say what would be published, change nothing
#   ./deploy/seed/seed-legal.sh --version 2  # a NEW version, when a document's text changed
#
# WHY THIS SCRIPT DID NOT EXIST AND HAD TO. The documents were authored, filled in and guarded by
# CI — ci/check_legal.py reads every token in every one of them — and NOTHING ever loaded them into
# the service that serves them. A fresh cluster came up with an empty legal library, which means:
#
#   * `GET /api/v1/compliance/legal` answers with an empty list, so the console's legal gate has no
#     document to show and no version to record an acceptance against;
#   * an owner signs up and accepts nothing. There is then no processing agreement between us and
#     the establishment whose customers' data we immediately begin processing — the one document
#     PDPL Article 17 requires to exist BEFORE the processing does.
#
# And it looked healthy the whole time: the service was up, the route answered 200, the list was
# simply empty. The same shape as every gap the deploy hooks exist to catch — a truthful report
# about the wrong thing.
#
# HOW IT WORKS, AND WHY IT IS NOT A FILE UPLOAD. compliance ships the PDPL pack as templates with
# {{TOKENS}}; our YAML files carry the VALUES for those tokens and nothing else. `instantiate` fills
# one with the other, refuses on any unfilled placeholder, and stores the result as a versioned
# legal page. So the words stay the pack's, the party details stay ours, and neither copy drifts.
#
# IDEMPOTENT. Re-running with the same version is a no-op that reports as one: the service answers
# 409 for a version that already exists, and this treats that as "already published" rather than as
# a failure. A changed document needs `--version`, deliberately — an accepted version must never
# change under the person who accepted it.
set -uo pipefail

NS="${NS:-base-services}"
HERE="$(cd "$(dirname "$0")" && pwd)"
VERSION="1"
DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --version) VERSION="${2:-1}"; shift 2 ;;
    *) shift ;;
  esac
done

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }
inf(){ printf '  %s\n' "$*"; }

# WHICH OF OUR FILES FILLS WHICH TEMPLATE. The same map ci/check_legal.py holds — and the reason it
# is written twice rather than shared is that the guard must keep working if this script is
# deleted. `terms` is ours alone: the pack is a data-protection pack and the Terms are a service
# contract, so no template exists for it upstream.
MAP="privacy-policy.yaml=doc01_privacy_policy
data-subject-rights.yaml=doc03_data_subject_rights
ropa.yaml=doc04_ropa
dpia.yaml=doc10_dpia
cookies.yaml=doc12_cookies
processing-agreement.yaml=doc13_processing_agreement
processor-dpa.yaml=doc14_processor_dpa"

POD=$(kubectl -n "$NS" get pods --no-headers \
      | awk '/^compliance-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "compliance-service is not running"; exit 1; }

# A SIGNED TOKEN, NOT THE INTERNAL ONE. These are user-tier routes wanting `platform.compliance`;
# the internal token authenticates a service and answers 401 here — the same 401 that cost an
# afternoon on seed-templates.sh before it was written down.
KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
printf '%s\n' "$KEY" > /tmp/.legal-key.pem
chmod 600 /tmp/.legal-key.pem
TOKEN=$(python3 -c '
import jwt, time
now = int(time.time())
print(jwt.encode({"sub": "seed-legal", "tenant": "_platform",
                  "caps": ["platform.compliance"],
                  "iss": "raje3", "aud": "raje3", "iat": now, "exp": now + 900},
                 open("/tmp/.legal-key.pem").read(), algorithm="RS256"))' 2>/dev/null)
rm -f /tmp/.legal-key.pem
[ -n "$TOKEN" ] || { red "could not mint a token (pyjwt installed?)"; exit 1; }

FAILED=0
printf '%s\n' "$MAP" | while IFS='=' read -r file template; do
  [ -n "$file" ] || continue
  src="$HERE/legal/$file"
  [ -f "$src" ] || { red "$file is missing"; FAILED=1; continue; }

  # THE VALUES ONLY. Our YAML also carries `publication` and `clauses` — the first is our own note
  # about how the document is used, the second is prose we keep for review. Neither belongs in the
  # instantiate body, and sending them would be sending the service fields it never declared.
  payload=$(python3 - "$src" "$VERSION" <<'PY'
import json, sys
import yaml
doc = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
vals = doc.get("values") or {}
# ACCEPTANCE IS A PROPERTY OF THE DOCUMENT, not a flag somebody remembers to pass. `publication:
# accept` in the file is what makes the gate hold a signup on it.
print(json.dumps({"values": vals, "version": sys.argv[2], "publish": True,
                  "requires_acceptance": (doc.get("publication") == "accept"),
                  "default_locale": "ar"}, ensure_ascii=False))
PY
)
  [ -n "$payload" ] || { red "$file: unreadable (is pyyaml installed?)"; FAILED=1; continue; }

  if [ "$DRY" = "1" ]; then inf "would publish $template v$VERSION from $file"; continue; fi

  out=$(kubectl -n "$NS" exec -i "$POD" -- python3 - "$template" "$VERSION" "$TOKEN" <<PY 2>/dev/null
import json, sys, urllib.error, urllib.request
template, ver, token = sys.argv[1], sys.argv[2], sys.argv[3]
body = json.loads('''$payload''')
req = urllib.request.Request(
    f"http://127.0.0.1:8000/api/v1/compliance/legal/templates/{template}/instantiate",
    data=json.dumps(body).encode(), method="POST",
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        print(r.status)
except urllib.error.HTTPError as e:
    print(f"{e.code} {e.read().decode()[:160]}")
except Exception as e:
    print(f"0 {e}")
PY
)
  case "$out" in
    2*)   grn "$template v$VERSION published" ;;
    409*) grn "$template v$VERSION already published" ;;
    *)    red "$template v$VERSION — ${out:-no answer}"; FAILED=1 ;;
  esac
done

[ "$DRY" = "1" ] && exit 0
grn "the legal library is published"
