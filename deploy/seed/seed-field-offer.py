"""Put ONE live offer on a known customer, so the counter screen can be checked against it.

    TENANT=<tenant> SUBJECT=<subject_ref> BRANCH=<branch_id> \
      kubectl -n base-services exec -i deploy/reminders -- python - < deploy/seed/seed-field-offer.py

WHY A SEED AND NOT A TEST FIXTURE. An offer is created by a SEND — it is the send log that records
the entitlement (§5.6.2), which is the whole reason the offer cannot be forged by a screen. So the
browser has no way to produce one: there is no owner-facing "grant this person an offer" action,
and there should not be. This writes the same row a real send writes, through the same store.

THE PHONE IS FIXED AND THE PSEUDONYM IS DERIVED FROM IT, exactly as operations derives it, because
reminders holds no phone numbers at all — only the HMAC pseudonym. A seed that invented a
subject_ref would create an offer belonging to nobody, and the screen would be right to show
nothing.

IDEMPOTENT: run it again and the same customer keeps one live offer, not two.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, "/app")

from app.config import get_settings          # noqa: E402
from app.container import build_container    # noqa: E402
from app.core.stores import SendLogStore     # noqa: E402

TENANT = os.environ.get("TENANT", "")
SUBJECT = os.environ.get("SUBJECT", "")
BRANCH = os.environ.get("BRANCH", "")
TEXT = os.environ.get("OFFER_TEXT", "غسلة مجانية مع أول زيارة هذا الشهر")
DAYS = int(os.environ.get("OFFER_DAYS", "14"))
# Catalogue service ids this offer applies to — empty means unscoped (every service). Comma-separated
# so a demo/tour seed can pin the offer badge to ONE specific service without inventing a new field.
OFFER_SERVICES = [s for s in os.environ.get("OFFER_SERVICES", "").split(",") if s]


async def main() -> int:
    if not TENANT or not SUBJECT:
        print("TENANT and SUBJECT are required — the pseudonym comes from operations, not from here")
        return 1

    c = build_container(get_settings())
    log = SendLogStore(c.datastore)
    now = int(time.time())
    expires = now + DAYS * 86400

    # `now` IS REQUIRED — 'live' is a question about a moment, and a store that assumed one
    # would be deciding on its own clock what the caller meant by expired. `used_refs` is
    # required too now — an offer already redeemed on a past send is not "live" even if its
    # expiry hasn't passed, and this seed has no such history to exclude.
    live = await log.live_offers(TENANT, SUBJECT, used_refs=set(), now=now)
    if live:
        print(f"already holds {len(live)} live offer(s) — left alone")
        print(f"  «{live[0].get('offer_text', '')}»")
        return 0

    # THE ID IS THE CALLER'S — `append` keys by it and does not mint one. A send log row is a
    # record of something that happened, and the thing that happened knows its own identity.
    await log.append(TENANT, {
        "id": f"snd_seed_{SUBJECT[-12:]}_{now}",
        "tenant": TENANT,
        "subject_ref": SUBJECT,
        "kind": "campaign",
        "template": "mkt_offer",
        "outcome": "sent",  # active_offer()/live_offers() query on THIS field, not "state"
        "at": now,
        "created": now,
        # THE THREE FIELDS THAT MAKE IT AN ENTITLEMENT: the sentence that persuades, the end that
        # makes it urgent, and the scope that decides what it actually applies to.
        "offer_text": TEXT,
        "offer_expires_at": expires,
        "offer_services": OFFER_SERVICES,
        # THE OWNER-FACING ROUTE FILTERS EVERY SEND-LOG ROW BY BRANCH SCOPE — a row with no
        # branch_id is invisible to a caller scoped to one, exactly like a real send would be
        # if it forgot to stamp its branch.
        "branch_id": BRANCH,
    })
    print(f"offer written, expires in {DAYS} days: «{TEXT}»")
    return 0


raise SystemExit(asyncio.run(main()))
