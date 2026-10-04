"""Fires whatsapp-assistant's own Meta Commerce Catalog item sync whenever a service's price,
photo, name, description or active flag changes — the operations-side leg of
`services/whatsapp-assistant/app/core/catalog_item_sync.py::sync_service_item`.

THE READINESS GATE LIVES HERE, NOT ON THE FAR SIDE — this module is the one place that knows
`Service`'s real shape (`price_minor`, `image_key`/`public_image_token`, `active`), so it is also
the one place that can honestly answer "is this service ready to sell on WhatsApp" without a
second copy of that logic drifting from `Service`'s own fields. whatsapp-assistant only ever sees
the PLAIN FACTS this trigger hands it (active/price_minor/image_url) and reacts to them —
`catalog_item_sync.py`'s own docstring says so explicitly.

THE PUBLIC IMAGE URL IS BUILT HERE TOO, from `public_catalog_image.public_url()` — the one function
that knows this service's own `PUBLIC_BASE_URL` and the `/api/v1/public_catalog/{token}` route
shape (see that module's own docstring for why Meta's crawler needs a URL, never a binary upload).
A service with no uploaded photo (`public_image_token` empty) sends `image_url=""`, which
`sync_service_item`'s own readiness gate reads as "not ready" — never a placeholder image.

FIRE-AND-FORGET, SAME SHAPE AS `CatalogProvisionTrigger`/`MetaAgentProvisionTrigger`. This module's
own `sync()` never raises: a background task that raised would only ever be logged and dropped by
FastAPI's own BackgroundTasks runner anyway, so swallowing here (and reporting via return value
instead) keeps the failure mode explicit rather than relying on that implicit behaviour.
"""
from __future__ import annotations

from typing import Any

from app.adapters import internal_http
from app.core.public_catalog_image import public_url


class CatalogItemSyncTrigger:
    """whatsapp-assistant's own Commerce Catalog item sync -- see that service's
    app/api/internal.py::sync_catalog_item."""

    def __init__(self, *, base_url: str, path: str, token: str, public_base_url: str,
                 timeout: int = 10) -> None:
        self._url = f"{base_url.rstrip('/')}{path}" if base_url else ""
        self._token = token
        self._public_base_url = public_base_url
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def sync(self, *, tenant: str, service: Any) -> bool:
        """`service` is a `core.models.Service` -- takes the live object rather than individual
        fields so a future field this trigger needs (a second photo, a longer description) is one
        read, not a signature change at every call site."""
        if not self._url:
            return False
        from starlette.concurrency import run_in_threadpool

        image_url = (public_url(self._public_base_url, service.public_image_token)
                    if service.public_image_token and self._public_base_url else "")
        try:
            data = await run_in_threadpool(
                internal_http.post_json, self._url,
                {"tenant": tenant, "service_id": service.id, "name": service.name,
                 "description": service.description, "price_minor": service.price_minor,
                 "active": service.active, "image_url": image_url},
                self._token, self._timeout)
        except Exception:                                                        # noqa: BLE001
            # whatsapp-assistant unreachable, or the call itself errored -- there is no retry
            # queue for this yet; the NEXT edit to this same service re-attempts the sync on its
            # own, same posture as every other fire-and-forget trigger in this fleet.
            return False
        return bool(data.get("ok"))

    async def backfill(self, *, tenant: str, services: list[Any]) -> int:
        """Sync EVERY one of this tenant's existing services, once, right after Step 1's own
        catalog provisioning succeeds -- the real case this closes: a shop that already built a
        full priced-and-photographed catalogue BEFORE ever connecting WhatsApp must not sit with
        an empty Meta catalog until someone happens to touch each service again. Sequential, not
        parallel -- a shop's catalogue is dozens of rows at most, never thousands, and items_batch
        itself has no concurrency benefit to chase for a one-time pass. Returns how many reported
        `ok=True`, purely for the caller's own audit metadata -- a partial backfill is not an
        error (each service also re-syncs on its own next edit, same as any other sync failure)."""
        ok_count = 0
        for service in services:
            if await self.sync(tenant=tenant, service=service):
                ok_count += 1
        return ok_count
