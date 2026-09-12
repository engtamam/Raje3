"""GET /api/v1/field/staff/performance — the rating app's staff-comparison report
(rating-app-feature.md phase 7). `bookings_desk` is left unconfigured in every test here
(BOOKINGS_SERVICE_URL unset), so the no-show half is always {} — exactly the best-effort
"omit the column, never fail the report" behavior the desk itself documents."""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"


def _make_app(**env_over) -> TestClient:
    from app.config import get_settings

    env = {
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": TOKEN_SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        "SECRETS_KEK": "unit-test-kek-not-a-real-key", "PII_SALT": "s" * 32,
    }
    env.update(env_over)
    os.environ.update(env)
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str = "tnt_perf", sub: str = "owner1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": sub, "iss": ISS, "aud": AUD, "caps": list(caps), "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture()
def client():
    saved = dict(os.environ)
    yield _make_app()
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def _seed_operator(client, *, ident: str, name: str, tenant: str = "tnt_perf"):
    from app.core.models import Operator
    from app.core.stores import OperatorStore
    asyncio.run(OperatorStore(client.app.state.container.datastore).save(
        Operator(tenant=tenant, id=ident, name=name)))


def _seed_visit(client, *, visit_id: str, tenant: str = "tnt_perf", **over):
    from app.core.models import Visit
    from app.core.stores import VisitStore
    base = dict(id=visit_id, tenant=tenant, customer_id="cus_1", created=1_000, occurred_at=1_000)
    base.update(over)
    asyncio.run(VisitStore(client.app.state.container.datastore).save(Visit(**base)))


def test_operations_read_is_not_enough_only_manage(client):
    r = client.get("/api/v1/field/staff/performance?since=0&until=2000",
                   headers=_auth("operations.read"))
    assert r.status_code == 403


def test_a_manager_sees_the_comparison(client):
    _seed_operator(client, ident="op_a", name="سارة")
    _seed_visit(client, visit_id="v1", operator_id="op_a", rating=5, rated_at=1_000)
    _seed_visit(client, visit_id="v2", operator_id="op_a", rating=3, rated_at=1_000)

    r = client.get("/api/v1/field/staff/performance?since=0&until=2000",
                   headers=_auth("operations.manage"))
    assert r.status_code == 200, r.text
    staff = r.json()["staff"]
    assert len(staff) == 1
    assert staff[0]["operator_id"] == "op_a"
    assert staff[0]["operator_name"] == "سارة"
    assert staff[0]["visits"] == 2
    assert staff[0]["ratings"] == 2
    assert staff[0]["average_rating"] == 4.0
    # bookings_desk has no BOOKINGS_SERVICE_URL configured in this test — the no-show column
    # degrades to 0.0 rather than failing the whole report.
    assert staff[0]["no_show_rate"] == 0.0


def test_an_empty_shop_gets_an_empty_list(client):
    r = client.get("/api/v1/field/staff/performance?since=0&until=2000",
                   headers=_auth("operations.manage"))
    assert r.status_code == 200, r.text
    assert r.json()["staff"] == []


def test_until_before_since_is_refused(client):
    r = client.get("/api/v1/field/staff/performance?since=2000&until=0",
                   headers=_auth("operations.manage"))
    assert r.status_code == 200, r.text
    assert r.json().get("error") == "BAD_REQUEST"


def test_another_tenants_operators_never_leak_in(client):
    _seed_operator(client, ident="op_a", name="سارة", tenant="tnt_perf")
    _seed_operator(client, ident="op_x", name="أخرى", tenant="tnt_other")
    _seed_visit(client, visit_id="v1", operator_id="op_a", tenant="tnt_perf", rating=5,
               rated_at=1_000)
    _seed_visit(client, visit_id="v2", operator_id="op_x", tenant="tnt_other", rating=1,
               rated_at=1_000)

    r = client.get("/api/v1/field/staff/performance?since=0&until=2000",
                   headers=_auth("operations.manage"))
    staff = r.json()["staff"]
    assert [s["operator_id"] for s in staff] == ["op_a"]
