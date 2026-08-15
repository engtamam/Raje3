"""The create route refuses a shop that has not bought campaigns — and says so readably.

TWO THINGS ARE ASSERTED HERE THAT A UNIT TEST CANNOT SEE:

  · the refusal REACHES the caller. The platform's error handler strips `detail` off every
    HTTPException on purpose (CWE-209), so a raised refusal arrives as an empty 402 and the screen
    has nothing to render. This one is returned as a body.
  · it happens BEFORE anything is written. A shop without the app must not leave a campaign row
    behind, and 402-after-write is how a "refused" campaign fires on the next tick.
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


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture(scope="module")
def client():
    saved = dict(os.environ)
    app = _make_app()
    yield app
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def _auth(caps, tenant="t1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "tenant": tenant, "caps": caps,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _Licence:
    def __init__(self, allowed):
        self._allowed = allowed
        self.asked = []

    async def allowed(self, tenant):
        self.asked.append(tenant)
        return self._allowed


def _rows(client):
    return client.app.state.container.datastore._data.get("campaigns", {})     # noqa: SLF001


def test_a_shop_without_the_app_is_refused_with_a_sentence(client):
    from app.core.licence import NOT_INCLUDED

    container = client.app.state.container
    before = getattr(container, "licence", None)
    container.licence = _Licence(False)
    try:
        r = client.post("/api/v1/campaigns",
                        json={"goal": "announce", "owner_text": "افتتحنا فرعاً"},
                        headers=_auth(["campaigns.manage"]))
        assert r.status_code == 402
        # THE SENTENCE SURVIVES. A raised HTTPException would arrive stripped and the screen would
        # show an empty refusal.
        assert r.json().get("reason") == NOT_INCLUDED
        # AND NOTHING WAS WRITTEN — a refused campaign that leaves a row fires on the next tick.
        assert _rows(client) == {}
    finally:
        container.licence = before


def test_the_check_is_asked_about_the_caller_s_own_establishment(client):
    container = client.app.state.container
    before = getattr(container, "licence", None)
    licence = _Licence(False)
    container.licence = licence
    try:
        client.post("/api/v1/campaigns", json={"goal": "announce", "owner_text": "جديد"},
                    headers=_auth(["campaigns.manage"], tenant="shop_9"))
        assert licence.asked == ["shop_9"]
    finally:
        container.licence = before


def test_the_capability_alone_is_not_enough(client):
    """THE DEFECT IN ONE LINE. `campaigns.manage` is on every plan's owner role, so the console's
    lock never appeared for the one person who would have paid to remove it."""
    container = client.app.state.container
    before = getattr(container, "licence", None)
    container.licence = _Licence(False)
    try:
        r = client.post("/api/v1/campaigns", json={"goal": "announce", "owner_text": "جديد"},
                        headers=_auth(["campaigns.manage", "campaigns.read"]))
        assert r.status_code == 402
    finally:
        container.licence = before
