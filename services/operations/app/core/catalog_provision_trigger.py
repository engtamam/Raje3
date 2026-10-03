"""Fires whatsapp-assistant's own Meta Commerce Catalog provisioning right after a WhatsApp number
connects -- the operations-side leg of `services/whatsapp-assistant/app/core/
catalog_provisioning.py::provision_catalog` (that module's own docstring has the full
create/connect/enable-cart sequence and its idempotency guarantees).

FIRE-AND-FORGET, SAME SHAPE AS `MetaAgentProvisionTrigger` RIGHT ABOVE IT IN `connect.py`. This
module's own `trigger()` never raises: a background task that raised would only ever be logged and
dropped by FastAPI's own BackgroundTasks runner anyway, so swallowing here (and reporting via
return value instead) keeps the failure mode explicit rather than relying on that implicit
behaviour.
"""
from __future__ import annotations

from app.adapters import internal_http


class CatalogProvisionTrigger:
    """whatsapp-assistant's own Commerce Catalog provisioning -- see that service's
    app/api/internal.py::provision_catalog."""

    def __init__(self, *, base_url: str, path: str, token: str, timeout: int = 20) -> None:
        # SAME LONGER TIMEOUT AS MetaAgentProvisionTrigger (20s vs an ordinary peer call's 8s) --
        # this call runs up to three real Graph API round-trips in sequence (create catalog,
        # connect to WABA, enable cart), not one single send.
        self._url = f"{base_url.rstrip('/')}{path}" if base_url else ""
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def trigger(self, *, tenant: str, business_id: str, waba_id: str,
                      phone_number_id: str) -> bool:
        """Best-effort: True only if whatsapp-assistant reports every step succeeded. A `False`
        here is never surfaced to the owner's connect response -- provisioning is a background
        enhancement to an already-successful connection, not a condition of it."""
        if not self._url:
            return False
        from starlette.concurrency import run_in_threadpool

        try:
            data = await run_in_threadpool(
                internal_http.post_json, self._url,
                {"tenant": tenant, "business_id": business_id, "waba_id": waba_id,
                 "phone_number_id": phone_number_id},
                self._token, self._timeout)
        except Exception:                                                        # noqa: BLE001
            # whatsapp-assistant unreachable, or the call itself errored -- there is no retry
            # queue for this yet (same as meta_agent_provision_trigger's own posture); a future
            # reconnect naturally retries (provision_catalog is idempotent, see its own docstring).
            return False
        return bool(data.get("ok"))
