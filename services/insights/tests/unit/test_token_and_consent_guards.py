"""Two boot guards that existed on paper but never fired: TOKEN_VERIFIER_DRIVER=null was never
refused in production, and assert_consent_config_ok() was defined but never called from
create_app(). Both are the same failure shape as audit/peers: a deny-by-default value that looks
healthy right up until the first real request needs the thing it silently lacks.
"""
from __future__ import annotations

import pytest

from app.config import Settings

_OK = {"INTERNAL_SERVICE_TOKEN": "x" * 40}


# ── assert_token_config_ok ────────────────────────────────────────────────────
def test_dev_defaults_boot_with_zero_infrastructure():
    Settings(ENV="test", **_OK).assert_token_config_ok()


def test_production_refuses_a_verifier_that_denies_everything():
    with pytest.raises(ValueError, match="TOKEN_VERIFIER_DRIVER=null"):
        Settings(ENV="production", TOKEN_VERIFIER_DRIVER="null", **_OK).assert_token_config_ok()


def test_production_refuses_hs256_with_no_secret():
    with pytest.raises(ValueError, match="TOKEN_HS256_SECRET"):
        Settings(ENV="production", TOKEN_VERIFIER_DRIVER="hs256", **_OK).assert_token_config_ok()


def test_production_refuses_rs256_with_no_public_key():
    with pytest.raises(ValueError, match="TOKEN_PUBLIC_KEY"):
        Settings(ENV="production", TOKEN_VERIFIER_DRIVER="rs256", **_OK).assert_token_config_ok()


def test_production_refuses_jwks_with_no_url():
    with pytest.raises(ValueError, match="TOKEN_JWKS_URL"):
        Settings(ENV="production", TOKEN_VERIFIER_DRIVER="jwks", **_OK).assert_token_config_ok()


def test_production_happy_config_passes():
    Settings(ENV="production", TOKEN_VERIFIER_DRIVER="hs256",
             TOKEN_HS256_SECRET="s" * 32, **_OK).assert_token_config_ok()
    Settings(ENV="production", TOKEN_VERIFIER_DRIVER="rs256",
             TOKEN_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----", **_OK).assert_token_config_ok()
    Settings(ENV="production", TOKEN_VERIFIER_DRIVER="jwks",
             TOKEN_JWKS_URL="https://issuer/.well-known/jwks.json", **_OK).assert_token_config_ok()


# ── create_app() actually calls both guards ───────────────────────────────────
def _set_other_guards_ok(monkeypatch):
    """So the guard under test is the one that fires, not audit/pii/peers ahead of it."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "x" * 40)
    monkeypatch.setenv("AUDIT_SINK_DRIVER", "eventbus")
    monkeypatch.setenv("PII_SALT", "s" * 32)
    monkeypatch.setenv("PEERS_DRIVER", "http")
    monkeypatch.setenv("OPERATIONS_SERVICE_URL", "http://operations")
    monkeypatch.setenv("REMINDERS_SERVICE_URL", "http://reminders")
    monkeypatch.setenv("BILLING_SERVICE_URL", "http://billing")


def test_create_app_refuses_a_deny_all_verifier_in_production(monkeypatch):
    _set_other_guards_ok(monkeypatch)
    monkeypatch.setenv("TOKEN_VERIFIER_DRIVER", "null")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import create_app
    with pytest.raises(ValueError, match="TOKEN_VERIFIER_DRIVER=null"):
        create_app()
    get_settings.cache_clear()


def test_create_app_refuses_a_consent_gate_left_unconfigured(monkeypatch):
    _set_other_guards_ok(monkeypatch)
    monkeypatch.setenv("TOKEN_VERIFIER_DRIVER", "hs256")
    monkeypatch.setenv("TOKEN_HS256_SECRET", "s" * 32)
    monkeypatch.setenv("CONSENT_GATED", "true")
    monkeypatch.setenv("CONSENT_GATE_DRIVER", "null")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import create_app
    with pytest.raises(ValueError, match="CONSENT_GATE_DRIVER=null"):
        create_app()
    get_settings.cache_clear()
