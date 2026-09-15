"""POST /internal/loyalty/replay-free-visits — migrated off its own CronJob to job-service push
dispatch (2026-09-16), same as tick and recover. Now requires a valid, unreplayed push signature
on top of the shared internal token."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

INTERNAL_TOKEN = "t" * 40


def push_headers(body: bytes, *, ts: int | None = None) -> dict[str, str]:
    import hashlib
    import hmac
    import time

    from app.core.push_verify import SIGNATURE_HEADER, TIMESTAMP_HEADER

    t = ts if ts is not None else int(time.time())
    signed = f"{t}.".encode("utf-8") + body
    sig = hmac.new(INTERNAL_TOKEN.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return {SIGNATURE_HEADER: sig, TIMESTAMP_HEADER: str(t)}


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({"ENV": "test", "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
                       "RATELIMIT_MAX": "1000", "SECRETS_KEK": "unit-test-kek-not-a-real-key"})
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def test_replay_free_visits_refuses_without_a_push_signature(client):
    r = client.post("/internal/loyalty/replay-free-visits",
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 401


def test_replay_free_visits_with_a_valid_push_signature_succeeds(client):
    r = client.post("/internal/loyalty/replay-free-visits",
                    headers={"X-Internal-Token": INTERNAL_TOKEN, **push_headers(b"")})
    assert r.status_code == 200, r.text


def test_replay_free_visits_with_a_replayed_old_signature_is_refused(client):
    import time

    old_headers = push_headers(b"", ts=int(time.time()) - 600)
    r = client.post("/internal/loyalty/replay-free-visits",
                    headers={"X-Internal-Token": INTERNAL_TOKEN, **old_headers})
    assert r.status_code == 401
