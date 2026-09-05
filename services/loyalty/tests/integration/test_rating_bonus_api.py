"""POST /internal/loyalty/rating-bonus — Phase 4 of the rating-app plan: crediting the loyalty
incentive `rating_cta.py`'s message text already promises, once a customer actually submits a
rating. Called by `operations`' own rating-write route (see its docstring for why THAT is the
idempotent gate, not this one)."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "k" * 40
ISS, AUD, TENANT = "iss", "aud", "shop"
S = "ref_rating_bonus_01"

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


def _auth(*caps: str, tenant: str = TENANT) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "emp-7", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _balance(client, subject_ref: str, tenant: str = TENANT) -> int:
    r = client.get(f"/api/v1/loyalty/balance/{subject_ref}", headers=_auth("loyalty.read",
                   tenant=tenant))
    assert r.status_code == 200, r.text
    return r.json()["points"]


def _bonus(client, *, tenant=TENANT, visit_id="vis_1", subject_ref=S, points=20,
          actor="reminders") -> dict:
    r = client.post("/internal/loyalty/rating-bonus", json={
        "tenant": tenant, "visit_id": visit_id, "subject_ref": subject_ref, "points": points,
        "actor": actor}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_real_rating_gets_a_real_credit_for_the_configured_points(client):
    out = _bonus(client, visit_id="vis_credit_1", subject_ref="ref_credit_1", points=30)
    assert out["earned"] == 30
    assert _balance(client, "ref_credit_1") == 30


def test_the_exact_points_amount_matches_configuration(client):
    out = _bonus(client, visit_id="vis_credit_exact", subject_ref="ref_credit_exact", points=777)
    assert out["earned"] == 777
    assert out["balance"] == 777


def test_zero_points_credits_nothing_no_ledger_entry_at_all(client):
    out = _bonus(client, visit_id="vis_zero", subject_ref="ref_zero", points=0)
    assert out["earned"] == 0
    assert "duplicate" not in out
    assert _balance(client, "ref_zero") == 0


def test_a_retried_write_never_double_credits(client):
    first = _bonus(client, visit_id="vis_retry", subject_ref="ref_retry", points=15)
    second = _bonus(client, visit_id="vis_retry", subject_ref="ref_retry", points=15)
    assert first["earned"] == 15
    assert second == {"earned": 0, "duplicate": True,
                      "reason": "already credited for this rating"}
    assert _balance(client, "ref_retry") == 15


def test_a_rating_bonus_does_not_collide_with_the_visits_own_regular_earn(client):
    """The same visit_id legitimately produces both an ordinary `earn` (the wash itself) and a
    rating bonus (the customer answering later) — the distinct `source` prefix keeps them from
    looking like the same movement retried."""
    tenant, visit_id, subject_ref = TENANT, "vis_both_1", "ref_both_1"
    client.put("/api/v1/loyalty/settings/general", json={"points": 20},
              headers=_auth("loyalty.manage", tenant=tenant))
    earn_r = client.post("/internal/loyalty/earn", json={
        "tenant": tenant, "visit_id": visit_id, "subject_ref": subject_ref,
        "service_ids": ["wash"]}, headers=INTERNAL)
    assert earn_r.status_code == 200
    earned = earn_r.json()["earned"]
    assert earned > 0
    bonus = _bonus(client, tenant=tenant, visit_id=visit_id, subject_ref=subject_ref, points=25)
    assert bonus["earned"] == 25
    assert _balance(client, subject_ref, tenant=tenant) == earned + 25


def test_a_blank_subject_ref_credits_nothing(client):
    r = client.post("/internal/loyalty/rating-bonus", json={
        "tenant": TENANT, "visit_id": "vis_blank_ref", "subject_ref": "", "points": 20,
        "actor": "reminders"}, headers=INTERNAL)
    assert r.status_code == 200
    assert r.json()["earned"] == 0


def test_negative_points_is_refused_at_the_schema_boundary(client):
    r = client.post("/internal/loyalty/rating-bonus", json={
        "tenant": TENANT, "visit_id": "vis_neg", "subject_ref": S, "points": -5},
        headers=INTERNAL)
    assert r.status_code == 422


def test_requires_the_internal_token(client):
    r = client.post("/internal/loyalty/rating-bonus", json={
        "tenant": TENANT, "visit_id": "vis_x", "subject_ref": S, "points": 10})
    assert r.status_code == 401


def test_two_tenants_credit_independently_even_with_the_same_subject_ref(client):
    same_ref = "ref_shared_rating"
    _bonus(client, tenant="tnt_rating_a", visit_id="vis_a", subject_ref=same_ref, points=10)
    assert _balance(client, same_ref, tenant="tnt_rating_b") == 0


# ── the audit trail ───────────────────────────────────────────────────────────────────────────
def test_a_real_credit_is_audited_as_rating_bonus_credited(client):
    from unittest.mock import AsyncMock

    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        _bonus(client, visit_id="vis_audit_1", subject_ref="ref_audit_1", points=12)
    finally:
        client.app.state.auditor.record = original
    actions = [c.args[0] for c in spy.await_args_list]
    assert "loyalty.rating_bonus_credited" in actions


def test_a_zero_point_credit_is_not_audited(client):
    from unittest.mock import AsyncMock

    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        _bonus(client, visit_id="vis_audit_zero", subject_ref="ref_audit_zero", points=0)
    finally:
        client.app.state.auditor.record = original
    assert spy.await_args_list == []


def test_a_duplicate_credit_is_not_audited_a_second_time(client):
    from unittest.mock import AsyncMock

    _bonus(client, visit_id="vis_audit_dup", subject_ref="ref_audit_dup", points=9)
    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        _bonus(client, visit_id="vis_audit_dup", subject_ref="ref_audit_dup", points=9)
    finally:
        client.app.state.auditor.record = original
    assert spy.await_args_list == []
