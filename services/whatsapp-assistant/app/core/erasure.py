"""whatsapp-assistant — erasing a data subject on request (DSAR), independent of the 30-day tick.

A customer may ask to be forgotten at any point — day one of a conversation, or day twenty-nine of
the CHAT_RETENTION_DAYS window. The scheduled purge in app/core/retention.py answers "this is old
enough to no longer be useful"; this module answers a different question, "this person asked", and
must not wait for the first to agree. Same target data (raw inbound messages + conversation state),
reached immediately rather than on a schedule — see app/api/internal.py's /internal/privacy/erase,
wired into compliance-service's DSAR fan-out exactly like services/reminders/app/core/erasure.py.
"""
from __future__ import annotations

from typing import Any

from app.core.models import CONVERSATIONS, PENDING_PROPOSALS


class WhatsAppAssistantErasure:
    """The privacy-erase contract for this service.

    IDEMPOTENT. A DSAR retries, and a fan-out that gets a 500 on the second call reports a failed
    erasure for data that is already gone — which is investigated as a leak and is not one.
    """

    def __init__(self, *, store: Any, inbound_store: Any, max_scan: int = 100_000) -> None:
        self._store = store
        self._inbound = inbound_store
        self._max_scan = max_scan

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        """Erase everything this service holds about one subject, immediately.

        `subject` is already the subject_ref — this service never sees the raw phone number
        (only the resolved pseudonym, see app/core/pii.py), so there is nothing to hash and no
        raw value this endpoint should ever be handed.
        """
        if not tenant or not subject:
            return {"service": "whatsapp-assistant", "erased": [], "retained": [],
                    "already_absent": True, "truncated": False,
                    "note": "tenant and subject are both required; nothing was scanned"}

        erased: list[str] = []
        truncated = False

        # RAW MESSAGES FIRST. Deleting the conversation row before the messages it belongs to
        # would leave the messages unreachable by subject_ref if this call is interrupted midway —
        # exactly the "half-finished erasure that looks fine" failure reminders' erasure module
        # warns about for its own ordering.
        deleted_msgs, msg_truncated = await self._inbound.purge_for_subject(
            tenant, subject, max_scan=self._max_scan)
        truncated = truncated or msg_truncated
        if deleted_msgs:
            erased.append(f"inbound_messages:{deleted_msgs}")

        # PENDING PROPOSALS. A tool call awaiting a button reply is still raw content about this
        # subject (a proposed booking time, a reward name) and has no value once they are erased —
        # nobody can confirm a proposal for a subject who no longer exists in this service.
        n, hit_ceiling = await self._delete_where(PENDING_PROPOSALS, tenant, subject)
        truncated = truncated or hit_ceiling
        if n:
            erased.append(f"{PENDING_PROPOSALS}:{n}")

        # CONVERSATION STATE LAST. It is the one row keyed directly by (tenant, subject_ref), so a
        # single delete rather than a scan — and last so an interruption before this point still
        # leaves the conversation row as the marker that more erasure work remains for this
        # subject, findable on retry rather than silently half-done.
        if await self._store.delete(CONVERSATIONS, f"{tenant}|{subject}"):
            erased.append(f"{CONVERSATIONS}:1")

        return {
            "service": "whatsapp-assistant",
            "category": "whatsapp_conversation",
            "subject_ref": subject,
            "erased": erased,
            "retained": [],
            "already_absent": not erased,
            "truncated": truncated,
        }

    async def _delete_where(self, collection: str, tenant: str, subject: str) -> tuple[int, bool]:
        """Delete every row in one collection for one subject. Bounded, same convention as
        services/reminders/app/core/erasure.py — a DSAR is rare but must never be an unbounded
        read, and hitting the ceiling is reported rather than silently leaving rows behind."""
        deleted = 0
        after: str | None = None
        scanned = 0
        while True:
            rows, after = await self._store.find(
                collection, {"tenant": tenant, "subject_ref": subject},
                limit=200, after=after, sort=("id", "asc"))
            if not rows:
                return deleted, False
            for row in rows:
                key = str(row.get("id") or "")
                if key:
                    await self._store.delete(collection, key)
                    deleted += 1
            scanned += len(rows)
            if scanned >= self._max_scan:
                return deleted, True
            if not after:
                return deleted, False
