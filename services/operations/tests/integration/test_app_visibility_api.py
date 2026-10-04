"""Per-tenant app-visibility overrides at the HTTP layer: the shop-self read
(`/subscription/apps/visibility-overrides`) never leaks another tenant's rows, and the platform
admin routes (`/platform/app-visibility`) require a real platform capability.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT_A = "tnt_alpha"
TENANT_B = "tnt_beta"
KEY = "feature.partner_loyalty"


def _make_app() -> TestClient:
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
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _shop_auth(tenant: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "staff1", "iss": ISS, "aud": AUD, "caps": [], "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _platform_auth(*caps: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": "_platform",
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


# ── the shop's OWN read ──────────────────────────────────────────────────────────────────────

def test_a_shop_with_no_overrides_gets_an_empty_list(client):
    r = client.get("/api/v1/subscription/apps/visibility-overrides", headers=_shop_auth(TENANT_A))
    assert r.status_code == 200
    assert r.json() == {"visible_keys": []}


def test_a_shop_sees_its_own_granted_key(client):
    client.put("/api/v1/platform/app-visibility", headers=_platform_auth("platform.operations"),
              json={"tenant": TENANT_A, "feature_key": KEY, "visible": True})
    r = client.get("/api/v1/subscription/apps/visibility-overrides", headers=_shop_auth(TENANT_A))
    assert r.status_code == 200
    assert r.json() == {"visible_keys": [KEY]}


def test_a_shop_can_never_see_another_shops_override_no_matter_what_it_asks(client):
    """THE core IDOR guarantee — the read route takes NO tenant parameter at all; the tenant comes
    only from the caller's own token, so there is no query string to attack in the first place."""
    client.put("/api/v1/platform/app-visibility", headers=_platform_auth("platform.operations"),
              json={"tenant": TENANT_A, "feature_key": KEY, "visible": True})
    r = client.get("/api/v1/subscription/apps/visibility-overrides",
                   headers=_shop_auth(TENANT_B),
                   params={"tenant": TENANT_A})  # even if a caller tries to smuggle one in
    assert r.status_code == 200
    assert r.json() == {"visible_keys": []}


def test_no_token_at_all_is_refused_on_the_shop_read(client):
    r = client.get("/api/v1/subscription/apps/visibility-overrides")
    assert r.status_code in (401, 403)


# ── the platform admin routes ───────────────────────────────────────────────────────────────────

def test_admin_set_requires_a_platform_capability(client):
    r = client.put("/api/v1/platform/app-visibility", headers=_shop_auth(TENANT_A),
                   json={"tenant": TENANT_A, "feature_key": KEY, "visible": True})
    assert r.status_code == 403


def test_admin_list_requires_a_platform_capability(client):
    r = client.get("/api/v1/platform/app-visibility", headers=_shop_auth(TENANT_A),
                   params={"tenant": TENANT_A})
    assert r.status_code == 403


def test_admin_set_succeeds_with_platform_operations(client):
    r = client.put("/api/v1/platform/app-visibility", headers=_platform_auth("platform.operations"),
                   json={"tenant": TENANT_A, "feature_key": KEY, "visible": True})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "tenant": TENANT_A, "feature_key": KEY, "visible": True}


def test_admin_set_refuses_a_malformed_feature_key(client):
    r = client.put("/api/v1/platform/app-visibility", headers=_platform_auth("platform.operations"),
                   json={"tenant": TENANT_A, "feature_key": "not-a-real-key", "visible": True})
    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_admin_set_rejects_a_blank_tenant_at_the_validation_layer(client):
    r = client.put("/api/v1/platform/app-visibility", headers=_platform_auth("platform.operations"),
                   json={"tenant": "", "feature_key": KEY, "visible": True})
    assert r.status_code == 422


def test_admin_list_reflects_what_was_set(client):
    client.put("/api/v1/platform/app-visibility", headers=_platform_auth("platform.operations"),
              json={"tenant": TENANT_A, "feature_key": KEY, "visible": True})
    r = client.get("/api/v1/platform/app-visibility", headers=_platform_auth("platform.operations"),
                   params={"tenant": TENANT_A})
    assert r.status_code == 200
    assert r.json() == {"tenant": TENANT_A, "overrides": [{"feature_key": KEY, "visible": True}]}


def test_admin_list_with_no_tenant_param_is_empty_not_an_error(client):
    r = client.get("/api/v1/platform/app-visibility", headers=_platform_auth("platform.operations"))
    assert r.status_code == 200
    assert r.json() == {"tenant": "", "overrides": []}


def test_no_token_at_all_is_refused_on_the_admin_routes(client):
    r = client.put("/api/v1/platform/app-visibility",
                   json={"tenant": TENANT_A, "feature_key": KEY, "visible": True})
    assert r.status_code in (401, 403)


def test_successful_set_is_audited(client):
    events: list[dict] = []

    async def _record(action, *, actor, tenant, resource, ip="", metadata=None):
        events.append({"action": action, "actor": actor, "tenant": tenant, "resource": resource,
                       "metadata": metadata})

    client.app.state.auditor.record = _record
    client.put("/api/v1/platform/app-visibility", headers=_platform_auth("platform.operations"),
              json={"tenant": TENANT_A, "feature_key": KEY, "visible": True})
    assert events == [{"action": "app_visibility.set", "actor": "op1", "tenant": TENANT_A,
                       "resource": f"tenant:{TENANT_A}:app:{KEY}", "metadata": {"visible": True}}]


def test_a_refused_set_is_never_audited(client):
    events: list[dict] = []

    async def _record(action, **kw):
        events.append(action)

    client.app.state.auditor.record = _record
    client.put("/api/v1/platform/app-visibility", headers=_platform_auth("platform.operations"),
              json={"tenant": TENANT_A, "feature_key": "bad-key", "visible": True})
    assert events == []
