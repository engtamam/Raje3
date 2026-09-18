"""The Flow clone goes up before the template library that references it by name.

WHY ORDER MATTERS. A template's `flow_button` names a Flow this shop's WABA must already have (or
have at least attempted) a clone of — Meta refuses a template pointing at a Flow that does not
exist on that WABA. Both calls are still fire-and-forget, "after the response, not inside it" (see
api/v1/connect.py's own comment): a slow or failed provision must never turn a successful
connection into a visible error.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS, AUD = "iss", "aud"


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(tenant="tnt_flow_order"):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _FakeExchange:
    async def exchange(self, *, tenant, code, waba_id, phone_number_id, branch_id="", root_tenant=""):
        return True, ""


def test_provision_shop_flow_is_scheduled_before_publish(client, monkeypatch):
    calls: list[str] = []

    async def _fake_provision(flows, tenant, master_flow_id, **_kwargs):
        # TWO CLONE CALLS (Phase 5's booking Flow, and visit-registration over WhatsApp) — all
        # still queued before the library publish, which is the property this test actually
        # protects. Rating and the weekly report USED to be two more of these (2026-09-16, both
        # removed — see core/flows.py's own module docstring). Subscription renewal is NOT one of
        # these — it is a platform-owned Flow, authored once on our own account via an explicit
        # admin action, never cloned at connect time (see api/v1/connect.py's own comment).
        # `**_kwargs` absorbs `flow_name`/`categories`/`endpoint_uri` without caring which Flow
        # this particular call is for.
        calls.append("flow")
        return {"ok": False, "reason": "test double"}

    async def _fake_publish(library, templates, tenant):
        calls.append("library")
        return {"registered": 0, "failed": 0, "drain": {"ok": False}}

    import app.core.connect as connect_module
    import app.core.flows as flows_module
    import app.core.library as library_module

    monkeypatch.setattr(connect_module, "build_exchange", lambda settings: _FakeExchange())
    monkeypatch.setattr(flows_module, "provision_shop_flow", _fake_provision)
    monkeypatch.setattr(library_module, "publish", _fake_publish)

    r = client.post("/api/v1/whatsapp/connect", json={
        "event": "FINISH", "code": "a-code", "waba_id": "waba_order",
        "phone_number_id": "pn_order", "business_id": "biz_order",
    }, headers=_headers())
    assert r.status_code == 200, r.text
    # THE ORDER IS THE ASSERTION. All three are background tasks queued during the same request;
    # a background task added later still runs after ones added earlier (BackgroundTasks is
    # FIFO), so this only holds if connect.py schedules BOTH Flow clones before the library
    # publish that references them by name.
    assert calls == ["flow", "flow", "library"], calls
