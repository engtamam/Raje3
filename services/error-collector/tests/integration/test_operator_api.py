"""The operator surface.

The load-bearing tests here are negative ones: that no route hands back a credential, that the
capability is required, and that a knob which must stay deploy-time is refused. The happy paths are
easy and were never the risk.
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
SECRET = "sk_live_abcdef0123456789"


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
    return _auth("platform.secrets", "platform.config")


@pytest.fixture
def reader_auth() -> dict:
    """Holds a capability, but not these two. Setting a payment key and reading a report are not
    the same privilege."""
    return _auth("reports.read")


# ── the guarantee ─────────────────────────────────────────────────────────────
def test_no_route_returns_a_stored_credential(client, operator_auth):
    """The whole point. A panel that can read a key back is a panel breach away from every
    tenant's provider account."""
    put = client.put("/api/v1/operator/secrets",
                     json={"name": "sms_api_key", "value": SECRET}, headers=operator_auth)
    assert put.status_code == 200, put.text

    bodies = [put.text,
              client.get("/api/v1/operator/secrets", headers=operator_auth).text,
              client.get("/api/v1/operator/config", headers=operator_auth).text]
    for body in bodies:
        assert SECRET not in body
        # Not even a long prefix: a hint is four characters, and anything more starts being a
        # meaningful fraction of a short token.
        assert SECRET[:8] not in body


def test_the_panel_gets_a_hint_it_can_act_on(client, operator_auth):
    # Enough to tell which key is loaded before replacing it — replacing the wrong one is the
    # mistake the hint prevents.
    client.put("/api/v1/operator/secrets",
               json={"name": "sms_api_key", "value": SECRET}, headers=operator_auth)
    got = client.get("/api/v1/operator/secrets", headers=operator_auth).json()["secrets"]
    entry = next(s for s in got if s["name"] == "sms_api_key")
    assert entry["hint"].endswith(SECRET[-4:])
    assert entry["hint"].count("•") == 4


# ── authorisation ─────────────────────────────────────────────────────────────
def test_credentials_need_their_own_capability(client, reader_auth):
    """Setting a payment key and reading a report are not the same privilege."""
    for method, url in [("get", "/api/v1/operator/secrets"),
                        ("delete", "/api/v1/operator/secrets/sms_api_key")]:
        assert getattr(client, method)(url, headers=reader_auth).status_code == 403
    assert client.put("/api/v1/operator/secrets",
                      json={"name": "k", "value": "v"}, headers=reader_auth).status_code == 403


def test_unauthenticated_is_refused(client):
    assert client.get("/api/v1/operator/secrets").status_code == 401


# ── rotation ──────────────────────────────────────────────────────────────────
def test_a_rotation_keeps_the_previous_value_accepted(client, operator_auth):
    """A request in flight when a key changes must not fail."""
    h = {"headers": operator_auth}
    client.put("/api/v1/operator/secrets", json={"name": "k", "value": "old-value-1111"}, **h)
    second = client.put("/api/v1/operator/secrets",
                        json={"name": "k", "value": "new-value-2222"}, **h)
    assert second.json()["rotating"] is True, "the previous value was dropped immediately"

    listed = next(s for s in client.get("/api/v1/operator/secrets", **h).json()["secrets"]
                  if s["name"] == "k")
    assert listed["rotating"] is True


def test_clearing_a_credential_removes_it(client, operator_auth):
    h = {"headers": operator_auth}
    client.put("/api/v1/operator/secrets", json={"name": "k", "value": "v-1234"}, **h)
    assert client.delete("/api/v1/operator/secrets/k", **h).json()["cleared"] is True
    assert not [s for s in client.get("/api/v1/operator/secrets", **h).json()["secrets"]
                if s["name"] == "k"]


# ── policy ────────────────────────────────────────────────────────────────────
def test_a_deploy_time_knob_is_refused(client, operator_auth):
    """Wiring changed under a live request is a class of bug nobody can reproduce."""
    for key in ("DATASTORE_DRIVER", "SECRETS_KEK", "PII_SALT", "INTERNAL_SERVICE_TOKEN"):
        r = client.put("/api/v1/operator/config",
                       json={"key": key, "value": "anything"}, headers=operator_auth)
        assert r.status_code == 400, f"{key} was accepted at runtime"


def test_the_config_view_never_carries_a_credential(client, operator_auth):
    view = client.get("/api/v1/operator/config", headers=operator_auth).json()["config"]
    for banned in ("SECRETS_KEK", "INTERNAL_SERVICE_TOKEN", "PII_SALT", "DATASTORE_DSN"):
        assert banned not in view


def test_only_the_two_declared_signal_settings_are_offered(client, operator_auth):
    """error-collector-001 (QA audit, 2026-09-12): RUNTIME_POLICY used to stay the template's
    empty frozenset() while admin_actions.py's own help text already called these two "the only
    two settings today" — the panel rendered empty and every PUT was refused, contradicting the
    very screen it was on. Fixed: exactly these two are offered, with their configured defaults,
    and an undeclared knob (RATELIMIT_MAX — deploy-time wiring, never settable here) is still
    refused, same as before."""
    h = {"headers": operator_auth}
    config = client.get("/api/v1/operator/config", **h).json()["config"]
    assert config == {"SIGNAL_RETENTION_DAYS": 10, "SIGNAL_REAP_LIMIT": 5000}
    r = client.put("/api/v1/operator/config", json={"key": "RATELIMIT_MAX", "value": 250}, **h)
    assert r.status_code == 400, "an undeclared knob was accepted and would have been inert"


def test_setting_the_signal_retention_actually_moves_what_ingest_reads(client, operator_auth):
    """The whole point of the fix: a saved override must not be a receipt for a change that never
    happened. Proved end to end — set through the panel, then read back through the SAME route a
    real ingest/reap call resolves its retention_days/reap_limit through."""
    from app.api.deps import get_runtime_config

    h = {"headers": operator_auth}
    r = client.put("/api/v1/operator/config",
                   json={"key": "SIGNAL_RETENTION_DAYS", "value": 45}, **h)
    assert r.status_code == 200, r.text
    config = client.get("/api/v1/operator/config", **h).json()["config"]
    assert config["SIGNAL_RETENTION_DAYS"] == 45

    async def read_effective():
        request = type("R", (), {"app": client.app})()
        rc = get_runtime_config(request)
        return await rc.get(tenant="", key="SIGNAL_RETENTION_DAYS", default=10)

    import asyncio
    assert asyncio.run(read_effective()) == 45


# ── availability ──────────────────────────────────────────────────────────────
def test_without_a_kek_the_surface_refuses_rather_than_storing_in_the_clear(env_guard):
    """No KEK means nothing to seal with. Storing the credential anyway — in the clear, while
    every check reports 'encrypted' — is the one outcome that must never happen."""
    c = _make_app(SECRETS_KEK="")
    r = c.put("/api/v1/operator/secrets", json={"name": "k", "value": "v"},
              headers=_auth("platform.secrets"))
    assert r.status_code == 503, "a credential was accepted with nothing to seal it with"
    # The reason is not echoed: the error middleware generalises every 5xx, deliberately. The
    # property under test is the refusal and the absence of a stored value, not the wording.
    assert "v" not in r.json().get("error", "")
    # And the read side refuses identically, rather than reporting an empty credential set —
    # "no secrets configured" and "secrets unreadable" must not look the same to an operator.
    assert c.get("/api/v1/operator/secrets", headers=_auth("platform.secrets")).status_code == 503


def test_a_kek_less_set_secret_corrects_its_own_write_ahead_audit_entry(env_guard):
    """error-collector-r2-001 (QA audit, 2026-09-12): `_secret_store()` raising HTTPException(503)
    (no SECRETS_KEK) used to escape `except SecretError` entirely — the write-ahead
    "operator.secret_set" entry stood uncorrected while the caller got a 503. A second, corrective
    entry must land in the same sink."""
    c = _make_app(SECRETS_KEK="")
    sink = c.app.state.auditor._sink
    sink.events.clear()
    r = c.put("/api/v1/operator/secrets", json={"name": "k", "value": "v"},
              headers=_auth("platform.secrets"))
    assert r.status_code == 503
    actions = [e.action for e in sink.events]
    assert actions.count("operator.secret_set") == 2
    refused = sink.events[-1]
    assert refused.metadata.get("outcome") == "refused"


def test_a_kek_less_clear_secret_corrects_its_own_write_ahead_audit_entry(env_guard):
    """Same gap, the OTHER route: clear_secret had no try/except at all."""
    c = _make_app(SECRETS_KEK="")
    sink = c.app.state.auditor._sink
    sink.events.clear()
    r = c.delete("/api/v1/operator/secrets/k", headers=_auth("platform.secrets"))
    assert r.status_code == 503
    actions = [e.action for e in sink.events]
    assert actions.count("operator.secret_cleared") == 2
    refused = sink.events[-1]
    assert refused.metadata.get("outcome") == "refused"


# ── error-collector-r2-003/005 ──────────────────────────────────────────────────
def test_the_kek_derived_secret_store_is_the_same_object_across_requests(client, operator_auth):
    """r2-003: SecretStore.__init__ runs a deliberately expensive scrypt KDF, and the store used
    to be rebuilt (re-deriving the key) on every single request. It is now cached on app.state,
    built once."""
    client.get("/api/v1/operator/secrets", headers=operator_auth)
    first = client.app.state.secret_store
    client.get("/api/v1/operator/secrets", headers=operator_auth)
    assert client.app.state.secret_store is first


@pytest.mark.parametrize("path", [
    "/api/v1/operator/secrets",
    "/api/v1/operator/config",
])
def test_an_overlong_tenant_query_param_is_refused_not_silently_truncated(path, client, operator_auth):
    r = client.get(path, params={"tenant": "t" * 200}, headers=operator_auth)
    assert r.status_code == 422
