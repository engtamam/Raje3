"""The five PRICING_AI_UNIT_* keys, going through the SAME /pricing/schedule gate every other
pricing key already goes through (never instant), plus their own sanity-bound validation.
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
    return _make_app()


@pytest.fixture
def operator_auth() -> dict:
    return _auth("platform.config")


def _schedule(client, headers, key, value, days=15):
    return client.post(f"{PREFIX}/pricing/schedule",
                       json={"key": key, "value": value, "effective_in_days": days},
                       headers=headers)


# ── the five keys go through the same scheduled gate as every other pricing key ────────────────
@pytest.mark.parametrize("key,value", [
    ("PRICING_AI_UNIT_UNITS_PER_HALALA", 2000),
    ("PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER", 6.0),
    ("PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER", 3.0),
    ("PRICING_AI_UNIT_USD_TO_SAR", 3.8),
    ("PRICING_AI_UNIT_MODEL_COSTS_JSON",
     '{"gemini-3.1-flash-lite": {"input_usd_per_million": 0.3, "output_usd_per_million": 1.8}}'),
])
def test_ai_unit_key_schedules_cleanly_and_never_applies_instantly(client, operator_auth, key, value):
    before = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    r = _schedule(client, operator_auth, key, value)
    assert r.status_code == 200, r.text
    after = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    assert after[key] == before[key]   # unchanged — still only pending, never instant

    pending = client.get(f"{PREFIX}/pricing/pending", headers=operator_auth).json()["pending"]
    assert any(c["key"] == key for c in pending)


def test_ai_unit_key_is_refused_on_the_instant_config_route(client, operator_auth):
    r = client.put(f"{PREFIX}/config",
                   json={"key": "PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER", "value": 6.0},
                   headers=operator_auth)
    assert r.status_code == 400
    assert "pricing key" in r.json()["reason"]


# ── sanity bounds ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("key,bad_value", [
    ("PRICING_AI_UNIT_UNITS_PER_HALALA", 0),
    ("PRICING_AI_UNIT_UNITS_PER_HALALA", -5),
    ("PRICING_AI_UNIT_UNITS_PER_HALALA", 5_000_000),
    ("PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER", 1.0),      # must be > 1, not >=
    ("PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER", 500),      # the exact typo scenario the task names
    ("PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER", 0),
    ("PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER", 51),
    ("PRICING_AI_UNIT_USD_TO_SAR", 0),
    ("PRICING_AI_UNIT_USD_TO_SAR", -3.75),
    ("PRICING_AI_UNIT_USD_TO_SAR", 999),
    ("PRICING_AI_UNIT_MODEL_COSTS_JSON", "not json at all"),
    ("PRICING_AI_UNIT_MODEL_COSTS_JSON", '{"m": {"input_usd_per_million": -1, "output_usd_per_million": 1}}'),
    ("PRICING_AI_UNIT_MODEL_COSTS_JSON", '{"m": {"input_usd_per_million": 5000, "output_usd_per_million": 1}}'),
])
def test_an_out_of_range_ai_unit_value_is_refused_not_silently_scheduled(client, operator_auth, key, bad_value):
    r = _schedule(client, operator_auth, key, bad_value)
    assert r.status_code == 400, r.text
    pending = client.get(f"{PREFIX}/pricing/pending", headers=operator_auth).json()["pending"]
    assert not any(c["key"] == key for c in pending)


def test_a_valid_model_costs_json_with_several_models_schedules_cleanly(client, operator_auth):
    value = ('{"gemini-3.1-flash-lite": {"input_usd_per_million": 0.25, "output_usd_per_million": 1.5}, '
             '"claude-haiku": {"input_usd_per_million": 0.8, "output_usd_per_million": 4.0}}')
    r = _schedule(client, operator_auth, "PRICING_AI_UNIT_MODEL_COSTS_JSON", value)
    assert r.status_code == 200, r.text


# ── the tick applies a due AI-unit change through the SAME mechanism ────────────────────────────
def test_a_due_ai_unit_change_lands_after_the_tick_like_any_other_pricing_key(client, operator_auth):
    import asyncio

    from app.core.pricing_schedule import apply_due, schedule

    container = client.app.state.container
    now = int(__import__("time").time())
    asyncio.run(schedule(container.datastore, key="PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER",
                         value=7.0, effective_at=now - 1, actor="op1", now=now - 100))
    applied = asyncio.run(apply_due(container.datastore, container.runtime_config, now=now))
    assert "PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER" in applied

    config = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    assert config["PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER"] == 7.0
