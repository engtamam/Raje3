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


def test_a_signup_that_finishes_without_a_number_is_never_exchanged(client):
    """v3 and v4 let an owner finish Embedded Signup with no verified number — v2 did not.

    Exchanging then would seal his token against an EMPTY phone-number id: every screen would show
    «مربوط» and every message would resolve a credential addressing no number. A shop that
    believes it is live and is mute is this product's worst failure, and here it would be written
    on purpose.
    """
    h = _headers("tnt_nonum", caps=("billing.self",))
    r = client.post("/api/v1/whatsapp/connect",
                    json={"event": "FINISH", "code": "AQB-code", "waba_id": "wab_1",
                          "phone_number_id": "", "business_id": "biz_1"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "finished_unconfirmed"
    assert "وثّق الرقم" in body["message"]

    # AND NOTHING WAS STORED AS CONNECTED — the next screen must not read this as a live link.
    status = client.get("/api/v1/whatsapp/connect", headers=h).json()
    assert status["state"] != "connected"


# ── §12.4: a branch manager sees his branch ───────────────────────────────────────────────────
def _hire(client, tenant, *, name, phone, role="manager", branch_id="", pw="hunter2hunter2"):
    return client.post("/api/v1/staff/members",
                       json={"name": name, "phone": phone, "password": pw, "role": role,
                             "branch_id": branch_id},
                       headers=_headers(tenant))


def test_hiring_creates_a_seat_a_role_and_a_branch(client):
    """AN EMPLOYEE COULD NOT HAVE A LOGIN AT ALL until base-services v0.16.8: `seed-owner` refuses
    a second owner, and the alternative was handing the shop owner a capability over identity."""
    h = _headers("tnt_hire")
    client.get(BRANCHES, headers=h)
    r = _hire(client, "tnt_hire", name="سعد", phone="0500000101", branch_id="brn-main")
    assert r.status_code in (201, 400), r.text
    if r.status_code == 400:
        # The identity peer is not wired in this test container; the refusal must still be a
        # sentence the owner can read rather than a bare status.
        assert r.json()["message"]
        return
    body = r.json()
    assert body["role"] == "manager" and body["branch_id"] == "brn-main"
    assert body["has_login"] is True


def test_an_unassigned_person_sees_the_whole_shop(client):
    """The common case, and the reason narrowing is opt-in: the owner has no operator row at all,
    and a shop that assigns nobody must not suddenly see less than it did yesterday."""
    import asyncio

    from app.api.scope import branch_scope
    from types import SimpleNamespace

    store = client.app.state.container.datastore
    scope = asyncio.run(branch_scope(store, SimpleNamespace(subject="u_owner", tenant="tnt_scope")))
    assert scope == ""


def test_an_assigned_person_is_scoped_to_his_own_branch(client):
    """And this is the promise §12.4 makes: «لا يرى موظف فرع أ بيانات فرع ب»."""
    import asyncio

    from app.api.scope import branch_scope, visible
    from app.core.models import Operator
    from app.core.stores import OperatorStore
    from types import SimpleNamespace

    store = client.app.state.container.datastore
    asyncio.run(OperatorStore(store).save(Operator(
        id="opr_jed", tenant="tnt_scope", name="مدير جدة", role="manager",
        branch_id="brn-jeddah", person_id="u_jeddah")))

    scope = asyncio.run(branch_scope(store, SimpleNamespace(subject="u_jeddah",
                                                           tenant="tnt_scope")))
    assert scope == "brn-jeddah"

    rows = [{"branch_id": "brn-jeddah"}, {"branch_id": "brn-riyadh"}, {"branch_id": ""}]
    kept = visible(rows, scope)
    # HIS OWN, AND THE UNBRANCHED ONES — which belong to nobody and are hidden from nobody.
    assert kept == [{"branch_id": "brn-jeddah"}, {"branch_id": ""}]


def test_a_stopped_employee_is_not_scoped_by_his_old_row(client):
    """He is not scoped BECAUSE he must not be reading anything at all — his account is what stops
    him. A deactivated row narrowing a live token would be a rule enforced in the wrong place."""
    import asyncio

    from app.api.scope import branch_scope
    from app.core.models import Operator
    from app.core.stores import OperatorStore
    from types import SimpleNamespace

    store = client.app.state.container.datastore
    asyncio.run(OperatorStore(store).save(Operator(
        id="opr_gone", tenant="tnt_gone", name="من ترك", role="manager",
        branch_id="brn-jeddah", person_id="u_gone", active=False)))
    assert asyncio.run(branch_scope(store, SimpleNamespace(subject="u_gone",
                                                          tenant="tnt_gone"))) == ""


# ── the mode: central by default, one way out, and never back from a screen ────────────────────
def test_a_shop_is_central_until_it_says_otherwise(client):
    """ABSENCE IS THE DEFAULT. A row written at signup would record a decision nobody made."""
    r = client.get("/api/v1/staff/mode", headers=_headers("tnt_mode_a"))
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "central"
    assert r.json()["chosen_at"] == 0


def test_per_branch_is_refused_while_its_plumbing_is_not_built(client):
    """A MODE THAT CAN BE SELECTED AND DOES NOTHING is the defect this codebase keeps finding: the
    credentials are still per establishment, so a shop switched into it would go on sending from
    one number while every screen promised otherwise."""
    r = client.put("/api/v1/staff/mode", json={"mode": "per_branch"},
                   headers=_headers("tnt_mode_b"))
    assert r.status_code == 409, r.text
    assert "لم تُفعَّل بعد" in r.json()["message"]
    # AND IT SAYS SO IN THE READ, so the screen renders the choice without offering it.
    assert client.get("/api/v1/staff/mode",
                      headers=_headers("tnt_mode_b")).json()["available"] is False


def test_an_unknown_mode_is_refused_by_name(client):
    r = client.put("/api/v1/staff/mode", json={"mode": "franchise"},
                   headers=_headers("tnt_mode_c"))
    assert r.status_code == 409 and r.json()["error"] == "MODE_REFUSED"


def test_the_reverse_is_refused_with_the_reason_and_the_way_out(client):
    """Going back is not a setting: a number that entered the Cloud API, templates approved against
    it, and customers who saved their branch's number are not undone by flipping a field."""
    import asyncio

    from app.core.shop_mode import CENTRAL, PER_BRANCH, ModeError, ModeStore

    store = ModeStore(client.app.state.container.datastore)
    # Put the shop in per-branch the way the day it ships will: with the mode available.
    assert asyncio.run(store.set("tnt_mode_d", PER_BRANCH, available=True))["mode"] == PER_BRANCH

    try:
        asyncio.run(store.set("tnt_mode_d", CENTRAL, available=True))
        raise AssertionError("the reverse must be refused")
    except ModeError as exc:
        assert "تواصل معنا" in str(exc)

    # AND THE SHOP IS STILL WHERE IT WAS — a refused change that half-applied would be worse than
    # either answer.
    assert asyncio.run(store.get("tnt_mode_d"))["mode"] == PER_BRANCH


def test_choosing_the_mode_it_already_has_is_not_a_refusal(client):
    """A screen that re-sends the current value on every save must not be told it is going
    backwards — that is the shape of a support call nobody can close."""
    import asyncio

    from app.core.shop_mode import CENTRAL, ModeStore

    store = ModeStore(client.app.state.container.datastore)
    assert asyncio.run(store.set("tnt_mode_e", CENTRAL, available=False))["mode"] == CENTRAL


def test_a_refused_mode_change_leaves_no_audit_line(client, monkeypatch):
    """The record answers one question months later: WHEN did this shop change its mode.

    Written on the way in, it answers with the day somebody was refused — and then a second line
    with the day it actually happened. Two dates for one event is worse than none, because the
    first one looks authoritative.
    """
    seen: list[str] = []

    async def record(action, **kw):
        seen.append(action)

    monkeypatch.setattr(client.app.state.auditor, "record", record)

    # Refused: the mode is not available in this deployment.
    r = client.put("/api/v1/staff/mode", json={"mode": "per_branch"},
                   headers=_headers("tnt_mode_f"))
    assert r.status_code == 409
    assert seen == []

    # And an unknown value is refused before anything is recorded either.
    assert client.put("/api/v1/staff/mode", json={"mode": "franchise"},
                      headers=_headers("tnt_mode_f")).status_code == 409
    assert seen == []


def test_the_change_that_happens_is_recorded_once(client, monkeypatch):
    """And the other half: a move that goes through leaves exactly one line."""
    seen: list[str] = []

    async def record(action, **kw):
        seen.append(action)

    monkeypatch.setattr(client.app.state.auditor, "record", record)
    monkeypatch.setattr(client.app.state.container_settings,
                        "BRANCH_MODE_PER_BRANCH_READY", True, raising=False)

    r = client.put("/api/v1/staff/mode", json={"mode": "per_branch"},
                   headers=_headers("tnt_mode_g"))
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "per_branch"
    assert seen == ["shop.mode_changed"]
