"""Turning a visit into points — the event path, and why it is idempotent by construction.

ONE LEDGER ENTRY PER VISIT, NOT ONE PER SERVICE (spec §9.2). A wash with three services writes one
row carrying the sum. The customer experienced one visit; a statement showing three lines for one
wash reads to him as a mistake, and the first thing he does about a mistake is ask the shop.

IDEMPOTENT ON THE VISIT ID, and that is not defensive coding. The event bus is at-most-once BY
CONTRACT — which means a consumer may be handed the same event twice as easily as never — so
"handle the redelivery" is the documented behaviour, not an edge case. `Ledger.post` refuses a
second movement with the same (source, reason), so the guarantee lives in one place rather than in
every caller that remembers.

A CATCH-UP PATH EXISTS FOR THE SAME REASON. At-most-once also means the event may never arrive at
all, so points cannot depend solely on the subscription: `catch_up()` reads visits since a
watermark and fills the gaps. Every consumer in this product needs one, and the two that shipped
without one were the two whose defects were found on the cluster rather than in a test.

INVOICE MODE (spec §9.3) EARNS FROM THE AMOUNT PAID, not the amount billed — the same distinction
partner-service already draws for commission, and for the same reason: a shop should not owe
loyalty points on an invoice the customer never settled.
"""
from __future__ import annotations

from typing import Any

from app.core.earning import EarnStore, EarnTree
from app.core.ledger import Ledger


class Earner:
    def __init__(self, ledger: Ledger, settings: EarnStore) -> None:
        self.ledger = ledger
        self.settings = settings

    async def from_visit(self, tenant: str, *, visit_id: str, subject_ref: str,
                         service_ids: list[str], amount_halalas: int = 0,
                         actor: str = "", branch_id: str = "",
                         tree: EarnTree | None = None) -> dict:
        """Award points for one visit. Returns what happened, and never raises for a redelivery.

        `amount_halalas` is used ONLY in invoice mode and ONLY when the establishment is integrated
        — the mode itself refuses to be set otherwise (`EarnConfig.validate`), so this function
        does not need to re-check the combination, and having one owner of that rule is the point.
        """
        if not subject_ref or not visit_id:
            return {"earned": 0, "reason": "missing subject or visit"}

        t = tree if tree is not None else await self.settings.load(tenant)
        cfg = t.config

        if cfg.mode == "invoice":
            # Whole riyals. A shop that grants "one point per riyal" and sees a customer earn 47
            # points on a 47.60 invoice understands the rule; fractional points would be a number
            # nobody can explain at the counter.
            points = (int(amount_halalas) // 100) * int(cfg.points_per_riyal)
            level = "invoice"
        else:
            points, level = t.points_for(list(service_ids or []))

        if points <= 0:
            # Not an error: an establishment can legitimately have set nothing yet, or set this
            # service to zero. Writing a zero entry would stamp `last_movement_at` and quietly
            # restart the expiry clock for a customer who earned nothing.
            return {"earned": 0, "reason": "no points configured", "rule_level": level}

        entry = await self.ledger.post(
            tenant=tenant, subject_ref=subject_ref, delta=points, reason="earn",
            source=visit_id, actor=actor, rule_level=level, branch_id=branch_id)
        if entry is None:
            return {"earned": 0, "duplicate": True, "reason": "already awarded for this visit"}
        return {"earned": points, "rule_level": level, "balance": entry.balance_after,
                "entry_id": entry.id}

    async def catch_up(self, tenant: str, visits: list[dict[str, Any]],
                       tree: EarnTree | None = None) -> dict:
        """Award points for visits the event never brought.

        Reads the SAME function as the subscription, deliberately: a catch-up with its own
        calculation is a second earning rule, and the second one is the one that drifts from the
        settings screen after somebody changes the first.
        """
        t = tree if tree is not None else await self.settings.load(tenant)
        awarded = skipped = 0
        for v in visits:
            res = await self.from_visit(
                tenant, visit_id=str(v.get("id") or v.get("visit_id") or ""),
                subject_ref=str(v.get("subject_ref") or ""),
                service_ids=list(v.get("service_ids") or []),
                amount_halalas=int(v.get("amount_halalas") or 0),
                actor=str(v.get("operator_id") or ""),
                branch_id=str(v.get("branch_id") or ""), tree=t)
            if res.get("earned"):
                awarded += 1
            else:
                skipped += 1
        return {"awarded": awarded, "skipped": skipped, "seen": len(visits)}
