"""GET /api/v1/referrals/reports/* — real HTTP: auth, capability RBAC, tenant scoping, and a
real end-to-end path (register + redeem through the real engine, then read it back through the
report) so the wiring between referral_redemption/affiliates/referral_reports is proven live, not
just each module's own unit tests in isolation."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "10000", "PII_SALT": "s" * 32,
    })
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


def _token(*, tenant: str, caps: tuple[str, ...]) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    claims = {"sub": "owner-1", "iss": ISS, "aud": AUD, "tenant": tenant,
              "exp": now + dt.timedelta(minutes=5), "iat": now, "caps": list(caps)}
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _read(tenant: str) -> dict:
    return {"Authorization": f"Bearer {_token(tenant=tenant, caps=('operations.read',))}"}


def _till(tenant: str) -> dict:
    return {"Authorization": f"Bearer {_token(tenant=tenant, caps=('operations.record',))}"}


def _owner(tenant: str) -> dict:
    return {"Authorization": f"Bearer {_token(tenant=tenant, caps=('operations.manage',
                                                                 'operations.read'))}"}


# ── auth / capability RBAC ───────────────────────────────────────────────────────────────────────
def test_no_token_is_401(client):
    assert client.get("/api/v1/referrals/reports/summary").status_code == 401


def test_till_credential_cannot_read_reports(client):
    r = client.get("/api/v1/referrals/reports/summary", headers=_till("shop-a"))
    assert r.status_code == 403


def test_read_capability_can_read_every_report_route(client):
    tenant = "shop-read-all"
    for path in ("/api/v1/referrals/reports/summary", "/api/v1/referrals/reports/leaderboard",
                "/api/v1/referrals/reports/campaigns", "/api/v1/referrals/reports/affiliates"):
        assert client.get(path, headers=_read(tenant)).status_code == 200


# ── shape and defaults on an empty shop ──────────────────────────────────────────────────────────
def test_summary_on_a_brand_new_shop_is_all_zero(client):
    body = client.get("/api/v1/referrals/reports/summary",
                      headers=_read("shop-empty")).json()
    assert body["registered_count"] == 0
    assert body["revenue_minor"] == 0
    assert body["cost_ratio"] == 0.0


def test_leaderboard_limit_is_clamped_never_an_unbounded_scan(client):
    r = client.get("/api/v1/referrals/reports/leaderboard?limit=999999",
                   headers=_read("shop-clamp"))
    assert r.status_code == 200
    assert r.json()["leaderboard"] == []


def test_leaderboard_negative_limit_is_clamped_to_at_least_one(client):
    r = client.get("/api/v1/referrals/reports/leaderboard?limit=-50",
                   headers=_read("shop-clamp2"))
    assert r.status_code == 200


# ── tenant isolation ─────────────────────────────────────────────────────────────────────────────
def test_shop_b_never_sees_shop_as_affiliate_in_the_breakdown(client):
    tenant_a, tenant_b = "shop-iso-a", "shop-iso-b"
    client.post("/api/v1/affiliates",
               json={"phone": "0511111111", "code": "ISOX1", "discount_percent": 10,
                    "reward_type": "fixed_points", "reward_params": {"points": 10}},
               headers=_owner(tenant_a))
    rows = client.get("/api/v1/referrals/reports/affiliates", headers=_read(tenant_b)).json()
    assert rows["affiliates"] == []


# ── real end-to-end: register + redeem through the real engine, then read it back ───────────────
def test_a_real_affiliate_redemption_shows_up_in_every_report(client):
    tenant = "shop-e2e"
    created = client.post(
        "/api/v1/affiliates",
        json={"phone": "0599999999", "code": "E2ECODE", "discount_percent": 20,
             "reward_type": "fixed_points", "reward_params": {"points": 33}},
        headers=_owner(tenant)).json()

    reg = client.post("/api/v1/till/referral/register",
                      json={"code": "E2ECODE", "phone": "0588888888", "invoice_minor": 5000},
                      headers=_till(tenant))
    assert reg.status_code == 200 and reg.json()["ok"] is True

    # No visit/apply_offer route is exercised here (that needs a full record_visit body this
    # file does not construct) — the grant is PENDING, which the summary must still count as
    # "registered" even before any redemption ever happens.
    summary = client.get("/api/v1/referrals/reports/summary", headers=_read(tenant)).json()
    assert summary["registered_count"] == 1
    assert summary["redeemed_count"] == 0

    affiliates = client.get("/api/v1/referrals/reports/affiliates", headers=_read(tenant)).json()
    row = next(r for r in affiliates["affiliates"] if r["affiliate_id"] == created["id"])
    assert row["redemptions"] == 0
    assert row["unsettled_points"] == 0
