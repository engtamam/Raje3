"""The port this service talks to notification-service through.

A PORT AND NOT A DIRECT CALL, for one concrete reason: the tick is the most important loop on the
product and it must be testable without a running peer. Every test in test_tick.py drives a fake
that implements this protocol, which is why the ordering guarantees — claim before send, key before
call, ledger after — are asserted rather than hoped for.

WHAT CROSSES THIS BOUNDARY, AND WHAT NEVER DOES. A `subject_ref`, a template name, and positional
variables. No phone number: this service does not have one and must not acquire one. The recipient
is resolved on the other side, from the same pseudonym operations published — which means a leak of
this service's database, its logs, or its traces leaks nobody.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MessageSender(Protocol):
    async def send(self, *, tenant: str, subject_ref: str, template_name: str,
                   variables: list[str], cls: str, idempotency_key: str) -> str:
        """Deliver one templated message, and return the peer's handle for it.

        THE HANDLE IS WHY THIS RETURNS ANYTHING AT ALL. A WhatsApp delivery receipt arrives minutes
        or hours later, and it names the message by the peer's `delivery_id`. Without keeping that
        id on our own row, «هل وصلت؟» has no answer that is not a guess — and `read_at` sat on the
        send log, declared for this purpose, fed by nothing, for as long as the log existed.

        An empty string is a legitimate answer, and means «no handle»: a driver with no delivery
        record. It must not be confused with «not delivered yet».

        `idempotency_key` is generated and persisted by the caller BEFORE this is called, and
        reused verbatim on every retry. A timeout is not evidence that nothing was sent, and the
        customer must not pay for our uncertainty with a duplicate.

        Raising is the correct response to any failure. The tick reschedules; swallowing an error
        here would turn a peer outage into reminders that silently never happen.
        """
        ...
