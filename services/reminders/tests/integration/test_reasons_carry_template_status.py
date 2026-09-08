"""GET /api/v1/reminders/reasons — each row now carries `template_status`, the same badge the
admin panel's own template screen shows, surfaced here instead of hidden behind a modal.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"
PATH = "/api/v1/reminders/reasons"


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(env_guard) -> TestClient:
    c = _make_app()

    class Library:
        async def all(self):
            # `svc_visit_confirmation` is `visit_recorded`'s own type (core/reasons.py); one
            # tone registered and approved, so the reason should read "approved" overall.
            return [{"name": "svc_visit_confirmation_warm", "type": "svc_visit_confirmation",
                     "tone": "warm", "active": True}]

    class Approved:
        async def statuses(self, tenant):
            return {"svc_visit_confirmation_warm": "approved"}

    c.app.state.container.library = Library()
    c.app.state.container.approved_templates = Approved()
    return c


def _auth() -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": "t1",
                      "caps": ["reminders.read"], "exp": now + dt.timedelta(minutes=5),
                      "iat": now}, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_known_reason_carries_its_own_templates_status(client):
    r = client.get(PATH, headers=_auth())
    assert r.status_code == 200, r.text
    row = next(x for x in r.json()["reasons"] if x["id"] == "visit_recorded")
    assert row["template_status"] == "approved"


def test_a_type_nobody_registered_yet_reads_not_registered(client):
    r = client.get(PATH, headers=_auth())
    # `gone_missing` — mkt_winback — is not in this fake's library at all, so it is not_seeded;
    # a reason whose type WAS seeded but never registered would read not_registered instead. Both
    # are distinct from "unknown" (the peer could not be asked), which no test here can produce
    # since this fake's `statuses()` never fails.
    row = next(x for x in r.json()["reasons"] if x["id"] == "gone_missing")
    assert row["template_status"] == "not_seeded"
