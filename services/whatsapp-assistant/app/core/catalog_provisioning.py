"""Meta Commerce Catalog provisioning for WhatsApp Direct Ordering -- one catalog per tenant,
connected to that tenant's own WhatsApp Business Account, with the shopping cart turned on for
their connected number. Same "fire-and-forget, report exactly which step failed, never fail the
caller's own response" shape `core/meta_agent_provisioning.py::provision_number` already uses for
Meta Business Agent onboarding -- this module is that same pattern applied to a different Meta
product (Commerce, not Business Agent), so it is built and tested the same way rather than
introducing a second idiom.

REAL PUBLIC GRAPH API SHAPES, confirmed against the PRIMARY developers.facebook.com reference
pages directly (not secondary summaries) on 2026-10-04:

    0. GET  /{business_id}/owned_pages                                        -> {"data": [Page]}
    1. POST /{business_id}/owned_product_catalogs {name, vertical: "commerce",
             page_id}                                                        -> {"id": str}
    2. POST /{waba_id}/product_catalogs           {catalog_id}                -> {"success": bool}
    3. POST /{phone_number_id}/whatsapp_commerce_settings?is_cart_enabled=true -> {"success": bool}

STEP 0 EXISTS BECAUSE OF A REAL MISTAKE CAUGHT BEFORE SHIPPING. The first version of this module
called step 1 with only `name`/`vertical`, on the assumption (several SECONDARY sources agreed)
that `business_id` alone was enough. Reading the PRIMARY reference page directly
(developers.facebook.com/docs/marketing-api/reference/business/owned_product_catalogs) showed
`page_id` listed as a REQUIRED parameter on that same POST -- a catalog cannot be created without
a Facebook Page backing it. `business_id` is NEVER on hand as a Page id (it identifies the Business
Manager account, a different object), so step 0 resolves it: Embedded Signup's own response CAN
include `page_ids` directly (only when the owner picked a Page during that flow -- not guaranteed),
but `GET /{business_id}/owned_pages` is unconditional and needs nothing operations.py does not
already have, so this module resolves its own page_id rather than depending on a frontend/connect.py
change that might arrive late or never. A BUSINESS WITH NO FACEBOOK PAGE AT ALL fails this step by
design (see `resolve_page_id` below) -- that is a real, nameable precondition this module cannot
manufacture around, not a bug to swallow.

`business_id`/`waba_id`/`phone_number_id` ARE ALL ALREADY ON HAND the moment a number connects --
`services/operations/app/core/connect.py::Attempt` already carries all three for every tenant
(captured straight from Embedded Signup), the same three identifiers
`meta_agent_provisioning.py::provision_number` only needed one of (entity_id/phone_number_id).
`page_id` is the one identifier this module resolves itself (step 0), rather than requiring a
fourth field from connect.py.

IDEMPOTENT BY CONSTRUCTION -- THE HARD CASE THIS MODULE EXISTS TO GET RIGHT. A shop can trigger
this more than once: a genuine reconnect (the owner re-runs Embedded Signup), a retry after a
transient Graph failure, or the health sweep settling a row that was already connected. Creating a
catalog is NOT a safe operation to repeat blindly -- a naive re-run would leave a tenant with a
trail of abandoned, empty catalogs in their own Meta Business Manager, one per retry, that nobody
would ever clean up and that would confuse an owner who opens Commerce Manager looking for "the"
catalog. So:

  * `catalog_id` is read from SecretStore FIRST. If one is already on file for this tenant, catalog
    CREATION is skipped entirely and the existing id is reused -- `create_catalog` runs at most
    once per tenant, ever, no matter how many times this function is called.
  * The catalog id is written to SecretStore THE MOMENT IT COMES BACK, before the connect/enable
    steps even run -- same write-ahead discipline `provision_number` uses for `agent_id`. A crash
    (or a Graph failure) between creation and the next step leaves a tenant with a real,
    recorded catalog and a partial provisioning that the NEXT trigger can finish from where it
    stopped, rather than one this module has lost track of and would recreate.
  * Connect-to-WABA and enable-cart are run on EVERY call, retry or not. Both are idempotent on
    Meta's own side by the shape of what they do (associating an already-associated catalog, or
    setting a boolean flag to the value it already holds, are each no-ops that report success) --
    this is the one assumption in this module not independently confirmed against a live sandbox
    account (same caveat `meta_agent_provisioning.py`'s own docstring already carries for several of
    its steps); if a future sandbox run shows either call hard-refusing a repeat, the fix is to add
    the same "read a stored flag, skip if already true" guard this module already uses for the
    catalog id itself, not to change the overall shape.

ONE CATALOG MAY SERVE SEVERAL PHONE NUMBERS, BY META'S OWN DESIGN -- so a shop with more than one
connected number under the same tenant (see `connect.py`'s own `branch_id` field) reconnecting a
SECOND number is not a reason to mint a second catalog. This function is keyed on the bare
`tenant`, never a tenant|branch composite, deliberately matching `meta_agent_provision_trigger`'s
own call shape -- a second branch's number calls `connect_catalog`/`enable_cart` again (both
idempotent, see above) against the SAME catalog this tenant already has.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

API_VERSION_HEADER_NAME = "X-API-Version"
API_VERSION_HEADER_VALUE = "2.0.0"

#: SAME STORE, SAME TOKEN NAME meta_agent_provisioning.py already reads -- one bearer token per
#: tenant covers every Graph API call this service makes on that tenant's behalf, Commerce
#: Catalog included; there is no separate "commerce" credential to provision.
SECRET_TOKEN_NAME = "META_KNOWLEDGE_TOKEN"
SECRET_CATALOG_ID_NAME = "META_CATALOG_ID"


class CatalogProvisioningError(RuntimeError):
    def __init__(self, step: str, message: str) -> None:
        super().__init__(f"{step}: {message}")
        self.step = step
        self.message = message


@dataclass
class ProvisionCatalogResult:
    """Reports exactly which step ran, and exactly which one failed -- never a bare bool, same
    discipline as `meta_agent_provisioning.py::ProvisioningResult`."""
    ok: bool
    failed_step: str = ""
    error: str = ""
    page_id: str = ""
    catalog_id: str = ""
    catalog_created: bool = False  # False when an existing catalog_id was reused, not minted
    connected: bool = False
    cart_enabled: bool = False


class NullCatalogProvisioner:
    """No Graph credential configured, or the feature is off. Same "runs, does nothing" posture as
    every other Null adapter in this service."""
    driver = "null"

    async def resolve_page_id(self, business_id: str) -> str:
        raise CatalogProvisioningError("resolve_page_id", "catalog provisioning is disabled")

    async def create_catalog(self, business_id: str, page_id: str, name: str) -> str:
        raise CatalogProvisioningError("create_catalog", "catalog provisioning is disabled")

    async def connect_catalog(self, waba_id: str, catalog_id: str) -> bool:
        return False

    async def enable_cart(self, phone_number_id: str) -> bool:
        return False


class HttpCatalogProvisioner:
    driver = "http"

    def __init__(self, *, token: str, graph_base_url: str, graph_version: str,
                 timeout: int = 8) -> None:
        self._token = token
        self._base = graph_base_url.rstrip("/")
        self._version = graph_version
        self._timeout = timeout

    def _call_sync(self, method: str, path: str, body: dict[str, Any] | None = None,
                   query: str = "") -> dict[str, Any]:
        url = f"{self._base}/{self._version}/{path}"
        if query:
            url = f"{url}?{query}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._token}",
                     API_VERSION_HEADER_NAME: API_VERSION_HEADER_VALUE})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                raw = resp.read() or b"{}"
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise CatalogProvisioningError(
                path, f"HTTP {exc.code}: {exc.read()[:500]!r}") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise CatalogProvisioningError(path, f"transport error: {exc}") from exc

    async def _call(self, method: str, path: str, body: dict[str, Any] | None = None,
                    query: str = "") -> dict[str, Any]:
        # OFF THE EVENT LOOP -- see core/customer_lookup.py::HttpCustomerLookup.resolve.
        return await asyncio.to_thread(self._call_sync, method, path, body, query)

    async def resolve_page_id(self, business_id: str) -> str:
        """The first Facebook Page this business owns -- `owned_product_catalogs` requires one
        and `business_id` is never itself a Page id (it names the Business Manager account, a
        different object). Returns "" when the business owns no Page at all, a real precondition
        `provision_catalog` reports as a named, actionable failure rather than guessing one."""
        data = await self._call("GET", f"{business_id}/owned_pages")
        pages = data.get("data") or []
        if not pages:
            return ""
        return str(pages[0].get("id") or "")

    async def create_catalog(self, business_id: str, page_id: str, name: str) -> str:
        data = await self._call(
            "POST", f"{business_id}/owned_product_catalogs",
            {"name": name[:100], "vertical": "commerce", "page_id": page_id})
        catalog_id = data.get("id") or ""
        if not catalog_id:
            raise CatalogProvisioningError(
                "create_catalog", f"no id in response: {data!r}")
        return str(catalog_id)

    async def connect_catalog(self, waba_id: str, catalog_id: str) -> bool:
        data = await self._call(
            "POST", f"{waba_id}/product_catalogs", {"catalog_id": catalog_id})
        return bool(data.get("success", True))

    async def enable_cart(self, phone_number_id: str) -> bool:
        data = await self._call(
            "POST", f"{phone_number_id}/whatsapp_commerce_settings",
            query="is_cart_enabled=true")
        return bool(data.get("success", True))


def build(settings: Any) -> Any:
    if not getattr(settings, "CATALOG_PROVISIONING_ENABLED", False):
        return NullCatalogProvisioner()
    return HttpCatalogProvisioner(
        token="",  # resolved per-tenant at call time via SecretStore, see provision_catalog
        graph_base_url=getattr(settings, "META_GRAPH_BASE_URL", "https://graph.facebook.com"),
        graph_version=getattr(settings, "META_GRAPH_API_VERSION", "v26.0"),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))


async def provision_catalog(
    *, tenant: str, business_id: str, waba_id: str, phone_number_id: str, secret_store: Any,
    settings: Any, provisioner_factory: Callable[[str], Any] | None = None,
    catalog_name: str = "",
) -> ProvisionCatalogResult:
    """Ensure this tenant has exactly one Commerce Catalog, connected to its WABA, with the cart
    turned on for the number that just connected. Safe to call on every connect/reconnect -- see
    this module's own docstring for the idempotency guarantees that make that true.

    NEVER RAISES. Fire-and-forget, same as `meta_agent_provisioning.py::provision_number` -- a
    provisioning failure must not break the connect response, and must report EXACTLY which step
    failed so it can be retried, never swallowed.
    """
    result = ProvisionCatalogResult(ok=False)

    if not business_id or not waba_id or not phone_number_id:
        result.failed_step = "validate_ids"
        result.error = "missing business_id/waba_id/phone_number_id for this connection"
        return result

    token = await secret_store.get(tenant=tenant, name=SECRET_TOKEN_NAME)
    if not token:
        result.failed_step = "validate_ids"
        result.error = "no Meta credential configured for this tenant"
        return result

    provisioner = provisioner_factory(token) if provisioner_factory else build(settings)

    # REUSE, NEVER RE-MINT -- the whole point of checking SecretStore before calling Graph at all.
    catalog_id = await secret_store.get(tenant=tenant, name=SECRET_CATALOG_ID_NAME)
    if catalog_id:
        result.catalog_id = str(catalog_id)
        result.catalog_created = False
    else:
        try:
            page_id = await provisioner.resolve_page_id(business_id)
        except Exception as exc:  # noqa: BLE001
            result.failed_step, result.error = "resolve_page_id", str(exc)
            return result
        if not page_id:
            result.failed_step = "resolve_page_id"
            result.error = ("this business owns no Facebook Page — one must exist before a "
                            "Commerce Catalog can be created for it")
            return result
        result.page_id = page_id

        try:
            catalog_id = await provisioner.create_catalog(
                business_id, page_id, catalog_name or f"Raje3 - {tenant}")
        except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
            result.failed_step, result.error = "create_catalog", str(exc)
            return result
        # WRITTEN BEFORE THE NEXT STEP EVEN RUNS -- see this module's own docstring on why a crash
        # here must not cost the tenant a second catalog on the next retry.
        await secret_store.set(tenant=tenant, name=SECRET_CATALOG_ID_NAME, value=catalog_id,
                                actor_ref="catalog_provisioning")
        result.catalog_id = catalog_id
        result.catalog_created = True

    try:
        result.connected = await provisioner.connect_catalog(waba_id, result.catalog_id)
    except Exception as exc:  # noqa: BLE001
        result.failed_step, result.error = "connect_catalog", str(exc)
        return result

    try:
        result.cart_enabled = await provisioner.enable_cart(phone_number_id)
    except Exception as exc:  # noqa: BLE001
        result.failed_step, result.error = "enable_cart", str(exc)
        return result

    result.ok = True
    return result
