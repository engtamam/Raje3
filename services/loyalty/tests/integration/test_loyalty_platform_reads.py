"""GET /loyalty/platform/balance and GET /loyalty/platform/history — the read-side companions of
`platform_reconcile` (spec/plan-support-customers-screen.md's own phase ج): a support agent
answering "where did my points go?" for a shop that is NOT the caller's own establishment, the same
`platform.loyalty` capability `platform_reconcile` already gates rather than a lesser one.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "k" * 40
ISS, AUD, TENANT = "iss", "aud", "shop_platform_reads"
S = "ref_platformread01"
INTERNAL = {"X-Internal-Token": "t" * 40}


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "5000",
        "SECRETS_KEK": "K" * 44, "PII_SALT": "s" * 32,
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
    return _make_app()


def _auth(*caps: str, tenant: str = "_platform") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "support-1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def platform() -> dict:
    return _auth("platform.loyalty")


@pytest.fixture
def owner() -> dict:
    """A caller with only the ORDINARY (establishment-scoped) capability — never platform.loyalty
    — proving these two routes are not reachable by an owner just because they hold `loyalty.read`
    on their own shop."""
    return _auth("loyalty.read", "loyalty.manage", tenant=TENANT)


def _earn(client, points=500, visit="v-plat-1", subject=S, tenant=TENANT):
    client.put("/api/v1/loyalty/settings/general", json={"points": points},
              headers=_auth("loyalty.manage", tenant=tenant))
    r = client.post("/internal/loyalty/earn",
                    json={"tenant": tenant, "visit_id": visit, "subject_ref": subject,
                         "service_ids": ["wash"]}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    return r.json()


# ── platform/balance ────────────────────────────────────────────────────────────────────────────
def test_refuses_without_platform_loyalty(client, owner):
    r = client.get("/api/v1/loyalty/platform/balance",
                   params={"tenant": TENANT, "subject_ref": S}, headers=owner)
    assert r.status_code == 403


def test_refuses_unauthenticated(client):
    r = client.get("/api/v1/loyalty/platform/balance", params={"tenant": TENANT, "subject_ref": S})
    assert r.status_code == 401


def test_reads_the_real_balance_for_an_establishment_that_is_not_the_callers_own(client, platform):
    _earn(client, points=250, visit="v-plat-bal", subject="ref_plat_bal01")
    r = client.get("/api/v1/loyalty/platform/balance",
                   params={"tenant": TENANT, "subject_ref": "ref_plat_bal01"}, headers=platform)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["points"] == 250
    assert body["subject_ref"] == "ref_plat_bal01"
    assert body["tenant"] == TENANT
    # NEVER the field-screen shape — no rewards menu, no manager_threshold, no to_next_reward:
    # those are counter-handoff concerns this support read has no business answering.
    assert "rewards" not in body
    assert "manager_threshold" not in body


def test_an_unknown_subject_reads_as_a_real_zero_balance_never_an_error(client, platform):
    r = client.get("/api/v1/loyalty/platform/balance",
                   params={"tenant": TENANT, "subject_ref": "ref_never_seen_ever"}, headers=platform)
    assert r.status_code == 200, r.text
    assert r.json()["points"] == 0


def test_isolated_per_tenant_same_subject_ref(client, platform):
    _earn(client, points=100, visit="v-plat-iso-a", subject="ref_plat_iso_shared", tenant="tnt_plat_a")
    _earn(client, points=999, visit="v-plat-iso-b", subject="ref_plat_iso_shared", tenant="tnt_plat_b")
    r = client.get("/api/v1/loyalty/platform/balance",
                   params={"tenant": "tnt_plat_a", "subject_ref": "ref_plat_iso_shared"},
                   headers=platform)
    assert r.json()["points"] == 100


def test_refuses_a_malformed_query_rather_than_500ing(client, platform):
    r = client.get("/api/v1/loyalty/platform/balance", params={"tenant": TENANT}, headers=platform)
    assert r.status_code == 422   # subject_ref missing


def test_refuses_a_subject_ref_shorter_than_the_pseudonym_floor(client, platform):
    """subject_ref is a real HMAC pseudonym (operations' own SUBJECT_REF), never shorter than 8 —
    the same floor `ReconcileIn`/the owner-scoped routes already enforce."""
    r = client.get("/api/v1/loyalty/platform/balance",
                   params={"tenant": TENANT, "subject_ref": "short"}, headers=platform)
    assert r.status_code == 422


def test_records_who_looked_at_whose_balance(client, platform):
    from unittest.mock import AsyncMock

    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        r = client.get("/api/v1/loyalty/platform/balance",
                       params={"tenant": TENANT, "subject_ref": "ref_plat_audit01"}, headers=platform)
        assert r.status_code == 200, r.text
    finally:
        client.app.state.auditor.record = original
    actions = [c.args[0] for c in spy.await_args_list]
    assert "loyalty.platform_balance_viewed" in actions
    call = next(c for c in spy.await_args_list if c.args[0] == "loyalty.platform_balance_viewed")
    assert call.kwargs["tenant"] == TENANT
    assert "ref_plat_audit01" in call.kwargs["resource"]


# ── platform/history ────────────────────────────────────────────────────────────────────────────
def test_history_refuses_without_platform_loyalty(client, owner):
    r = client.get("/api/v1/loyalty/platform/history",
                   params={"tenant": TENANT, "subject_ref": S}, headers=owner)
    assert r.status_code == 403


def test_history_reads_real_movements_for_another_establishment(client, platform):
    _earn(client, points=77, visit="v-plat-hist", subject="ref_plat_hist01")
    r = client.get("/api/v1/loyalty/platform/history",
                   params={"tenant": TENANT, "subject_ref": "ref_plat_hist01"}, headers=platform)
    assert r.status_code == 200, r.text
    entries = r.json()["entries"]
    assert len(entries) >= 1
    assert entries[0]["reason"] == "earn"
    assert entries[0]["delta"] > 0
    # THE REAL LedgerEntry SHAPE, not a guessed subset — balance_after and note are exactly what
    # let support explain a specific movement rather than just its sign.
    assert set(entries[0]) >= {"id", "tenant", "subject_ref", "delta", "reason", "source",
                              "actor", "branch_id", "balance_after", "note", "created_at"}


def test_history_an_unknown_subject_is_an_empty_list_never_an_error(client, platform):
    r = client.get("/api/v1/loyalty/platform/history",
                   params={"tenant": TENANT, "subject_ref": "ref_never_seen_either"}, headers=platform)
    assert r.status_code == 200, r.text
    assert r.json()["entries"] == []


def test_history_respects_the_limit_parameter(client, platform):
    for i in range(5):
        _earn(client, points=1, visit=f"v-plat-limit-{i}", subject="ref_plat_limit01")
    r = client.get("/api/v1/loyalty/platform/history",
                   params={"tenant": TENANT, "subject_ref": "ref_plat_limit01", "limit": 2},
                   headers=platform)
    assert r.status_code == 200, r.text
    assert len(r.json()["entries"]) == 2


def test_history_refuses_a_limit_above_the_hundred_row_ceiling(client, platform):
    """Same ceiling the owner's own `/history/{subject_ref}` enforces — a platform read must not
    be a wider door than the establishment's own."""
    r = client.get("/api/v1/loyalty/platform/history",
                   params={"tenant": TENANT, "subject_ref": S, "limit": 101}, headers=platform)
    assert r.status_code == 422


def test_history_refuses_a_zero_or_negative_limit(client, platform):
    r = client.get("/api/v1/loyalty/platform/history",
                   params={"tenant": TENANT, "subject_ref": S, "limit": 0}, headers=platform)
    assert r.status_code == 422


def test_history_isolated_per_tenant_same_subject_ref(client, platform):
    _earn(client, points=1, visit="v-plat-hist-iso-a", subject="ref_plat_hist_iso", tenant="tnt_plat_hist_a")
    _earn(client, points=1, visit="v-plat-hist-iso-b", subject="ref_plat_hist_iso", tenant="tnt_plat_hist_b")
    r = client.get("/api/v1/loyalty/platform/history",
                   params={"tenant": "tnt_plat_hist_a", "subject_ref": "ref_plat_hist_iso"},
                   headers=platform)
    assert len(r.json()["entries"]) == 1


def test_records_who_looked_at_whose_history(client, platform):
    from unittest.mock import AsyncMock

    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        r = client.get("/api/v1/loyalty/platform/history",
                       params={"tenant": TENANT, "subject_ref": "ref_plat_hist_audit01"},
                       headers=platform)
        assert r.status_code == 200, r.text
    finally:
        client.app.state.auditor.record = original
    actions = [c.args[0] for c in spy.await_args_list]
    assert "loyalty.platform_history_viewed" in actions
