"""POST /internal/loyalty/award — crediting points for a reason that is NOT a visit (a campaign's
own gift, e.g. an anniversary). No sender's caller exists yet (2026-09-13, deliberately: the
capability is built ahead of any template wiring it) — these tests exercise the route directly."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "k" * 40
ISS, AUD, TENANT = "iss", "aud", "shop"
S = "ref_award_01"

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


def _award(client, *, tenant=TENANT, key="cmp_1:ref", subject_ref=S, points=20,
          reason="occasion", actor="campaigns") -> dict:
    r = client.post("/internal/loyalty/award", json={
        "tenant": tenant, "subject_ref": subject_ref, "points": points,
        "idempotency_key": key, "reason": reason, "actor": actor}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_real_award_credits_the_exact_amount(client):
    out = _award(client, key="cmp_credit_1:ref_credit_1", subject_ref="ref_credit_1", points=30)
    assert out["earned"] == 30
    assert _balance(client, "ref_credit_1") == 30


def test_a_retried_key_never_double_credits(client):
    first = _award(client, key="cmp_retry:ref_retry", subject_ref="ref_retry", points=15)
    second = _award(client, key="cmp_retry:ref_retry", subject_ref="ref_retry", points=15)
    assert first["earned"] == 15
    assert second == {"earned": 0, "duplicate": True,
                      "reason": "already credited for this key"}
    assert _balance(client, "ref_retry") == 15


def test_an_award_does_not_collide_with_the_subjects_own_visit_earning(client):
    """The same subject legitimately holds both an ordinary visit earn and a campaign award — the
    distinct `award:` source prefix keeps them from looking like the same movement retried."""
    tenant, subject_ref = TENANT, "ref_both_award"
    client.put("/api/v1/loyalty/settings/general", json={"points": 20},
              headers=_auth("loyalty.manage", tenant=tenant))
    earn_r = client.post("/internal/loyalty/earn", json={
        "tenant": tenant, "visit_id": "vis_award_both", "subject_ref": subject_ref,
        "service_ids": ["wash"]}, headers=INTERNAL)
    assert earn_r.status_code == 200
    earned = earn_r.json()["earned"]
    assert earned > 0
    award = _award(client, tenant=tenant, key="cmp_both:ref_both_award",
                   subject_ref=subject_ref, points=25)
    assert award["earned"] == 25
    assert _balance(client, subject_ref, tenant=tenant) == earned + 25


def test_zero_points_is_refused_at_the_schema_boundary(client):
    r = client.post("/internal/loyalty/award", json={
        "tenant": TENANT, "subject_ref": S, "points": 0, "idempotency_key": "cmp_zero:ref"},
        headers=INTERNAL)
    assert r.status_code == 422


def test_negative_points_is_refused_at_the_schema_boundary(client):
    r = client.post("/internal/loyalty/award", json={
        "tenant": TENANT, "subject_ref": S, "points": -5, "idempotency_key": "cmp_neg:ref"},
        headers=INTERNAL)
    assert r.status_code == 422


def test_a_blank_idempotency_key_is_refused_at_the_schema_boundary(client):
    r = client.post("/internal/loyalty/award", json={
        "tenant": TENANT, "subject_ref": S, "points": 10, "idempotency_key": ""},
        headers=INTERNAL)
    assert r.status_code == 422


def test_requires_the_internal_token(client):
    r = client.post("/internal/loyalty/award", json={
        "tenant": TENANT, "subject_ref": S, "points": 10, "idempotency_key": "cmp_noauth:ref"})
    assert r.status_code == 401


def test_two_tenants_credit_independently_even_with_the_same_subject_ref(client):
    same_ref = "ref_shared_award"
    _award(client, tenant="tnt_award_a", key="cmp_a:ref", subject_ref=same_ref, points=10)
    assert _balance(client, same_ref, tenant="tnt_award_b") == 0


# ── the audit trail ───────────────────────────────────────────────────────────────────────────
def test_a_real_credit_is_audited_as_award_credited(client):
    from unittest.mock import AsyncMock

    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        _award(client, key="cmp_audit_1:ref_audit_1", subject_ref="ref_audit_1", points=12)
    finally:
        client.app.state.auditor.record = original
    actions = [c.args[0] for c in spy.await_args_list]
    assert "loyalty.award_credited" in actions


def test_a_duplicate_credit_is_not_audited_a_second_time(client):
    from unittest.mock import AsyncMock

    _award(client, key="cmp_audit_dup:ref_audit_dup", subject_ref="ref_audit_dup", points=9)
    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        _award(client, key="cmp_audit_dup:ref_audit_dup", subject_ref="ref_audit_dup", points=9)
    finally:
        client.app.state.auditor.record = original
    assert spy.await_args_list == []
