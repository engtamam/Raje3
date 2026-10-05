"""Customer-service freelancers — the shop's own admin door (api/v1/freelancers.py). HTTP-layer
tests, with particular emphasis on capability gating: `operator` and `partner` must be refused on
every route here (operator has no business running escalations; partner is walled off from a
shop's own customers by design, deploy/seed/roles.json's own `partner.description`).
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
INTERNAL_TOKEN = "t" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_freelancers_api"
OTHER_TENANT = "tnt_freelancers_api_other"

MANAGE = "operations.freelancer_manage"


def _make_app() -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": INTERNAL_TOKEN,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "PII_SALT": "s" * 32,
    }
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = TENANT, sub: str = "owner1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": sub, "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
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


# ── capability gating — the whole point of this suite ──────────────────────────────────────────
@pytest.mark.parametrize("caps", [(), ("operations.record",), ("operations.operator",)])
def test_list_refuses_anyone_without_the_manage_capability(client, caps):
    r = client.get("/api/v1/staff/freelancers", headers=_auth(*caps))
    assert r.status_code == 403


def test_list_refuses_the_operator_role_explicitly(client):
    # the operator role's own real capability set, mirroring deploy/seed/roles.json
    r = client.get("/api/v1/staff/freelancers",
                   headers=_auth("operations.record", "operations.mobile_requests_execute"))
    assert r.status_code == 403


def test_list_refuses_the_partner_role_explicitly(client):
    # partner's own real capability set is walled off from customer data by design
    r = client.get("/api/v1/staff/freelancers", headers=_auth("partner.till"))
    assert r.status_code == 403


def test_list_with_the_manage_capability_succeeds(client):
    r = client.get("/api/v1/staff/freelancers", headers=_auth(MANAGE))
    assert r.status_code == 200
    assert r.json() == {"freelancers": []}


def test_add_refuses_without_the_manage_capability(client):
    r = client.post("/api/v1/staff/freelancers", headers=_auth("operations.record"),
                    json={"phone": "0501234567", "display_name": "سارة"})
    assert r.status_code == 403


def test_every_mutating_route_refuses_the_partner_role(client):
    partner = _auth("partner.till")
    assert client.post("/api/v1/staff/freelancers", headers=partner,
                       json={"phone": "0501234567", "display_name": "سارة"}).status_code == 403
    assert client.post("/api/v1/staff/freelancers/x/deactivate",
                       headers=partner).status_code == 403
    assert client.post("/api/v1/staff/freelancers/rules", headers=partner,
                       json={"cooldown_days": 7, "daily_cap": 2}).status_code == 403
    assert client.get("/api/v1/staff/freelancers/escalations", headers=partner).status_code == 403
    assert client.get("/api/v1/staff/freelancers/notes/export",
                      headers=partner, params={"since": 0, "until": 1}).status_code == 403


# ── add / deactivate ────────────────────────────────────────────────────────────────────────────
def test_add_then_list_round_trips(client):
    r = client.post("/api/v1/staff/freelancers", headers=_auth(MANAGE),
                    json={"phone": "0501234567", "display_name": "سارة"})
    assert r.status_code == 200
    body = r.json()
    assert body["active"] is True

    listed = client.get("/api/v1/staff/freelancers", headers=_auth(MANAGE)).json()
    assert len(listed["freelancers"]) == 1


def test_add_refuses_a_fourth_active_freelancer(client):
    for i in range(3):
        r = client.post("/api/v1/staff/freelancers", headers=_auth(MANAGE),
                        json={"phone": f"05011111{i:02d}", "display_name": f"مستقل {i}"})
        assert r.status_code == 200
    r = client.post("/api/v1/staff/freelancers", headers=_auth(MANAGE),
                    json={"phone": "0509999999", "display_name": "رابع"})
    assert r.status_code == 400


def test_add_is_scoped_to_the_callers_own_tenant(client):
    client.post("/api/v1/staff/freelancers", headers=_auth(MANAGE),
               json={"phone": "0501234567", "display_name": "سارة"})
    other = client.get("/api/v1/staff/freelancers",
                       headers=_auth(MANAGE, tenant=OTHER_TENANT)).json()
    assert other == {"freelancers": []}


def test_deactivate_round_trips(client):
    added = client.post("/api/v1/staff/freelancers", headers=_auth(MANAGE),
                        json={"phone": "0501234567", "display_name": "سارة"}).json()
    r = client.post(f"/api/v1/staff/freelancers/{added['id']}/deactivate", headers=_auth(MANAGE))
    assert r.status_code == 200
    assert r.json()["active"] is False


# ── business rules ──────────────────────────────────────────────────────────────────────────────
def test_set_rules_then_get_rules_round_trips(client):
    client.post("/api/v1/staff/freelancers/rules", headers=_auth(MANAGE),
               json={"cooldown_days": 14, "daily_cap": 3})
    r = client.get("/api/v1/staff/freelancers/rules", headers=_auth(MANAGE))
    assert r.json()["cooldown_days"] == 14
    assert r.json()["daily_cap"] == 3


def test_set_rules_rejects_an_out_of_range_value(client):
    r = client.post("/api/v1/staff/freelancers/rules", headers=_auth(MANAGE),
                    json={"cooldown_days": -1, "daily_cap": 3})
    assert r.status_code == 422


# ── reward catalog ───────────────────────────────────────────────────────────────────────────────
def test_add_reward_option_then_list_round_trips(client):
    client.post("/api/v1/staff/freelancers/reward-options", headers=_auth(MANAGE),
               json={"kind": "points", "label": "50 نقطة", "points": 50})
    r = client.get("/api/v1/staff/freelancers/reward-options", headers=_auth(MANAGE))
    assert len(r.json()["options"]) == 1


# ── escalations + export ────────────────────────────────────────────────────────────────────────
def test_list_escalations_starts_empty(client):
    r = client.get("/api/v1/staff/freelancers/escalations", headers=_auth(MANAGE))
    assert r.json() == {"escalations": []}


def test_resolve_escalation_refuses_an_unknown_id(client):
    r = client.post("/api/v1/staff/freelancers/escalations/nope/resolve", headers=_auth(MANAGE),
                    json={})
    assert r.status_code == 400


def test_export_notes_returns_an_empty_string_with_no_notes(client):
    r = client.get("/api/v1/staff/freelancers/notes/export", headers=_auth(MANAGE),
                   params={"since": 0, "until": 9_999_999_999})
    assert r.json() == {"text": ""}
