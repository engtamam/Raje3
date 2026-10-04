"""A product photo, reachable with NO login at all — the one deliberate hole in this service's own
"every read below takes the tenant as a required argument" rule (`core/stores.py`'s own module
docstring), and why it lives in its own small, carefully-bounded file instead of quietly weakening
that rule inside `stores.py` itself.

WHY THIS MUST EXIST AT ALL. Meta's own Commerce Catalog API takes an `image_url` it crawls itself
(confirmed against Meta's own docs, 2026-10-03 — there is no binary-upload alternative for a batch
catalog sync); every existing image route on this service (`GET /staff/services/{id}/image`) is
gated behind a real login, which Meta's crawler does not have and cannot be given one.

THE SECURITY MODEL IS A CAPABILITY TOKEN, NEVER AN IDENTITY CHECK — the same shape a pre-signed
cloud-storage URL already uses, chosen deliberately over "make the route public but still take
`tenant`/`service_id`" for one reason: a tenant/service id is OUR OWN internal identifier, and
making it a lookup key anyone can query (even if only 404/200, no data) turns it into an existence
oracle an outsider could probe to learn which ids we use and how many a tenant has. A random,
unguessable, 256-bit token carries no information at all before it is known, and knowing it proves
nothing except having once legitimately received this exact URL (from US, when the image was set).

ROTATES ON EVERY RE-UPLOAD, NEVER REUSED. `issue()` always mints a FRESH token and the caller
(`staff.py`'s own image routes) is responsible for revoking the old one in the same breath — so a
URL someone saved, shared in a group chat, or scraped from a stale cache goes dead the moment the
photo is replaced, not later. A deleted image revokes its token outright: no token survives longer
than the row it points to.

CONSTANT-TIME-SAFE BY CONSTRUCTION, NOT BY A MANUAL COMPARISON — lookup is a single indexed KV read
(`resolve()` below), the same shape `PHONE_INDEX`/`WhatsAppNumberIndex` already use for an identical
"global, not tenant-scoped, needed before we know who is asking" case; there is no loop or string
compare in this file for an attacker's timing to measure in the first place.

THE INDEX NEVER STORES ANYTHING BUT THE POINTER — `{tenant, service_id}`, never the image bytes,
never a phone, never anything PII. Resolving a token still goes through `ServiceStore.get(tenant,
service_id)` and `read_image()` exactly like the authenticated route does; this file only answers
"whose image is this", not "here are the bytes".
"""
from __future__ import annotations

import secrets
from typing import Any

PUBLIC_IMAGE_INDEX = "public_catalog_image_index"
_TOKEN_BYTES = 32  # 256 bits — astronomically unguessable; cost of generating one is irrelevant


def new_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def public_url(base: str, token: str) -> str:
    """The URL that actually goes into `ProductItem.image_url` for Meta's catalog sync. `base` is
    `settings.PUBLIC_BASE_URL` — composed here, once, so no caller hand-assembles this shape a
    second way that could drift from the route it must actually match (below)."""
    return f"{base.rstrip('/')}/api/v1/public_catalog/{token}"


async def register(store: Any, token: str, *, tenant: str, service_id: str) -> None:
    await store.put(PUBLIC_IMAGE_INDEX, token, {"tenant": tenant, "service_id": service_id})


async def resolve(store: Any, token: str) -> tuple[str, str] | None:
    """`(tenant, service_id)`, or `None` for an unknown/revoked/malformed token — ALWAYS the same
    shape of answer regardless of WHY it failed (no token issued, wrong token, revoked token), so
    the route above this can return one identical 404 for every failure case. Distinguishing them
    would hand a prober three different oracles instead of a flat wall."""
    if not token:
        return None
    row = await store.get(PUBLIC_IMAGE_INDEX, token)
    if not row:
        return None
    tenant, service_id = row.get("tenant", ""), row.get("service_id", "")
    if not tenant or not service_id:
        return None
    return tenant, service_id


async def revoke(store: Any, token: str) -> None:
    if not token:
        return
    try:
        await store.delete(PUBLIC_IMAGE_INDEX, token)
    except Exception:                                                        # noqa: BLE001
        pass
