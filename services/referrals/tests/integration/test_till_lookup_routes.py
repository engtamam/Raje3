"""GET /internal/referrals/lookup/{code} and GET /internal/referrals/campaigns/active — the two
reads a till-side redemption in another service (services/operations, Phase 3) needs before it can
validate a code a customer presented."""
from __future__ import annotations

from tests.conftest import INTERNAL_TOKEN

_HEADERS = {"X-Internal-Token": INTERNAL_TOKEN}


def test_lookup_unknown_code_is_404(client):
    r = client.get("/internal/referrals/lookup/ZZZZZ", headers=_HEADERS)
    assert r.status_code == 404


def test_lookup_a_real_code_returns_its_referrer_phone(client):
    minted = client.post("/internal/referrals/code", json={"phone": "0509998888"},
                         headers=_HEADERS)
    code = minted.json()["code"]
    r = client.get(f"/internal/referrals/lookup/{code}", headers=_HEADERS)
    assert r.status_code == 200
    assert r.json()["phone"]


def test_lookup_requires_the_internal_token(client):
    assert client.get("/internal/referrals/lookup/ABCDE").status_code == 401


def test_active_campaign_for_a_tenant_with_none_is_404(client):
    r = client.get("/internal/referrals/campaigns/active", params={"tenant": "no-campaigns-here"},
                   headers=_HEADERS)
    assert r.status_code == 404


def test_active_campaign_requires_the_internal_token(client):
    assert client.get("/internal/referrals/campaigns/active",
                      params={"tenant": "t1"}).status_code == 401
