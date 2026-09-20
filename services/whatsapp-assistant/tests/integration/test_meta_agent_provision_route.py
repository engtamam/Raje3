"""Integration: /internal/whatsapp/meta-agent/provision — the cross-service leg operations'
/whatsapp/connect background task calls right after a number connects. See
app/core/meta_agent_provisioning.py for the 7-step sequence this route runs."""
from __future__ import annotations

from tests.conftest import INTERNAL_TOKEN

TENANT = "meta_provision_shop"
ENTITY_ID = "1234567890"


def _headers():
    return {"X-Internal-Token": INTERNAL_TOKEN}


class _FakeSecretStore:
    """A store with no credential for this tenant -- same shape provision_number's own
    `secret_store.get(tenant=, name=)` expects, returning nothing rather than raising, so the
    real "no Meta credential configured" refusal path runs (never a real network call)."""

    def __init__(self, token: str = "") -> None:
        self._token = token

    async def get(self, *, tenant: str, name: str) -> str:
        return self._token

    async def set(self, *, tenant: str, name: str, value: str, actor_ref: str = "") -> None:
        return None


def _swap_secret_store(client, token: str = ""):
    c = client.app.state.container
    saved = c.secret_store
    c.secret_store = _FakeSecretStore(token)
    return saved


def _restore_secret_store(client, saved):
    client.app.state.container.secret_store = saved


def test_flag_off_reports_disabled_and_never_calls_meta(client, monkeypatch):
    """META_AGENT_PROVISIONING_ENABLED off -- even WITH a credential configured, the route binds
    NullMetaAgentProvisioner (check_eligibility always False there), never a real network call."""
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "false")
    saved = _swap_secret_store(client, token="fake-bearer-token")
    try:
        r = client.post("/internal/whatsapp/meta-agent/provision",
                        json={"tenant": TENANT, "entity_id": ENTITY_ID}, headers=_headers())
    finally:
        _restore_secret_store(client, saved)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["failed_step"] == "check_eligibility"
    assert body["agent_id"] == ""


def test_flag_on_but_no_credential_fails_at_the_first_step(client, monkeypatch):
    """META_AGENT_PROVISIONING_ENABLED on, but this tenant has no META_KNOWLEDGE_TOKEN/
    META_WA_PHONE_NUMBER_ID secret configured -- provision_number's own first check refuses
    cleanly, never a crash, and never a real network call (no token to authenticate with)."""
    monkeypatch.setenv("META_AGENT_PROVISIONING_ENABLED", "true")
    saved = _swap_secret_store(client)
    try:
        r = client.post("/internal/whatsapp/meta-agent/provision",
                        json={"tenant": TENANT, "entity_id": ENTITY_ID}, headers=_headers())
    finally:
        _restore_secret_store(client, saved)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["failed_step"] == "check_eligibility"
    assert "credential" in body["error"] or "entity_id" in body["error"]


def test_refuses_without_the_internal_token(client):
    r = client.post("/internal/whatsapp/meta-agent/provision",
                    json={"tenant": TENANT, "entity_id": ENTITY_ID})
    assert r.status_code in (401, 403)


def test_refuses_a_missing_tenant(client):
    r = client.post("/internal/whatsapp/meta-agent/provision",
                    json={"entity_id": ENTITY_ID}, headers=_headers())
    assert r.status_code == 422


def test_refuses_a_missing_entity_id(client):
    r = client.post("/internal/whatsapp/meta-agent/provision",
                    json={"tenant": TENANT}, headers=_headers())
    assert r.status_code == 422
