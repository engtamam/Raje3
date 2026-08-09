"""campaigns — erasing a data subject.

WHAT THIS SERVICE HOLDS ABOUT A PERSON is a pseudonym in two places: the reached-ledger that stops
a standing campaign messaging them twice, and nothing else. The campaign itself is the shop's, and
the run is a count.

SO THE REACHED-LEDGER GOES, and the runs stay.

That split is the whole decision. Deleting the ledger row is right — it is a record that we
messaged this person, keyed to them, with no purpose once they are gone. Deleting the RUN would
destroy the establishment's own record of a campaign it sent, which is not the customer's personal
data to erase: "43 messages went out on Tuesday" identifies nobody.

AND THE ORDER MATTERS, as it did in reminders. The ledger is deleted, and the run counts are left
alone — there is no partial state here that could make us send MORE, because deleting a reached-row
only makes a future campaign eligible to reach them again, and a future campaign will ask the gate,
and the gate will find their erasure at the source.
"""
from __future__ import annotations

from typing import Any


class CampaignsErasure:
    """The privacy-erase contract for this service."""

    def __init__(self, *, store, max_scan: int = 5000) -> None:
        self._s = store
        self._max = max_scan

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        """Erase what this service holds about one subject. IDEMPOTENT."""
        if not tenant or not subject:
            return {"service": "campaigns", "erased": [], "retained": [],
                    "already_absent": True, "truncated": False,
                    "note": "tenant and subject are both required; nothing was scanned"}

        deleted = 0
        after = None
        scanned = 0
        truncated = False
        while True:
            rows, after = await self._s.find(
                "campaign_reached", {"tenant": tenant, "subject_ref": subject},
                limit=200, after=after, sort=("at", "asc"))
            if not rows:
                break
            for row in rows:
                key = f"{tenant}|{row.get('campaign_id','')}|{subject}"
                await self._s.delete("campaign_reached", key)
                deleted += 1
            scanned += len(rows)
            if scanned >= self._max:
                # Surfaced, not swallowed: a partial erasure reported as complete is the false ack
                # this contract exists to prevent.
                truncated = True
                break
            if not after:
                break

        return {
            "service": "campaigns",
            "category": "campaign_delivery",
            "subject_ref": subject,
            "erased": [f"campaign_reached:{deleted}"] if deleted else [],
            "retained": [{
                "what": "campaign run counts",
                "basis": "operational_record",
                "why": "the establishment's own record of a campaign it sent — how many messages "
                       "went out and how many were refused. It carries no identifier: '43 arrived "
                       "on Tuesday' identifies nobody, and it is not the customer's data to erase.",
            }],
            "already_absent": not deleted,
            "truncated": truncated,
        }
