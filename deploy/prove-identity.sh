#!/usr/bin/env bash
# The phone IS the identity — proven against the running cluster.
#
#   ./deploy/prove-identity.sh
#
# THE ASSERTION THAT MATTERS, AND THE ONE WE ESCALATED FOR. `0501234567`, `+966501234567` and
# `966501234567` are ONE human. If uniqueness or lookup keys on the raw string instead of the
# canonical form, the same person registers three times — and by the time anyone notices, three
# accounts hold three fragments of one shop's history and no migration can tell which is which.
#
# A CONFIG READ CANNOT PROVE THIS. IDENTITY_LOGIN_FIELD=phone says the adapter is selected; it says
# nothing about whether the second spelling collides with the first. Only registering twice does.
set -uo pipefail

NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

red(){ printf '  \e[31m%s\e[0m\n' "$*" >&2; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^identity-service-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "identity-service is not running"; exit 1; }

# NO BACKTICKS AND NO COMMAND SUBSTITUTION BELOW THIS LINE, INCLUDING IN COMMENTS.
kubectl -n "$NS" exec -i "$POD" -- python - <<'PY'
import json, sys, time, urllib.error, urllib.request
H = "http://localhost:8000"

def call(path, body=None, method=None, headers=None):
    d = json.dumps(body).encode() if body is not None else None
    h = dict(headers or {})
    if d:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(H + path, data=d, method=method or ("POST" if d else "GET"),
                               headers=h)
    try:
        u = urllib.request.urlopen(r, timeout=30)
        return u.status, json.loads(u.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()[:300]
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"_raw": raw}

fails = []
# THE FIELD IS `username`, WHATEVER THE LOGIN FIELD IS CONFIGURED TO HOLD. Sending `identifier`
# produced a bare 422 that read exactly like the number being rejected — and it made the email
# assertion below pass for the wrong reason, which is worse than failing: a proof that reports a
# green line it did not earn is a proof nobody should trust the rest of.
#
# A SAUDI MOBILE IS TEN DIGITS: 05 then eight more. The first version of this built nine and the
# service refused it with a bare 422 — which is the adapter being correct and the proof being
# wrong, and exactly the kind of failure that gets blamed on the service.
stamp = str(int(time.time()))[-8:].rjust(8, "0")
national = "05" + stamp
intl = "+966" + national[1:]
bare = "966" + national[1:]

# ── one human, three spellings ────────────────────────────────────────────────────────────────
s1, r1 = call("/api/v1/auth/register", {"username": national, "password": "Pr0veIdent!ty"})
if s1 >= 400:
    fails.append("could not register the national form " + national + ": " + str(s1) + " " + json.dumps(r1)[:160])
else:
    print("  ok a national number registers: " + national)

    for label, spelling in (("international", intl), ("bare country code", bare)):
        s2, r2 = call("/api/v1/auth/register", {"username": spelling, "password": "Pr0veIdent!ty"})
        if s2 < 400:
            fails.append("THE " + label.upper() + " SPELLING " + spelling +
                         " CREATED A SECOND ACCOUNT for the same person — uniqueness is keyed on "
                         "the raw string, not the canonical form")
        else:
            print("  ok the " + label + " spelling is refused as a duplicate: " + spelling)

# ── an email is not an identifier here ────────────────────────────────────────────────────────
# Not pedantry: if the field accepts anything, then "identity is the phone" is a description of
# what we hope users type rather than a property of the system.
s, r = call("/api/v1/auth/register", {"username": "someone@example.com", "password": "Pr0veIdent!ty"})
if s < 400:
    fails.append("an EMAIL registered while the login field is `phone` — the adapter is not enforcing")
else:
    print("  ok an email is refused while the login field is the phone")

# ── the OTP routes exist, and never hand back the code ────────────────────────────────────────
s, r = call("/api/v1/otp/request", {"identifier": national, "purpose": "verify"})
if s == 404:
    fails.append("/api/v1/otp/request is not served — the OTP axis is not deployed")
elif s >= 500:
    fails.append("/api/v1/otp/request answered " + str(s) + ": " + json.dumps(r)[:160])
else:
    print("  ok the OTP request route answers " + str(s))
    body = json.dumps(r)
    # THE WHOLE POINT OF A ONE-TIME CODE. If the response carries it, anyone who can call the
    # endpoint can prove control of a number they do not hold.
    if any(k in r for k in ("code", "otp", "secret")):
        fails.append("THE RESPONSE CARRIES THE CODE: " + body[:200])
    else:
        print("  ok the code never appears in the response")

s, r = call("/api/v1/otp/verify", {"identifier": national, "code": "000000", "purpose": "verify"})
if s == 404:
    fails.append("/api/v1/otp/verify is not served")
elif s < 400:
    fails.append("A GUESSED CODE VERIFIED — the code is not being checked at all")
else:
    print("  ok a guessed code is refused")

print("")
for f in fails:
    print("  ! " + f)
if not fails:
    print("  one human is one account whichever way the number is written, and the code is never returned")
sys.exit(1 if fails else 0)
PY
