"""Erasing one person's points — and NOT the receipt of what he redeemed.

A customer redeems a real reward — cost, branch, when, who approved it — asks
to be forgotten, and later disputes something ("I was never given that free wash", or the shop's
own bookkeeping needs to explain a discount it gave). Answering that dispute needs the receipt to
still exist. This file used to argue the opposite ("the aggregate is what is retained") and then
never actually kept one — it just deleted every REDEMPTIONS and ENTRIES row outright, so the
argument was never true in the code, only in the comment.

THE ACTUAL SPLIT, matching operations' own erasure exactly (a Customer row's phone/name blanked,
its Visit rows kept):

  Balance      DELETED. A live running total has no receipt value once the person is gone — it is
               the identity record, not the history.

  LedgerEntry  KEPT, subject_ref BLANKED. "Append-only... the truth" (core/models.py's own words)
               — the movement (delta, reason, branch, balance_after, timestamp) is the shop's own
               accounting trail. Deleting it destroyed the very aggregate the old comment claimed
               was retained.

  Redemption   KEPT, subject_ref BLANKED. reward_name, cost, branch_id, approved_by, created_at —
               a RECEIPT, by the model's own docstring ("not a reference... a receipt"). This is
               exactly the record that answers a later dispute; deleting it left the platform with
               no defence against the customer's own complaint, or against a false one.

Both are found by `subject_ref` before erasure and re-saved with it replaced by a REDACTED marker
— never a real pseudonym, so a later query for the real subject_ref can never re-associate the row
with him, and the row can never collide with a genuine future subject_ref either.

IDEMPOTENT, because a DSAR retries. Erasing an already-erased subject reports `already_absent` and
succeeds; failing on the second call would stall a fan-out that is designed to be repeated.

BOUNDED, and a truncation is REPORTED rather than swallowed. A partial erasure acknowledged as
complete is the false ack this whole contract exists to prevent — and it is silent by construction,
because the caller sees a success either way.
"""
from __future__ import annotations

from typing import Any

from app.core.models import BALANCES, ENTRIES, REDEMPTIONS

_REDACTED = "[erased]"


class TemplateErasure:
    # Must match the data-map row registered for this service in compliance-service. A mismatch
    # means the DSAR waits for an ack that never arrives — and waits without erroring.
    service = "loyalty"
    category = "loyalty_balance"

    def __init__(self, *, store, pii_salt: str, max_scan: int = 100_000) -> None:
        self._s = store
        self._salt = pii_salt
        self._max = max_scan

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        """`subject` is the SUBJECT_REF — the pseudonym, which is all this service ever holds.

        It never receives a raw identifier, so there is nothing here to hash: the caller
        (compliance-service) fans out the same pseudonym every peer already knows the person by.
        """
        if not tenant or not subject:
            return {"service": self.service, "erased": [], "retained": [],
                    "already_absent": True, "truncated": False,
                    "note": "tenant and subject are both required; nothing was scanned"}

        counts: dict[str, int] = {}
        truncated = False

        # The balance is a single natural key — no scan needed, and no scan possible to get wrong.
        if await self._s.get(BALANCES, f"{tenant}|{subject}"):
            await self._s.delete(BALANCES, f"{tenant}|{subject}")
            counts[BALANCES] = 1

        # BLANKED, NOT DELETED — see the module docstring. Both collections are keyed by their
        # own `id` (core/ledger.py::record, core/redeem.py::redeem both call
        # `store.put(COLLECTION, row.id, row.to_dict())`), so re-saving under the same key
        # overwrites in place rather than creating a second row.
        retained_counts: dict[str, int] = {}
        for collection in (ENTRIES, REDEMPTIONS):
            touched = 0
            scanned = 0
            while True:
                rows, _ = await self._s.find(collection,
                                             {"tenant": tenant, "subject_ref": subject},
                                             limit=200, sort=("created_at", "asc"))
                rows = list(rows or [])
                if not rows:
                    break
                for row in rows:
                    if row.get("subject_ref") == _REDACTED:
                        continue   # already processed by an earlier, truncated run
                    row["subject_ref"] = _REDACTED
                    await self._s.put(collection, row["id"], row)
                    touched += 1
                scanned += len(rows)
                if scanned >= self._max:
                    truncated = True
                    break
                if len(rows) < 200:
                    break
            if touched:
                retained_counts[collection] = touched

        return {
            "service": self.service,
            "category": self.category,
            "subject_ref": subject,
            "erased": [f"{k}:{v}" for k, v in counts.items()],
            "retained": (
                [{"what": f"{k}:{v}", "basis": "financial_record",
                  "why": "the shop's own receipt — reward, cost, branch and when it was given "
                        "(or the ledger movement that produced it). The customer's identifier is "
                        "removed; the receipt itself answers a later dispute about what was "
                        "actually granted, and is not the customer's personal data to erase."}
                 for k, v in retained_counts.items()]
            ),
            "already_absent": not counts and not retained_counts,
            "truncated": truncated,
        }
