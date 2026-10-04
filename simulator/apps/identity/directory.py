"""A tiny, real, internal-token-authenticated lookup against a spawned identity-service: resolve
a phone to the `person_id` a real membership was actually minted under. Needed ONLY because
services/operations' own `hire_member` response (`Operator.public()`) deliberately never returns
the raw identifier or the person_id — "the identifier itself is identity's and belongs in no
response of ours" (services/operations/app/core/models.py's own comment) — a real privacy
boundary, not an oversight this module works around by reaching into anything private; it asks
identity itself, over the same internal door a background job would use
(`GET /internal/tenancy/members`, platform/services/identity-service/app/api/internal.py).
"""
from __future__ import annotations

from simulator.common import httpclient
from simulator.shared.service_env import INTERNAL_SERVICE_TOKEN


def _canonical_saudi_phone(raw: str) -> str:
    """The same "0XXXXXXXXX -> +966XXXXXXXXX" transform services/operations' own
    `canonical_phone(phone, default_cc="966")` applies before ever calling identity — this module
    only needs to construct the SAME lookup key identity actually stored the member under, not
    reimplement phone validation generally."""
    digits = raw.strip()
    if digits.startswith("+"):
        return digits
    if digits.startswith("0"):
        return "+966" + digits[1:]
    return "+966" + digits


async def lookup_person_id(base_url: str, *, tenant: str, phone: str,
                           timeout: float = 10.0) -> str | None:
    """The real `person_id` a real `hire_member` call minted for this phone at this tenant, or
    `None` if no such member exists — read straight from identity-service's own member directory,
    never guessed or derived."""
    canonical = _canonical_saudi_phone(phone)
    r = await httpclient.request(
        "GET", f"{base_url}/internal/tenancy/members", params={"tenant": tenant},
        headers={"X-Internal-Token": INTERNAL_SERVICE_TOKEN}, timeout=timeout)
    r.raise_for_status()
    for member in r.json().get("members", []):
        if member.get("identifier") == canonical:
            return member.get("person_id")
    return None
