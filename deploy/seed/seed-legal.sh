#!/usr/bin/env bash
# Draft our legal documents into compliance-service — FROM THE MARKDOWN FILES. DRAFT-ONLY, ALWAYS,
# NO EXCEPTION — including a from-scratch install (`deploy/bring-up.sh` calls this with no flags).
# Publishing is a decision only a human makes, from AdminLegal.tsx, one document at a time.
#
#   ./deploy/seed/seed-legal.sh              # DRAFT every deploy/seed/legal/*.md — review, then
#                                             # publish each one yourself from the admin console
#   ./deploy/seed/seed-legal.sh --dry-run    # say what would be drafted, change nothing
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
# THE MARKDOWN FILE IS THE SOURCE OF TRUTH — a deliberate change from this script's first version.
# That one filled compliance's own PDPL-pack templates (`{{TOKEN}}` placeholders, `instantiate`)
# for seven of the ten documents, and hand-built content for the other three. Both paths are gone:
#
#   * the pack's OWN authoring notes ("delete this red note once published", "replace
#     [PLACEHOLDERS] before publishing") were being sent to `instantiate` UNFILTERED and rendered,
#     verbatim, in the actually-published privacy policy — found live, reading the rendered output;
#   * editing a document meant editing YAML `values:`/`clauses:` — correct, but not something
#     anyone could read or review as prose without running this script's own renderer first.
#
# `deploy/seed/legal/render_markdown.py` used to be the one-way generator (YAML+pack -> .md); now
# the .md file IS what gets published, edited directly (by hand, or via AdminLegal.tsx — which
# writes the identical `legal_text` block shape), and the YAML files stay only for `publication:`
# (does this document require explicit acceptance) — nothing else about them is read here anymore.
#
# THE BLOCK SHAPE IS `{legal_text: {md_ar, md_en}}`, NOT `{type:"text", data:{...}}`. A real
# customer reads published legal content through DocBlocksView (compliance's unified renderer,
# single-key `{kind:{...}}` nodes) — never through the separate markdown-only BlockRenderer that
# AdminLegal.tsx's OWN preview happens to use locally. `legal_text` is the namespaced shim
# DocBlockRenderer.tsx/legalToDocBlocks.ts define for exactly this markdown content, and is what
# makes it actually render at accept-time (found live: the admin preview looked correct while the
# real customer view was blank, because the two renderers were never the same one).
#
# affiliate-agreement.md IS DELIBERATELY EXCLUDED. Its own YAML source says so: "DRAFT ONLY. ...
# not a Saudi legal consultation... do not publish this file before a licensed Saudi lawyer
# reviews it". A contract term reaching a real marketer is a commitment made in the company's
# name — outside what a repeatable seed step should ever decide on its own.
#
# IDEMPOTENT. Re-drafting the same version is a plain overwrite — always fine, since a draft was
# never live to anyone. Re-running against a version that was since PUBLISHED (by a human, from
# the admin console) gets a 409, reported as "already published" rather than a failure: the
# service itself refuses to edit a published version out from under whoever accepted it. Publish
# a changed document as a NEW `--version` instead.
set -uo pipefail
# shellcheck disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../cluster.sh"

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

# doc_id = title_ar = title_en — one row per PUBLISHABLE document, matched to legal/<doc_id>.md and
# legal/<doc_id>.yaml (the latter read only for `publication:`). Titles kept here, not derived from
# anything, because the .md file's own body starts at the content, not a title line to parse.
TITLES="privacy-policy=سياسة الخصوصية=Privacy Policy
data-subject-rights=إجراء حقوق أصحاب البيانات=Data Subject Rights Procedure
ropa=سجل أنشطة معالجة البيانات الشخصية=Records of Processing Activities (ROPA)
dpia=تقييم الأثر لحماية البيانات الشخصية=Data Protection Impact Assessment (DPIA)
cookies=سياسة ملفات الارتباط والتقنيات المتتبِّعة=Cookies & Tracking Technologies Policy
processing-agreement=اتفاقية معالجة البيانات=Data Processing Agreement
processor-dpa=اتفاقية معالجة البيانات (التزامات المعالِج)=Data Processing Agreement (Processor's Commitments)
terms=الشروط والأحكام=Terms of Service
affiliate-privacy-policy=سياسة خصوصية المسوّقين=Affiliate Privacy Policy"

POD=$(kubectl -n "$NS" get pods --no-headers \
      | awk '/^compliance-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "compliance-service is not running"; exit 1; }

# A SIGNED TOKEN, NOT THE INTERNAL ONE. These are user-tier routes wanting `platform.compliance`;
# the internal token authenticates a service and answers 401 here — the same 401 that cost an
# afternoon on seed-templates.sh before it was written down.
KEY=$(kubectl -n "$NS" get secret identity-service-secrets \
      -o jsonpath='{.data.TOKEN_PRIVATE_KEY}' 2>/dev/null | base64 -d)
[ -n "$KEY" ] || { red "no signing key in identity-service-secrets"; exit 1; }
printf '%s\n' "$KEY" > "$HERE/.legal-key.pem"
chmod 600 "$HERE/.legal-key.pem"
# THE kid HEADER — see seed-roles.sh's own note. A token minted with none is rejected by every
# JWKS verifier on this fleet; this thumbprints the SAME key it signs with (RFC 7638, identical to
# identity-service's own `public_jwk`), so it works across a rotation with no code change.
TOKEN=$(python3 -c '
import base64, hashlib, json, jwt, sys, time
from jwt.algorithms import RSAAlgorithm
now = int(time.time())
private_pem = open(sys.argv[1]).read()
key_obj = RSAAlgorithm(RSAAlgorithm.SHA256).prepare_key(private_pem)
jwk = json.loads(RSAAlgorithm.to_jwk(key_obj))
canonical = json.dumps({"e": jwk["e"], "kty": jwk["kty"], "n": jwk["n"]},
                       separators=(",", ":"), sort_keys=True).encode("ascii")
kid = base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).rstrip(b"=").decode("ascii")
print(jwt.encode({"sub": "seed-legal", "tenant": "_platform",
                  "caps": ["platform.compliance"],
                  "iss": "raje3", "aud": "raje3", "iat": now, "exp": now + 900},
                 private_pem, algorithm="RS256", headers={"kid": kid}))' "$HERE/.legal-key.pem" 2>/dev/null)
rm -f "$HERE/.legal-key.pem"
[ -n "$TOKEN" ] || { red "could not mint a token (pyjwt installed?)"; exit 1; }

# A SUBSHELL CANNOT REPORT. `printf | while` runs the loop in a subshell, so a variable set inside
# it is discarded — the first version ended by announcing success over five refusals, which is the
# exact class of lie this whole seed step exists to prevent. A marker file survives the subshell.
FAILMARK="$(mktemp -u)"
printf '%s\n' "$TITLES" | while IFS='=' read -r doc_id title_ar title_en; do
  [ -n "$doc_id" ] || continue
  md_src="$HERE/legal/$doc_id.md"
  yaml_src="$HERE/legal/$doc_id.yaml"
  [ -f "$md_src" ] || { red "$doc_id.md is missing"; : > "$FAILMARK"; continue; }

  if [ "$DRY" = "1" ]; then inf "would draft $doc_id v$VERSION from $doc_id.md"; continue; fi

  # ONE PYTHON PROCESS, EVERYTHING BY ARGV — no bash-built JSON/Python-literal string is ever
  # interpolated into a -c script. That used to be two separate calls stitched together with
  # `'''$content'''` and `'$title_en'` — broke on the first apostrophe in a title ("Processor's
  # Commitments") and on the first real newline inside the parsed Markdown (a JSON string built by
  # one process, re-embedded as a Python literal by fragments of shell, is exactly the kind of
  # thing that looks fine until a character neither side expected shows up). Argv is untouched by
  # either JSON or Python string-literal escaping — the OS hands the exact bytes across, so this
  # class of bug cannot recur here.
  draft_body=$(python3 - "$md_src" "$yaml_src" "$title_ar" "$title_en" <<'PY'
import json, re, sys
md_src, yaml_src, title_ar, title_en = sys.argv[1:5]

text = open(md_src, encoding="utf-8").read()
text = re.sub(r"<!--.*?-->\n*", "", text, flags=re.DOTALL)

def section(marker):
    # ONLY the two exact section markers end a section — NOT every "## " (a document's own
    # clauses/headings inside the section use "##" too, e.g. "## 1. جهة التحكم..." — matching any
    # "## " here cut the Arabic section off at its OWN first clause heading, a real bug caught by
    # testing this against privacy-policy.md directly: 723 chars back instead of the ~11,000 the
    # document actually has).
    m = re.search(rf"^## {marker}\s*\n", text, re.MULTILINE)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^## (?:العربية|English)\s*$", text[start:], re.MULTILINE)
    body = text[start:start + nxt.start()] if nxt else text[start:]
    return body.rstrip().removesuffix("---").rstrip()

md_ar, md_en = section("العربية"), section("English")

requires_accept = False
try:
    import yaml
    d = yaml.safe_load(open(yaml_src, encoding="utf-8")) or {}
    requires_accept = d.get("publication") == "accept"
except FileNotFoundError:
    pass

print(json.dumps({
    "content": {"title": {"ar": title_ar, "en": title_en},
               "blocks": [{"legal_text": {"md_ar": md_ar, "md_en": md_en}}]},
    "requires_acceptance": requires_accept,
}, ensure_ascii=False))
PY
)
  [ -n "$draft_body" ] || { red "$doc_id.md: unreadable"; : > "$FAILMARK"; continue; }

  # PUT ONLY — NEVER A publish CALL HERE. Drafting a version is reversible (it is not yet live to
  # anyone); publishing is not, and is exactly the one act this script leaves entirely to a human
  # in AdminLegal.tsx, confirm dialog and all — see this file's own header.
  #
  # base64, NOT `'''$draft_body'''`. This crosses TWO shells (this one, then whatever ssh runs
  # remotely inside cluster.sh's kubectl() wrapper) before a THIRD process (the remote python3)
  # ever reads it — three chances for a quote, a backslash or a real document's own apostrophe to
  # be read as syntax instead of data. base64 has no character any of those three layers treats
  # specially, so it crosses all three unchanged; the remote side decodes it, never re-parses it.
  body_b64=$(printf '%s' "$draft_body" | base64 -w0 2>/dev/null || printf '%s' "$draft_body" | base64)
  out=$(kubectl -n "$NS" exec -i "$POD" -- python3 - "$doc_id" "$VERSION" "$TOKEN" "$body_b64" <<PY 2>/dev/null
import base64, json, sys, urllib.error, urllib.request
doc_id, ver, token, body_b64 = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
body = json.loads(base64.b64decode(body_b64))
req = urllib.request.Request(
    f"http://127.0.0.1:8000/api/v1/compliance/legal/{doc_id}/versions/{ver}",
    data=json.dumps(body).encode(), method="PUT",
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
    2*)   grn "$doc_id v$VERSION drafted" ;;
    409*) grn "$doc_id v$VERSION already published — draft a new version to change it" ;;
    *)    red "$doc_id v$VERSION — ${out:-no answer}"; : > "$FAILMARK" ;;
  esac
done

inf ""
inf "affiliate-agreement.md was NOT touched — it needs a licensed Saudi lawyer's review first"
inf "(its own YAML source says so)."
inf ""
inf "Every document above is a DRAFT, not yet live. Open المستندات القانونية in the admin"
inf "console, review each one, and publish the ones you want live — this script never does."

[ "$DRY" = "1" ] && exit 0
if [ -e "$FAILMARK" ]; then
  rm -f "$FAILMARK"
  red "some documents were refused — see above."
  exit 1
fi
grn "the legal library is drafted — nothing is live until you publish it from the admin console"
