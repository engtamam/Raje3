"""portal — erasing a data subject, from a service that holds none.

THIS SERVICE STORES NOTHING ABOUT ANYBODY. It renders a page by reading other services: the shop's
identity from tenant-service, the visits from operations, the preferences from reminders. There is
no customer row here, no schedule, no ledger — nothing a deletion request could delete.

SO WHY IMPLEMENT THE CONTRACT AT ALL?

Because "holds nothing" and "is not in the fan-out" look identical from the outside, and only one
of them is a decision. A service missing from PRIVACY_TARGETS is a service nobody asked — and
nobody can tell, later, whether it was omitted because it holds nothing or because somebody forgot.
Registering it and answering honestly turns a silence into a record: asked, answered, held nothing.

It also survives the day this stops being true. The moment someone adds a cache with a name in it,
the endpoint is already wired and already called, and the change is one line here rather than a
service-shaped gap discovered during an audit.

WHAT IT MUST NOT DO: forward the erasure. It would be tempting to have this call operations and
reminders on the subject's behalf, since it already talks to both. That would be a second fan-out
racing the real one, with its own partial failures and no record — compliance-service owns the
fan-out, and a page must not quietly become an orchestrator.
"""
from __future__ import annotations

from typing import Any


class PortalErasure:
    """The privacy-erase contract for a service with no storage."""

    def __init__(self, *, store=None, max_scan: int = 0) -> None:
        # The store is accepted and ignored. The signature matches every other service's so the
        # composition root stays uniform — and so the day this service does hold something, the
        # wiring does not have to change too.
        self._s = store

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        """Answer honestly, and idempotently.

        `already_absent` is True on every call, which is the truthful answer rather than a
        convenient one: there was nothing here before the request and nothing after it.
        """
        return {
            "service": "portal",
            "category": "presentation",
            "subject_ref": subject,
            "erased": [],
            "retained": [],
            "already_absent": True,
            "truncated": False,
            "note": "portal stores no personal data — it renders what operations, reminders and "
                    "tenant-service hold. This ack records that the request reached a service "
                    "that had nothing to delete, which is different from a service nobody asked.",
        }
