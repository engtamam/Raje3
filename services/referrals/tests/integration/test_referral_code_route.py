"""POST /internal/referrals/code — real HTTP, real auth, real idempotency."""
from __future__ import annotations

from tests.conftest import INTERNAL_TOKEN

_HEADERS = {"X-Internal-Token": INTERNAL_TOKEN}


def test_requires_the_internal_token(client):
    r = client.post("/internal/referrals/code", json={"phone": "0501234567"})
    assert r.status_code == 401


def test_mints_a_real_five_character_code(client):
    r = client.post("/internal/referrals/code", json={"phone": "0501234567"}, headers=_HEADERS)
    assert r.status_code == 200
    code = r.json()["code"]
    assert len(code) == 5
    assert code[0].isalpha()


def test_is_idempotent_across_two_separate_requests(client):
    first = client.post("/internal/referrals/code", json={"phone": "0507654321"}, headers=_HEADERS)
    second = client.post("/internal/referrals/code", json={"phone": "0507654321"}, headers=_HEADERS)
    assert first.json()["code"] == second.json()["code"]


def test_different_typed_shapes_of_the_same_phone_get_the_same_code(client):
    a = client.post("/internal/referrals/code", json={"phone": "0501112222"}, headers=_HEADERS)
    b = client.post("/internal/referrals/code", json={"phone": "+966501112222"}, headers=_HEADERS)
    assert a.json()["code"] == b.json()["code"]


def test_an_empty_phone_is_refused_honestly(client):
    r = client.post("/internal/referrals/code", json={"phone": ""}, headers=_HEADERS)
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"
