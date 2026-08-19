"""POST /internal/referrals/stamp — reached only by another service (operations), never a user."""
from __future__ import annotations

from tests.conftest import INTERNAL_TOKEN


def test_stamp_refuses_without_the_internal_token(client):
    r = client.post("/internal/referrals/stamp",
                    json={"tenant": "t-1", "affiliate_id": "aff-1"})
    assert r.status_code == 401


def test_stamp_refuses_an_unknown_affiliate_with_a_clean_400(client):
    r = client.post("/internal/referrals/stamp",
                    json={"tenant": "t-x", "affiliate_id": "does-not-exist"},
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 400


def test_commissions_sync_refuses_without_the_internal_token(client):
    r = client.post("/internal/commissions/sync", json={"tenant": "t-1"})
    assert r.status_code == 401


def test_commissions_sync_reports_billing_not_configured_in_this_test_app(client):
    # This integration app has no BILLING_SERVICE_URL set — see test_commission.py for the real
    # sync() logic (referral lookup, conversion window, refunds, renewals) against a configured
    # engine; this only proves the route itself is wired and internal-token-gated.
    r = client.post("/internal/commissions/sync", json={"tenant": "no-such-tenant"},
                    headers={"X-Internal-Token": INTERNAL_TOKEN})
    assert r.status_code == 200, r.text
    assert r.json() == {"synced": False, "reason": "billing_not_configured"}
