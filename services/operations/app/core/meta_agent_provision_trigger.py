"""Fires whatsapp-assistant's own Meta Business Agent onboarding sequence right after a WhatsApp
number connects — the operations-side leg of `services/whatsapp-assistant/app/core/
meta_agent_provisioning.py::provision_number` (that module's own docstring has the full 7-step
sequence and why it never raises the caller's response).

FIRE-AND-FORGET, SAME SHAPE AS `provision_shop_flow`/`publish` IN connect.py. This module's own
`trigger()` never raises: a background task that raised would only ever be logged and dropped by
FastAPI's own BackgroundTasks runner anyway, so swallowing here (and reporting via return value
instead) keeps the failure mode explicit rather than relying on that implicit behaviour.
"""
from __future__ import annotations

from app.adapters import internal_http


class MetaAgentProvisionTrigger:
    """whatsapp-assistant's own onboarding-sequence trigger — see that service's
    app/api/internal.py::provision_meta_agent."""

    def __init__(self, *, base_url: str, path: str, token: str, timeout: int = 20) -> None:
        # LONGER TIMEOUT THAN THE RENEWAL TRIGGER (20s vs 8s) -- this call runs seven real Graph
        # API round-trips in sequence (eligibility, create agent, register connector, one call per
        # tool, upload skill, push knowledge, enable), not one single send.
        self._url = f"{base_url.rstrip('/')}{path}" if base_url else ""
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def trigger(self, *, tenant: str, entity_id: str) -> bool:
        """Best-effort: True only if whatsapp-assistant reports every step succeeded. A `False`
        here is never surfaced to the owner's connect response -- provisioning is a background
        enhancement to an already-successful connection, not a condition of it."""
        if not self._url:
            return False
        from starlette.concurrency import run_in_threadpool

        try:
            data = await run_in_threadpool(
                internal_http.post_json, self._url,
                {"tenant": tenant, "entity_id": entity_id}, self._token, self._timeout)
        except Exception:                                                        # noqa: BLE001
            # whatsapp-assistant unreachable, or the call itself errored -- there is no retry
            # queue for this yet (same as provision_shop_flow's own after-the-response posture);
            # a future reconnect or an explicit operator retry covers it.
            return False
        return bool(data.get("ok"))
