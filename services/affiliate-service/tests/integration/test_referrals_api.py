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
