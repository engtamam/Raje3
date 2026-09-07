"""/api/v1/assistant/operator/pricing/* — المحاسبة's own backend: real usage (COST_LEDGER), and a
pricing change that always waits before it lands (core/pricing_schedule.py). Same harness shape as
test_operator_config_api.py.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
KEK = "unit-test-kek-not-a-real-key"

PREFIX = "/api/v1/assistant/operator"


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


def _auth(*caps: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def env_guard():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def client(env_guard) -> TestClient:
    # FUNCTION-SCOPED, UNLIKE test_operator_config_api.py's module-scoped client — a fresh
    # in-memory datastore per test, since scheduling/cancelling a pricing change is exactly the
    # kind of mutation that must never leak from one test into the next here.
    return _make_app()


@pytest.fixture
def operator_auth() -> dict:
    return _auth("platform.config")


@pytest.fixture
def reader_auth() -> dict:
    return _auth("reports.read")


# ── authorisation ─────────────────────────────────────────────────────────────
def test_report_needs_the_capability(client, reader_auth):
    assert client.get(f"{PREFIX}/pricing/report", headers=reader_auth).status_code == 403


def test_schedule_needs_the_capability(client, reader_auth):
    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "PRICING_STRATEGY", "value": "usage_based", "effective_in_days": 15},
                    headers=reader_auth)
    assert r.status_code == 403


# ── report ────────────────────────────────────────────────────────────────────
def test_report_on_an_empty_ledger_is_honestly_zero(client, operator_auth):
    body = client.get(f"{PREFIX}/pricing/report", headers=operator_auth).json()
    assert body == {
        "days": 30, "calls": 0, "conversations": 0, "input_tokens": 0, "output_tokens": 0,
        "avg_input_tokens_per_call": 0.0, "avg_output_tokens_per_call": 0.0,
        "avg_calls_per_conversation": 0.0, "truncated": False,
    }


def test_report_days_is_clamped_not_refused(client, operator_auth):
    r = client.get(f"{PREFIX}/pricing/report", params={"days": 9000}, headers=operator_auth)
    assert r.status_code == 200 and r.json()["days"] == 365
    r = client.get(f"{PREFIX}/pricing/report", params={"days": 0}, headers=operator_auth)
    assert r.status_code == 200 and r.json()["days"] == 1


# ── schedule / pending / cancel ────────────────────────────────────────────────
def test_scheduling_a_pricing_change_never_applies_it_instantly(client, operator_auth):
    before = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    assert before["PRICING_USAGE_HALALAS_PER_1K_TOKENS"] == 0

    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "PRICING_USAGE_HALALAS_PER_1K_TOKENS", "value": 40,
                          "effective_in_days": 15},
                    headers=operator_auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["key"] == "PRICING_USAGE_HALALAS_PER_1K_TOKENS" and body["value"] == 40

    # STILL ZERO — nothing landed. The whole point.
    after = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    assert after["PRICING_USAGE_HALALAS_PER_1K_TOKENS"] == 0


def test_a_scheduled_change_appears_in_pending_with_its_own_effective_at(client, operator_auth):
    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "PRICING_STRATEGY", "value": "usage_based",
                          "effective_in_days": 15},
                    headers=operator_auth)
    scheduled_at_effective = r.json()["effective_at"]

    pending = client.get(f"{PREFIX}/pricing/pending", headers=operator_auth).json()["pending"]
    assert len(pending) == 1
    assert pending[0]["key"] == "PRICING_STRATEGY"
    assert pending[0]["value"] == "usage_based"
    assert pending[0]["effective_at"] == scheduled_at_effective
    # ~15 days out, not "today" — the floor this whole feature exists to enforce.
    import time
    assert pending[0]["effective_at"] - int(time.time()) > 14 * 86_400


def test_a_zero_or_negative_delay_is_refused_not_silently_floored(client, operator_auth):
    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "PRICING_STRATEGY", "value": "usage_based",
                          "effective_in_days": 0},
                    headers=operator_auth)
    assert r.status_code == 422   # pydantic's own Field(ge=1) refusal
    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "PRICING_STRATEGY", "value": "usage_based",
                          "effective_in_days": -5},
                    headers=operator_auth)
    assert r.status_code == 422


def test_a_non_pricing_key_is_refused_by_the_scheduler(client, operator_auth):
    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "ASSISTANT_MODEL_NAME", "value": "gemini-x",
                          "effective_in_days": 15},
                    headers=operator_auth)
    assert r.status_code == 400
    assert "not a pricing key" in r.json()["reason"]


def test_scheduling_again_replaces_the_earlier_pending_change_for_the_same_key(
    client, operator_auth,
):
    client.post(f"{PREFIX}/pricing/schedule",
               json={"key": "PRICING_STRATEGY", "value": "usage_based", "effective_in_days": 15},
               headers=operator_auth)
    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "PRICING_STRATEGY", "value": "addon_on_existing_plan",
                          "effective_in_days": 7},
                    headers=operator_auth)
    assert r.status_code == 200

    pending = client.get(f"{PREFIX}/pricing/pending", headers=operator_auth).json()["pending"]
    assert len(pending) == 1   # not two — the second call replaced the first, never queued beside it
    assert pending[0]["value"] == "addon_on_existing_plan"


def test_cancelling_a_pending_change_removes_it_and_leaves_the_effective_value_untouched(
    client, operator_auth,
):
    client.post(f"{PREFIX}/pricing/schedule",
               json={"key": "PRICING_STRATEGY", "value": "usage_based", "effective_in_days": 15},
               headers=operator_auth)
    r = client.delete(f"{PREFIX}/pricing/pending/PRICING_STRATEGY", headers=operator_auth)
    assert r.status_code == 200 and r.json()["cancelled"] is True

    assert client.get(f"{PREFIX}/pricing/pending", headers=operator_auth).json()["pending"] == []
    config = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    assert config["PRICING_STRATEGY"] == "tier_plus_cap"   # the deploy-time default, untouched


def test_cancelling_a_key_with_nothing_pending_says_so_honestly(client, operator_auth):
    r = client.delete(f"{PREFIX}/pricing/pending/PRICING_STRATEGY", headers=operator_auth)
    assert r.status_code == 200 and r.json()["cancelled"] is False
