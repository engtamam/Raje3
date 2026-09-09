"""/api/v1/assistant/operator/config — app/runtime_policy.py's declared knobs, live-overridable
without a redeploy. Same shape as services/reminders' own test_operator_api.py; unlike that
template (which declares nothing), this service has three REAL keys, so the happy paths are worth
covering here too, not just the negative/refusal ones.
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


@pytest.fixture(scope="module")
def client(env_guard) -> TestClient:
    return _make_app()


@pytest.fixture
def operator_auth() -> dict:
    return _auth("platform.config")


@pytest.fixture
def reader_auth() -> dict:
    """Holds a capability, but not this one."""
    return _auth("reports.read")


@pytest.fixture
def secrets_auth() -> dict:
    return _auth("platform.secrets")


# ── authorisation ─────────────────────────────────────────────────────────────
def test_config_needs_its_own_capability(client, reader_auth):
    assert client.get(f"{PREFIX}/config", headers=reader_auth).status_code == 403


def test_unauthenticated_is_refused(client):
    assert client.get(f"{PREFIX}/config").status_code == 401


# ── policy ────────────────────────────────────────────────────────────────────
def test_a_deploy_time_knob_is_refused(client, operator_auth):
    """Wiring changed under a live request is a class of bug nobody can reproduce."""
    for key in ("DATASTORE_DRIVER", "SECRETS_KEK", "PII_SALT", "INTERNAL_SERVICE_TOKEN",
               "ASSISTANT_MODEL_PROJECT", "ASSISTANT_MODEL_CREDENTIAL"):
        r = client.put(f"{PREFIX}/config", json={"key": key, "value": "anything"},
                      headers=operator_auth)
        assert r.status_code == 400, f"{key} was accepted at runtime"


def test_the_config_view_never_carries_a_credential(client, operator_auth):
    view = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    for banned in ("SECRETS_KEK", "INTERNAL_SERVICE_TOKEN", "PII_SALT", "ASSISTANT_MODEL_CREDENTIAL"):
        assert banned not in view


def test_the_nine_declared_knobs_start_at_their_configured_defaults(client, operator_auth):
    view = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    assert view == {
        "ASSISTANT_MODEL_NAME": "gemini-2.5-flash",
        "MAX_CAROUSEL_CARDS": 5,
        "MAX_REPLY_TOKENS": 500,
        "SOFT_DECLINE_THRESHOLD": 2,
        "PRICING_AI_UNIT_UNITS_PER_HALALA": 1000,
        "PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER": 5.0,
        "PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER": 2.0,
        "PRICING_AI_UNIT_USD_TO_SAR": 3.75,
        "PRICING_AI_UNIT_MODEL_COSTS_JSON": (
            '{"gemini-3.1-flash-lite": {"input_usd_per_million": 0.25, '
            '"output_usd_per_million": 1.50}}'),
    }


def test_a_pricing_key_cannot_take_the_instant_config_route_even_though_it_is_settable(
    client, operator_auth,
):
    """PRICING_* keys ARE in RUNTIME_POLICY (effective_config lists them, above) but must never be
    settable through PUT/DELETE /config — only through the scheduled /pricing/schedule route
    below. Settable-but-refused-here is a real, deliberate state this gate must hold."""
    r = client.put(f"{PREFIX}/config",
                   json={"key": "PRICING_AI_UNIT_USD_TO_SAR", "value": 4.0},
                   headers=operator_auth)
    assert r.status_code == 400
    assert "pricing/schedule" in r.json()["reason"]

    r = client.delete(f"{PREFIX}/config/PRICING_AI_UNIT_USD_TO_SAR", headers=operator_auth)
    assert r.status_code == 400
    assert "pricing/schedule" in r.json()["reason"]


def test_setting_and_reading_back_an_override(client, operator_auth):
    r = client.put(f"{PREFIX}/config", json={"key": "MAX_CAROUSEL_CARDS", "value": 3},
                   headers=operator_auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"key": "MAX_CAROUSEL_CARDS", "value": 3}

    view = client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"]
    assert view["MAX_CAROUSEL_CARDS"] == 3


def test_clearing_an_override_restores_the_configured_default(client, operator_auth):
    client.put(f"{PREFIX}/config", json={"key": "SOFT_DECLINE_THRESHOLD", "value": 5},
              headers=operator_auth)
    assert client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"][
        "SOFT_DECLINE_THRESHOLD"] == 5

    r = client.delete(f"{PREFIX}/config/SOFT_DECLINE_THRESHOLD", headers=operator_auth)
    assert r.status_code == 200 and r.json()["cleared"] is True

    assert client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"][
        "SOFT_DECLINE_THRESHOLD"] == 2


def test_an_undeclared_knob_is_refused_even_though_settings_has_the_field(client, operator_auth):
    """RATELIMIT_MAX is a real Settings field this service has, but nothing declared it in
    RUNTIME_POLICY — an advertised-but-unread knob is the exact defect this whole gate exists to
    prevent (app/core/runtime_config.py's own docstring)."""
    r = client.put(f"{PREFIX}/config", json={"key": "RATELIMIT_MAX", "value": 250},
                   headers=operator_auth)
    assert r.status_code == 400


def test_a_wrong_typed_value_is_refused_not_silently_stored(client, operator_auth):
    r = client.put(f"{PREFIX}/config", json={"key": "MAX_CAROUSEL_CARDS", "value": "not-a-number"},
                   headers=operator_auth)
    assert r.status_code == 400


# ── runtime bounds — the boot guard's rules applied to a LIVE override too (validate_runtime_
# override, wired as RuntimeConfig's own `validate=`). Type-correct but nonsensical used to pass
# straight through: `_coerce` only casts type, it never re-runs Settings' own field_validators. ──
def test_a_value_past_metas_own_carousel_bounds_is_refused_at_runtime_not_only_at_boot(
    client, operator_auth,
):
    r = client.put(f"{PREFIX}/config", json={"key": "MAX_CAROUSEL_CARDS", "value": 11},
                   headers=operator_auth)
    assert r.status_code == 400
    # NEVER 11 — whatever it was before this call, the refused write must not have landed. Not
    # asserted against a specific baseline: `client` is module-scoped and shared with earlier
    # tests in this file that legitimately change this same key.
    assert client.get(f"{PREFIX}/config", headers=operator_auth).json()["config"][
        "MAX_CAROUSEL_CARDS"] != 11


def test_a_nonpositive_reply_token_ceiling_is_refused(client, operator_auth):
    r = client.put(f"{PREFIX}/config", json={"key": "MAX_REPLY_TOKENS", "value": 0},
                   headers=operator_auth)
    assert r.status_code == 400


def test_an_implausibly_large_reply_token_ceiling_is_refused(client, operator_auth):
    """4,000 is already generous headroom for a WhatsApp reply — 50,000 is far more likely a typo
    (a word/character count entered where a token count was meant) than a real ceiling."""
    r = client.put(f"{PREFIX}/config", json={"key": "MAX_REPLY_TOKENS", "value": 50_000},
                   headers=operator_auth)
    assert r.status_code == 400


def test_a_zero_soft_decline_threshold_is_refused_at_runtime(client, operator_auth):
    """Same rule as this field's own boot-time field_validator — SOFT_DECLINE_THRESHOLD=0 would
    escalate every single turn."""
    r = client.put(f"{PREFIX}/config", json={"key": "SOFT_DECLINE_THRESHOLD", "value": 0},
                   headers=operator_auth)
    assert r.status_code == 400


# ── secrets — audit-ordering fix ────────────────────────────────────────────────────────────────
def test_setting_an_empty_secret_is_refused_not_logged_as_a_completed_rotation(client, secrets_auth):
    """THE REAL BUG: this route used to audit "operator.secret_set" BEFORE calling `.set()`, so a
    refused write (an empty value here) was still permanently logged as a completed rotation.
    Proves the fix cleanly returns 400 — a regression here (the new "operator.secret_set_refused"
    event undeclared in auditable_actions.py) would surface as a 500 (DeclarationError), not a 400."""
    r = client.put(f"{PREFIX}/secrets", json={"name": "ASSISTANT_MODEL_PROJECT", "value": " "},
                   headers=secrets_auth)
    assert r.status_code == 400


def test_setting_a_real_secret_still_succeeds(client, secrets_auth):
    r = client.put(f"{PREFIX}/secrets",
                   json={"name": "ASSISTANT_MODEL_PROJECT", "value": "proj-123"},
                   headers=secrets_auth)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "ASSISTANT_MODEL_PROJECT"


# ── persona preview (read-only — see operator.py's own note) ──────────────────────────────────
def test_persona_preview_needs_the_same_capability_as_config(client, reader_auth):
    assert client.get(f"{PREFIX}/persona-preview", headers=reader_auth).status_code == 403


def test_persona_preview_carries_the_real_house_rules_with_a_generic_shop_label_by_default(
    client, operator_auth,
):
    text = client.get(f"{PREFIX}/persona-preview", headers=operator_auth).json()["prompt"]
    assert "لا تدّعِ أبدًا أنك أتممت حجزًا" in text
    from app.core.shop_identity import GENERIC_SHOP_LABEL
    assert GENERIC_SHOP_LABEL in text


def test_persona_preview_reflects_a_real_shop_name_and_owner_notes_when_given(client, operator_auth):
    text = client.get(f"{PREFIX}/persona-preview", headers=operator_auth,
                      params={"shop_name": "صالون لمسة", "owner_notes": "نغلق الجمعة"}).json()["prompt"]
    assert "صالون لمسة" in text
    assert "نغلق الجمعة" in text
