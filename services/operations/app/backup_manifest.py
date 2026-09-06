"""What backup-service must capture to restore this service, and what it may skip.

A pure declaration, read as a literal — like admin_actions and auditable_actions. The
`safety:backup-coverage` gate checks this against the collections the code actually writes, so a
collection added later without a line here fails the build rather than being silently missing the
day a restore is needed.

FILL THIS as the generated service grows a datastore. Every collection the code writes must appear
either in `collections` (backed up) or `excluded` (skipped, with a reason a person can challenge).
There is no third state — the third state is a silent hole, which is the one thing a backup system
must never have. A brand-new service that writes nothing yet declares nothing yet, and that is
correct; the gate reports it as "not onboarded" rather than failing.

`tenant_scoped` on each collection tells a restore whether it may be restored for one tenant in
isolation, or only whole. Get it wrong toward False and a per-tenant restore refuses; wrong toward
True and it may restore rows that were never tenant-partitioned.
"""
from __future__ import annotations

from typing import Any

BACKUP: dict[str, Any] = {
    # No files. operations records what happened; it stores no blobs.
    "object_prefix": "",
    # Every one of these is tenant-scoped, and that matters for a restore: an establishment that
    # loses its data can be restored ALONE, without touching anyone else's rows. A whole-service
    # restore to recover one tenant would be a second outage caused by the recovery.
    "collections": [
        {"name": "customers", "tenant_scoped": True},
        {"name": "assets", "tenant_scoped": True},
        {"name": "services", "tenant_scoped": True},
        {"name": "visits", "tenant_scoped": True},
        {"name": "operators", "tenant_scoped": True},
        {"name": "branches", "tenant_scoped": True},
        # WHO BROUGHT EACH SHOP. Losing this loses the commission history, and there is no way to
        # reconstruct it: the stamp is the only record that a partner ever introduced a customer.
        {"name": "partner_stamps", "tenant_scoped": True},
        # Platform-scoped: one row per partner per month, under the reserved tenant. A per-tenant
        # restore must not be able to rewrite what we owe somebody.
        {"name": "commission_statements", "tenant_scoped": False},
        # ── DECLARED AFTER ج-2, AND EVERY ONE OF THESE WAS A SILENT HOLE ────────────────────
        # The gate that finds them (`platform/tools/ci/check_backup_coverage.py`) existed the
        # whole time and nothing ever pointed it at this repository. It does now.
        #
        # THE WORST OF THEM. A restore that brings back visits and leaves this empty is a shop
        # that reads «غير مربوط» and cannot send a single message, while the backup run that
        # produced the archive reported success.
        {"name": "whatsapp_connections", "tenant_scoped": True},
        # The shop's own template library — including texts Meta approved. Lose the rows and the
        # same NAME is submitted again with new content, which Meta refuses permanently: the name
        # is burned and cannot be recovered.
        {"name": "templates", "tenant_scoped": True},
        # WHO LAPSED AND WHEN. The retention clock reads it; restored empty, customers are either
        # swept early or kept with nothing to justify keeping them — and both are PDPL answers we
        # would have to give.
        {"name": "lapsed_since", "tenant_scoped": True},
        # Central or per-branch, and it changes what every screen shows.
        {"name": "shop_modes", "tenant_scoped": True},
        # A partner's claim on a shop it brought — the input to what we owe them.
        {"name": "partner_claims", "tenant_scoped": True},
        # The signup proofs. Losing them leaves an establishment whose ownership we cannot
        # evidence, and the index that stops one phone claiming two shops.
        {"name": "signup_phone_index", "tenant_scoped": False},
        {"name": "signup_tenant_proof", "tenant_scoped": True},
        # WHAT WE KNOW ABOUT A SHOP THAT THE SHOP DID NOT TELL US: whether its till has ever sent
        # an invoice, and whether it is a vendor's test shop. Losing the second bills somebody for
        # a demo; losing the first makes an integrated shop look like it types its own catalogue.
        {"name": "tenant_standing", "tenant_scoped": True},
        # AND WHETHER IT WORKS ON CARS — the one question we still ask, and the one the visit sheet
        # changes shape for. Losing it takes the plate page away from every tyre shop at once.
        {"name": "shop_vehicles", "tenant_scoped": True},
        # WHAT THE OWNER TOLD THE AI ASSISTANT about his own shop — losing it silently degrades
        # the WhatsApp bot back to generic answers, with no error anywhere to say why.
        {"name": "shop_ai_notes", "tenant_scoped": True},
        # THE CUSTOMER-MESSAGE WORD LIMIT — losing it silently resets a shop's own tightened/
        # loosened ceiling back to the default, with no error anywhere to say why.
        {"name": "shop_msg_word_limits", "tenant_scoped": True},
    ],
    # Nothing is excluded. The idempotency key lives ON the visit row rather than in a side table,
    # precisely so there is no collection anyone has to argue about — an excluded collection is a
    # judgement call, and the fewer of those a backup manifest carries the better.
    "excluded": [
        # The partner REGISTRY is platform-scoped, not tenant-scoped, and it holds hashed bearer
        # credentials. It is excluded from the per-tenant archive deliberately: a tenant restore
        # must never be able to write into it, and a tenant export must never carry it.
        {"name": "partners", "reason": "platform-scoped credential registry; backed up with "
                                       "the platform, never inside a tenant archive"},
        # A LIVENESS SIGNAL, NOT A RECORD. «When did this till last speak» is rebuilt by the
        # next request from the till; restoring a stale one would make a dead integration look
        # alive on the recovery screen, which is worse than an empty one.
        {"name": "till_health", "reason": "liveness signal, rebuilt by the next call from the "
                                          "till; a restored stale value reads as healthy"},
        # THE DAILY EXTRACTION BUDGET (ب-1). Counters keyed on the day. Restoring them would
        # carry yesterday's usage into today; letting them start empty gives a till its full
        # allowance on the day of a recovery, which is the direction that keeps the shop working.
        {"name": "till_lookup_counters", "reason": "per-day rate counters; restoring them would "
                                                   "apply an old day's usage to a new day"},
    ],
}
