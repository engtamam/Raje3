"""GET /api/v1/assistant/growth/my-impact — محلّي's own "أثر الذكاء الاصطناعي" card. Same shop
capability as pricing/current; ALWAYS scoped to the caller's own tenant, never platform-wide, and
never another tenant's — the whole point of the fix this route exists alongside.
"""
from __future__ import annotations

import datetime as dt
import os
import time
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
KEK = "unit-test-kek-not-a-real-key"

PATH = "/api/v1/assistant/growth/my-impact"


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
        "SECRETS_KEK": KEK,
        "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str | None = "t1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "shop1", "iss": ISS, "aud": AUD, "caps": list(caps),
             "exp": now + dt.timedelta(minutes=5), "iat": now}
    if tenant is not None:
        claims["tenant"] = tenant
    tok = jwt.encode(claims, TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client() -> TestClient:
    saved = dict(os.environ)
    app = _make_app()
    yield app
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def shop_auth() -> dict:
    return _auth("whatsapp_assistant.pricing_read", tenant="t1")


class _StubActorReport:
    def __init__(self, bookings: list[dict[str, Any]]) -> None:
        self._bookings = bookings

    async def by_actor(self, tenant, created_by, *, branch_id="", since=None, until=None):
        rows = [b for b in self._bookings if b["tenant"] == tenant
               and (since is None or b["created"] >= since) and (until is None or b["created"] <= until)]
        return {"bookings": rows, "truncated": False}


class _StubCatalog:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def list_active(self, tenant):
        return self._rows


def test_unauthenticated_is_refused(client):
    assert client.get(PATH).status_code == 401


def test_a_shop_without_the_capability_is_refused(client, shop_auth):
    r = client.get(PATH, headers=_auth("reports.read", tenant="t1"))
    assert r.status_code == 403


def test_a_platform_operator_token_with_no_tenant_is_refused_not_computed_empty(client):
    """The real bug fixed elsewhere this same day, guarded against structurally here: a platform-
    operator token genuinely has no tenant claim — this route must refuse, not silently compute a
    meaningless report for tenant=''."""
    r = client.get(PATH, headers=_auth("whatsapp_assistant.pricing_read", tenant=None))
    assert r.status_code == 400


def test_an_empty_shop_gets_an_honest_zero_report(client, shop_auth):
    body = client.get(PATH, headers=shop_auth).json()
    assert body == {
        "days": 30, "conversations": 0, "ai_bookings": 0, "conversion_rate": None,
        "avg_invoice_value_minor": None, "upsell_offered": 0, "upsell_accepted": 0,
        "upsell_acceptance_rate": None, "truncated": False,
    }


def test_two_tenants_never_mix_in_this_shops_own_report(client, shop_auth):
    """The whole reason this route exists as a SEPARATE module from the admin panel's own
    (platform-wide) reports — see core/shop_impact_report.py's own docstring."""
    container = client.app.state.container
    now = int(time.time())

    async def _seed():
        import uuid

        from app.core.models import COST_LEDGER
        await container.datastore.put(COST_LEDGER, f"t1:{now}:{uuid.uuid4().hex[:8]}", {
            "tenant": "t1", "subject_ref": "s1", "at": now - 5,
            "input_tokens": 100, "output_tokens": 50})
        await container.datastore.put(COST_LEDGER, f"t2:{now}:{uuid.uuid4().hex[:8]}", {
            "tenant": "t2", "subject_ref": "s2", "at": now - 5,
            "input_tokens": 100, "output_tokens": 50})

    import asyncio
    asyncio.run(_seed())

    container.booking_actor_report = _StubActorReport([
        {"id": "b1", "tenant": "t1", "branch_id": "br1", "status": "attended",
         "service_ids": ["svc1"], "package_id": "", "price_override_minor": None,
         "created": now - 5},
        {"id": "b2", "tenant": "t2", "branch_id": "br1", "status": "attended",
         "service_ids": ["svc1"], "package_id": "", "price_override_minor": None,
         "created": now - 5},
    ])
    container.service_catalog = _StubCatalog([{"id": "svc1", "price_minor": 9000}])
    container.package_catalog = _StubCatalog([])

    body = client.get(PATH, headers=shop_auth).json()
    assert body["conversations"] == 1        # only t1's own, not t2's
    assert body["ai_bookings"] == 1
    assert body["avg_invoice_value_minor"] == 9000
