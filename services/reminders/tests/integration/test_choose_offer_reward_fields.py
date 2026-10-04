"""`/internal/reminders/offer/choose` used to hand back only display text (`value`, a free-text
string meant to be read, not compared) — a caller that needs to compare this offer against OTHER
entitlement sources by real SAR value (`services/operations/app/core/entitlements.py`'s own
`EntitlementGateway`, 2026-10-04) had nothing to compare WITH. This is that gap, closed: the same
structured `reward_kind`/`reward_amount` the order-side `active-discount` route already exposes.
"""
from __future__ import annotations

import asyncio

import pytest

from tests.conftest import INTERNAL_TOKEN

TENANT = "tnt_choose_reward"


@pytest.fixture()
def client(client, monkeypatch):
    """`choose_offer` refuses to answer unless it can ask operations what was already spent (see
    that route's own docstring) — reachable and nothing spent, for every test in this file."""
    import app.api.internal as internal

    async def _nothing_spent(tenant, subject_ref):
        return set()

    monkeypatch.setattr(internal, "_spent_or_empty", _nothing_spent)
    return client


def _seed(client, subject_ref: str, **row) -> None:
    from app.core.stores import SendLogStore

    store = client.app.state.container.datastore
    base = {"id": "snd_cr1", "tenant": TENANT, "subject_ref": subject_ref, "cls": "marketing",
           "outcome": "sent", "at": 1000, "offer_text": "خصم خاص لك",
           "offer_expires_at": 9_999_999_999}
    base.update(row)
    asyncio.run(SendLogStore(store).append(TENANT, base))


def _choose(client, subject_ref: str, service_ids: list | None = None) -> dict:
    r = client.post("/internal/reminders/offer/choose",
                    json={"tenant": TENANT, "subject_ref": subject_ref,
                         "service_ids": service_ids or []},
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200, r.text
    return r.json()


def test_a_structured_discount_send_exposes_its_real_reward_fields(client):
    _seed(client, "sub_cr_1", id="snd_cr_1", reward_kind="percent", reward_amount=20,
         offer_services=["svc_wash"])
    body = _choose(client, "sub_cr_1", service_ids=["svc_wash"])
    offer = body["offer"]
    assert offer is not None
    assert offer["reward_kind"] == "percent"
    assert offer["reward_amount"] == 20
    assert offer["scope_service_ids"] == ["svc_wash"]


def test_an_owner_written_free_text_offer_with_no_structured_reward_exposes_empty_fields(client):
    """A send with only `offer_text` (the owner's own line, no `reward_kind` at all) must still
    be chosen and shown — just with nothing a caller can compare numerically, never a crash or a
    guessed value."""
    _seed(client, "sub_cr_2", id="snd_cr_2")
    body = _choose(client, "sub_cr_2")
    offer = body["offer"]
    assert offer is not None
    assert offer["reward_kind"] == ""
    assert offer["reward_amount"] == 0
    assert offer["scope_service_ids"] == []


def test_a_fixed_halalas_discount_exposes_the_real_halalas_amount_not_a_riyal_float(client):
    """Same money discipline everywhere else in this product: the wire number is always an
    integer count of halalas, never something a caller must multiply or round itself."""
    _seed(client, "sub_cr_3", id="snd_cr_3", reward_kind="fixed_halalas", reward_amount=1500)
    body = _choose(client, "sub_cr_3")
    offer = body["offer"]
    assert offer["reward_kind"] == "fixed_halalas"
    assert offer["reward_amount"] == 1500
    assert isinstance(offer["reward_amount"], int)
