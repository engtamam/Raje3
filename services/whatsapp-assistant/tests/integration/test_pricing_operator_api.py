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
                    json={"key": "PRICING_AI_UNIT_USD_TO_SAR", "value": 4.0, "effective_in_days": 15},
                    headers=reader_auth)
    assert r.status_code == 403


# ── report ────────────────────────────────────────────────────────────────────
def test_report_on_an_empty_ledger_is_honestly_zero(client, operator_auth):
    body = client.get(f"{PREFIX}/pricing/report", headers=operator_auth).json()
    assert body == {
        "days": 30, "ai_enabled": True, "calls": 0, "conversations": 0, "input_tokens": 0,
        "output_tokens": 0, "avg_input_tokens_per_call": 0.0, "avg_output_tokens_per_call": 0.0,
        "avg_calls_per_conversation": 0.0, "truncated": False,
    }


def test_report_is_null_not_computed_when_ai_assistant_disabled(monkeypatch, client, operator_auth):
    """AI_ASSISTANT_ENABLED=False must skip the COST_LEDGER read entirely — a real behavioural
    check, not just a response-shape one: seed a row that WOULD show up if the switch were on, then
    prove it never gets counted (and every ledger-sourced field comes back None, not 0)."""
    container = client.app.state.container
    now = int(__import__("time").time())
    import asyncio
    asyncio.run(_seed_cost_row(container.datastore, tenant="shop-a", subject_ref="s1",
                               input_tokens=100, output_tokens=50, at=now - 10))

    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AI_ASSISTANT_ENABLED", "false")
    get_settings.cache_clear()
    try:
        body = client.get(f"{PREFIX}/pricing/report", headers=operator_auth).json()
    finally:
        monkeypatch.delenv("AI_ASSISTANT_ENABLED", raising=False)
        get_settings.cache_clear()

    assert body == {
        "days": 30, "ai_enabled": False, "calls": None, "conversations": None,
        "input_tokens": None, "output_tokens": None, "avg_input_tokens_per_call": None,
        "avg_output_tokens_per_call": None, "avg_calls_per_conversation": None,
        "truncated": False,
    }


def test_report_days_is_clamped_not_refused(client, operator_auth):
    r = client.get(f"{PREFIX}/pricing/report", params={"days": 9000}, headers=operator_auth)
    assert r.status_code == 200 and r.json()["days"] == 365
    r = client.get(f"{PREFIX}/pricing/report", params={"days": 0}, headers=operator_auth)
    assert r.status_code == 200 and r.json()["days"] == 1


async def _seed_cost_row(store, *, tenant, subject_ref, input_tokens, output_tokens, at):
    import uuid

    from app.core.models import COST_LEDGER
    await store.put(COST_LEDGER, f"{tenant}:{at}:{uuid.uuid4().hex[:8]}", {
        "tenant": tenant, "subject_ref": subject_ref, "at": at,
        "input_tokens": input_tokens, "output_tokens": output_tokens})


def test_report_tenant_none_stays_platform_wide_across_shops(client, operator_auth):
    """Default behaviour (no `tenant` query param) must keep aggregating every shop together —
    the internal admin panel's own correct number, unchanged by adding tenant-scoping capability."""
    container = client.app.state.container
    now = int(__import__("time").time())
    import asyncio
    asyncio.run(_seed_cost_row(container.datastore, tenant="shop-a", subject_ref="s1",
                               input_tokens=100, output_tokens=50, at=now - 10))
    asyncio.run(_seed_cost_row(container.datastore, tenant="shop-b", subject_ref="s2",
                               input_tokens=200, output_tokens=80, at=now - 5))

    body = client.get(f"{PREFIX}/pricing/report", headers=operator_auth).json()
    assert body["calls"] == 2 and body["input_tokens"] == 300   # both shops combined


def test_report_with_an_explicit_tenant_sees_only_that_shops_own_rows(client, operator_auth):
    """Real isolation: another shop's real LLM calls must never inflate the number a single shop's
    own future usage screen would show."""
    container = client.app.state.container
    now = int(__import__("time").time())
    import asyncio
    asyncio.run(_seed_cost_row(container.datastore, tenant="shop-a", subject_ref="s1",
                               input_tokens=100, output_tokens=50, at=now - 10))
    asyncio.run(_seed_cost_row(container.datastore, tenant="shop-b", subject_ref="s2",
                               input_tokens=200, output_tokens=80, at=now - 5))

    body = client.get(f"{PREFIX}/pricing/report", params={"tenant": "shop-a"},
                      headers=operator_auth).json()
    assert body["calls"] == 1
    assert body["input_tokens"] == 100 and body["output_tokens"] == 50   # shop-b never counted


# ── schedule / pending / cancel ────────────────────────────────────────────────
def test_scheduling_a_pricing_change_never_applies_it_instantly(client, operator_auth):
    before = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    assert before["PRICING_AI_UNIT_USD_TO_SAR"] == 3.75

    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "PRICING_AI_UNIT_USD_TO_SAR", "value": 4.0,
                          "effective_in_days": 15},
                    headers=operator_auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["key"] == "PRICING_AI_UNIT_USD_TO_SAR" and body["value"] == 4.0

    # STILL THE DEPLOY-TIME DEFAULT — nothing landed. The whole point.
    after = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    assert after["PRICING_AI_UNIT_USD_TO_SAR"] == 3.75


def test_a_scheduled_change_appears_in_pending_with_its_own_effective_at(client, operator_auth):
    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "PRICING_AI_UNIT_USD_TO_SAR", "value": 4.0,
                          "effective_in_days": 15},
                    headers=operator_auth)
    scheduled_at_effective = r.json()["effective_at"]

    pending = client.get(f"{PREFIX}/pricing/pending", headers=operator_auth).json()["pending"]
    assert len(pending) == 1
    assert pending[0]["key"] == "PRICING_AI_UNIT_USD_TO_SAR"
    assert pending[0]["value"] == 4.0
    assert pending[0]["effective_at"] == scheduled_at_effective
    # ~15 days out, not "today" — the floor this whole feature exists to enforce.
    import time
    assert pending[0]["effective_at"] - int(time.time()) > 14 * 86_400


def test_a_zero_or_negative_delay_is_refused_not_silently_floored(client, operator_auth):
    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "PRICING_AI_UNIT_USD_TO_SAR", "value": 4.0,
                          "effective_in_days": 0},
                    headers=operator_auth)
    assert r.status_code == 422   # pydantic's own Field(ge=1) refusal
    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "PRICING_AI_UNIT_USD_TO_SAR", "value": 4.0,
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
               json={"key": "PRICING_AI_UNIT_USD_TO_SAR", "value": 4.0, "effective_in_days": 15},
               headers=operator_auth)
    r = client.post(f"{PREFIX}/pricing/schedule",
                    json={"key": "PRICING_AI_UNIT_USD_TO_SAR", "value": 4.2,
                          "effective_in_days": 7},
                    headers=operator_auth)
    assert r.status_code == 200

    pending = client.get(f"{PREFIX}/pricing/pending", headers=operator_auth).json()["pending"]
    assert len(pending) == 1   # not two — the second call replaced the first, never queued beside it
    assert pending[0]["value"] == 4.2


def test_cancelling_a_pending_change_removes_it_and_leaves_the_effective_value_untouched(
    client, operator_auth,
):
    client.post(f"{PREFIX}/pricing/schedule",
               json={"key": "PRICING_AI_UNIT_USD_TO_SAR", "value": 4.0, "effective_in_days": 15},
               headers=operator_auth)
    r = client.delete(f"{PREFIX}/pricing/pending/PRICING_AI_UNIT_USD_TO_SAR", headers=operator_auth)
    assert r.status_code == 200 and r.json()["cancelled"] is True

    assert client.get(f"{PREFIX}/pricing/pending", headers=operator_auth).json()["pending"] == []
    config = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    assert config["PRICING_AI_UNIT_USD_TO_SAR"] == 3.75   # the deploy-time default, untouched


def test_cancelling_a_key_with_nothing_pending_says_so_honestly(client, operator_auth):
    r = client.delete(f"{PREFIX}/pricing/pending/PRICING_AI_UNIT_USD_TO_SAR", headers=operator_auth)
    assert r.status_code == 200 and r.json()["cancelled"] is False
