"""/internal/operations/whatsapp/meta-agent/rollout-sweep — the periodic catch-all that enforces
Meta's own AI rollout flag for every connected number, covering what the instant AI-toggle trigger
cannot: `feature.whatsapp` simply lapsing with nobody touching the switch. See
app/core/meta_agent_rollout_trigger.py and staff.py::set_ai_toggle for the instant-reaction half."""
from __future__ import annotations

import asyncio

from app.core import ai_toggle as AT
from app.core import connect
from tests.conftest import push_headers

PATH = "/internal/operations/whatsapp/meta-agent/rollout-sweep"


def _connect(client, tenant: str, phone_number_id: str = "pn_1") -> None:
    store = connect.ConnectionStore(client.app.state.container.datastore)
    asyncio.run(store.record(connect.Attempt(
        tenant=tenant, state=connect.STATE_CONNECTED,
        waba_id=f"waba_{tenant}", phone_number_id=phone_number_id)))


class _FakeWhatsappLicence:
    def __init__(self, by_tenant: dict[str, bool | None]) -> None:
        self._by_tenant = by_tenant

    async def allowed(self, tenant: str) -> bool | None:
        return self._by_tenant.get(tenant, True)


def _headers():
    return {"X-Internal-Token": "t" * 40, **push_headers(b"")}


def test_a_connected_but_unentitled_tenant_is_pushed_disabled(client):
    _connect(client, "tnt_sweep_lapsed")
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, enabled):
        calls.append({"tenant": tenant, "enabled": enabled})
        return True

    c = client.app.state.container
    saved_trigger, saved_licence = c.meta_agent_rollout_trigger.trigger, c.whatsapp_licence
    c.meta_agent_rollout_trigger.trigger = _fake_trigger
    c.whatsapp_licence = _FakeWhatsappLicence({"tnt_sweep_lapsed": False})
    try:
        r = client.post(PATH, headers=_headers())
    finally:
        c.meta_agent_rollout_trigger.trigger = saved_trigger
        c.whatsapp_licence = saved_licence
    assert r.status_code == 200, r.text
    assert {"tenant": "tnt_sweep_lapsed", "enabled": False} in calls


def test_a_connected_entitled_tenant_with_the_switch_on_is_pushed_enabled(client):
    _connect(client, "tnt_sweep_entitled")
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, enabled):
        calls.append({"tenant": tenant, "enabled": enabled})
        return True

    c = client.app.state.container
    saved_trigger, saved_licence = c.meta_agent_rollout_trigger.trigger, c.whatsapp_licence
    c.meta_agent_rollout_trigger.trigger = _fake_trigger
    c.whatsapp_licence = _FakeWhatsappLicence({"tnt_sweep_entitled": True})
    try:
        r = client.post(PATH, headers=_headers())
    finally:
        c.meta_agent_rollout_trigger.trigger = saved_trigger
        c.whatsapp_licence = saved_licence
    assert r.status_code == 200, r.text
    assert {"tenant": "tnt_sweep_entitled", "enabled": True} in calls


def test_entitled_but_the_owners_own_switch_is_off_is_still_pushed_disabled(client):
    """Entitlement alone is not enough — the owner's own AI kill switch overrides it, same
    priority `ToggleGatedLicence` already enforces on the reply-engine side."""
    _connect(client, "tnt_sweep_toggled_off")
    asyncio.run(AT.AiToggleStore(client.app.state.container.datastore).set(
        "tnt_sweep_toggled_off", False))
    calls: list[dict] = []

    async def _fake_trigger(*, tenant, enabled):
        calls.append({"tenant": tenant, "enabled": enabled})
        return True

    c = client.app.state.container
    saved_trigger, saved_licence = c.meta_agent_rollout_trigger.trigger, c.whatsapp_licence
    c.meta_agent_rollout_trigger.trigger = _fake_trigger
    c.whatsapp_licence = _FakeWhatsappLicence({"tnt_sweep_toggled_off": True})
    try:
        r = client.post(PATH, headers=_headers())
    finally:
        c.meta_agent_rollout_trigger.trigger = saved_trigger
        c.whatsapp_licence = saved_licence
    assert r.status_code == 200, r.text
    assert {"tenant": "tnt_sweep_toggled_off", "enabled": False} in calls


def test_one_tenants_trigger_failure_does_not_block_the_rest_of_the_pass(client):
    _connect(client, "tnt_sweep_fail")
    _connect(client, "tnt_sweep_ok", phone_number_id="pn_2")
    calls: list[dict] = []

    async def _flaky_trigger(*, tenant, enabled):
        calls.append({"tenant": tenant, "enabled": enabled})
        if tenant == "tnt_sweep_fail":
            return False
        return True

    c = client.app.state.container
    saved_trigger, saved_licence = c.meta_agent_rollout_trigger.trigger, c.whatsapp_licence
    c.meta_agent_rollout_trigger.trigger = _flaky_trigger
    c.whatsapp_licence = _FakeWhatsappLicence(
        {"tnt_sweep_fail": True, "tnt_sweep_ok": True})
    try:
        r = client.post(PATH, headers=_headers())
    finally:
        c.meta_agent_rollout_trigger.trigger = saved_trigger
        c.whatsapp_licence = saved_licence
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["failed"] >= 1
    tenants_seen = {c["tenant"] for c in calls}
    assert {"tnt_sweep_fail", "tnt_sweep_ok"} <= tenants_seen
