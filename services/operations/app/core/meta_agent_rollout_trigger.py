"""Fires whatsapp-assistant's own Meta Business Agent rollout switch on or off for a tenant --
the sibling of `meta_agent_provision_trigger.py`, but for a number that was already onboarded once
and now needs Meta's AI itself turned off (or back on), never a re-run of onboarding and never a
change to the connection or the handover mode. See whatsapp-assistant's own `app/core/
meta_agent_provisioning.py::set_agent_rollout` for the full reasoning.

CALLER: `api/v1/staff.py::set_ai_toggle` (instant, the owner's own kill switch). A subscription
simply lapsing with nobody touching the switch has no caller yet -- a periodic sweep was built and
tested for that, then deliberately removed (2026-09-20, the owner's own call): billing's own
renewal cycle only ever changes a subscription's status once a day, at a fixed cron time, so a
sweep bought nothing a same-day reaction to a real SUBSCRIPTION_SUSPENDED event wouldn't do better
-- that event was requested from base-services instead of rebuilding the sweep."""
from __future__ import annotations

from app.adapters import internal_http


class MetaAgentRolloutTrigger:
    """whatsapp-assistant's own rollout switch -- see that service's
    app/api/internal.py::set_meta_agent_rollout."""

    def __init__(self, *, base_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = f"{base_url.rstrip('/')}{path}" if base_url else ""
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._url)

    async def trigger(self, *, tenant: str, enabled: bool) -> bool:
        """Best-effort: True only if whatsapp-assistant reports the call itself succeeded (which
        includes the ordinary "this tenant was never Meta-provisioned" no-op). Never surfaced to
        an owner's own /ai-toggle response -- this is a background enhancement, same posture as
        `MetaAgentProvisionTrigger.trigger`."""
        if not self._url:
            return False
        from starlette.concurrency import run_in_threadpool

        try:
            data = await run_in_threadpool(
                internal_http.post_json, self._url,
                {"tenant": tenant, "enabled": enabled}, self._token, self._timeout)
        except Exception:                                                        # noqa: BLE001
            return False
        return bool(data.get("ok"))
