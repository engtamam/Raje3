"""What the owner told the WhatsApp AI assistant about his own shop — read/write from his own
token, plus the internal peer route whatsapp-assistant calls to get it.

THE KILL SWITCH IS ENFORCED AT EVERY DOOR, not only hidden from the console: `AI_NOTES_ENABLED`
false blanks GET, refuses PUT, and blanks the internal route — the same value stored, unreachable
three different ways, is the point (see config.py's own comment on why this is never a data-loss
switch).
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/staff/ai-notes"
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


def _headers(tenant="tnt_notes", *, caps=("operations.manage",)) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u_owner", "iss": ISS, "aud": AUD,
                      "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_shop_that_never_wrote_anything_reads_back_empty(client):
    r = client.get(PATH, headers=_headers())
    assert r.status_code == 200
    assert r.json() == {"text": ""}


def test_the_owner_writes_and_reads_back_his_own_notes(client):
    put = client.put(PATH, json={"text": "نفتح من السبت للخميس"}, headers=_headers())
    assert put.status_code == 200, put.text
    assert put.json()["text"] == "نفتح من السبت للخميس"
    assert put.json()["redacted"] == []

    got = client.get(PATH, headers=_headers())
    assert got.json()["text"] == "نفتح من السبت للخميس"


def test_a_phone_number_is_redacted_and_the_owner_is_told_so(client):
    put = client.put(PATH, json={"text": "اتصل على 0501234567"}, headers=_headers())
    assert put.status_code == 200, put.text
    assert "0501234567" not in put.json()["text"]
    assert "phone" in put.json()["redacted"]


def test_an_oversized_note_is_refused_with_a_reason(client):
    r = client.put(PATH, json={"text": "x" * 2001}, headers=_headers())
    assert r.status_code == 400
    assert r.json()["error"] == "BAD_REQUEST"


def test_one_shops_notes_are_not_readable_by_another(client):
    client.put(PATH, json={"text": "سرّ محل أ"}, headers=_headers("tnt_a"))
    r = client.get(PATH, headers=_headers("tnt_b"))
    assert r.json()["text"] == ""


def test_a_reader_without_manage_capability_is_refused(client):
    r = client.get(PATH, headers=_headers(caps=("operations.read",)))
    assert r.status_code == 403


def test_ai_notes_enabled_false_blanks_the_field_without_erasing_it(client):
    """Turning it off is a behaviour switch, not a data-loss one — the stored text survives and
    reappears the moment it is turned back on. Flipped on the SAME running app/datastore, not a
    freshly created one, so the only thing that changes between reads is the flag."""
    client.put(PATH, json={"text": "ملاحظات ما قبل الإيقاف"}, headers=_headers())
    settings = client.app.state.container_settings

    settings.AI_NOTES_ENABLED = False
    try:
        got_off = client.get(PATH, headers=_headers())
        assert got_off.json()["text"] == ""

        put_off = client.put(PATH, json={"text": "محاولة أثناء الإيقاف"}, headers=_headers())
        assert put_off.status_code == 503
    finally:
        settings.AI_NOTES_ENABLED = True

    got_back = client.get(PATH, headers=_headers())
    assert got_back.json()["text"] == "ملاحظات ما قبل الإيقاف"


# ── the internal peer route whatsapp-assistant calls ──────────────────────────
def test_the_internal_shop_name_route_also_returns_ai_notes(client):
    client.put(PATH, json={"text": "ملاحظات لواتساب"}, headers=_headers("tnt_peer"))

    r = client.post("/internal/operations/shop-name", json={"tenant": "tnt_peer"},
                    headers={"X-Internal-Token": "t" * 40})
    assert r.status_code == 200, r.text
    assert r.json()["ai_notes"] == "ملاحظات لواتساب"


def test_the_internal_route_blanks_ai_notes_too_when_disabled(client):
    client.put(PATH, json={"text": "قبل الإيقاف"}, headers=_headers("tnt_peer2"))
    settings = client.app.state.container_settings

    settings.AI_NOTES_ENABLED = False
    try:
        r = client.post("/internal/operations/shop-name", json={"tenant": "tnt_peer2"},
                        headers={"X-Internal-Token": "t" * 40})
        assert r.json()["ai_notes"] == ""
    finally:
        settings.AI_NOTES_ENABLED = True
