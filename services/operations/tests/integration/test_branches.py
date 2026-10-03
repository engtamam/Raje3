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
        # Needed from the customer-id-by-phone tests on: ensure_customer computes a real
        # subject_ref, and subject_ref() itself refuses an empty salt outright (core/pii.py) — a
        # real value here, not a workaround for it.
        "PII_SALT": "s" * 32,
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
    # A SECOND BRANCH NEEDS A LOCATION — see test_a_second_branch_without_a_location_is_refused
    # below for the refusal itself; every other test here about a SECOND branch just needs one to
    # get past that gate.
    created = client.post(BRANCHES, json={"name": "فرع الملز", "lat": 24.71, "lng": 46.68},
                          headers=h)
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
    created = client.post(BRANCHES, json={"name": "فرع مؤقت", "lat": 24.71, "lng": 46.68},
                          headers=h)
    bid = created.json()["id"]
    client.patch(f"{BRANCHES}/{bid}", json={"active": False}, headers=h)

    gauges = client.app.state.container.gauges
    reported = [v for (t, k, v) in gauges.reported if t == "tnt_gauge" and k == "branches"]
    # 2 when the second was added, 1 once it was closed.
    assert reported[-2:] == [2, 1]


# ── the lock the screen draws is the shop's plan, not the caller's role (هـ-3) ─────────────────
def test_the_branch_list_carries_the_plan_limit_so_the_screen_need_not_guess(client):
    """«فريقي» locked its branches tab on whether the CALLER holds `operations.list_branches` and
    wrote a sentence about the shop's PLAN on the lock. An owner capped at one branch holds that
    capability on every plan, so he saw no lock, typed a name, and met a 402 — and somebody who
    merely lacks the permission was told his shop must upgrade, which is a claim about money.

    So the entitlement travels with the read, exactly as `shop_mode.available` does."""
    class _Capped:
        driver = "capped"
        reported: list = []

        async def report(self, tenant, key, value):
            pass

        async def allows_one_more(self, tenant, key, current):
            return current + 1 <= 1, 1

    saved = client.app.state.container.gauges
    client.app.state.container.gauges = _Capped()
    try:
        body = client.get(BRANCHES, headers=_headers("tnt_capped")).json()
    finally:
        client.app.state.container.gauges = saved
    assert body["branch_limit"] == 1


def test_a_shop_at_its_ceiling_is_told_before_it_types_a_name(client):
    """THE CEILING ALONE ONLY ANSWERS FOR A PLAN THAT ALLOWS EXACTLY ONE.

    A shop allowed THREE branches and already holding three is at its limit too, and `branch_limit`
    of 3 draws no lock — so «إضافة فرع» stays live, the owner types a name, presses save, and reads
    the refusal at the end of the journey. That is the same defect هـ-3 named, met at a different
    number, and the gauge was already computing the answer: `allows_one_more` returns whether one
    more fits, and the route was keeping only the ceiling beside it.
    """
    class _Full:
        driver = "full"
        reported: list = []

        async def report(self, tenant, key, value):
            pass

        async def allows_one_more(self, tenant, key, current):
            # Three allowed, three held: a real ceiling that `branch_limit` alone cannot express.
            return False, 3

    saved = client.app.state.container.gauges
    client.app.state.container.gauges = _Full()
    try:
        body = client.get(BRANCHES, headers=_headers("tnt_full")).json()
    finally:
        client.app.state.container.gauges = saved
    assert body["branch_limit"] == 3
    assert body["may_add_branch"] is False, "the screen cannot tell he is full from the limit alone"


def test_a_billing_we_could_not_ask_reports_no_ceiling_rather_than_a_lock(client):
    """`allows_one_more` fails open by design (core/seats.py), and its `-1` covers an unlimited
    plan AND an unreachable billing. Neither may draw a lock: telling a paying shop it has not
    paid is the worst sentence in the product, and an outage must not be what says it."""
    body = client.get(BRANCHES, headers=_headers("tnt_open")).json()
    assert body["branch_limit"] == -1


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


def test_a_stopped_employee_sees_nothing_rather_than_everything(client):
    """THIS TEST USED TO ASSERT THE DEFECT, and its reasoning was «his account is what stops him».

    It did not. Stopping somebody wrote this row and nothing else — the membership at identity
    lived on, so he signed in that same evening. And an inactive row matched nobody, an unmatched
    person was read as unnarrowed, and unnarrowed means the whole establishment: dismissal
    PROMOTED him from one branch to every branch.

    Both halves are closed now. The membership is revoked when he is stopped, and a stopped row is
    its own answer here — REVOKED, which shows nothing, and which `visible` must not confuse with
    the empty scope that shows everything.
    """
    import asyncio

    from app.api.scope import REVOKED, branch_scope, visible
    from app.core.models import Operator
    from app.core.stores import OperatorStore
    from types import SimpleNamespace

    store = client.app.state.container.datastore
    asyncio.run(OperatorStore(store).save(Operator(
        id="opr_gone", tenant="tnt_gone", name="من ترك", role="manager",
        branch_id="brn-jeddah", person_id="u_gone", active=False)))
    scope = asyncio.run(branch_scope(store, SimpleNamespace(subject="u_gone",
                                                            tenant="tnt_gone")))
    assert scope is REVOKED
    # NOT ONE ROW — not even the unbranched ones everybody else may see.
    assert visible([{"branch_id": "brn-jeddah"}, {"branch_id": "brn-riyadh"},
                    {"branch_id": ""}], scope) == []


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


def test_a_customers_page_says_which_branch_each_visit_was_at(client):
    """«زيارتك — تغيير زيت» tells a chain's customer nothing about WHERE, which makes his own
    history useless to him and a booking impossible to place.

    THE NAME TRAVELS, NEVER THE ID: `brn-7f21` is not information, and an id on a public page is
    an invitation to guess the next one.
    """
    import asyncio

    from app.core.models import Customer, Visit
    from app.core.stores import CustomerStore, VisitStore

    store = client.app.state.container.datastore
    tenant = "tnt_where"
    h = _headers(tenant)
    made = client.post(BRANCHES, json={"name": "فرع العليا", "lat": 24.71, "lng": 46.68},
                       headers=h)
    assert made.status_code in (200, 201), made.text
    bid = made.json()["id"]

    async def seed():
        await CustomerStore(store).save(Customer(id="cus_w", tenant=tenant,
                                                 phone="+966500000011",
                                                 subject_ref="sub_where01", created=1))
        vs = VisitStore(store)
        await vs.save(Visit(id="vis_w1", tenant=tenant, customer_id="cus_w",
                            service_ids=["srv_1"], branch_id=bid, created=20, occurred_at=20))
        # And one with NO branch — the ordinary case for a till, and it must stay silent rather
        # than inventing «غير محدَّد» on the customer's own page.
        await vs.save(Visit(id="vis_w2", tenant=tenant, customer_id="cus_w",
                            service_ids=["srv_1"], created=10, occurred_at=10))

    asyncio.run(seed())

    r = client.post("/internal/operations/customer-visits",
                    json={"tenant": tenant, "subject_ref": "sub_where01", "limit": 10},
                    headers={"X-Internal-Token": "t" * 40})
    assert r.status_code == 200, r.text
    visits = r.json()["visits"]
    assert [v["branch"] for v in visits] == ["فرع العليا", ""]
    assert bid not in r.text


def test_a_second_branch_connection_does_not_erase_the_first(client):
    """THE DEFECT: the connection row was keyed on the tenant alone.

    A chain connecting its Jeddah number overwrote Riyadh's `waba_id` and `phone_number_id` — gone,
    with no copy anywhere and no way to send from the first number again. Nothing failed: the
    screen said «تم الربط» about the number that had just replaced the other one.
    """
    import asyncio

    from app.core import connect

    store = connect.ConnectionStore(client.app.state.container.datastore)
    tenant = "tnt_two_numbers"

    async def go():
        await store.record(connect.Attempt(
            tenant=tenant, state=connect.STATE_CONNECTED, waba_id="waba_ruh",
            phone_number_id="pn_ruh", branch_id="brn-ruh"))
        await store.record(connect.Attempt(
            tenant=tenant, state=connect.STATE_CONNECTED, waba_id="waba_jed",
            phone_number_id="pn_jed", branch_id="brn-jed"))
        return (await store.get(tenant, "brn-ruh"),
                await store.get(tenant, "brn-jed"),
                await store.for_tenant(tenant))

    ruh, jed, both = asyncio.run(go())
    assert ruh is not None and ruh.phone_number_id == "pn_ruh"
    assert jed is not None and jed.phone_number_id == "pn_jed"
    assert {a.branch_id for a in both} == {"brn-ruh", "brn-jed"}


def test_the_establishments_own_connection_keeps_its_old_key(client):
    """Every row written before this change is keyed on the tenant alone, and must still be found
    by the same lookup — nothing is migrated."""
    import asyncio

    from app.core import connect

    store = connect.ConnectionStore(client.app.state.container.datastore)
    tenant = "tnt_one_number"

    async def go():
        await store.record(connect.Attempt(
            tenant=tenant, state=connect.STATE_CONNECTED, waba_id="waba_1",
            phone_number_id="pn_1"))
        raw = await client.app.state.container.datastore.get("whatsapp_connections", tenant)
        return raw, await store.get(tenant)

    raw, got = asyncio.run(go())
    assert raw is not None, "a central shop's row must still be stored under its tenant id"
    assert got is not None and got.phone_number_id == "pn_1"
    assert got.branch_id == ""


def test_the_screen_does_not_promise_sending_it_cannot_do(client):
    """«حسابك جاهز للإرسال» IS A CLAIM, and it was made without checking.

    Meta handing us a token means the connection worked. It does not mean a message can leave —
    and on a deployment whose WhatsApp channel is not open, none can. An owner read «جاهز
    للإرسال», recorded visits all week, and wondered where his messages went.
    """
    from app.core import connect

    ready = connect.Attempt(tenant="t", state=connect.STATE_CONNECTED)

    open_line = connect.sentence_for(ready, can_send=True)
    shut_line = connect.sentence_for(ready, can_send=False)

    assert "جاهز للإرسال" in open_line
    # THE CONNECTION IS STILL HIS, and the sentence keeps it: he did the work and it succeeded.
    assert "تم الربط" in shut_line
    assert "جاهز للإرسال" not in shut_line
    # AND IT SAYS WHOSE FAULT IT IS. A shop told to wait waits; a shop told it is ready blames
    # itself, then us, then leaves.
    assert "من طرفنا" in shut_line
    assert "لا ينقصك" in shut_line

    assert ready.public(can_send=False)["can_send"] is False
    assert ready.public(can_send=True)["can_send"] is True


def test_a_failed_connection_is_not_reported_as_unable_to_send(client):
    """`can_send` answers «could a message leave», and for a shop that never connected the honest
    answer is the connection sentence — not a second complaint about our own channel."""
    from app.core import connect

    failed = connect.Attempt(tenant="t", state=connect.STATE_FAILED)
    assert failed.public(can_send=False)["can_send"] is True


# ── the list itself is narrowed, not only what the list is about ──────────────────────────────
def _headers_for(tenant: str, subject: str) -> dict:
    """The same token as `_headers`, for a NAMED person — the scope is resolved from `sub`."""
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": subject, "iss": ISS, "aud": AUD,
                      "caps": ["operations.manage", "operations.read"], "tenant": tenant,
                      "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def test_a_supervisor_is_offered_only_the_branches_he_may_read(client):
    """The branch LIST obeys §12.4 too — and until now it was the one read that did not.

    THE HOLE, AND WHY IT WAS INVISIBLE. Every other read in this service — visits, customers,
    the dashboards, the team table — passes through `branch_scope`. `GET /staff/branches` did
    not: it returned every row of the establishment to anybody holding `operations.list_branches`.
    So a manager granted Jeddah could not read Riyadh's numbers and could read Riyadh's NAME, its
    id, and how many places the chain has. «لا يرى موظف فرع أ بيانات فرع ب» covers the names.

    AND IT IS THE LIST THE SIDEBAR SWITCHER IS BUILT FROM. That control's one non-negotiable rule
    is «يُضيِّق ولا يوسّع أبداً»: it must offer him his own branches and nothing else. Built from
    an unnarrowed list it offers a branch the server then refuses — and the product looks broken
    to somebody who did nothing wrong. This is the assertion that makes that rule true at the
    source rather than repeated hopefully in a component.
    """
    import asyncio

    from app.core.models import Operator
    from app.core.stores import OperatorStore

    tenant = "tnt_switch"
    owner = _headers(tenant)
    for name in ("جدة", "الرياض", "الدمام"):
        assert client.post(BRANCHES, json={"name": name, "lat": 24.0, "lng": 46.0},
                           headers=owner).status_code in (200, 201)

    everything = client.get(BRANCHES, headers=owner).json()["branches"]
    ids = {b["id"] for b in everything}
    assert len(ids) >= 4, everything            # the three above plus the main one

    # A SUPERVISOR OVER TWO OF THEM — the case that made a set necessary in the first place
    # (#344): «مشرف على أربعة» had to be handed the whole chain to be handed his four.
    mine = sorted(ids - {"brn-main"})[:2]
    store = client.app.state.container.datastore
    asyncio.run(OperatorStore(store).save(Operator(
        id="opr_two", tenant=tenant, name="مشرف على فرعين", role="manager",
        branch_id=mine[0], visible_branch_ids=list(mine), person_id="u_two", active=True)))

    got = client.get(BRANCHES, headers=_headers_for(tenant, "u_two")).json()["branches"]
    assert sorted(b["id"] for b in got) == sorted(mine), got
    # NAMED EXPLICITLY: not «fewer», but none of the others at all — a leak of one branch name
    # is the same leak as a leak of three.
    assert not (ids - set(mine)) & {b["id"] for b in got}

    # AND THE OWNER IS UNCHANGED. Narrowing is opt-in per person (api/scope.py): the man with no
    # operator row is the common case, and he must still see his whole chain.
    assert {b["id"] for b in client.get(BRANCHES, headers=owner).json()["branches"]} == ids


def test_a_field_operator_with_only_bookings_caps_can_now_read_his_own_branch(client):
    """A plain field operator holds `bookings.read`/`bookings.write` but
    never `operations.read` — so this exact route used to answer him 403, and the console read
    that as «لا فروع بعد» (no branches EXIST), which was false. He simply held neither
    capability the route required. `_READ_BRANCHES` (staff.py) reopens this one self-narrowing
    read to bookings holders too, without touching any other `_READ`-gated route."""
    import asyncio

    from app.core.models import Operator
    from app.core.stores import OperatorStore

    tenant = "tnt_field_op"
    owner = _headers(tenant)
    assert client.post(BRANCHES, json={"name": "جدة", "lat": 21.54, "lng": 39.17},
                       headers=owner).status_code in (200, 201)

    store = client.app.state.container.datastore
    asyncio.run(OperatorStore(store).save(Operator(
        id="opr_field", tenant=tenant, name="عامل ميداني", role="operator",
        branch_id="brn-main", person_id="u_field", active=True)))

    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u_field", "iss": ISS, "aud": AUD,
                      "caps": ["operations.record", "bookings.read", "bookings.write"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    r = client.get(BRANCHES, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    # NARROWED, NOT JUST REACHABLE — his own branch only, same §12.4 promise as the manager/
    # supervisor cases above.
    assert [b["id"] for b in r.json()["branches"]] == ["brn-main"]

    # AND operations.record ALONE (no bookings.* either) IS STILL REFUSED — this did not become
    # a blanket door for anyone signed in.
    tok2 = jwt.encode({"sub": "u_field2", "iss": ISS, "aud": AUD, "caps": ["operations.record"],
                       "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                      SECRET, algorithm="HS256")
    assert client.get(BRANCHES, headers={"Authorization": f"Bearer {tok2}"}).status_code == 403


def test_the_plan_limit_is_the_shops_own_even_for_a_narrowed_person(client):
    """The ceiling is a fact about the ESTABLISHMENT's plan, never about this caller's view.

    Computing it from the narrowed list would tell a one-branch manager that his chain of five has
    room for four more — a number about money, wrong, on a screen he cannot act on anyway.
    """
    import asyncio

    from app.core.models import Operator
    from app.core.stores import OperatorStore

    tenant = "tnt_limit_scope"
    owner = _headers(tenant)
    for name in ("أ", "ب"):
        client.post(BRANCHES, json={"name": name, "lat": 24.0, "lng": 46.0}, headers=owner)
    whole = client.get(BRANCHES, headers=owner).json()

    store = client.app.state.container.datastore
    asyncio.run(OperatorStore(store).save(Operator(
        id="opr_one", tenant=tenant, name="مدير فرع", role="manager",
        branch_id="brn-main", person_id="u_one", active=True)))
    narrowed = client.get(BRANCHES, headers=_headers_for(tenant, "u_one")).json()

    assert len(narrowed["branches"]) == 1, narrowed["branches"]
    assert narrowed["branch_limit"] == whole["branch_limit"]
    assert narrowed["may_add_branch"] == whole["may_add_branch"]


def test_the_switcher_can_only_ever_narrow(client):
    """«يُضيِّق ولا يوسّع أبداً» — asserted on the function every scoped read now passes through.

    THE TWO FACTS A REQUEST NOW CARRIES. What this person MAY see, resolved from his token; and
    what he is currently LOOKING at, chosen in the sidebar. `narrow` returns the intersection, and
    every case below is a way that intersection could have been got wrong — each one silently, and
    each one a §12.4 breach rather than a bug an owner would ever notice.
    """
    from app.api.scope import REVOKED, narrow

    # A DISMISSED PERSON STAYS DISMISSED. `None` is falsy, so a bare truthiness test here would
    # hand him whatever he asked for — the exact widening the whole of و-1 exists to stop.
    assert narrow(REVOKED, "brn-jeddah") is REVOKED

    # NOTHING ASKED CHANGES NOTHING. «كل الفروع» means «whatever I may see», never «everything».
    assert narrow("brn-jeddah", "") == "brn-jeddah"
    assert narrow(frozenset({"a", "b"}), "") == frozenset({"a", "b"})
    assert narrow("", "") == ""

    # THE OWNER FILTERS. He could already read all of it; asking for less is a filter, not a grant.
    assert narrow("", "brn-jeddah") == "brn-jeddah"

    # A SUPERVISOR PICKS ONE OF HIS OWN — and gets exactly that one, not all four.
    assert narrow(frozenset({"a", "b"}), "a") == "a"

    # AND ASKING FOR SOMEBODY ELSE'S CHANGES NOTHING AT ALL. Not an error: a console can hold a
    # stale choice for innocent reasons — a branch closed, a scope changed since Tuesday — and a
    # refusal in the middle of an ordinary screen reads as an accusation for something he did not
    # do. He is answered with his own scope, which is the honest «I showed you what is yours».
    assert narrow("brn-jeddah", "brn-riyadh") == "brn-jeddah"
    assert narrow(frozenset({"a", "b"}), "z") == frozenset({"a", "b"})


# ── location: unset on the main branch, owner-set on any other, required from the second on ────
# THE RULE: the auto-created main branch is never asked to locate itself (a one-branch shop has
# no ambiguity to resolve — see create_branch's own note on why). The moment a SECOND branch is
# added, a location becomes required — a shop with two places and only one located is a shop
# whose admin map, and whose whatsapp-assistant branch-selection step, cannot tell them apart.

def test_a_branch_can_be_created_with_a_location(client):
    h = _headers("tnt_geo_create")
    r = client.post(BRANCHES, json={"name": "فرع الروضة", "lat": 24.71, "lng": 46.68, "city": "الرياض"},
                    headers=h)
    assert r.status_code == 201
    assert r.json()["lat"] == 24.71 and r.json()["lng"] == 46.68 and r.json()["city"] == "الرياض"


def test_the_auto_created_main_branch_alone_reports_its_location_as_unset(client):
    """No POST /branches call ever happens for the main branch — it exists the moment the shop is
    read at all (B.ensure_main). This is the one branch this rule never touches."""
    h = _headers("tnt_geo_unset")
    r = client.get(BRANCHES, headers=h).json()["branches"]
    assert r[0]["id"] == "brn-main"
    assert r[0]["lat"] == 0.0 and r[0]["lng"] == 0.0 and r[0]["city"] == ""


def test_a_second_branch_without_a_location_is_refused(client):
    h = _headers("tnt_geo_required")
    r = client.post(BRANCHES, json={"name": "فرع بلا موقع"}, headers=h)
    assert r.status_code == 400
    assert r.json()["error"] == "LOCATION_REQUIRED"


def test_a_second_branch_with_only_lat_and_not_lng_is_still_refused(client):
    h = _headers("tnt_geo_half")
    r = client.post(BRANCHES, json={"name": "فرع", "lat": 24.71}, headers=h)
    assert r.status_code == 400
    assert r.json()["error"] == "LOCATION_REQUIRED"


def test_a_branchs_location_can_be_set_later_by_patch(client):
    h = _headers("tnt_geo_patch")
    client.get(BRANCHES, headers=h)  # provisions brn-main
    r = client.patch(f"{BRANCHES}/brn-main", json={"lat": 21.54, "lng": 39.17, "city": "جدة"}, headers=h)
    assert r.status_code == 200
    assert r.json()["lat"] == 21.54 and r.json()["city"] == "جدة"


def test_an_out_of_range_coordinate_is_refused_not_silently_clamped(client):
    h = _headers("tnt_geo_bad")
    r = client.post(BRANCHES, json={"name": "فرع", "lat": 200, "lng": 0}, headers=h)
    assert r.status_code == 422


def test_platform_branch_locations_lists_only_located_active_branches_across_tenants(client):
    h1 = _headers("tnt_geo_a")
    h2 = _headers("tnt_geo_b")
    client.post(BRANCHES, json={"name": "محل أ", "lat": 24.0, "lng": 46.0, "city": "الرياض"}, headers=h1)
    # A SECOND, EXPLICITLY-ADDED branch can no longer be unlocated (see the section above) — the
    # unlocated row proving exclusion here is tnt_geo_b's own auto-created main branch instead,
    # provisioned by this one read, never posted.
    client.get(BRANCHES, headers=h2)

    admin = _headers("_platform", caps=("platform.operations",))
    r = client.get("/api/v1/platform/branches/locations", headers=admin)
    assert r.status_code == 200
    rows = r.json()["branches"]
    names = {b["name"] for b in rows}
    assert "محل أ" in names
    # tnt_geo_b's OWN unlocated main branch is excluded — proven by tenant, not by a name that
    # was never created: two tenants both auto-provision a main branch named the same thing
    # ("الفرع الرئيسي"), so asserting the NAME's absence would be trivially true even if this
    # tenant's own located branch leaked through under a different name.
    assert not any(b["tenant"] == "tnt_geo_b" for b in rows)


def test_platform_branch_locations_refuses_without_the_capability(client):
    h = _headers("tnt_geo_c", caps=("operations.manage",))
    r = client.get("/api/v1/platform/branches/locations", headers=h)
    assert r.status_code == 403


def test_platform_tenant_capacity_counts_this_tenants_branches_and_operators_only(client):
    h1 = _headers("tnt_cap_a")
    h2 = _headers("tnt_cap_b")
    # tnt_cap_a: the auto-provisioned main branch, plus one more explicitly added.
    client.get(BRANCHES, headers=h1)
    client.post(BRANCHES, json={"name": "فرع ثانٍ", "lat": 24.71, "lng": 46.68}, headers=h1)
    # tnt_cap_b: a different tenant entirely — must never leak into tnt_cap_a's count.
    client.get(BRANCHES, headers=h2)

    admin = _headers("_platform", caps=("platform.operations",))
    r = client.get("/api/v1/platform/tenants/tnt_cap_a/capacity", headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["branches"] == 2
    # GAUGE_DRIVER=null in tests (NullGauges) — always reports unlimited/unreachable, -1. A real
    # deployment runs GAUGE_DRIVER=http and gets the establishment's actual plan limit here, off
    # the same entitlements/check call guard_and_report already makes on every hire/branch-add.
    assert body["branches_limit"] == -1
    assert body["operators_limit"] == -1


def test_platform_tenant_capacity_refuses_without_the_capability(client):
    h = _headers("tnt_cap_c", caps=("operations.manage",))
    r = client.get("/api/v1/platform/tenants/tnt_cap_c/capacity", headers=h)
    assert r.status_code == 403


# ── /internal/operations/active-branches — whatsapp-assistant's branch-selection gate ────────────
def _internal_headers() -> dict:
    return {"X-Internal-Token": "t" * 40}


def test_active_branches_returns_only_open_branches_with_city(client):
    h = _headers("tnt_active_br")
    client.post(BRANCHES, json={"name": "فرع مغلق", "lat": 24.0, "lng": 46.0, "city": "الرياض"}, headers=h)
    rows = client.get(BRANCHES, headers=h).json()["branches"]
    closed_id = next(b["id"] for b in rows if b["name"] == "فرع مغلق")
    client.patch(f"{BRANCHES}/{closed_id}", json={"active": False}, headers=h)
    client.post(BRANCHES, json={"name": "فرع مفتوح", "lat": 21.5, "lng": 39.1, "city": "جدة"}, headers=h)

    r = client.post("/internal/operations/active-branches", json={"tenant": "tnt_active_br"},
                    headers=_internal_headers())
    assert r.status_code == 200
    rows = r.json()["branches"]
    names = {b["name"] for b in rows}
    assert "فرع مفتوح" in names
    assert "فرع مغلق" not in names
    opened = next(b for b in rows if b["name"] == "فرع مفتوح")
    assert opened["city"] == "جدة"
    assert "lat" not in opened and "active" not in opened


def test_active_branches_is_isolated_per_tenant(client):
    client.get(BRANCHES, headers=_headers("tnt_active_iso_a"))  # provisions its own main branch
    r = client.post("/internal/operations/active-branches", json={"tenant": "tnt_active_iso_b"},
                    headers=_internal_headers())
    names = {b["name"] for b in r.json()["branches"]}
    assert not any("iso_a" in n for n in names)


def test_active_branches_refuses_without_the_internal_token(client):
    r = client.post("/internal/operations/active-branches", json={"tenant": "tnt_active_br"})
    assert r.status_code in (401, 403)


# ── /internal/operations/branch-operators — bookings-assignment's candidate pool ─────────────────
def test_branch_operators_returns_only_active_people_at_that_branch(client):
    client.get(BRANCHES, headers=_headers("tnt_br_ops"))   # provisions brn-main
    hire = _hire(client, "tnt_br_ops", name="خالد", phone="0501111111", branch_id="brn-main")
    if hire.status_code != 201:
        pytest.skip("identity peer not wired in this test container — see test_hiring_creates_a_seat")
    op_id = hire.json()["id"]

    r = client.post("/internal/operations/branch-operators",
                    json={"tenant": "tnt_br_ops", "branch_id": "brn-main"}, headers=_internal_headers())
    assert r.status_code == 200
    ids = {o["id"] for o in r.json()["operators"]}
    assert op_id in ids

    # A DIFFERENT branch never sees him.
    r2 = client.post("/internal/operations/branch-operators",
                     json={"tenant": "tnt_br_ops", "branch_id": "brn-elsewhere"},
                     headers=_internal_headers())
    assert op_id not in {o["id"] for o in r2.json()["operators"]}


def test_branch_operators_is_isolated_per_tenant(client):
    """The SAME branch_id string ("brn-main" — every tenant's auto-created main branch shares it)
    in two different tenants must never mix their people — seeded directly into the store so this
    does not depend on the identity peer being wired (see the skip above)."""
    import asyncio

    from app.core.models import Operator
    from app.core.stores import OperatorStore

    store = client.app.state.container.datastore

    async def seed():
        await OperatorStore(store).save(Operator(
            id="op_iso_a", tenant="tnt_ops_iso_a", name="أحمد", branch_id="brn-main", active=True))

    asyncio.run(seed())

    r = client.post("/internal/operations/branch-operators",
                    json={"tenant": "tnt_ops_iso_b", "branch_id": "brn-main"},
                    headers=_internal_headers())
    assert r.status_code == 200
    assert "op_iso_a" not in {o["id"] for o in r.json()["operators"]}


# ── /internal/operations/customer-id-by-phone — bookings-assignment's real customer_id ───────────
def test_customer_id_by_phone_creates_then_reuses_the_same_customer(client):
    tenant = "tnt_cust_id"
    r1 = client.post("/internal/operations/customer-id-by-phone",
                     json={"tenant": tenant, "phone": "0509998888"}, headers=_internal_headers())
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["customer_id"]
    assert body1["subject_ref"]

    r2 = client.post("/internal/operations/customer-id-by-phone",
                     json={"tenant": tenant, "phone": "0509998888"}, headers=_internal_headers())
    assert r2.json()["customer_id"] == body1["customer_id"]


def test_customer_id_by_phone_never_leaks_the_phone_or_name_back(client):
    r = client.post("/internal/operations/customer-id-by-phone",
                    json={"tenant": "tnt_cust_id2", "phone": "0507776666"},
                    headers=_internal_headers())
    assert "phone" not in r.json() and "name" not in r.json()


def test_customer_id_by_phone_refuses_without_the_internal_token(client):
    r = client.post("/internal/operations/customer-id-by-phone",
                    json={"tenant": "tnt_cust_id", "phone": "0509998888"})
    assert r.status_code in (401, 403)


# ── closed_at, branch.updated's real diff, and the ops-mcp report routes ─────────────────────────

def test_closing_a_branch_stamps_closed_at_reopening_clears_it(client):
    h = _headers("tnt_closed_at")
    created = client.post(BRANCHES, json={"name": "فرع الاختبار", "lat": 24.71, "lng": 46.68},
                          headers=h)
    bid = created.json()["id"]

    closed = client.patch(f"{BRANCHES}/{bid}", json={"active": False}, headers=h)
    assert closed.json()["closed_at"] > 0

    reopened = client.patch(f"{BRANCHES}/{bid}", json={"active": True}, headers=h)
    assert reopened.json()["closed_at"] == 0


def test_branch_updated_audit_event_carries_a_real_before_after_diff(client, monkeypatch):
    """THE BUG THIS FIXES: this event used to carry NO metadata at all — a close, a reopen, a
    rename and a relocation were all one indistinguishable "branch.updated" line."""
    seen: list[dict] = []

    async def record(action, **kw):
        seen.append({"action": action, **kw})

    monkeypatch.setattr(client.app.state.auditor, "record", record)
    h = _headers("tnt_branch_diff")
    created = client.post(BRANCHES, json={"name": "الاسم القديم", "lat": 24.71, "lng": 46.68},
                          headers=h)
    bid = created.json()["id"]
    seen.clear()   # drop the create's own audit line, if any — only the update below matters

    client.patch(f"{BRANCHES}/{bid}", json={"name": "الاسم الجديد", "active": False}, headers=h)
    assert len(seen) == 1
    meta = seen[0]["metadata"]
    assert meta["name"] == {"from": "الاسم القديم", "to": "الاسم الجديد"}
    assert meta["active"] == {"from": True, "to": False}


def test_branch_updated_with_no_actual_change_carries_empty_metadata_not_a_stale_guess(client, monkeypatch):
    seen: list[dict] = []

    async def record(action, **kw):
        seen.append({"action": action, **kw})

    monkeypatch.setattr(client.app.state.auditor, "record", record)
    h = _headers("tnt_branch_nodiff")
    created = client.post(BRANCHES, json={"name": "فرع ثابت", "lat": 24.71, "lng": 46.68}, headers=h)
    bid = created.json()["id"]
    seen.clear()

    # Same name sent back — nothing actually changes.
    client.patch(f"{BRANCHES}/{bid}", json={"name": "فرع ثابت"}, headers=h)
    assert seen[0]["metadata"] == {}


def test_branches_full_refuses_without_the_internal_token(client):
    r = client.post("/internal/operations/branches-full", json={"tenant": "tnt_x"})
    assert r.status_code == 401


def test_branches_full_returns_every_field_including_closed_at_and_location(client):
    h = _headers("tnt_br_full")
    created = client.post(BRANCHES, json={"name": "فرع كامل", "lat": 24.71, "lng": 46.68,
                                          "city": "الرياض"}, headers=h)
    bid = created.json()["id"]
    client.patch(f"{BRANCHES}/{bid}", json={"active": False}, headers=h)

    r = client.post("/internal/operations/branches-full", json={"tenant": "tnt_br_full"},
                    headers=_internal_headers())
    assert r.status_code == 200, r.text
    row = next(b for b in r.json()["branches"] if b["id"] == bid)
    assert row["active"] is False
    assert row["closed_at"] > 0
    assert row["lat"] == 24.71 and row["city"] == "الرياض"
    assert row["created"] > 0


def test_operators_full_refuses_without_the_internal_token(client):
    r = client.post("/internal/operations/operators-full", json={"tenant": "tnt_x"})
    assert r.status_code == 401


def test_operators_full_returns_the_full_record(client):
    from app.core.models import OPERATORS, Operator
    import asyncio

    store = client.app.state.container.datastore

    async def seed():
        op = Operator(id="op_full_1", tenant="tnt_op_full", name="أحمد",
                     role="manager", branch_id="brn-main", active=True, created=100,
                     visible_all=True)
        await store.put(OPERATORS, f"tnt_op_full|op_full_1", op.__dict__.copy())

    asyncio.run(seed())
    r = client.post("/internal/operations/operators-full", json={"tenant": "tnt_op_full"},
                    headers=_internal_headers())
    assert r.status_code == 200, r.text
    row = r.json()["operators"][0]
    assert row["role"] == "manager"
    assert row["branch_id"] == "brn-main"
    assert row["visible_all"] is True
    assert row["created"] == 100


# ── ci/check_branch_scope.py: GET /whatsapp/connect must ask who is asking ─────────────────────
def test_a_branch_manager_cannot_read_another_branchs_whatsapp_status(client):
    """FOUND BY THE GATE. `branch_id` used to be taken from the query string and used as-is — a
    manager scoped to Jeddah could pass `?branch_id=brn-ryd` and read whether RIYADH's number is
    connected and able to send, the same widening §12.4 exists to stop everywhere else."""
    import asyncio

    from app.core import connect
    from app.core.models import Operator
    from app.core.shop_mode import PER_BRANCH, ModeStore
    from app.core.stores import OperatorStore

    tenant = "tnt_connect_scope"
    store = client.app.state.container.datastore

    async def seed():
        await ModeStore(store).set(tenant, PER_BRANCH, available=True)
        await OperatorStore(store).save(Operator(
            id="opr_jed_c", tenant=tenant, name="مدير جدة", role="manager",
            branch_id="brn-jed", person_id="u_jed_c"))
        await connect.ConnectionStore(store).record(connect.Attempt(
            tenant=tenant, state=connect.STATE_CONNECTED, branch_id="brn-jed"))
        await connect.ConnectionStore(store).record(connect.Attempt(
            tenant=tenant, state=connect.STATE_CONNECTED, branch_id="brn-ryd"))

    asyncio.run(seed())
    # `_headers_for` grants operations.manage/read, not billing.self — this route's own
    # capability — so mint a token for the same subject with the cap it actually needs.
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u_jed_c", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    h = {"Authorization": f"Bearer {tok}"}

    # HIS OWN BRANCH — the real, connected status.
    mine = client.get("/api/v1/whatsapp/connect", params={"branch_id": "brn-jed"}, headers=h)
    assert mine.status_code == 200, mine.text
    assert mine.json()["state"] == "connected" and mine.json()["branch_id"] == "brn-jed"

    # RIYADH — never Riyadh's real "connected" state, however it is asked for. The request falls
    # back to his own scope (no bare-tenant row seeded), so this reads as "لم تبدأ الربط بعد" —
    # never the branch he actually asked for and never a leak of its real status.
    theirs = client.get("/api/v1/whatsapp/connect", params={"branch_id": "brn-ryd"}, headers=h)
    assert theirs.status_code == 200, theirs.text
    assert theirs.json()["state"] != "connected"
    assert "brn-ryd" not in theirs.json().values()
