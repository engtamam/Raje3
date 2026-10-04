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


def test_active_campaign_with_no_tenant_query_param_is_422_not_500(client):
    r = client.get("/internal/referrals/campaigns/active", headers=_HEADERS)
    assert r.status_code == 422


def test_lookup_a_very_long_code_is_a_clean_404_not_a_crash(client):
    r = client.get("/internal/referrals/lookup/" + "X" * 500, headers=_HEADERS)
    assert r.status_code == 404


def test_lookup_a_code_shaped_like_a_path_traversal_attempt_is_a_clean_404(client):
    # An exact-string datastore key lookup (see core/referral_code.py's own phone_for_code) has
    # no filesystem or query semantics to escape — this proves the route treats it as inert text,
    # never as a path segment to resolve or a query fragment to interpret.
    r = client.get("/internal/referrals/lookup/..%2F..%2Fetc%2Fpasswd", headers=_HEADERS)
    assert r.status_code == 404


def test_lookup_a_code_with_sql_injection_shaped_text_is_a_clean_404(client):
    r = client.get("/internal/referrals/lookup/" + "1%27%20OR%20%271%27%3D%271",
                   headers=_HEADERS)
    assert r.status_code == 404
