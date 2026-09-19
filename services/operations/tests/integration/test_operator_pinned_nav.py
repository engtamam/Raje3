"""PATCH /staff/operators/me/pinned-nav — an operator's own mobile bottom-bar personalisation.
Same self-service shape as test_operator_locale.py: found by WHO is asking (`sub` == a row's
`person_id`), never by an id in the path, so nobody can read or change another operator's
pin list through this door.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_pinned_nav"


def _make_app(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(subject: str, *caps: str, tenant: str = TENANT) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": subject, "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture
def client(env_guard) -> TestClient:
    return _make_app()


def _seed_operator(client, *, oid: str, person_id: str, pinned: list[str] | None = None) -> str:
    from app.core.models import Operator
    from app.core.stores import OperatorStore

    op = Operator(id=oid, tenant=TENANT, name="محمد", role="operator", person_id=person_id,
                 active=True, pinned_nav_ids=list(pinned or []))
    asyncio.run(OperatorStore(client.app.state.container.datastore).save(op))
    return op.id


def test_an_operator_sets_his_own_pin_list(client):
    _seed_operator(client, oid="opr_1", person_id="person_abc")
    auth = _auth("person_abc", "bookings.write")

    res = client.patch("/api/v1/staff/operators/me/pinned-nav",
                       json={"pinned_nav_ids": ["visit", "bookings"]}, headers=auth)
    assert res.status_code == 200, res.text
    assert res.json()["pinned_nav_ids"] == ["visit", "bookings"]

    # PERSISTED, not just echoed — a fresh read agrees.
    again = client.get("/api/v1/staff/operators/me", headers=auth)
    assert again.json()["pinned_nav_ids"] == ["visit", "bookings"]


def test_default_is_an_empty_list(client):
    _seed_operator(client, oid="opr_2", person_id="person_default")
    res = client.get("/api/v1/staff/operators/me", headers=_auth("person_default", "bookings.write"))
    assert res.json()["pinned_nav_ids"] == []


def test_duplicates_are_collapsed_keeping_first_occurrence_order(client):
    _seed_operator(client, oid="opr_3", person_id="person_dup")
    res = client.patch("/api/v1/staff/operators/me/pinned-nav",
                       json={"pinned_nav_ids": ["visit", "shop", "visit"]},
                       headers=_auth("person_dup", "bookings.write"))
    assert res.status_code == 200, res.text
    assert res.json()["pinned_nav_ids"] == ["visit", "shop"]


def test_more_than_four_pins_is_refused(client):
    _seed_operator(client, oid="opr_4", person_id="person_toomany")
    res = client.patch("/api/v1/staff/operators/me/pinned-nav",
                       json={"pinned_nav_ids": ["a", "b", "c", "d", "e"]},
                       headers=_auth("person_toomany", "bookings.write"))
    assert res.status_code == 422


def test_one_operator_cannot_set_a_colleagues_pin_list(client):
    """There is no id in this route at all — the ONLY row that can ever be touched is the
    caller's own, found by `sub`. Seeding a second operator and asserting the FIRST one's row
    is untouched is the real guarantee here, not a permission string."""
    _seed_operator(client, oid="opr_5", person_id="person_a", pinned=["visit"])
    _seed_operator(client, oid="opr_6", person_id="person_b", pinned=["visit"])

    client.patch("/api/v1/staff/operators/me/pinned-nav", json={"pinned_nav_ids": ["shop", "points"]},
                headers=_auth("person_b", "bookings.write"))

    untouched = client.get("/api/v1/staff/operators/me", headers=_auth("person_a", "bookings.write"))
    assert untouched.json()["pinned_nav_ids"] == ["visit"]


def test_no_write_capability_at_all_is_refused(client):
    _seed_operator(client, oid="opr_7", person_id="person_noauth")
    res = client.patch("/api/v1/staff/operators/me/pinned-nav", json={"pinned_nav_ids": ["visit"]},
                       headers=_auth("person_noauth"))
    assert res.status_code == 403


def test_the_owner_himself_cannot_patch_a_pin_list_he_has_no_row_for(client):
    res = client.patch("/api/v1/staff/operators/me/pinned-nav", json={"pinned_nav_ids": ["visit"]},
                       headers=_auth("owner_person", "bookings.write"))
    assert res.status_code == 404
