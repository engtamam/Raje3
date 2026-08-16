"""Asking reminders which offer applies — the call that was rejected every single time.

TWO DEFECTS, AND THE SECOND HID THE FIRST.

The body omitted `tenant`, which reminders' ChooseOfferIn requires (min_length=1). So every call in
this product's history came back 422. And the adapter turned EVERY failure into `None`, which the
visit path reads as «this customer holds no offer» — so the rejection was invisible. An exclusive
offer could never be applied at the counter, and nothing anywhere said so.

The file's own docstring said «A FAILURE REFUSES, NEVER GUESSES» the whole time. It was a comment,
not a behaviour, which is the most expensive kind of documentation there is.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.adapters.offer_choice import OfferPeerUnavailable, http_chooser


class FakeResponse:
    def __init__(self, payload, status=200):
        self._body = json.dumps(payload).encode()
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def run(c):
    return asyncio.run(c)


def chooser(monkeypatch, *, payload=None, status=200, boom=None):
    """Install a fake urlopen and hand back (chooser, captured_requests)."""
    seen: list = []

    def fake_urlopen(req, timeout=0):
        seen.append(req)
        if boom is not None:
            raise boom
        return FakeResponse(payload or {}, status)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return http_chooser(reminders_url="http://reminders:8000", token="t" * 40), seen


def test_the_tenant_travels_or_the_peer_rejects_every_call(monkeypatch):
    """THE DEFECT ITSELF. reminders requires `tenant`; without it the answer is always 422."""
    choose, seen = chooser(monkeypatch, payload={"offer": {"ref": "off_1", "text": "خصم"}})

    run(choose(tenant="tnt_1", subject_ref="sub_1", service_ids=["svc_a"]))

    body = json.loads(seen[0].data.decode())
    assert body["tenant"] == "tnt_1", "the peer's model requires this and it was never sent"
    assert body["subject_ref"] == "sub_1"
    assert body["service_ids"] == ["svc_a"]


def test_a_peer_that_cannot_be_reached_refuses_it_does_not_say_none(monkeypatch):
    """«لا يوجد عرض» and «تعذّر السؤال» are different sentences for the customer in front of you."""
    choose, _ = chooser(monkeypatch, boom=OSError("connection refused"))

    with pytest.raises(OfferPeerUnavailable):
        run(choose(tenant="tnt_1", subject_ref="sub_1", service_ids=[]))


def test_a_rejected_request_refuses_too(monkeypatch):
    """A 422 is the exact failure this product shipped with — it must never read as «none»."""
    choose, _ = chooser(monkeypatch, payload={}, status=422)

    with pytest.raises(OfferPeerUnavailable):
        run(choose(tenant="tnt_1", subject_ref="sub_1", service_ids=[]))


def test_an_unconfigured_peer_refuses_rather_than_denying_the_customer(monkeypatch):
    choose = http_chooser(reminders_url="", token="t")
    with pytest.raises(OfferPeerUnavailable):
        run(choose(tenant="tnt_1", subject_ref="sub_1", service_ids=[]))


def test_an_answer_of_no_offer_is_still_no_offer(monkeypatch):
    """The other half: once the peer HAS answered, an absent offer is the truth and must pass."""
    choose, _ = chooser(monkeypatch, payload={"offer": None})
    assert run(choose(tenant="tnt_1", subject_ref="sub_1", service_ids=[])) is None


def test_an_offer_without_a_ref_is_not_an_offer(monkeypatch):
    """`ref` is what the visit records; text alone cannot be marked as applied or audited."""
    choose, _ = chooser(monkeypatch, payload={"offer": {"text": "خصم بلا مرجع"}})
    assert run(choose(tenant="tnt_1", subject_ref="sub_1", service_ids=[])) is None
