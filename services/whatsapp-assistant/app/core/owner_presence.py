"""COEXISTENCE's actual behaviour change: when the shop owner replies to a customer from their OWN
phone, the AI must go quiet on that one conversation for a while, not keep answering on top of them.

Without this, coexistence would only be a compliance nicety (we technically saw the echo) while the
customer's actual experience got worse — a human answer immediately followed by a bot answer to the
same message reads as broken, not helpful. So every message echo notes "the owner is handling this"
for a bounded cooldown, and app/core/inbound_ingest.py checks it before sending an auto-reply — the
message is still read, still logged, the conversation still advances; only the SEND is suppressed.

BOUNDED, NEVER PERMANENT: a cooldown that never expired would mean one manual reply silences the
assistant on that customer forever, which is a worse failure than the one this fixes. Keyed by
(tenant, contact) — the same customer number — not by wamid, so it is one small row per active
hand-off, not one per message.
"""
from __future__ import annotations

from typing import Any

_OWNER_ACTIVE = "wa_owner_active"


def _key(tenant: str, contact: str) -> str:
    # LENGTH-PREFIXED, same convention as CoexistenceStore.record_contact on the platform — tenant
    # and contact are both attacker-influenceable-length strings, and a plain "tenant|contact" join
    # could collide across a tenant/contact boundary (tenant="a|b", contact="c" vs tenant="a",
    # contact="b|c"). Never actually reachable here (tenant is ours, contact is E.164), but the cost
    # of getting it right is one f-string.
    return f"{len(tenant)}:{tenant}|{contact}"


async def note_owner_reply(container: Any, *, tenant: str, contact: str, now: int,
                           cooldown_seconds: int) -> None:
    """Record that the owner just answered `contact` by hand. A cooldown_seconds<=0 is a no-op —
    the caller (coexistence poll) treats that as "the feature is configured off", never as
    "silence forever"."""
    if not tenant or not contact or cooldown_seconds <= 0:
        return
    await container.datastore.put(_OWNER_ACTIVE, _key(tenant, contact), {
        "id": _key(tenant, contact), "tenant": tenant, "contact": contact,
        "until": now + cooldown_seconds})


async def is_owner_active(container: Any, *, tenant: str, contact: str, now: int) -> bool:
    """True while the owner's own hand-off cooldown for `contact` has not yet expired. A store this
    fails to reach reads as False — the assistant answering when it did not strictly need to is the
    safe failure; going silent because a lookup errored is not."""
    if not tenant or not contact:
        return False
    try:
        row = await container.datastore.get(_OWNER_ACTIVE, _key(tenant, contact))
    except Exception:                                                    # noqa: BLE001
        return False
    if not row:
        return False
    return int(row.get("until") or 0) > now
