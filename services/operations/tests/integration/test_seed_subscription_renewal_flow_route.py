"""POST /api/v1/platform/flows/subscription-renewal/seed — the manual, one-time admin action
that authors the subscription-renewal Flow on PLATFORM ("_platform"), never at a shop's own
connect time."""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"
ROUTE = "/api/v1/platform/flows/subscription-renewal/seed"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(caps=("platform.operations",)) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "op-1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": "_platform", "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _FakeFlows:
    def __init__(self, *, author_result=None, encryption_result=None) -> None:
        self.author_calls: list[dict] = []
        self.encryption_calls: list[str] = []
        self._author = author_result if author_result is not None else \
            {"ok": True, "flow_id": "flow_1"}
        self._encryption = encryption_result if encryption_result is not None else {"ok": True}

    async def author_master(self, *, name, categories, flow_json, endpoint_uri=""):
        self.author_calls.append({"name": name, "categories": categories,
                                  "flow_json": flow_json, "endpoint_uri": endpoint_uri})
        return self._author

    async def ensure_encryption(self, tenant, *, phone_number_id=""):
        self.encryption_calls.append(tenant)
        return self._encryption

    async def provision(self, *a, **k):
        raise AssertionError("seed must never clone — author_master only")


def _swap(client, flows):
    saved = client.app.state.container.flows
    client.app.state.container.flows = flows
    return saved


def _clear_seeded(client) -> None:
    """The `client` fixture is module-scoped (one shared datastore) — clear the stored master id
    directly before any test that needs a genuinely fresh "not seeded yet" state, the same way a
    RuntimeConfig override is removed (see core/runtime_config.py's own `_key_of`/`clear`)."""
    import asyncio
    asyncio.run(client.app.state.container.datastore.delete(
        "runtime_config", "*|MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID"))


def test_requires_the_capability(client):
    r = client.post(ROUTE, headers=_headers(caps=("operations.manage",)))
    assert r.status_code == 403


def test_a_fresh_seed_authors_on_platform_and_seals_encryption(client):
    _clear_seeded(client)
    flows = _FakeFlows()
    saved = _swap(client, flows)
    try:
        r = client.post(ROUTE, headers=_headers())
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {"ok": True, "flow_id": "flow_1", "already_seeded": False,
                        "encryption": True}
        assert len(flows.author_calls) == 1
        call = flows.author_calls[0]
        assert call["name"] == "subscription_renewal"
        assert "SELECT" in str(call["flow_json"])
        assert flows.encryption_calls == ["_platform"]
    finally:
        client.app.state.container.flows = saved


def test_a_second_call_finds_it_already_seeded_and_authors_nothing_again(client):
    _clear_seeded(client)
    flows = _FakeFlows()
    saved = _swap(client, flows)
    try:
        client.post(ROUTE, headers=_headers())
        r = client.post(ROUTE, headers=_headers())
        assert r.status_code == 200
        assert r.json() == {"ok": True, "flow_id": "flow_1", "already_seeded": True}
        assert len(flows.author_calls) == 1     # not called the second time
    finally:
        client.app.state.container.flows = saved


def test_a_failed_authoring_is_a_named_refusal_not_a_500(client):
    _clear_seeded(client)
    flows = _FakeFlows(author_result={"ok": False, "reason": "META_REJECTED"})
    saved = _swap(client, flows)
    try:
        r = client.post(ROUTE, headers=_headers())
        assert r.status_code == 502
        assert r.json() == {"ok": False, "reason": "META_REJECTED"}
    finally:
        client.app.state.container.flows = saved
