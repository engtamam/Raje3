"""The per-shop customer-message word limit — read/write from the owner's own token, plus the
internal peer route whatsapp-assistant calls to get it.

THE KILL SWITCH IS ENFORCED AT EVERY DOOR, not only hidden from the console: `MSG_WORD_LIMIT_
ENABLED` false blanks GET (back to the default), refuses PUT, and blanks the internal route — same
posture as `AI_NOTES_ENABLED` (test_shop_ai_notes.py).
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/staff/msg-word-limit"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"


def _make_app(**env_over):
    from app.config import get_settings

    env = {
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture()
def client():
    saved = dict(os.environ)
    yield _make_app()
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def _headers(tenant="tnt_limit", *, caps=("operations.manage",)) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u_owner", "iss": ISS, "aud": AUD,
                      "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_shop_that_never_set_anything_reads_back_the_default(client):
    r = client.get(PATH, headers=_headers())
    assert r.status_code == 200
    assert r.json() == {"limit": 100}


def test_the_owner_sets_and_reads_back_his_own_limit(client):
    put = client.put(PATH, json={"limit": 60}, headers=_headers())
    assert put.status_code == 200, put.text
    assert put.json()["limit"] == 60

    got = client.get(PATH, headers=_headers())
    assert got.json()["limit"] == 60


def test_a_value_below_the_minimum_is_refused_with_a_reason(client):
    r = client.put(PATH, json={"limit": 5}, headers=_headers())
    assert r.status_code in (400, 422)


def test_a_value_above_the_maximum_is_refused_with_a_reason(client):
    r = client.put(PATH, json={"limit": 5000}, headers=_headers())
    assert r.status_code in (400, 422)


def test_one_shops_limit_is_not_readable_by_another(client):
    client.put(PATH, json={"limit": 30}, headers=_headers("tnt_a"))
    r = client.get(PATH, headers=_headers("tnt_b"))
    assert r.json()["limit"] == 100


def test_a_reader_without_manage_capability_is_refused(client):
    r = client.get(PATH, headers=_headers(caps=("operations.read",)))
    assert r.status_code == 403


def test_msg_word_limit_enabled_false_blanks_the_field_without_erasing_it(client):
    """Turning it off is a behaviour switch, not a data-loss one — the stored value survives and
    reappears the moment it is turned back on. Flipped on the SAME running app/datastore, not a
    freshly created one, so the only thing that changes between reads is the flag."""
    client.put(PATH, json={"limit": 40}, headers=_headers())
    settings = client.app.state.container_settings

    settings.MSG_WORD_LIMIT_ENABLED = False
    try:
        got_off = client.get(PATH, headers=_headers())
        assert got_off.json()["limit"] == 100

        put_off = client.put(PATH, json={"limit": 25}, headers=_headers())
        assert put_off.status_code == 503
    finally:
        settings.MSG_WORD_LIMIT_ENABLED = True

    got_back = client.get(PATH, headers=_headers())
    assert got_back.json()["limit"] == 40


# ── the internal peer route whatsapp-assistant calls ──────────────────────────
def test_the_internal_shop_name_route_also_returns_msg_word_limit(client):
    client.put(PATH, json={"limit": 45}, headers=_headers("tnt_peer"))

    r = client.post("/internal/operations/shop-name", json={"tenant": "tnt_peer"},
                    headers={"X-Internal-Token": "t" * 40})
    assert r.status_code == 200, r.text
    assert r.json()["msg_word_limit"] == 45


def test_the_internal_route_defaults_msg_word_limit_too_when_disabled(client):
    client.put(PATH, json={"limit": 45}, headers=_headers("tnt_peer2"))
    settings = client.app.state.container_settings

    settings.MSG_WORD_LIMIT_ENABLED = False
    try:
        r = client.post("/internal/operations/shop-name", json={"tenant": "tnt_peer2"},
                        headers={"X-Internal-Token": "t" * 40})
        assert r.json()["msg_word_limit"] == 100
    finally:
        settings.MSG_WORD_LIMIT_ENABLED = True


def test_the_internal_route_defaults_msg_word_limit_for_an_unknown_tenant(client):
    r = client.post("/internal/operations/shop-name", json={"tenant": "tnt_never_seen"},
                    headers={"X-Internal-Token": "t" * 40})
    assert r.status_code == 200, r.text
    assert r.json()["found"] is False
    assert r.json()["msg_word_limit"] == 100
