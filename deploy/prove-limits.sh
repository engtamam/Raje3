#!/usr/bin/env bash
# Prove the per-customer limits on the cluster — against the running reminders (spec §5.8).
#
#   ./deploy/prove-limits.sh
#
# WHAT THE UNIT TESTS CANNOT SAY. `gate.py` is proven against fakes we wrote: our Limits, our
# clock, our send log. Every one of those is a thing the deployment can disagree with — the caps
# come from env vars, the window comes from env vars, and a values file with a typo in
# DAILY_TOTAL_CAP produces a service that enforces nothing while every test stays green. That is
# playbook 4.38 in a different costume: a green suite over a limit that is not there.
#
# So this calls the gate INSIDE the running pod, with the Limits that pod actually built from its
# own environment:
#
#   the first message of the day          -> allowed
#   the second, same customer, same day   -> held, with a reason and a time to return
#   a support reply                       -> allowed regardless; he started it
#
# AND NOT THROUGH /internal/reminders/eligibility, which was the first attempt and reads the wrong
# way for this: that route answers "will he receive it AT ALL", so a message the cap defers to
# tomorrow is reported as allowed — correct for a campaign preview, and the opposite of what a cap
# proof must see. The route is right; the question was.
#
# It writes send-log rows for a throwaway subject and deletes them at the end, so nothing real is
# touched. And it reads the caps out of the RUNNING pod's environment rather than assuming them —
# a proof that hardcodes the number it is checking proves the number, not the service.
set -uo pipefail

NS="${NS:-base-services}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

red(){ printf '  \e[31m✗ %s\e[0m\n' "$*" >&2; }
grn(){ printf '  \e[32m✔ %s\e[0m\n' "$*"; }
say(){ printf '\n\e[1m▸ %s\e[0m\n' "$*"; }

POD=$(kubectl -n "$NS" get pods --no-headers | awk '/^reminders-/ && $3=="Running" {print $1; exit}')
[ -n "$POD" ] || { red "reminders is not running"; exit 1; }

TOKEN=$(kubectl -n "$NS" get secret reminders-secrets \
        -o jsonpath='{.data.INTERNAL_SERVICE_TOKEN}' 2>/dev/null | base64 -d)
[ -n "$TOKEN" ] || { red "no internal token in reminders-secrets"; exit 1; }

# A subject_ref that is a pseudonym of nothing — it matches no real customer, and the rows it
# leaves behind are removed below.
TENANT="_prove_limits"
SUBJECT="prove_limits_subject_0000000000"

say "the caps this pod actually runs on"
kubectl -n "$NS" exec "$POD" -- printenv DAILY_TOTAL_CAP DAILY_SERVICE_CAP \
  MONTHLY_MARKETING_CAP MARKETING_COOLDOWN_HOURS 2>/dev/null | paste -sd' ' - | sed 's/^/    /'

# Everything below runs INSIDE the pod: the datastore is reachable from there and from nowhere
# else, and the eligibility route is internal-tier by design.
kubectl -n "$NS" exec -i "$POD" -- env TOKEN="$TOKEN" TENANT="$TENANT" SUBJECT="$SUBJECT" python3 - <<'PY'
import asyncio, os, time

TENANT, SUBJECT = os.environ["TENANT"], os.environ["SUBJECT"]
ok = True


def check(label: str, got: bool, want: bool, detail: str = "") -> None:
    global ok
    if got == want:
        print(f"  \033[32m✔ {label}\033[0m" + (f" — {detail}" if detail else ""))
    else:
        ok = False
        print(f"  \033[31m✗ {label}: expected {'allowed' if want else 'refused'}, "
              f"got {'allowed' if got else 'refused'} {detail}\033[0m")


async def main() -> int:
    global ok
    from app.container import build_container
    from app.config import get_settings
    from app.core import engagement as E
    from app.core import gate as G
    from app.core.models import SendLog, as_row
    from app.core.stores import SendLogStore

    s = get_settings()
    c = build_container(s)
    log = SendLogStore(c.datastore)
    now = int(time.time())

    # THE LIMITS THIS POD BUILT FROM ITS OWN ENVIRONMENT — which is the whole point. A values file
    # with a typo produces a service enforcing nothing while every unit test stays green, because
    # the tests construct their own Limits.
    limits = G.Limits(window_start_hour=s.SEND_WINDOW_START_HOUR,
                      window_end_hour=s.SEND_WINDOW_END_HOUR,
                      daily_service_cap=s.DAILY_SERVICE_CAP,
                      monthly_marketing_cap=s.MONTHLY_MARKETING_CAP,
                      monthly_awareness_cap=s.MONTHLY_AWARENESS_CAP,
                      marketing_cooldown_hours=s.MARKETING_COOLDOWN_HOURS,
                      daily_total_cap=s.DAILY_TOTAL_CAP)
    eng_cfg = E.EngagementConfig(half_life_days=s.ENGAGEMENT_HALF_LIFE_DAYS,
                                 full_threshold=s.ENGAGEMENT_FULL_THRESHOLD,
                                 minimal_threshold=s.ENGAGEMENT_MINIMAL_THRESHOLD)

    # MIDDAY, NOT NOW. The window is a separate rule with its own proof; running this at 2am would
    # fail every check for a reason that has nothing to do with caps.
    noon = now - (now % 86400) + 9 * 3600

    async def ask(cls: str):
        recent = await log.since(TENANT, SUBJECT, since=noon - 31 * 86400)
        return G.evaluate(cls=cls, template_type="", now=noon, limits=limits,
                          prefs_stopped={}, engagement_score=99.0, engagement_at=noon,
                          recent_sends=recent, eng_cfg=eng_cfg, class_enabled=True)

    # ── a customer nobody has messaged ────────────────────────────────────────────────────────
    print("\n\033[1m▸ nothing sent yet\033[0m")
    d = await ask("service")
    check("the first service message of the day is allowed", d.allowed, True)

    # ── one already sent today ────────────────────────────────────────────────────────────────
    # THE ROW IS THE INPUT. The gate reads the send log and nothing else, so writing one row is
    # the honest way to put the service in the state this proof is about.
    await log.append(TENANT, as_row(SendLog(tenant=TENANT, subject_ref=SUBJECT, cls="service",
                                            at=noon - 3600, outcome="sent")))
    print("\n\033[1m▸ one message already sent today\033[0m")
    d = await ask("service")
    check("a second the same day is held", d.allowed, False, d.reason)
    # HELD, NOT KILLED. A service reminder the cap stops must come back tomorrow — dropping it
    # loses a visit's reminder entirely, and "wait" and "never" are answers an owner must be able
    # to tell apart in «رسائلي».
    if not d.allowed:
        check("and it is deferred rather than dropped", bool(d.retry_at), True)
        if not d.reason:
            ok = False
            print("  \033[31m✗ held with no reason — «رسائلي» shows a gap and no cause\033[0m")

    # ── the reply the customer started ────────────────────────────────────────────────────────
    print("\n\033[1m▸ a class the caps never touch\033[0m")
    d = await ask("personal")
    check("a support reply still goes through", d.allowed, True,
          "silencing his own answer is not protecting him")

    # ── clean up ─────────────────────────────────────────────────────────────────────────────
    rows = await log.since(TENANT, SUBJECT, since=noon - 86400)
    for row in rows:
        await c.datastore.delete("send_log", f"{TENANT}|{row.get('id')}")
    print(f"\n  removed {len(rows)} row(s) written by this proof")

    return 0 if ok else 1


raise SystemExit(asyncio.run(main()))
PY
rc=$?
[ $rc -eq 0 ] && grn "the per-customer limits hold on the running service" \
              || red "a limit did not behave as specified — see above"
exit $rc
