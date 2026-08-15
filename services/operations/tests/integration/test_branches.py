"""Branches — the main one exists, it cannot be closed, and closing a branch frees its capacity.

WHAT THESE PROVE, AND WHY EACH ONE WAS WORTH WRITING. Before this, a shop owned ZERO branch rows
until somebody typed a name into «فريقي», so every visit recorded in its first month carried no
place at all — and the two endpoints could create and list, nothing more. The rules added around
them are exactly the ones a test can hold: the main branch is there, it is one row however many
times you ask, it survives a close attempt, and a closed branch is not capacity you keep paying
for.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "h" * 40
ISS = "iss"
AUD = "aud"
BRANCHES = "/api/v1/staff/branches"


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


def _headers(tenant: str, caps=("operations.manage", "operations.read")) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_shop_that_never_opened_the_screen_still_has_its_main_branch(client):
    """The list is never empty — the repair runs on the read, because there is no migration."""
    rows = client.get(BRANCHES, headers=_headers("tnt_main")).json()["branches"]
    assert [b["id"] for b in rows] == ["brn-main"]
    assert rows[0]["active"] is True


def test_asking_twice_does_not_create_a_second_one(client):
    """The fixed id IS the idempotency — not a uniqueness check a second call could race past."""
    client.get(BRANCHES, headers=_headers("tnt_twice"))
    rows = client.get(BRANCHES, headers=_headers("tnt_twice")).json()["branches"]
    assert len(rows) == 1


def test_the_main_branch_can_be_renamed_because_the_name_is_his(client):
    h = _headers("tnt_rename")
    client.get(BRANCHES, headers=h)
    r = client.patch(f"{BRANCHES}/brn-main", json={"name": "فرع العليا"}, headers=h)
    assert r.status_code == 200 and r.json()["name"] == "فرع العليا"


def test_the_main_branch_cannot_be_closed(client):
    """It is the fallback every unrecognised branch resolves to, and the only place a one-branch
    shop has. The refusal is RETURNED with its sentence — a raised one reaches him stripped."""
    h = _headers("tnt_close")
    client.get(BRANCHES, headers=h)
    r = client.patch(f"{BRANCHES}/brn-main", json={"active": False}, headers=h)
    assert r.status_code == 409
    assert r.json()["error"] == "MAIN_BRANCH" and r.json()["message"]


def test_a_second_branch_can_be_closed_and_stays_in_the_list(client):
    """DEACTIVATED, NEVER DELETED — last year's visits point at it by a plain string id."""
    h = _headers("tnt_second")
    created = client.post(BRANCHES, json={"name": "فرع الملز"}, headers=h)
    assert created.status_code == 201
    bid = created.json()["id"]

    assert client.patch(f"{BRANCHES}/{bid}", json={"active": False},
                        headers=h).json()["active"] is False
    rows = {b["id"]: b for b in client.get(BRANCHES, headers=h).json()["branches"]}
    assert bid in rows and rows[bid]["active"] is False


def test_editing_a_branch_that_does_not_exist_is_a_404(client):
    h = _headers("tnt_404")
    assert client.patch(f"{BRANCHES}/brn-nope", json={"name": "x"}, headers=h).status_code == 404


def test_a_closed_branch_stops_counting_against_the_plan(client):
    """He is not paying to keep a place he shut down — and the gauge is REPORTED, so the count
    sent to billing is the live one rather than a total that only ever rises."""
    h = _headers("tnt_gauge")
    created = client.post(BRANCHES, json={"name": "فرع مؤقت"}, headers=h)
    bid = created.json()["id"]
    client.patch(f"{BRANCHES}/{bid}", json={"active": False}, headers=h)

    gauges = client.app.state.container.gauges
    reported = [v for (t, k, v) in gauges.reported if t == "tnt_gauge" and k == "branches"]
    # 2 when the second was added, 1 once it was closed.
    assert reported[-2:] == [2, 1]


def test_a_customers_page_shows_HIS_visits_even_in_a_busy_shop(client):
    """THE READ USED TO BE THE SHOP'S LAST 200 VISITS, FILTERED. So a customer of a busy
    establishment opened the page we messaged him a link to and found no history at all — the
    busier the shop, the more certainly empty."""
    from app.core.models import Customer, Visit
    from app.core.stores import CustomerStore, VisitStore

    store = client.app.state.container.datastore
    tenant = "tnt_busy"
    mine = Customer(id="cus_mine", tenant=tenant, phone="+966500000009",
                    subject_ref="sub_mine", created=1)
    import asyncio

    async def seed():
        await CustomerStore(store).save(mine)
        vs = VisitStore(store)
        # His visit is the OLDEST, and then 250 visits by other people bury it.
        await vs.save(Visit(id="vis_mine", tenant=tenant, customer_id="cus_mine",
                            service_ids=["srv_1"], created=1, occurred_at=1))
        for i in range(250):
            await vs.save(Visit(id=f"vis_o{i}", tenant=tenant, customer_id="cus_other",
                                service_ids=["srv_1"], created=100 + i, occurred_at=100 + i))

    asyncio.run(seed())

    r = client.post("/internal/operations/customer-visits",
                    json={"tenant": tenant, "subject_ref": "sub_mine", "limit": 10},
                    headers={"X-Internal-Token": "t" * 40})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 1
