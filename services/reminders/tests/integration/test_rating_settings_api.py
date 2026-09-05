"""GET/PUT /api/v1/reminders/rating_settings — real auth, real capability gate, real validation."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"


def _make_app(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def auth_env():
    from app.config import get_settings

    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(auth_env) -> TestClient:
    return _make_app()


def _token(caps=None, tenant="t1", secret=SECRET, **over) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "u1", "iss": ISS, "aud": AUD, "tenant": tenant,
              "exp": now + dt.timedelta(minutes=5), "iat": now}
    if caps is not None:
        claims["caps"] = caps
    claims.update(over)
    return jwt.encode(claims, secret, algorithm="HS256")


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


READ = ["reminders.read"]
MANAGE = ["reminders.manage"]
# AN OWNER HOLDS BOTH IN REAL LIFE — `reminders.manage` alone (no `reminders.read`) is a token
# shape that never occurs for a person, only useful for proving the two capabilities are checked
# separately (`test_read_capability_alone_cannot_write`, `test_manage_capability_can_write`).
# Every round-trip test below needs an actual owner token, so it carries both.
READ_MANAGE = READ + MANAGE
PATH = "/api/v1/reminders/rating_settings"


# ── auth ──────────────────────────────────────────────────────────────────────────────────────
def test_no_bearer_is_401(client):
    assert client.get(PATH).status_code == 401


def test_read_capability_can_read(client):
    r = client.get(PATH, headers=_auth(_token(caps=READ, tenant="t_read")))
    assert r.status_code == 200


def test_read_capability_alone_cannot_write(client):
    r = client.put(PATH, json={"enabled": False},
                   headers=_auth(_token(caps=READ, tenant="t_read2")))
    assert r.status_code == 403


def test_manage_capability_can_write(client):
    r = client.put(PATH, json={"enabled": False},
                   headers=_auth(_token(caps=MANAGE, tenant="t_manage")))
    assert r.status_code == 200


def test_no_capability_at_all_is_refused_on_read(client):
    r = client.get(PATH, headers=_auth(_token(caps=[], tenant="t_none")))
    assert r.status_code == 403


# ── the defaults, over the wire ──────────────────────────────────────────────────────────────
def test_a_tenant_who_never_wrote_reads_the_products_defaults(client):
    r = client.get(PATH, headers=_auth(_token(caps=READ, tenant="t_fresh")))
    body = r.json()
    assert body["enabled"] is True
    assert body["delay_minutes"] == 10
    assert body["points"] == 0


# ── round trip over the wire ──────────────────────────────────────────────────────────────────
def test_writing_delay_minutes_is_readable_back(client):
    h = _auth(_token(caps=READ_MANAGE, tenant="t_rt1"))
    client.put(PATH, json={"delay_minutes": 90}, headers=h)
    assert client.get(PATH, headers=h).json()["delay_minutes"] == 90


def test_writing_points_is_readable_back(client):
    h = _auth(_token(caps=READ_MANAGE, tenant="t_rt2"))
    client.put(PATH, json={"points": 3}, headers=h)
    assert client.get(PATH, headers=h).json()["points"] == 3


def test_partial_write_leaves_the_other_fields_alone(client):
    h = _auth(_token(caps=READ_MANAGE, tenant="t_rt3"))
    client.put(PATH, json={"enabled": False, "delay_minutes": 30, "points": 2}, headers=h)
    client.put(PATH, json={"points": 9}, headers=h)
    body = client.get(PATH, headers=h).json()
    assert body == {"enabled": False, "delay_minutes": 30, "points": 9}


def test_two_tenants_are_fully_isolated_over_the_wire(client):
    ha = _auth(_token(caps=READ_MANAGE, tenant="t_iso_a"))
    hb = _auth(_token(caps=READ_MANAGE, tenant="t_iso_b"))
    client.put(PATH, json={"delay_minutes": 15}, headers=ha)
    client.put(PATH, json={"delay_minutes": 300}, headers=hb)
    assert client.get(PATH, headers=ha).json()["delay_minutes"] == 15
    assert client.get(PATH, headers=hb).json()["delay_minutes"] == 300


# ── validation, over the wire ─────────────────────────────────────────────────────────────────
# `ge`/`le` ON THE PYDANTIC FIELD MIRROR THE STORE'S OWN BOUNDS EXACTLY, on purpose — belt and
# suspenders, not two different rules. So an out-of-range value never reaches
# `RatingSettingsStore.set`'s own `ValueError` at all; it is refused as an ordinary 422 at the
# schema boundary, and `test_rating_settings.py` (unit) is what actually exercises that
# `ValueError` path directly against the store.
def test_zero_delay_is_refused_at_the_schema_boundary(client):
    h = _auth(_token(caps=MANAGE, tenant="t_bad1"))
    r = client.put(PATH, json={"delay_minutes": 0}, headers=h)
    assert r.status_code == 422


def test_negative_points_is_refused_at_the_schema_boundary(client):
    h = _auth(_token(caps=MANAGE, tenant="t_bad2"))
    r = client.put(PATH, json={"points": -1}, headers=h)
    assert r.status_code == 422


def test_a_refused_write_does_not_change_the_stored_value(client):
    h = _auth(_token(caps=READ_MANAGE, tenant="t_bad3"))
    client.put(PATH, json={"delay_minutes": 45}, headers=h)
    r = client.put(PATH, json={"delay_minutes": 0}, headers=h)
    assert r.status_code == 422
    assert client.get(PATH, headers=h).json()["delay_minutes"] == 45


def test_pydantic_itself_refuses_an_out_of_range_delay_before_the_store_is_asked(client):
    # ge/le on the field — a request this malformed never reaches RatingSettingsStore.set at all.
    h = _auth(_token(caps=MANAGE, tenant="t_bad4"))
    r = client.put(PATH, json={"delay_minutes": 999_999}, headers=h)
    assert r.status_code == 422


def test_pydantic_itself_refuses_a_negative_points_before_the_store_is_asked(client):
    h = _auth(_token(caps=MANAGE, tenant="t_bad5"))
    r = client.put(PATH, json={"points": -5}, headers=h)
    assert r.status_code == 422


def test_an_empty_body_is_accepted_and_changes_nothing(client):
    h = _auth(_token(caps=READ_MANAGE, tenant="t_empty"))
    client.put(PATH, json={"delay_minutes": 60}, headers=h)
    r = client.put(PATH, json={}, headers=h)
    assert r.status_code == 200
    assert r.json()["delay_minutes"] == 60
