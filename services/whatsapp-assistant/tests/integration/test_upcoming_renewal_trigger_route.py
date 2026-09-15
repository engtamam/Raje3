"""Integration: /internal/whatsapp/upcoming-renewal/trigger — fires the 2-days-ahead renewal
heads-up for one subscription. See app/core/upcoming_renewal_trigger.py."""
from __future__ import annotations

from tests.conftest import INTERNAL_TOKEN

TENANT = "renewsoon_shop"


def _headers():
    return {"X-Internal-Token": INTERNAL_TOKEN}


class _FakeSender:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_template(self, **kwargs):
        self.sent.append(kwargs)
        return "dlv_1"


class _FakeOwnerPhone:
    def __init__(self, phones: dict[str, str]) -> None:
        self._phones = phones

    async def resolve(self, tenant: str) -> str:
        return self._phones.get(tenant, "")


def _swap(client, *, sender=None, owner_phone=None):
    c = client.app.state.container
    saved = (c.sender, c.owner_phone, c.upcoming_renewal_trigger)
    from app.core.upcoming_renewal_trigger import UpcomingRenewalTrigger
    from app.core.upcoming_renewal_trigger_store import UpcomingRenewalTriggerStore

    sender = sender or _FakeSender()
    owner_phone = owner_phone or _FakeOwnerPhone({TENANT: "+966500000001"})
    c.sender = sender
    c.owner_phone = owner_phone
    c.upcoming_renewal_trigger = UpcomingRenewalTrigger(
        claims=UpcomingRenewalTriggerStore(c.datastore), owner_phone=owner_phone, sender=sender)
    return saved, sender


def _restore(client, saved):
    c = client.app.state.container
    c.sender, c.owner_phone, c.upcoming_renewal_trigger = saved


def test_a_real_row_sends_and_reports_sent_true(client):
    saved, sender = _swap(client)
    try:
        r = client.post("/internal/whatsapp/upcoming-renewal/trigger",
                        json={"tenant": TENANT, "subscription_id": "sub_1", "period_end": 99999999},
                        headers=_headers())
        assert r.status_code == 200
        assert r.json() == {"sent": True}
        assert len(sender.sent) == 1
        assert sender.sent[0]["flow_action_data"]["customer"] == f"{TENANT}:sub:sub_1"
    finally:
        _restore(client, saved)


def test_a_repeat_for_the_same_cycle_reports_sent_false(client):
    saved, sender = _swap(client)
    try:
        body = {"tenant": TENANT, "subscription_id": "sub_repeat", "period_end": 99999998}
        client.post("/internal/whatsapp/upcoming-renewal/trigger", json=body, headers=_headers())
        r = client.post("/internal/whatsapp/upcoming-renewal/trigger", json=body, headers=_headers())
        assert r.json() == {"sent": False}
        assert len(sender.sent) == 1
    finally:
        _restore(client, saved)


def test_refuses_without_the_internal_token(client):
    r = client.post("/internal/whatsapp/upcoming-renewal/trigger",
                    json={"tenant": TENANT, "subscription_id": "sub_1", "period_end": 99999999})
    assert r.status_code in (401, 403)


def test_refuses_a_missing_field(client):
    r = client.post("/internal/whatsapp/upcoming-renewal/trigger",
                    json={"tenant": TENANT, "subscription_id": "sub_1"}, headers=_headers())
    assert r.status_code == 422


def test_refuses_a_zero_period_end(client):
    r = client.post("/internal/whatsapp/upcoming-renewal/trigger",
                    json={"tenant": TENANT, "subscription_id": "sub_1", "period_end": 0},
                    headers=_headers())
    assert r.status_code == 422
