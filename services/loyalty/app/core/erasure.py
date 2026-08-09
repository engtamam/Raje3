"""Erasing one person's points, and the one thing that is kept.

WHAT GOES: the balance, every ledger entry, and every redemption row. All three are keyed by
`subject_ref` and all three are that person's relationship with the shop — his points, his history,
his rewards. There is no argument for keeping any of it once he has asked to be forgotten.

AND THE TEMPTING ARGUMENT FOR KEEPING THE LEDGER IS WRONG. "It is a financial record" is true and
does not survive the question "a record of what?": it is a record of promises to one identified
person, and the shop's own accounting question — how much was granted, spent and expired — is
answered by the aggregate, which carries no identifier at all. So the aggregate is what is
retained, and it is retained because '43 rewards were given in March' identifies nobody.

IDEMPOTENT, because a DSAR retries. Erasing an already-erased subject reports `already_absent` and
succeeds; failing on the second call would stall a fan-out that is designed to be repeated.

BOUNDED, and a truncation is REPORTED rather than swallowed. A partial erasure acknowledged as
complete is the false ack this whole contract exists to prevent — and it is silent by construction,
because the caller sees a success either way.
"""
from __future__ import annotations

from typing import Any

from app.core.models import BALANCES, ENTRIES, REDEMPTIONS


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

        for collection in (ENTRIES, REDEMPTIONS):
            deleted = 0
            scanned = 0
            while True:
                rows, _ = await self._s.find(collection,
                                             {"tenant": tenant, "subject_ref": subject},
                                             limit=200, sort=("created_at", "asc"))
                rows = list(rows or [])
                if not rows:
                    break
                for row in rows:
                    await self._s.delete(collection, row["id"])
                    deleted += 1
                scanned += len(rows)
                if scanned >= self._max:
                    truncated = True
                    break
                if len(rows) < 200:
                    break
            if deleted:
                counts[collection] = deleted

        return {
            "service": self.service,
            "category": self.category,
            "subject_ref": subject,
            "erased": [f"{k}:{v}" for k, v in counts.items()],
            "retained": [{
                "what": "the establishment's aggregate loyalty totals",
                "basis": "operational_record",
                "why": "how many points were granted, spent and expired across the whole shop. "
                       "It carries no identifier — '43 rewards in March' identifies nobody — and "
                       "it is the shop's own accounting record rather than the customer's data.",
            }],
            "already_absent": not counts,
            "truncated": truncated,
        }
