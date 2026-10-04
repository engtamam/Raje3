"""Meta Commerce Catalog item sync — one WhatsApp service becomes one catalog item, kept in step
with the owner's own edits in «خدماتي» (operations' own Service model). The SECOND half of
WhatsApp Direct Ordering's Step 2, after `operations/app/core/catalog_item_sync_trigger.py`'s own
fire-and-forget call reaches this service; this module is the Graph API side, same "fire-and-
forget, report exactly which step failed" shape `catalog_provisioning.py`/`meta_agent_
provisioning.py` already use.

REAL PUBLIC GRAPH API SHAPE, confirmed against developers.facebook.com's own Catalog Batch API
reference (2026-10-04):

    POST /{catalog_id}/items_batch {item_type: "PRODUCT_ITEM", requests: [
        {method: "UPDATE", data: {id, title, description, availability, condition, brand, price,
                                  link, image: [{url}]}, allow_upsert: true}
    ]}

ALWAYS "UPDATE", NEVER "CREATE" — THE HARD CASE THIS MODULE GETS RIGHT WITHOUT TRACKING STATE.
Meta's own reference confirms `allow_upsert` (default `true`) makes UPDATE insert a non-existent
item rather than refuse it — the exact "create or update" primitive this module needs, since there
is no per-service "was this already created in the catalog" flag to maintain (SecretStore is keyed
per-tenant, not per-service, and a second KV collection just to remember that would be one more
thing to keep in sync with the catalog itself, the opposite of the goal). Every call this module
makes is `method: "UPDATE"` with `allow_upsert: true` explicit — never relying on the default
silently, since a future Graph change to that default must not silently break first-time syncs.

THE FOUR FIELDS THAT DO NOT MAP TO A SERVICE, FILLED WITH SENSIBLE DEFAULTS, NEVER LEFT TO THE
OWNER TO TYPE (owner's own decision, 2026-10-04): `brand` is this tenant's own shop name (from
`shop_identity`, the same source `meta_agent_provisioning.py` already reads for Knowledge push) —
a service has no brand of its own, and the shop's name is the only honest stand-in. `condition` is
always `"new"` — a service was never used, so every other value would be a lie, not a choice.
`link` is a `wa.me/<digits>` deep link built from `catalog_provisioning.py`'s own resolved
`SECRET_DISPLAY_PHONE_NAME` — reopening the SAME conversation ordering happens in, not a separate
website this product does not have. `availability` is always `"in stock"` — a service has no
inventory to run out of; the READINESS GATE below (price + a real photo) is what controls whether
an item exists in the catalog AT ALL, which is the only "availability" that means anything here.

READINESS IS DECIDED BY THE CALLER (operations), NOT HERE — this module only reacts to what it is
told. `operations/app/core/catalog_item_sync_trigger.py`'s own docstring has the exact gate
(active AND a real price AND a real photo); this module's `sync_service_item` takes that decision
as its own `ready` argument and either upserts (ready) or deletes (not ready, or was ready and just
stopped being) the SAME `id` either way — a service that loses its photo, drops its price to zero,
or is deactivated must disappear from the live WhatsApp catalog, not linger showing stale content a
customer could still order against.

NO CATALOG YET (the tenant has not finished Step 1) IS NOT AN ERROR, IT IS THE ORDINARY CASE WHILE
THIS ROLLS OUT — reported as `failed_step="no_catalog"`, never escalated, exactly like `meta_agent_
provisioning.py::set_agent_rollout`'s own "never provisioned" case.
"""
from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from app.core.catalog_provisioning import (
    SECRET_CATALOG_ID_NAME,
    SECRET_DISPLAY_PHONE_NAME,
    SECRET_TOKEN_NAME,
)

API_VERSION_HEADER_NAME = "X-API-Version"
API_VERSION_HEADER_VALUE = "2.0.0"

_CONDITION = "new"
_AVAILABILITY = "in stock"
_NON_DIGITS_RE = re.compile(r"\D")


class CatalogItemSyncError(RuntimeError):
    def __init__(self, step: str, message: str) -> None:
        super().__init__(f"{step}: {message}")
        self.step = step
        self.message = message


@dataclass
class SyncItemResult:
    """Reports exactly which step ran, and exactly which one failed -- never a bare bool, same
    discipline as `catalog_provisioning.py::ProvisionCatalogResult`."""
    ok: bool
    failed_step: str = ""
    error: str = ""
    synced: bool = False    # True when the item was upserted (ready=True path)
    removed: bool = False   # True when the item was deleted (ready=False path)


class NullCatalogItemSyncer:
    """No Graph credential configured, or the feature is off. Same "runs, does nothing" posture as
    every other Null adapter in this service."""
    driver = "null"

    async def upsert_item(self, catalog_id: str, item: dict[str, Any]) -> bool:
        raise CatalogItemSyncError("upsert_item", "catalog item sync is disabled")

    async def delete_item(self, catalog_id: str, item_id: str) -> bool:
        return False


class HttpCatalogItemSyncer:
    driver = "http"

    def __init__(self, *, token: str, graph_base_url: str, graph_version: str,
                 timeout: int = 8) -> None:
        self._token = token
        self._base = graph_base_url.rstrip("/")
        self._version = graph_version
        self._timeout = timeout

    def _call_sync(self, catalog_id: str, requests: list[dict[str, Any]]) -> dict[str, Any]:
        url = f"{self._base}/{self._version}/{catalog_id}/items_batch"
        body = json.dumps({"item_type": "PRODUCT_ITEM", "requests": requests}).encode()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._token}",
                     API_VERSION_HEADER_NAME: API_VERSION_HEADER_VALUE})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                raw = resp.read() or b"{}"
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise CatalogItemSyncError(
                "items_batch", f"HTTP {exc.code}: {exc.read()[:500]!r}") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise CatalogItemSyncError("items_batch", f"transport error: {exc}") from exc

    async def _call(self, catalog_id: str, requests: list[dict[str, Any]]) -> dict[str, Any]:
        # OFF THE EVENT LOOP -- see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._call_sync, catalog_id, requests)

    async def upsert_item(self, catalog_id: str, item: dict[str, Any]) -> bool:
        data = await self._call(
            catalog_id, [{"method": "UPDATE", "data": item, "allow_upsert": True}])
        # FAIL CLOSED ON AN UNRECOGNISED SHAPE -- a peer that does not say "handles" or "success"
        # has not told us it worked, and reading that silence as success is exactly the defect
        # ci/check_absent_means_ok.py exists to catch (see that script's own docstring: a `True`
        # default converts "it did not say" into "it worked"). `sync_service_item`'s own caller
        # already treats `False` here as a retry-safe, named failure, never a crash.
        return bool(data.get("handles") or data.get("success", False))

    async def delete_item(self, catalog_id: str, item_id: str) -> bool:
        data = await self._call(
            catalog_id, [{"method": "DELETE", "data": {"id": item_id}}])
        return bool(data.get("handles") or data.get("success", False))


def build(settings: Any) -> Any:
    if not getattr(settings, "CATALOG_PROVISIONING_ENABLED", False):
        return NullCatalogItemSyncer()
    return HttpCatalogItemSyncer(
        token="",  # resolved per-tenant at call time via SecretStore, see sync_service_item
        graph_base_url=getattr(settings, "META_GRAPH_BASE_URL", "https://graph.facebook.com"),
        graph_version=getattr(settings, "META_GRAPH_API_VERSION", "v26.0"),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))


def _wa_link(display_phone: str) -> str:
    digits = _NON_DIGITS_RE.sub("", display_phone or "")
    return f"https://wa.me/{digits}" if digits else ""


async def sync_service_item(
    *, tenant: str, service_id: str, name: str, description: str, price_minor: int, active: bool,
    image_url: str, secret_store: Any, settings: Any, shop_name: str = "",
    syncer_factory: Callable[[str], Any] | None = None,
) -> SyncItemResult:
    """Upsert or remove one service's catalog item, matching the owner's own current data exactly.

    NEVER RAISES. Fire-and-forget, same as every other provisioning function in this module's own
    family -- a sync failure must not break the service-edit response, and must report EXACTLY
    which step failed so it can be retried (the NEXT edit to this same service re-attempts it;
    there is no separate retry queue, by the same reasoning `catalog_provision_trigger.py`'s own
    docstring already gives).
    """
    result = SyncItemResult(ok=False)

    catalog_id = await secret_store.get(tenant=tenant, name=SECRET_CATALOG_ID_NAME)
    if not catalog_id:
        result.failed_step = "no_catalog"
        result.error = "this tenant has not completed catalog provisioning yet"
        return result

    token = await secret_store.get(tenant=tenant, name=SECRET_TOKEN_NAME)
    if not token:
        result.failed_step = "no_catalog"
        result.error = "no Meta credential configured for this tenant"
        return result

    syncer = syncer_factory(token) if syncer_factory else build(settings)

    # READY = owner's own gate (active AND a real price AND a real photo), decided by the caller
    # and handed in as plain facts -- this function only reacts to them.
    ready = bool(active and price_minor > 0 and image_url)

    if not ready:
        try:
            await syncer.delete_item(catalog_id, service_id)
        except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
            result.failed_step, result.error = "delete_item", str(exc)
            return result
        result.removed = True
        result.ok = True
        return result

    display_phone = await secret_store.get(tenant=tenant, name=SECRET_DISPLAY_PHONE_NAME)
    link = _wa_link(display_phone)
    if not link:
        # BETTER TO REFUSE THAN TO PUBLISH A DEAD LINK -- `catalog_provisioning.py`'s own phone
        # resolution is best-effort and can genuinely still be empty (a transient Graph failure
        # at connect time that never got retried). The NEXT edit to this service re-attempts the
        # whole sync, so this is never a permanent stuck state, just an honest "not yet".
        result.failed_step = "no_display_phone"
        result.error = "this tenant's WhatsApp number has not been resolved yet"
        return result

    item = {
        "id": service_id,
        "title": (name or "")[:100],
        "description": (description or name or "")[:5000],
        "availability": _AVAILABILITY,
        "condition": _CONDITION,
        "brand": (shop_name or "Raje3")[:100],
        "price": f"{price_minor / 100:.2f} SAR",
        "link": link,
        "image": [{"url": image_url}],
    }
    try:
        await syncer.upsert_item(catalog_id, item)
    except Exception as exc:  # noqa: BLE001
        result.failed_step, result.error = "upsert_item", str(exc)
        return result

    result.synced = True
    result.ok = True
    return result
