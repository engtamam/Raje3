#!/usr/bin/env bash
# Prove the follow-up ladder ON THE CLUSTER, not in the test suite.
#
#   bash deploy/prove-ladder.sh
#
# WHY THIS EXISTS SEPARATELY FROM THE UNIT TESTS. `core/ladder.py` has ten of them and they all
# pass; that proves the arithmetic. It does not prove the one thing that was actually wrong for
# weeks — that anything CALLS it. The module was written, tested, correct, and wired to nothing:
# no customer would ever have received a second message, and every test was green the whole time.
# That failure is invisible to a unit test by construction, so it is checked here instead.
#
# IT RUNS THE REAL TICK, against the real datastore, inside the running pod. What is faked is the
# clock and the sender — the clock because a reminder due in ninety days cannot be waited for, and
# the sender because Meta is not connected yet and a ladder must be provable before the first real
# message goes out. Everything between them is the shipped code path.
#
# AND IT CLEANS UP AFTER ITSELF. It writes into a tenant of its own making, and deletes it.
set -euo pipefail
NS="${NS:-base-services}"
SSH="${SSH:-ssh -o StrictHostKeyChecking=no -p 2224 tamam@127.0.0.1}"

C_G=$'\e[32m'; C_R=$'\e[31m'; C_C=$'\e[36m'; C_N=$'\e[0m'
echo -e "${C_C}━━━ the follow-up ladder, on the cluster ━━━${C_N}"

$SSH "kubectl -n $NS exec -i deploy/reminders -- python3 -" <<'PY'
import asyncio, sys, time
sys.path.insert(0, "/app")

from app.config import get_settings
from app.container import build_container
from app.core.tick import Tick
from app.core import gate as G, engagement as E
from app.core.stores import RuleStore, ScheduleStore, SCHEDULES

TENANT = "t_prove_ladder"
SUBJECT = "sub_prove_ladder"
SERVICE = "srv_prove_ladder"
NOW = 1800000000          # a fixed instant: the assertions below are arithmetic, not "recently"


class Sender:
    """Accepts everything and remembers it. The ladder is scheduled only after a SUCCESSFUL send,
    so a sender that refuses would prove nothing — and one that lies about failing would prove the
    wrong branch."""

    def __init__(self):
        self.sent = []

    async def send(self, *a, **k):
        self.sent.append((a, k))
        return {"ok": True, "message_id": f"m{len(self.sent)}"}


async def main() -> int:
    s = get_settings()
    c = build_container(s)
    store = c.datastore

    # THE RULE THE LADDER READS: a 60-day cycle, so the rung spacing is a number we can name.
    await RuleStore(store).upsert(TENANT, f"{TENANT}|{SUBJECT}|{SERVICE}", {
        "tenant": TENANT, "subject_ref": SUBJECT, "service_id": SERVICE,
        "interval_days": 60, "first_rung_returns": 0,
    })

    tick = Tick(store=store, sender=Sender(), limits=G.Limits(), eng_cfg=E.EngagementConfig())

    row = {
        "id": "sch_prove_ladder", "tenant": TENANT, "subject_ref": SUBJECT,
        "service_id": SERVICE, "kind": "reminder", "state": "pending",
        "due_at": NOW, "cls": "service", "template": "svc_due_soon",
    }
    # THROUGH THE STORE, under the key the tick itself would use. Writing the row by hand into
    # a collection whose name I guessed is what made the first run of this script report the
    # ladder broken when it was not — the probe was wrong, and it accused the code.
    await ScheduleStore(store).upsert(TENANT, f"{TENANT}|{SUBJECT}|{SERVICE}|reminder", row)

    await tick._ladder(TENANT, row, SUBJECT, now=NOW, cls="service")

    rows = await store.scan_all(SCHEDULES, 5000)
    rungs = sorted(
        (r for r in rows if r.get("tenant") == TENANT and str(r.get("kind", "")).startswith("ladder_")),
        key=lambda r: r["due_at"])

    ok = True
    if not rungs:
        print("  ✗ nothing scheduled — the ladder is wired to nothing again")
        ok = False
    else:
        print(f"  rungs written: {len(rungs)}")
        for r in rungs:
            days = (r["due_at"] - NOW) / 86400
            print(f"    {r['kind']}: +{days:.0f}d  cls={r.get('cls')}  tone={r.get('tone_index')}")

        # 15% OF THE LEARNED CYCLE BETWEEN RUNGS (§5.6.1) — 60 days gives 9, which is the whole
        # point of variation-not-escalation: the gaps are a property of HIS cycle, not a constant.
        # 15% OF A 60-DAY CYCLE IS 9 DAYS, and the FIRST rung is that far from the send — which
        # is the assertion that matters even when there is only one rung. Without consent the
        # marketing rung is dropped rather than substituted (§8.5), so one rung is the correct
        # count here, and a script that only checked the GAPS would pass on an empty ladder.
        first = round((rungs[0]["due_at"] - NOW) / 86400)
        if first != 9:
            print(f"  ✗ first rung is +{first}d, expected +9d (15% of a 60-day cycle)")
            ok = False
        gaps = [round((b["due_at"] - a["due_at"]) / 86400) for a, b in zip(rungs, rungs[1:])]
        if gaps and any(g != 9 for g in gaps):
            print(f"  ✗ rung spacing is {gaps}, expected 9 days")
            ok = False

        # NO TWO RUNGS SHARE A KIND. The schedule's natural key is (tenant, customer, service,
        # kind); two rungs called the same thing would be one row, and the second would silently
        # replace the first — a ladder that looks scheduled and sends once.
        kinds = [r["kind"] for r in rungs]
        if len(set(kinds)) != len(kinds):
            print(f"  ✗ two rungs share a kind: {kinds}")
            ok = False

        # AND WITHOUT CONSENT NOTHING MARKETING IS SCHEDULED. This tenant never granted any, so a
        # marketing rung here would be a message we are not allowed to send (§8.5).
        if any(r.get("cls") == "marketing" for r in rungs):
            print("  ✗ a marketing rung was scheduled for a customer who never consented")
            ok = False

    # ── the two rules the first case cannot reach ────────────────────────────────────────────
    #
    # WITH CONSENT the ladder gains its marketing rung, and WITH TWO FIRST-RUNG RETURNS it locks.
    # Both are read from stored state by `_ladder` itself, so they are exercised here rather than
    # asserted against `L.build` — the arithmetic already has ten unit tests, and what is unproven
    # is that this code reads the right rows.
    from app.core.consent import Consent
    # `record`, and `field_screen` — the service refuses a source it does not recognise, which
    # is correct: "where did this consent come from" answered with a word somebody invented is
    # not an answer. My first attempt invented one.
    await Consent(store).record(TENANT, SUBJECT, state="granted", source="field_screen")
    for r in list(rows):
        if r.get("tenant") == TENANT and str(r.get("kind", "")).startswith("ladder_"):
            await store.delete(SCHEDULES, f"{TENANT}|{SUBJECT}|{SERVICE}|{r['kind']}")

    await tick._ladder(TENANT, row, SUBJECT, now=NOW, cls="service")
    granted = [r for r in await store.scan_all(SCHEDULES, 5000)
               if r.get("tenant") == TENANT and str(r.get("kind", "")).startswith("ladder_")]
    marketing = [r for r in granted if r.get("cls") == "marketing"]
    print(f"  with consent: {len(granted)} rungs, {len(marketing)} of them marketing")
    if not marketing:
        print("  ✗ consent was granted and no marketing rung was scheduled — the rung is lost, "
              "not gained")
        ok = False

    # THE LOCK (§5.6.1): two returns on the first rung and the shop stops paying for the rest.
    await RuleStore(store).upsert(TENANT, f"{TENANT}|{SUBJECT}|{SERVICE}", {
        "tenant": TENANT, "subject_ref": SUBJECT, "service_id": SERVICE,
        "interval_days": 60, "first_rung_returns": 2,
    })
    for r in granted:
        await store.delete(SCHEDULES, f"{TENANT}|{SUBJECT}|{SERVICE}|{r['kind']}")
    await tick._ladder(TENANT, row, SUBJECT, now=NOW, cls="service")
    locked = [r for r in await store.scan_all(SCHEDULES, 5000)
              if r.get("tenant") == TENANT and str(r.get("kind", "")).startswith("ladder_")]
    print(f"  after two first-rung returns: {len(locked)} rung(s)")
    if len(locked) >= len(granted):
        print("  ✗ the lock did not bite — he is still paying for the whole ladder")
        ok = False

    rows = await store.scan_all(SCHEDULES, 5000)
    for r in rows:
        if r.get("tenant") == TENANT:
            await store.delete(SCHEDULES, f"{r.get('tenant','')}|{r.get('subject_ref','')}|{r.get('service_id','')}|{r.get('kind','')}")
    await store.delete("rules", f"{TENANT}|{SUBJECT}|{SERVICE}")

    print("  ✔ the ladder is called, spaced from his cycle, and silent without consent"
          if ok else "  ✗ FAILED")
    return 0 if ok else 1


raise SystemExit(asyncio.run(main()))
PY

echo -e "${C_G}✔ ladder proven live${C_N}"
