"""The consent journey, through the routes the customer and the owner actually touch.

Everything here is a legal record before it is a feature. The unit tests prove the model; these
prove the TAP writes it — which is the half that was missing, because ticking the box used to
clear a refusal and record nothing.
"""
from __future__ import annotations

from tests.conftest import INTERNAL_TOKEN

REF = "shopx.ref_consentproof01"
TENANT, SUBJECT = "shopx", "ref_consentproof01"
INTERNAL = {"X-Internal-Token": INTERNAL_TOKEN}


def _count(client) -> int:
    r = client.post("/internal/reminders/consent/count", json={"tenant": TENANT},
                    headers=INTERNAL)
    assert r.status_code == 200, r.text
    return r.json()["granted"]


def _set(client, stopped):
    return client.put(f"/api/v1/prefs/{REF}", json={"stopped": stopped})


def test_nobody_has_agreed_before_anybody_is_asked(client):
    """The number an owner is shown must start at zero, not at "every customer he has"."""
    assert _count(client) == 0


def test_ticking_the_box_records_a_grant_not_just_the_absence_of_a_refusal(client):
    """THE DEFECT THIS CLOSES. The tap used to clear `stopped` and write nothing — so "agreed" and
    "was never asked" were the same row, and PDPL's prior consent had no evidence behind it."""
    before = _count(client)
    r = _set(client, [])                       # nothing stopped: marketing is on
    assert r.status_code == 200 and r.json()["saved"] is True
    assert _count(client) == before + 1


def test_saving_the_page_again_without_touching_the_box_appends_nothing(client):
    """A history of identical grants is evidence of nothing, and it would inflate the owner's
    count with the same person twice."""
    _set(client, [])
    once = _count(client)
    _set(client, [])
    _set(client, ["service"])                  # a different switch entirely
    assert _count(client) == once


def test_the_one_tap_withdrawal_writes_a_record_and_not_only_a_flag(client):
    """Otherwise the message stops and the record still says they agreed — which is the worse of
    the two failures, because it is the one we would be asked to produce."""
    _set(client, [])
    granted = _count(client)
    r = _set(client, ["marketing"])
    assert r.status_code == 200
    assert _count(client) == granted - 1


def test_agreeing_again_after_a_withdrawal_counts_once(client):
    _set(client, [])
    _set(client, ["marketing"])
    base = _count(client)
    _set(client, [])
    assert _count(client) == base + 1


def test_the_count_route_needs_the_internal_token(client):
    assert client.post("/internal/reminders/consent/count",
                       json={"tenant": TENANT}).status_code == 401


def test_the_count_route_returns_a_number_and_never_a_list(client):
    """A route that returned WHO consented would be a customer export wearing a different name."""
    _set(client, [])
    body = client.post("/internal/reminders/consent/count", json={"tenant": TENANT},
                       headers=INTERNAL).json()
    assert set(body) == {"tenant", "granted"}
    assert isinstance(body["granted"], int)


def test_a_malformed_reference_changes_nothing_and_says_nothing(client):
    """Same shape of answer as a valid reference that changed nothing — the link must never become
    an oracle for whether a customer exists."""
    r = client.put("/api/v1/prefs/not-a-reference", json={"stopped": []})
    assert r.status_code == 200 and r.json()["saved"] is False
