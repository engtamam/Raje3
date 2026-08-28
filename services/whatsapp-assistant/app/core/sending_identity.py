"""The inverse half of operations-service's `sending_identity.py` — kept here as our own copy
rather than a shared import, same convention every port/adapter in this scaffold already follows
(see app/ports/consent_gate.py's own note on why: every service here is self-contained by design).

WHY THIS SERVICE NEEDS IT AT ALL. `tenant` for a shop sending from one number, `tenant:branch_id`
for a chain whose branches each have their own (operations' `core/sending_identity.py` mints this
string when a per-branch shop connects WhatsApp; notification-service's WhatsAppNumberIndex binds
`phone_number_id -> that string` and hands it straight back on every inbound message as the
row's own "tenant" field). Every inbound message this service receives — from the live bus AND
the durable catch-up poll — carries that string, verbatim, in what both callers name `tenant`.

FOUND BY READING, NOT ASSUMED: before this file existed, app/core/inbound_ingest.py treated that
string as a single opaque tenant id everywhere — for a central shop that is exactly right (the
string IS the tenant, no branch was ever appended); for a per-branch shop it silently fed the
COMPOSITE string to every peer call (consent_gate, customer_lookup, wallet, bookings) as if it
were a real tenant id, and threw away the one piece of information (which branch's number this
customer actually messaged) most needed to answer "which branch are we booking at" without ever
asking.
"""
from __future__ import annotations

SEPARATOR = ":"


def split(sending_identity: str) -> tuple[str, str]:
    """`(tenant, branch_id)` — `branch_id` is `""` for a central shop's identity (nothing to
    split) or for anything empty/malformed. Never raises: a string this service did not mint
    itself is handled as leniently as operations' own inverse function handles it."""
    value = (sending_identity or "").strip()
    if not value:
        return "", ""
    tenant, sep, branch = value.partition(SEPARATOR)
    return tenant, branch if sep else ""
