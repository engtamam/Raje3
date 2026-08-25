"""InboundMessageStore port — the durable seam over a non-durable bus.

notification-service's EventBus is explicitly at-most-once, best-effort and non-durable (its own
ports/event_bus.py docstring says so in capitals): a redelivery, a restart mid-publish, or two
replicas of THIS service both subscribed can each see the same `whatsapp.message` event more than
once, or not at all.

The "not at all" half is out of our hands — there is no catch-up read for inbound messages on
notification-service (only for delivery receipts, via GET /internal/notifications/receipts). We
document that as an accepted platform gap rather than pretend to fix it (see the values file).

The "more than once" half IS ours to fix, and this port is how: every inbound message is persisted
here, KEYED BY META'S wamid, BEFORE any reply is composed or any tool is proposed. A redelivery
looks up its own wamid, finds it already `processed`, and is dropped — the conversation engine
never sees it twice.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class InboundMessageStore(Protocol):
    driver: str

    async def record_if_new(self, tenant: str, wamid: str, message: dict[str, Any]) -> bool:
        """Persist `message` under `wamid` iff it has not been seen before.

        Returns True the FIRST time a wamid is seen (caller should process it), False on every
        redelivery (caller must drop it). Must be atomic against a concurrent duplicate — two
        replicas racing on the same wamid must not both return True.
        """
        ...

    async def mark_processed(self, tenant: str, wamid: str) -> None: ...

    async def get(self, tenant: str, wamid: str) -> dict[str, Any] | None: ...

    async def attach_subject_ref(self, tenant: str, wamid: str, subject_ref: str) -> None:
        """Stamp the resolved subject_ref onto an already-recorded message.

        The message is persisted (record_if_new) BEFORE the customer lookup that resolves
        subject_ref runs — see app/main.py — so this is a second, best-effort write that makes the
        row findable by subject for retention (purge_for_subject) and DSAR erasure. A message that
        never gets this stamp (a crash between record and lookup) ages out anyway once
        CHAT_RETENTION_DAYS decides its whole conversation is due — it is not silently retained
        forever, only unreachable by subject_ref until then.
        """
        ...

    async def purge_for_subject(self, tenant: str, subject_ref: str, *, max_scan: int = 5000
                                ) -> tuple[int, bool]:
        """Delete every stored inbound message for one (tenant, subject_ref).

        Used by BOTH the retention tick (app/core/retention.py) and DSAR erasure (app/core/
        erasure.py) — the same purge, one on a schedule and one on request. Bounded by `max_scan`
        and REPORTS hitting it (the second element of the tuple) rather than silently leaving
        messages behind and claiming completion. Returns (deleted_count, truncated).
        """
        ...
