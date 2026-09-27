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

from app.core import branches
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"

KEK = "unit-test-kek-not-a-real-key"


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


def _auth(*caps: str, tenant: str = "") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    # `tenant`, never `tenant_id` — the claim name the platform reads. A route that needs one
    # answers 403 NO_TENANT without it, which reads exactly like a missing capability.
    tok = jwt.encode({"sub": "op1", "iss": ISS, "aud": AUD, "caps": list(caps),
                      **({"tenant": tenant} if tenant else {}),
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
    return _auth("platform.config")


@pytest.fixture
def reader_auth() -> dict:
    """Holds a capability, but not this one."""
    return _auth("reports.read")


# ── authorisation ─────────────────────────────────────────────────────────────
def test_config_needs_its_own_capability(client, reader_auth):
    assert client.get("/api/v1/operations/operator/config",
                      headers=reader_auth).status_code == 403


def test_unauthenticated_is_refused(client):
    assert client.get("/api/v1/operations/operator/config").status_code == 401


# ── policy ────────────────────────────────────────────────────────────────────
def test_a_deploy_time_knob_is_refused(client, operator_auth):
    """Wiring changed under a live request is a class of bug nobody can reproduce."""
    for key in ("DATASTORE_DRIVER", "SECRETS_KEK", "PII_SALT", "INTERNAL_SERVICE_TOKEN"):
        r = client.put("/api/v1/operations/operator/config",
                       json={"key": key, "value": "anything"}, headers=operator_auth)
        assert r.status_code == 400, f"{key} was accepted at runtime"


def test_the_config_view_never_carries_a_credential(client, operator_auth):
    view = client.get("/api/v1/operations/operator/config", headers=operator_auth).json()["config"]
    for banned in ("SECRETS_KEK", "INTERNAL_SERVICE_TOKEN", "PII_SALT", "DATASTORE_DSN"):
        assert banned not in view


def test_the_config_surface_offers_exactly_what_something_reads(client, operator_auth):
    """Three knobs, because exactly three are wired.

    A key enters RUNTIME_POLICY in the same change that wires the read — the retention horizon is
    read per tenant by core/retention.py on every sweep; the booking/visit master Flow ids are
    read (platform scope) by api/v1/connect.py's background provisioning task; the
    subscription-renewal master Flow id is read (also platform scope, but as a one-time
    idempotency check, never per shop) by api/v1/platform.py's explicit admin action. Everything
    else stays unavailable, which is honest: an advertised knob nothing consults reports a change
    that never happened, with an audit entry to prove it. Order is not the contract (a frozenset
    has none) — set equality is.

    `MASTER_RATING_FLOW_ID`/`MASTER_REPORT_FLOW_ID` REMOVED (2026-09-16) — see
    core/flows.py's own module docstring.
    """
    h = {"headers": operator_auth}
    assert set(client.get("/api/v1/operations/operator/config", **h).json()["config"]) == {
        "MASTER_BOOKING_FLOW_ID",
        "MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID", "RETENTION_CUSTOMER_YEARS"}
    r = client.put("/api/v1/operations/operator/config", json={"key": "RATELIMIT_MAX", "value": 250}, **h)
    assert r.status_code == 400, "an undeclared knob was accepted and would have been inert"


def test_a_shop_may_shorten_its_own_retention(client, operator_auth):
    """It is the controller of its customers' data — the horizon is its decision to tighten."""
    h = {"headers": operator_auth}
    r = client.put("/api/v1/operations/operator/config",
                   json={"key": "RETENTION_CUSTOMER_YEARS", "value": 2}, **h)
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/operations/operator/config", **h).json()["config"][
        "RETENTION_CUSTOMER_YEARS"] == 2


# ── the seat limit, at the door ────────────────────────────────────────────────────────────────
def test_the_employee_past_the_limit_is_refused_with_his_limit_named(client, monkeypatch):
    """A nightly sweep that finds sixteen employees on a plan of fifteen and does nothing is a
    limit that does not exist; one that deactivates somebody fires days after the mistake at a
    person who did not make it. So it is refused here, in the screen he is being added in.

    AND THE SENTENCE HAS TO SURVIVE THE ERROR HANDLER. The platform's handler strips an
    HTTPException's detail, so a raised refusal reaches the owner as a bare 402 and the only part
    that tells him what to do is thrown away. It is RETURNED as a response body instead.
    """
    from app.core import seats as S

    class Full:
        async def report(self, tenant, key, value):
            pass

        async def allows_one_more(self, tenant, key, current):
            return False, 15

    # THE CAPABILITY IS SWITCHED OFF IN PRODUCTION, and this test is about what happens
    # BEHIND the switch. Turning it on here rather than weakening the door keeps both facts
    # testable: the refusal has its own test below.
    monkeypatch.setattr(client.app.state.container_settings, "PIN_OPERATORS_ENABLED", True)
    monkeypatch.setattr(client.app.state.container, "gauges", Full())
    r = client.post("/api/v1/staff/operators",
                    json={"name": "موظف", "pin": "1234", "branch_id": "brn-main"},
                    headers=_auth("operations.manage", tenant="t1"))
    assert r.status_code == 402
    body = r.json()
    assert body["error"] == "SEAT_LIMIT"
    assert "15" in body["message"]
    assert S.SEATS == "staff.seats"


def test_a_created_employee_reports_the_new_total(client, monkeypatch):
    """The whole count, after the write. Before it, the number is a lie for as long as the write
    takes; as a delta, a failed report never heals."""
    seen = []

    class Counting:
        async def report(self, tenant, key, value):
            seen.append((key, value))

        async def allows_one_more(self, tenant, key, current):
            return True, 15

    # THE CAPABILITY IS SWITCHED OFF IN PRODUCTION, and this test is about what happens
    # BEHIND the switch. Turning it on here rather than weakening the door keeps both facts
    # testable: the refusal has its own test below.
    monkeypatch.setattr(client.app.state.container_settings, "PIN_OPERATORS_ENABLED", True)
    monkeypatch.setattr(client.app.state.container, "gauges", Counting())
    r = client.post("/api/v1/staff/operators",
                    json={"name": "موظف جديد", "pin": "4321", "branch_id": "brn-main"},
                    headers=_auth("operations.manage", tenant="t1"))
    assert r.status_code == 201, r.text
    assert seen and seen[-1][0] == "staff.seats"
    assert seen[-1][1] >= 1


def test_a_switched_off_pin_employee_is_refused_by_the_route_not_only_the_screen(client, monkeypatch):
    """«رمز على الجهاز» is built, wired and OFF. Hiding the button is not switching it off: a stale
    tab, a queued request or anybody reading our own API still reaches this route. The screen is
    told the same answer so that turning it back on is a flag, never a console release."""
    monkeypatch.setattr(client.app.state.container_settings, "PIN_OPERATORS_ENABLED", False)
    r = client.post("/api/v1/staff/operators",
                    json={"name": "موظف", "pin": "1234", "branch_id": "brn-main"},
                    headers=_auth("operations.manage", tenant="t1"))
    assert r.status_code == 409, r.text
    assert r.json()["error"] == "PIN_OPERATORS_OFF"

    listing = client.get("/api/v1/staff/operators",
                         headers=_auth("operations.read", tenant="t1"))
    assert listing.status_code == 200, listing.text
    assert listing.json()["pin_operators_enabled"] is False


# ── every operator now names a real branch ──────────────────────────────────────────────────────
def test_creating_an_operator_with_no_branch_is_a_clean_400_not_a_silent_unassigned(
        client, monkeypatch):
    """The model itself refuses a missing/empty branch_id (Field(min_length=1)) — this proves the
    ROUTE also refuses an unrecognised one, over the seat/audit lane it must never enter first."""
    monkeypatch.setattr(client.app.state.container_settings, "PIN_OPERATORS_ENABLED", True)
    r = client.post("/api/v1/staff/operators",
                    json={"name": "موظف", "pin": "1234", "branch_id": "brn-does-not-exist"},
                    headers=_auth("operations.manage", tenant="t_no_branch"))
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "BRANCH_REQUIRED"


def test_creating_an_operator_with_the_main_branch_id_succeeds(client, monkeypatch):
    """«brn-main» always resolves — every shop has it from signup — with no Branch row required."""
    monkeypatch.setattr(client.app.state.container_settings, "PIN_OPERATORS_ENABLED", True)
    r = client.post("/api/v1/staff/operators",
                    json={"name": "موظف", "pin": "1234", "branch_id": "brn-main"},
                    headers=_auth("operations.manage", tenant="t_main_branch"))
    assert r.status_code == 201, r.text
    assert r.json()["branch_id"] == "brn-main"


def test_updating_an_operator_to_an_empty_branch_is_refused(client, monkeypatch):
    """«كل الفروع» is no longer a state PATCH may put somebody back into."""
    fake = _Signup()
    monkeypatch.setattr(client.app.state.container, "signup", fake, raising=False)
    _hired(client, "t_unset", "u_unset", oid="opr_unset")

    r = client.patch("/api/v1/staff/operators/opr_unset", json={"branch_id": ""},
                     headers=_auth("operations.manage", tenant="t_unset"))
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "BRANCH_REQUIRED"


# ── our own subscribe path ─────────────────────────────────────────────────────────────────────
class FakePlans:
    def __init__(self, trial: int = 0, limits=None, amount: int | None = 9900):
        self.trial = trial
        self.subscribed = []
        # READABLE BY DEFAULT, and this used to be None — «could not read». Every test here was
        # therefore written in an outage, which is exactly the state the guard now refuses; the
        # default state of a test must be the normal one, and the outage must be asked for.
        # A REAL BASE ROW BY DEFAULT — an empty dict is not a plan at all, and `may_add` rightly
        # refuses it («apps need a base first»). What these tests buy is a subscription.
        self.plan_limits = {"messages.monthly": {"limit": "unlimited"}} if limits is None else limits
        self.held: list | None = []
        # A REAL, PAID PRICE BY DEFAULT — 99 SAR, same as every other app on the price list — so
        # the existing "no token, no plan" tests below keep exercising exactly what they always
        # did. A test of the FREE-plan path passes `amount=0` explicitly.
        self.amount = amount

    async def trial_days(self, plan_id):
        return self.trial

    async def limits(self, plan_id):
        return self.plan_limits

    async def amount_minor(self, plan_id):
        return self.amount

    async def subscriptions(self, tenant):
        return self.held

    async def subscribe(self, *, tenant, plan_id, interval="month", payment_token=""):
        # THE TOKEN IS RECORDED, because "did money change hands" is the question these tests now
        # exist to answer — a subscription that reached billing without one is a free plan.
        self.subscribed.append((tenant, plan_id, interval))
        self.tokens = getattr(self, "tokens", []) + [payment_token]
        return 201, {"id": "sub_1", "tenant": tenant, "plan_id": plan_id}

    async def cancel(self, *, tenant, sub_id, at_period_end=True):
        self.cancelled = getattr(self, "cancelled", []) + [(tenant, sub_id, at_period_end)]
        return True


class FakeConnections:
    def __init__(self, connected: bool):
        self._c = connected

    async def connected(self, tenant):
        return self._c


def _wire(client, *, connected: bool, trial: int = 0, limits=None, amount: int | None = 9900):
    plans = FakePlans(trial, limits, amount=amount)
    client.app.state.container.billing_plans = plans
    client.app.state.container.connections = FakeConnections(connected)
    return plans


def test_a_paid_subscription_without_whatsapp_goes_through_and_says_what_is_left(client,
                                                                                 monkeypatch):
    """THE GATE IS GONE, AND THE SENTENCE IS NOT. Connecting used to block the payment; it now
    follows it — see core/subscribe.py for why the toll was in the wrong place. What must survive
    is the telling: a silent success is how an owner discovers, a week later and from the absence
    of messages, that one step was left."""
    plans = _wire(client, connected=False, trial=0)
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_x", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201
    body = r.json()
    assert "ربط" in body["notice"] and "دقائق" in body["notice"]
    # AND IT REACHED BILLING. The whole point of the reversal is that the sale completes.
    assert plans.subscribed == [("t1", "plan_x", "month")]


# ── the three apps that ARE a WhatsApp message: refused outright, unconnected, before any money
# moves (the owner's own distinction, 2026-09-20 — see apps.py::REQUIRES_WHATSAPP_KEYS) ──────────
def test_campaigns_is_refused_unconnected_with_a_redirect_to_connect(client):
    plans = _wire(client, connected=False, trial=0,
                  limits={"feature.campaigns": {"limit": "unlimited"}})
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_campaigns",
                                                   "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 409
    body = r.json()
    assert body["error"] == "WHATSAPP_CONNECTION_REQUIRED"
    assert body["redirect_screen"] == "connect"
    assert "واتساب" in body["message"]
    assert plans.subscribed == [], "nothing may reach billing for an undeliverable app"


def test_rating_is_refused_unconnected(client):
    plans = _wire(client, connected=False, trial=0,
                  limits={"feature.rating": {"limit": "unlimited"}})
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_rating",
                                                   "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 409
    assert r.json()["error"] == "WHATSAPP_CONNECTION_REQUIRED"
    assert plans.subscribed == []


def test_the_assistant_itself_is_refused_unconnected(client):
    plans = _wire(client, connected=False, trial=0,
                  limits={"feature.whatsapp": {"limit": "unlimited"}})
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_whatsapp",
                                                   "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 409
    assert r.json()["error"] == "WHATSAPP_CONNECTION_REQUIRED"
    assert plans.subscribed == []


def test_a_free_trial_of_campaigns_is_still_refused_unconnected(client):
    """A free trial of something undeliverable proves nothing — refused just like a paid plan,
    unlike every OTHER app's trial (see test_a_trial_subscribes_without_any_connection below)."""
    plans = _wire(client, connected=False, trial=14,
                  limits={"feature.campaigns": {"limit": "unlimited"}})
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_campaigns"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 409
    assert plans.subscribed == []


def test_campaigns_subscribes_normally_once_connected(client):
    plans = _wire(client, connected=True, trial=0,
                  limits={"feature.campaigns": {"limit": "unlimited"}})
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_campaigns",
                                                   "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201, r.text
    assert r.json().get("notice", "") == ""
    assert plans.subscribed == [("t1", "plan_campaigns", "month")]


def test_a_bundle_granting_one_requiring_key_alongside_others_is_still_refused(client):
    """A plan whose limits carry BOTH a requiring key and a non-requiring one -- the requiring
    key alone is enough to refuse the whole plan, since it cannot be delivered either way."""
    plans = _wire(client, connected=False, trial=0,
                  limits={"feature.loyalty": {"limit": "unlimited"},
                          "feature.campaigns": {"limit": "unlimited"}})
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_bundle",
                                                   "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 409
    assert plans.subscribed == []


def test_already_holding_it_refuses_as_already_subscribed_not_connection_required(client):
    """The duplicate-purchase check runs BEFORE the connection check in this route -- a shop that
    already owns feature.campaigns and tries to buy it again gets ALREADY_SUBSCRIBED, the more
    specific and correct reason, even while unconnected."""
    plans = _wire(client, connected=False, trial=0,
                  limits={"feature.campaigns": {"limit": "unlimited"}})
    plans.held = [{"limits_snapshot": {"feature.campaigns": {"limit": "unlimited"}}}]
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_campaigns",
                                                   "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 409
    assert r.json()["error"] == "ALREADY_SUBSCRIBED"
    assert plans.subscribed == []


def test_a_plan_with_a_declared_key_at_limit_zero_is_not_treated_as_granting_it(client):
    """`limit: 0` is a declared DENY (granted_keys' own rule), not a grant -- a plan carrying
    feature.campaigns at 0 does not trigger the connection requirement for it."""
    plans = _wire(client, connected=False, trial=0,
                  limits={"messages.monthly": {"limit": "unlimited"},
                          "feature.campaigns": {"limit": 0}})
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_base_only",
                                                   "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201, r.text
    assert plans.subscribed == [("t1", "plan_base_only", "month")]


def test_an_unrelated_app_still_goes_through_unconnected_with_its_notice(client):
    """REGRESSION GUARD — the new rule touches only the three declared keys; every other app
    keeps the exact "pay now, connect later" behaviour this whole file otherwise tests."""
    plans = _wire(client, connected=False, trial=0,
                  limits={"feature.loyalty": {"limit": "unlimited"}})
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_loyalty",
                                                   "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201
    assert "ربط" in r.json()["notice"]
    assert plans.subscribed == [("t1", "plan_loyalty", "month")]


def test_a_connected_shop_is_told_nothing_extra(client, monkeypatch):
    """A notice with nothing owed is noise, and noise is what teaches people to skip notices."""
    _wire(client, connected=True, trial=0)
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_pro", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201
    assert "notice" not in r.json()


def test_a_trial_subscribes_without_any_connection(client, monkeypatch):
    """The trial is for TRYING. Gating the evaluation on a step whose purpose is only visible
    afterwards is how an evaluation ends."""
    plans = _wire(client, connected=False, trial=14)
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_basic"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201
    assert plans.subscribed == [("t1", "plan_basic", "month")]


def test_a_connected_shop_subscribes_to_a_paid_plan(client, monkeypatch):
    plans = _wire(client, connected=True, trial=0)
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_pro", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201


def test_the_interval_is_passed_through_rather_than_inferred(client, monkeypatch):
    """The plan's PRICE carries an interval but the SUBSCRIPTION takes its own — defaulting it
    here would repeat the bug that made a one-time pack renew every month."""
    # A PACK, because `once` is now refused on a recurring plan (ز-1) — and a pack is exactly the
    # row that is sold once. The limits say so: it carries no message meter, so it is not a base.
    plans = _wire(client, connected=True, trial=0, limits={"messages.extra": {"limit": 500}})
    _holding(client, plans, [{"limits_snapshot": {"messages.monthly": {"limit": "unlimited"}}}])
    client.post("/api/v1/subscription",
                json={"plan_id": "pack_500", "interval": "once", "payment_token": "tok_1"},
                headers=_auth("billing.self", tenant="t1"))
    assert plans.subscribed[-1][2] == "once"


def test_a_paid_plan_without_a_payment_token_is_refused(client, monkeypatch):
    """THE FREE-PLAN BUG, AS A TEST. With no gateway configured the screen let an owner walk
    between «الأساسية» and «الاحترافية» as often as he liked — every press writing «باقتك» over the
    last, and not one riyal moving. A press is not a payment."""
    plans = _wire(client, connected=True, trial=0)
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_pro"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 402
    assert r.json()["error"] == "PAYMENT_REQUIRED"
    assert plans.subscribed == [], "nothing may reach billing when nothing was paid"


def test_a_free_plan_subscribes_with_no_payment_token_at_all(client, monkeypatch):
    """جهات الاتصال (plans.json, amount: 0) — the free-plan bug's own fix, as a test. A plan
    whose RESOLVED price is 0 must go through with no token at all, same as a trial does; unlike a
    trial it is billed forever at nothing, so it is subscribed `once` rather than monthly (see
    subscription.py's own comment on that override) — this test also proves that override fires."""
    plans = _wire(client, connected=True, trial=0, amount=0,
                 limits={"feature.contacts": {"kind": "boolean", "limit": 1},
                        "plan.standalone": {"kind": "boolean", "limit": 1}})
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_free"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201, r.text
    assert plans.subscribed == [("t1", "plan_free", "once")]
    assert plans.tokens == [""], "no token was sent, and none was required"


def test_a_paid_plan_still_refuses_with_no_token_even_when_free_plans_exist(client, monkeypatch):
    """REGRESSION CHECK. The free-plan exemption must not have widened into "no plan needs a
    token any more" — an ordinary paid app is refused exactly as before."""
    plans = _wire(client, connected=True, trial=0, amount=9900)
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_pro"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 402
    assert r.json()["error"] == "PAYMENT_REQUIRED"
    assert plans.subscribed == []


def test_a_trial_still_needs_no_card(client, monkeypatch):
    """Otherwise the payment rule swallows the trial, and an evaluation that asks for a card is
    not an evaluation."""
    plans = _wire(client, connected=False, trial=14)
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_basic"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201 and plans.subscribed


def test_the_screen_can_ask_whether_paying_is_even_possible(client, monkeypatch):
    """ONE KEY IS THE WHOLE SWITCH — absent, the plans page apologises instead of selling; present,
    the card form appears. And the SECRET key never appears in this answer or any other."""
    r = client.get("/api/v1/subscription/payment", headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert "نعتذر" in body["message"]


def test_a_token_without_a_tenant_cannot_subscribe_anybody(client, monkeypatch):
    _wire(client, connected=True, trial=0)
    r = client.post("/api/v1/subscription", json={"plan_id": "plan_x", "payment_token": "tok_1"},
                    headers=_auth("billing.self"))
    assert r.status_code == 403


# ── «ما الذي أملكه»: one call, and every lock in the console drawn from it ─────────────────────
def _apps(client, owned=(), reachable=True):
    from app.core.apps import NullApps

    reader = NullApps(set(owned))
    reader.reachable = reachable
    client.app.state.container.apps = reader
    return reader


def test_the_owner_is_told_which_apps_he_owns(client):
    """THE DEFECT IN ONE LINE. Before this, a screen deciding whether to lock a paid surface had
    only the CAPABILITY to go on — and an owner holds every capability on every plan, so the lock
    never appeared for the one person who would have paid to remove it."""
    _apps(client, owned={"feature.loyalty"})
    r = client.get("/api/v1/subscription/apps", headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 200
    body = r.json()
    assert body["checked"] is True
    assert body["keys"] == ["feature.loyalty"]
    owned = {a["key"]: a["owned"] for a in body["apps"]}
    assert owned["feature.loyalty"] is True and owned["feature.campaigns"] is False


def test_every_app_arrives_with_a_sentence_the_screen_can_render(client):
    """A store that prints `feature.roles.custom` is a glossary, not a page somebody buys from."""
    _apps(client)
    body = client.get("/api/v1/subscription/apps",
                      headers=_auth("billing.self", tenant="t1")).json()
    assert body["apps"] and all(a["name"] and a["what"] for a in body["apps"])


def test_a_billing_outage_is_never_reported_as_not_bought(client):
    """The worst sentence in the product to show a paying shop — and it would be shown to all of
    them at once. `owned` is null, and the screen draws «تعذّر التحقق» with a retry."""
    _apps(client, owned={"feature.campaigns"}, reachable=False)
    body = client.get("/api/v1/subscription/apps",
                      headers=_auth("billing.self", tenant="t1")).json()
    assert body["checked"] is False
    assert all(a["owned"] is None for a in body["apps"])
    assert body["keys"] == [] and body["message"]


def test_it_answers_about_the_caller_s_own_establishment_only(client):
    """A reader that ignored the tenant would hand one shop another shop's purchases."""
    class _Seen:
        driver = "null"

        def __init__(self):
            self.asked = []

        async def held(self, tenant):
            self.asked.append(tenant)
            return set(), True

    seen = _Seen()
    client.app.state.container.apps = seen
    client.get("/api/v1/subscription/apps", headers=_auth("billing.self", tenant="shop_9"))
    assert seen.asked == ["shop_9"]


# ── self-healing an orphaned dependent app — a FEATURE, not a sweep (2026-09-11) ────────────────
def test_a_dependent_app_orphaned_by_any_cancellation_path_is_cancelled_on_read(client):
    """برنامج النقاط cancelled through no path this console owns (a direct API call, dunning
    elsewhere, a support action) — the very next read of this tenant's own apps must catch and
    cancel it itself, exactly as if the console's own cascade button had done it."""
    _apps(client, owned=set())  # neither تسجيل زيارة nor الحجوزات held
    plans = _wire(client, connected=True, trial=0)
    plans.held = [
        {"id": "sub_loyalty", "plan_id": "plan_loyalty", "status": "active",
         "cancel_at_period_end": False,
         "limits_snapshot": {"feature.loyalty": {"kind": "boolean", "limit": 1},
                             "plan.requires_any": {"kind": "list",
                                                   "list": ["feature.visit", "feature.bookings"]}}},
    ]
    r = client.get("/api/v1/subscription/apps", headers=_auth("billing.self", tenant="t_orphan"))
    assert r.status_code == 200
    assert plans.cancelled == [("t_orphan", "sub_loyalty", True)]


def test_a_dependent_app_with_its_prerequisite_still_held_is_left_alone(client):
    _apps(client, owned={"feature.visit"})
    plans = _wire(client, connected=True, trial=0)
    plans.held = [
        {"id": "sub_loyalty", "plan_id": "plan_loyalty", "status": "active",
         "cancel_at_period_end": False,
         "limits_snapshot": {"plan.requires_any": {"kind": "list",
                                                   "list": ["feature.visit", "feature.bookings"]}}},
    ]
    client.get("/api/v1/subscription/apps", headers=_auth("billing.self", tenant="t_ok"))
    assert getattr(plans, "cancelled", []) == []


def test_the_self_heal_never_fires_during_a_billing_outage(client):
    """`checked=False` means the held-keys read itself failed — cancelling off an untrustworthy
    answer would orphan-cancel a perfectly healthy subscription the moment billing hiccups."""
    _apps(client, owned=set(), reachable=False)
    plans = _wire(client, connected=True, trial=0)
    plans.held = [
        {"id": "sub_loyalty", "plan_id": "plan_loyalty", "status": "active",
         "cancel_at_period_end": False,
         "limits_snapshot": {"plan.requires_any": {"kind": "list", "list": ["feature.visit"]}}},
    ]
    client.get("/api/v1/subscription/apps", headers=_auth("billing.self", tenant="t_outage"))
    assert getattr(plans, "cancelled", []) == []


# ── the till, and `feature.api` ────────────────────────────────────────────────────────────────
def _till_body():
    # EVERY SALE NAMES ITS BRANCH. The field became mandatory once a register could no longer be
    # allowed to pile every branch's work into one heap (§12.2), so a payload without one is not a
    # payload any till can send — and a fixture that omitted it would be exercising a shape the
    # door refuses before any of this file's subjects run.
    return {"visits": [{"idempotency_key": "inv-1", "phone": "0500000001",
                        "branch_id": branches.MAIN,
                        "lines": [{"service_id": "svc_1", "qty": 1}]}]}


def test_a_shop_without_the_programmatic_link_cannot_stream_visits_from_a_till(client):
    """THE DEFECT. `feature.api` was sold from the first price list and checked by nothing — any
    shop on any plan could point a till at us. The guard passed because `Plans.tsx` names the key
    as a price-list LABEL and a mention counted as enforcement."""
    from app.core.licence import NOT_INCLUDED, NullApiLicence

    client.app.state.container.api_licence = NullApiLicence(False)
    try:
        r = client.post("/api/v1/till/visits", json=_till_body(),
                        headers=_auth("operations.record", tenant="t1"))
        assert r.status_code == 200
        assert r.json()["accepted"] == 0
        assert r.json()["message"] == NOT_INCLUDED
    finally:
        client.app.state.container.api_licence = NullApiLicence(True)


def test_an_unreachable_billing_never_stops_a_counter(client):
    """THE DELIBERATE DIFFERENCE FROM CAMPAIGNS, which fails closed. A fleet-wide billing hiccup
    that refused every till would stop every shop from recording its day at once."""
    from app.core.licence import NOT_INCLUDED, NullApiLicence

    client.app.state.container.api_licence = NullApiLicence(None)
    try:
        r = client.post("/api/v1/till/visits", json=_till_body(),
                        headers=_auth("operations.record", tenant="t1"))
        assert r.json().get("message") != NOT_INCLUDED
    finally:
        client.app.state.container.api_licence = NullApiLicence(True)


def test_one_unkeyable_sale_does_not_refuse_the_rest_of_the_batch(client):
    """THE DEFECT. A sale carrying none of (idempotency_key, invoice_id, occurred_at) cannot be
    told apart from a second sale on retry, so it is refused — correctly. But the whole POST was
    refused with it: `accepted: 0` for all fifty. A till whose driver omits the invoice number on
    cash sales lost every other sale in the same post, on every retry, silently.

    The refusal is per item, the rest lands, and `total` still counts what the till SENT so the
    partner can reconcile."""
    body = {"visits": [
        {"idempotency_key": "keyed-1", "phone": "0500000021", "branch_id": branches.MAIN,
         "lines": [{"service_id": "svc_1", "qty": 1}]},
        {"phone": "0500000022", "branch_id": branches.MAIN,
         "lines": [{"service_id": "svc_1", "qty": 1}]},
        {"invoice_id": "inv-77", "phone": "0500000023", "branch_id": branches.MAIN,
         "lines": [{"service_id": "svc_1", "qty": 1}]}]}
    r = client.post("/api/v1/till/visits", json=body,
                    headers=_auth("operations.record", tenant="t_batch_partial"))
    assert r.status_code == 200
    out = r.json()
    assert out["total"] == 3, out
    # ONE item carries the key refusal — not three. The other two reached the batch handler and
    # were judged on their own merits there (this fixture has no service catalogue, so they are
    # refused for a DIFFERENT reason), which is exactly the proof: they were forwarded.
    key_refusals = [x for x in out["results"] if "idempotency_key, invoice_id" in x["reason"]]
    assert len(key_refusals) == 1 and key_refusals[0]["index"] == 1
    assert len(out["results"]) == 3, out


def test_a_batch_of_nothing_but_unkeyable_sales_is_still_refused_whole(client):
    """The narrowing must not become a hole: when NOTHING in the post can be keyed there is
    nothing to accept, and the answer stays a refusal rather than an empty success."""
    body = {"visits": [{"phone": "0500000031", "branch_id": branches.MAIN,
                        "lines": [{"service_id": "svc_1", "qty": 1}]}]}
    r = client.post("/api/v1/till/visits", json=body,
                    headers=_auth("operations.record", tenant="t_batch_none"))
    out = r.json()
    assert out["accepted"] == 0 and out["total"] == 1
    assert out["results"][0]["status"] == "rejected"


def test_billing_never_stands_between_a_customer_and_what_he_earned(client):
    """ب-2 — AND THIS TEST USED TO ASSERT THE OPPOSITE, which is why it is worth naming.

    It was written to close a real hole: `feature.api` gates the machine link, only the VISITS
    route checked it, and a redemption IS a ledger write. Consistent reasoning, and wrong here —
    because the question that check asks billing is «is this establishment entitled today», and a
    shop whose subscription has lapsed is entitled to nothing. So the guard refused not only the
    shop that never bought the link but the shop that stopped paying, at the counter, holding
    points its customer earned by coming back.

    §9.9, verbatim: «أما قراءة الرصيد واستبداله فلا تُسأل عنها فوترةٌ أبداً — عميلٌ واقفٌ عند
    الصندوق يحمل نقاطاً وعده بها المحل ليس طرفاً في فاتورة المحل، واشتراكٌ منقطع لا يُصادِر ما
    استحقّه العميل.» `loyalty` applies it exactly: it guards only what GROWS the debt.

    So the assertions are inverted, deliberately: with billing saying a flat NO, the till must get
    as far as looking for the customer — «لا يوجد عميل بهذا الرقم» is the shop's own answer about
    its own data, and it is proof the licence never spoke.
    """
    from app.core.licence import NOT_INCLUDED, NullApiLicence

    client.app.state.container.api_licence = NullApiLicence(False)
    try:
        r = client.post("/api/v1/till/redeem",
                        json={"phone": "0500000041", "reward_id": "rw_1",
                                  "branch_id": branches.MAIN,
                              "idempotency_key": "k-1"},
                        headers=_auth("operations.record", tenant="t_nolink"))
        assert r.status_code == 200 and r.json().get("message") != NOT_INCLUDED

        r = client.post("/api/v1/till/offer/apply",
                        json={"phone": "0500000041", "visit_id": "vis_1"},
                        headers=_auth("operations.record", tenant="t_nolink"))
        assert r.status_code == 200 and r.json().get("reason") != NOT_INCLUDED

        # AND THE READ STAYS OPEN — it always was, and for the same reason as the two above.
        r = client.get("/api/v1/till/customer?phone=0500000041",
                       headers=_auth("operations.record", tenant="t_nolink"))
        assert r.status_code == 200 and r.json().get("message") != NOT_INCLUDED

        # WHAT THE LICENCE STILL REFUSES: the link itself. A shop that never bought «ربط برمجي»
        # must not stream its sales in through a machine, and nobody's earned balance is in that.
        r = client.post("/api/v1/till/visits",
                        json={"visits": [{"phone": "0500000041", "external_id": "x-1",
                                          "branch_id": branches.MAIN,
                                          "lines": [{"service_id": "svc_1", "qty": 1}]}]},
                        headers=_auth("operations.record", tenant="t_nolink"))
        assert r.status_code == 200 and r.json().get("message") == NOT_INCLUDED
    finally:
        client.app.state.container.api_licence = NullApiLicence(True)


def _holding(client, plans, rows):
    """What billing says this shop already holds — ONE read, carrying each row's own terms.

    IT REPLACED TWO. «has a base» was a `feature.base` entitlement flag and «already owns this
    app» was a five-key sweep — two reads of two different things that could disagree with each
    other and with the resolver. v0.16.7 answered the escalation with the billable list itself.
    """
    plans.held = rows
    return plans


def test_an_app_needs_no_base_any_more(client):
    """CONFIRMED FIX (2026-09-11) — الأساس was retired from plans.json (2026-09-10) but
    `may_add`'s own base-required gate was left in place, and since no plan row anywhere still
    carries `messages.monthly`, `has_base` could never be true again: every app without its own
    `plan.standalone` marker had become permanently unsellable. Caught here at the real route,
    not just in `test_may_add.py`'s own unit tests."""
    plans = _wire(client, connected=True, trial=0, limits=_APP_LIMITS)
    _holding(client, plans, [])
    r = client.post("/api/v1/subscription",
                    json={"plan_id": "plan_campaigns", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201
    assert plans.subscribed == [("t1", "plan_campaigns", "month")]


def test_the_same_app_is_not_sold_twice(client):
    plans = _wire(client, connected=True, trial=0, limits=_APP_LIMITS)
    _holding(client, plans, [{"limits_snapshot": _BASE_LIMITS},
                             {"limits_snapshot": _APP_LIMITS}])
    r = client.post("/api/v1/subscription",
                    json={"plan_id": "plan_campaigns", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 409
    assert plans.subscribed == []


def test_an_app_on_a_base_goes_through(client):
    plans = _wire(client, connected=True, trial=0, limits=_APP_LIMITS)
    _holding(client, plans, [{"limits_snapshot": _BASE_LIMITS},
                             {"limits_snapshot": {"feature.loyalty": {"limit": 1}}}])
    r = client.post("/api/v1/subscription",
                    json={"plan_id": "plan_campaigns", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201
    assert plans.subscribed == [("t1", "plan_campaigns", "month")]


# ── one base per shop, and an app bought once ─────────────────────────────────────────────────
_BASE_LIMITS = {"messages.monthly": {"kind": "counter", "limit": -1},
                "feature.campaigns": {"kind": "boolean", "limit": 0}}
_APP_LIMITS = {"feature.campaigns": {"kind": "boolean", "limit": 1}}


def test_a_billing_outage_refuses_the_purchase_and_takes_no_money(client):
    """ز-2 — AND THIS TEST ASSERTED THE OPPOSITE. The rules used to stand aside when they could
    not be decided, on the reasoning that refusing would stop a shop buying during an outage it
    did not cause. But the two mistakes are not the same size: failing open charges a card for a
    second base, recoverable only by noticing, explaining and refunding it; failing closed costs
    one press. He is told plainly that nothing was taken."""
    plans = _wire(client, connected=True, trial=0, limits=_APP_LIMITS)
    _holding(client, plans, None)     # None is «could not read», not «holds nothing»
    r = client.post("/api/v1/subscription",
                    json={"plan_id": "plan_campaigns", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 503, r.text
    assert plans.subscribed == [], "billing must never be asked when we could not check"
    assert "لم يُخصم" in r.json()["message"]


def test_the_apps_answer_carries_the_base_and_when_it_renews(client):
    """WHAT THE FLAG COULD NEVER SAY. «هل عنده أساس؟» used to be a `feature.base` entitlement
    boolean — true or false and nothing else. The subscription row carries the plan, the status and
    the period end, so «يتجدّد في …» becomes sayable: the first question an owner opens «الاشتراك»
    with, and one we had no way to answer until base-services v0.16.7."""
    plans = _wire(client, connected=True, trial=0, limits=_BASE_LIMITS)
    _holding(client, plans, [{"plan_id": "plan_base", "status": "active",
                              "current_period_end": 1_800_000_000,
                              "limits_snapshot": _BASE_LIMITS}])
    body = client.get("/api/v1/subscription/apps",
                      headers=_auth("billing.self", tenant="t1")).json()
    assert body["base"] == {"plan_id": "plan_base", "status": "active",
                            "renews_at": 1_800_000_000}


def test_a_shop_with_no_base_is_told_so_rather_than_left_guessing(client):
    plans = _wire(client, connected=True, trial=0, limits=_BASE_LIMITS)
    _holding(client, plans, [])
    body = client.get("/api/v1/subscription/apps",
                      headers=_auth("billing.self", tenant="t1")).json()
    assert body["base"] is None


def test_an_app_row_is_never_mistaken_for_the_base(client):
    """A shop holding only apps — impossible by the purchase rules, and the read must still not
    invent a base out of one."""
    plans = _wire(client, connected=True, trial=0, limits=_BASE_LIMITS)
    _holding(client, plans, [{"plan_id": "plan_campaigns", "status": "active",
                              "limits_snapshot": _APP_LIMITS}])
    body = client.get("/api/v1/subscription/apps",
                      headers=_auth("billing.self", tenant="t1")).json()
    assert body["base"] is None


# ── the library goes up at the moment of connection ───────────────────────────────────────────
class _Templates:
    async def list(self):
        return [{"name": "svc_visit_confirm", "language": "ar", "category": "UTILITY",
                 "body": "أهلاً {{1}}", "variables": ["name"], "examples": ["محمد"]}]


class _Exchange:
    """Meta's code-for-token step, answered without Meta."""

    def __init__(self, ok=True):
        self.ok = ok

    async def exchange(self, *, tenant, code, waba_id, phone_number_id, branch_id="", root_tenant=""):
        return self.ok, "" if self.ok else "refused"


def _connecting(client, monkeypatch, ok=True):
    from app.core import connect as connect_core
    from app.core.library import NullLibrary

    # THROUGH monkeypatch, SO IT IS RESTORED. Assigning the module attribute outright leaves every
    # later test in this file talking to a fake Meta — and a test that passes because of another
    # test's leftovers is worse than one that fails.
    monkeypatch.setattr(connect_core, "build_exchange", lambda s: _Exchange(ok))
    lib = NullLibrary()
    client.app.state.container.library = lib
    # A LIBRARY TO PUBLISH. The seed file is loaded at boot in production; this app is built
    # against a memory store, so the templates are put here rather than assumed.
    client.app.state.container.templates = _Templates()
    return lib


def test_connecting_publishes_the_shop_s_template_library(client, monkeypatch):
    """THE SEVERED WIRE, AND IT WAS THE WHOLE ONBOARDING. A shop finished Embedded Signup, was
    recorded `connected`, and owned no templates anywhere — somebody had to run a script by hand
    for each new establishment. Until they did, the send path had nothing approved to choose and
    refused every message with a sentence about a review nobody had asked for. Connected, green,
    and mute."""
    lib = _connecting(client, monkeypatch)
    r = client.post("/api/v1/whatsapp/connect",
                    json={"event": "FINISH", "code": "c1", "waba_id": "w1",
                          "phone_number_id": "p1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 200
    # THE BACKGROUND TASK RAN — TestClient drains them before returning, which is exactly why the
    # assertion is here and not on a mock of the scheduler.
    assert lib.registered, "the library must be registered for the shop that just connected"
    assert all(t == "t1" for t, _ in lib.registered)


def test_a_failed_connection_publishes_nothing(client, monkeypatch):
    """Meta refused the code: there is no account to register a library against, and doing it
    anyway would leave templates attached to a connection that does not exist."""
    lib = _connecting(client, monkeypatch, ok=False)
    client.post("/api/v1/whatsapp/connect",
                json={"event": "FINISH", "code": "bad", "waba_id": "w1",
                      "phone_number_id": "p1"},
                headers=_auth("billing.self", tenant="t1"))
    assert lib.registered == []


def test_a_cancelled_signup_publishes_nothing(client, monkeypatch):
    lib = _connecting(client, monkeypatch)
    client.post("/api/v1/whatsapp/connect",
                json={"event": "CANCEL", "step": "PHONE_NUMBER"},
                headers=_auth("billing.self", tenant="t1"))
    assert lib.registered == []


# ── stopping somebody must actually stop him (و-1) ─────────────────────────────────────────────
#
# The whole chain, because every link was sound alone: the row was written, the flag was read, the
# screen said «موقوف». What nothing did was take the membership away — and what nothing noticed
# was that an inactive row stopped narrowing him, so the shop's own dismissal handed him the chain.


class _Signup:
    """Stands in for the identity round trip: records the revoke, or refuses it."""

    def __init__(self, *, fails: bool = False) -> None:
        self.revoked: list[tuple[str, str]] = []
        self._fails = fails

    async def revoke(self, tenant: str, person_id: str) -> bool:
        from app.core.signup import SignupRefused

        if self._fails:
            raise SignupRefused("تعذّر إيقاف دخول الموظف. حاول بعد قليل.")
        self.revoked.append((tenant, person_id))
        return True


def _hired(client, tenant: str, person_id: str, *, oid: str) -> None:
    import asyncio

    from app.core.models import Operator
    from app.core.stores import OperatorStore

    asyncio.run(OperatorStore(client.app.state.container.datastore).save(Operator(
        id=oid, tenant=tenant, name="موظف", role="manager",
        branch_id="brn-jeddah", person_id=person_id, active=True)))


def test_stopping_an_employee_revokes_the_login_he_would_have_used(client, monkeypatch):
    fake = _Signup()
    monkeypatch.setattr(client.app.state.container, "signup", fake, raising=False)
    _hired(client, "t_stop", "u_stop", oid="opr_stop")

    r = client.patch("/api/v1/staff/operators/opr_stop", json={"active": False},
                     headers=_auth("operations.manage", tenant="t_stop"))
    assert r.status_code == 200, r.text
    assert fake.revoked == [("t_stop", "u_stop")], "the membership must be revoked, not just the row"
    # AND THE ROW NO LONGER CLAIMS A LIVE ACCOUNT.
    assert r.json().get("active") is False


def test_a_failed_revoke_refuses_rather_than_reporting_him_stopped(client, monkeypatch):
    """A row marked stopped beside a login that still works is the exact lie being fixed."""
    fake = _Signup(fails=True)
    monkeypatch.setattr(client.app.state.container, "signup", fake, raising=False)
    _hired(client, "t_fail", "u_fail", oid="opr_fail")

    r = client.patch("/api/v1/staff/operators/opr_fail", json={"active": False},
                     headers=_auth("operations.manage", tenant="t_fail"))
    assert r.status_code == 400
    assert r.json()["error"] == "NOT_STOPPED"

    import asyncio

    from app.core.stores import OperatorStore

    op = asyncio.run(OperatorStore(client.app.state.container.datastore).get("t_fail", "opr_fail"))
    assert op.active is True, "still active is at least TRUE — a false «stopped» is the defect"


def test_stopping_moves_his_identity_to_revoked_person_id_never_just_erases_it(client, monkeypatch):
    """A real gap found live by an end-to-end simulator run, not a hypothetical: `person_id` gets
    blanked on stop (the line above this one already proves that), but blanking it with nothing
    left in its place meant `branch_scope`'s own lookup could never again recognise this exact
    person as "this row, now stopped" — it matched no row at all, which reads as unassigned, which
    means the whole establishment. `revoked_person_id` is where that identity has to land instead,
    checked directly here at the route level (core/scope.py's own unit tests cover the read side)."""
    fake = _Signup()
    monkeypatch.setattr(client.app.state.container, "signup", fake, raising=False)
    _hired(client, "t_revoke_id", "u_revoke_id", oid="opr_revoke_id")

    r = client.patch("/api/v1/staff/operators/opr_revoke_id", json={"active": False},
                     headers=_auth("operations.manage", tenant="t_revoke_id"))
    assert r.status_code == 200, r.text

    import asyncio

    from app.core.stores import OperatorStore

    op = asyncio.run(
        OperatorStore(client.app.state.container.datastore).get("t_revoke_id", "opr_revoke_id"))
    assert op.person_id == "", "still blanked — the has_login/rehire-required rule is unchanged"
    assert op.revoked_person_id == "u_revoke_id", (
        "the identity a stale token might still carry must be preserved, not simply discarded")


def test_he_is_not_brought_back_by_flipping_the_flag(client, monkeypatch):
    """His membership is gone and only a password nobody here holds can mint another. A toggle
    would return a name to «فريقي» that consumes a seat and cannot open the app."""
    fake = _Signup()
    monkeypatch.setattr(client.app.state.container, "signup", fake, raising=False)
    _hired(client, "t_back", "u_back", oid="opr_back")
    client.patch("/api/v1/staff/operators/opr_back", json={"active": False},
                 headers=_auth("operations.manage", tenant="t_back"))

    r = client.patch("/api/v1/staff/operators/opr_back", json={"active": True},
                     headers=_auth("operations.manage", tenant="t_back"))
    assert r.status_code == 400
    assert r.json()["error"] == "REHIRE_REQUIRED"


def test_the_internal_scope_route_says_stopped_in_a_field_of_its_own(client, monkeypatch):
    """Every consumer reads `branch_id` as `str(... or "")`, and "" means the WHOLE establishment.
    So «stopped» cannot be said there — three services would have widened him at once."""
    fake = _Signup()
    monkeypatch.setattr(client.app.state.container, "signup", fake, raising=False)
    _hired(client, "t_wire", "u_wire", oid="opr_wire")
    client.patch("/api/v1/staff/operators/opr_wire", json={"active": False},
                 headers=_auth("operations.manage", tenant="t_wire"))

    import asyncio

    from app.core.models import Operator
    from app.core.stores import OperatorStore

    # He keeps a row — old visits still name him — but it is stopped, and person_id was cleared on
    # the way out, so the scope is asked about the subject his token still carries.
    op = asyncio.run(OperatorStore(client.app.state.container.datastore).get("t_wire", "opr_wire"))
    op.person_id = "u_wire"
    asyncio.run(OperatorStore(client.app.state.container.datastore).save(op))

    r = client.post("/internal/operations/branch-scope",
                    json={"tenant": "t_wire", "subject": "u_wire"},
                    headers={"X-Internal-Token": "t" * 40})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["revoked"] is True
    assert body["branch_id"] == "", "an empty branch must never be the carrier of «stopped»"


def test_the_internal_scope_route_is_isolated_per_tenant(client):
    """The SAME subject id, narrowed to «brn-jeddah» in one tenant, must answer «whole
    establishment» (empty) in a tenant that never hired him at all — the join is `(tenant,
    subject)`, and a route that forgot the tenant half would leak tenant A's narrowing onto
    every other tenant's token carrying the same subject."""
    _hired(client, "t_scope_iso_a", "u_scope_shared", oid="opr_scope_iso_a")

    r = client.post("/internal/operations/branch-scope",
                    json={"tenant": "t_scope_iso_b", "subject": "u_scope_shared"},
                    headers={"X-Internal-Token": "t" * 40})
    assert r.status_code == 200, r.text
    assert r.json()["branch_id"] == "", "tenant A's narrowing must not leak onto tenant B"


# ── an erasure must not fan out over a narrowed map (و-3) ──────────────────────────────────────
#
# The owner needs `compliance.manage` — the erase button travels on HIS token so the act is his —
# and the same capability grants DELETE on his data targets. Narrow the map once and every erasure
# afterwards closes COMPLETED over less than everything, while the customer is told he is gone.


class _Map:
    def __init__(self, missing: str = "") -> None:
        self.missing = missing
        self.asked: list[str] = []

    async def reassert_data_map(self, tenant: str) -> str:
        self.asked.append(tenant)
        return self.missing


def _customer(client, tenant: str, cid: str) -> None:
    import asyncio

    from app.core.models import Customer
    from app.core.stores import CustomerStore

    asyncio.run(CustomerStore(client.app.state.container.datastore).save(Customer(
        id=cid, tenant=tenant, name="عميل", phone="0500000001", subject_ref="sub_x")))


def test_an_erasure_reasserts_the_data_map_before_it_fans_out(client, monkeypatch):
    fake = _Map()
    monkeypatch.setattr(client.app.state.container, "signup", fake, raising=False)
    _customer(client, "t_map", "cus_map")

    client.post("/api/v1/field/customers/cus_map/erase",
                headers=_auth("operations.manage", tenant="t_map"))
    assert fake.asked == ["t_map"], "the map must be re-read, not trusted from signup day"


def test_an_incomplete_map_refuses_the_erasure_instead_of_closing_it(client, monkeypatch):
    """A false «تم» on an erasure is the worst sentence this product can say."""
    fake = _Map(missing="loyalty:points")
    monkeypatch.setattr(client.app.state.container, "signup", fake, raising=False)
    _customer(client, "t_gap", "cus_gap")

    r = client.post("/api/v1/field/customers/cus_gap/erase",
                    headers=_auth("operations.manage", tenant="t_gap"))
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "لم يبدأ" in body["reason"], "and he is told it did NOT happen"


def test_todays_customers_strip_is_narrowed_to_his_branch(client):
    """و-8: `public()` carries the name, the phone and `last_branch_id`. The strip returned the
    whole chain's, ten at a time, to anyone who opened the field screen — and the branch gate
    could not see it, because it exempts `branch_id` and this field is `last_branch_id`."""
    import asyncio

    from app.core.models import Customer, Operator
    from app.core.stores import CustomerStore, OperatorStore

    ds = client.app.state.container.datastore
    asyncio.run(OperatorStore(ds).save(Operator(
        id="opr_jed2", tenant="t_strip", name="مدير جدة", role="manager",
        branch_id="brn-jeddah", person_id="op1", active=True)))
    for cid, branch in (("c_jed", "brn-jeddah"), ("c_ryd", "brn-riyadh"), ("c_none", "")):
        asyncio.run(CustomerStore(ds).save(Customer(
            id=cid, tenant="t_strip", name=cid, phone=f"05000000{cid[-1]}",
            subject_ref=f"sub_{cid}", last_branch_id=branch)))

    r = client.get("/api/v1/field/customers/recent",
                   headers=_auth("operations.read", tenant="t_strip"))
    assert r.status_code == 200, r.text
    got = {c["id"] for c in r.json()["customers"]}
    assert "c_ryd" not in got, "another branch's customers, by name and phone"
    assert "c_jed" in got and "c_none" in got


# ── a name on a visit must be a name somebody proved (و-4) ─────────────────────────────────────


def _operator_with_pin(client, tenant: str, oid: str, pin: str, branch: str = "") -> None:
    import asyncio

    from app.api.v1.staff import _pin_hash
    from app.core.models import Operator
    from app.core.stores import OperatorStore

    op = Operator(id=oid, tenant=tenant, name="فنّي", role="operator",
                  branch_id=branch, active=True)
    op.pin_hash = _pin_hash("s" * 32, tenant, oid, pin)
    asyncio.run(OperatorStore(client.app.state.container.datastore).save(op))


def test_verify_pin_issues_a_ticket_and_not_only_a_name(client):
    _operator_with_pin(client, "t_tkt", "opr_t1", "4321")
    r = client.post("/api/v1/staff/operators/verify-pin",
                    json={"operator_id": "opr_t1", "pin": "4321"},
                    headers=_auth("operations.read", tenant="t_tkt"))
    assert r.status_code == 200, r.text
    assert r.json()["ticket"], "confirming who is saving and issuing nothing was the whole defect"


def test_a_ticket_proves_one_operator_and_not_another(client):
    """The signature covers the id, so a device that holds one man's ticket cannot file work
    against his colleague — which is how another BRANCH's numbers used to be reachable."""
    from app.core import operator_ticket as OT

    mine = OT.issue("s" * 32, "t_tkt", "opr_t1")
    assert OT.verifies("s" * 32, "t_tkt", "opr_t1", mine)
    assert not OT.verifies("s" * 32, "t_tkt", "opr_OTHER", mine)
    assert not OT.verifies("s" * 32, "t_OTHER", "opr_t1", mine)
    # AND IT EXPIRES. A tablet left on a counter stops being somebody's signature.
    stale = OT.issue("s" * 32, "t_tkt", "opr_t1", now=0, ttl=1)
    assert not OT.verifies("s" * 32, "t_tkt", "opr_t1", stale, now=10)


def test_an_unproven_operator_is_dropped_and_the_visit_still_records(client):
    """The visit is the product: losing it costs a customer, losing the attribution costs a column.
    What must never happen is the attribution being wrong — the branch is read off this field."""
    import asyncio

    from app.core.stores import ServiceStore

    _operator_with_pin(client, "t_drop", "opr_jed", "1111", branch="brn-jeddah")
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        __import__("app.core.models", fromlist=["Service"]).Service(
            id="svc_x", tenant="t_drop", name="غسيل", price_minor=1000)))

    r = client.post("/api/v1/field/visits",
                    json={"phone": "0501234599", "service_ids": ["svc_x"],
                          "operator_id": "opr_jed"},
                    headers=_auth("operations.record", tenant="t_drop"))
    assert r.status_code == 201, r.text
    assert r.json()["visit"]["operator_id"] == "", "a name nobody proved must not be written"
    assert r.json()["visit"]["branch_id"] == "", "and it must not carry his branch either"


def test_a_visit_queued_through_an_outage_keeps_its_operator(client):
    """أ-3 · THE SHOP WITH THE WORST CONNECTION LOSES THE MOST.

    The field screen holds a visit on the device when the network is gone and drains it when the
    signal returns — sometimes hours later. Checking the ticket against the clock AT ARRIVAL drops
    the operator off every one of those visits, silently, because a dropped attribution is not an
    error. What is checked is the moment being attributed, which the device now sends.
    """
    from app.core import operator_ticket as OT

    ticket = OT.issue("s" * 32, "t_q", "opr_q", now=1_000)
    took_it_at = 1_060                      # a minute into the window the PIN opened
    drained_at = 1_000 + 6 * 3_600          # six hours later, when the signal came back

    assert OT.verifies("s" * 32, "t_q", "opr_q", ticket, at=took_it_at, now=drained_at)
    # AND THE WINDOW IS STILL FIVE MINUTES OF WORK. Holding the ticket buys nothing but the same
    # five minutes, which have long passed: it cannot sign for what happened after them.
    assert not OT.verifies("s" * 32, "t_q", "opr_q", ticket, at=drained_at, now=drained_at)
    # Nor for anything before the PIN was typed.
    assert not OT.verifies("s" * 32, "t_q", "opr_q", ticket, at=900, now=drained_at)


def test_a_drained_visit_is_still_filed_against_the_man_who_did_the_work(client):
    """THE WHOLE CHAIN, at the door: PIN → ticket → an outage → the drain → the branch.

    Every link was sound alone and the value died between them. This is the one that proves the
    route passes the visit's own moment to the ticket check rather than the arrival clock — the
    difference between a shop with a bad connection keeping its branch numbers and losing them.
    """
    import asyncio
    import time

    from app.core import operator_ticket as OT
    from app.core.stores import ServiceStore

    _operator_with_pin(client, "t_late", "opr_late", "2222", branch="brn-riyadh")
    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        __import__("app.core.models", fromlist=["Service"]).Service(
            id="svc_l", tenant="t_late", name="غسيل", price_minor=1000)))

    took_it_at = int(time.time()) - 4 * 3_600           # four hours ago, in the pit, no signal
    ticket = OT.issue("s" * 32, "t_late", "opr_late", now=took_it_at - 30)

    r = client.post("/api/v1/field/visits",
                    json={"phone": "0501234597", "service_ids": ["svc_l"],
                          "operator_id": "opr_late", "operator_ticket": ticket,
                          "occurred_at": took_it_at},
                    headers=_auth("operations.record", tenant="t_late"))
    assert r.status_code == 201, r.text
    assert r.json()["visit"]["operator_id"] == "opr_late", (
        "checking the ticket against the ARRIVAL clock drops the operator off every visit the "
        "device held through an outage")
    assert r.json()["visit"]["branch_id"] == "brn-riyadh", "and the branch follows the man"


def test_the_field_door_records_when_the_visit_happened(client):
    """أ-3 · the till door has always accepted `occurred_at`; the field door — the only one with a
    queue behind it — did not, so a morning of visits was stamped with the reconnection."""
    import asyncio
    import time

    from app.core.stores import ServiceStore

    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        __import__("app.core.models", fromlist=["Service"]).Service(
            id="svc_q", tenant="t_when", name="غسيل", price_minor=1000)))

    took_it_at = int(time.time()) - 6 * 3_600
    r = client.post("/api/v1/field/visits",
                    json={"phone": "0501234598", "service_ids": ["svc_q"],
                          "occurred_at": took_it_at},
                    headers=_auth("operations.record", tenant="t_when"))
    assert r.status_code == 201, r.text
    assert r.json()["visit"]["occurred_at"] == took_it_at, (
        "the reminder is scheduled from this, and the confirmation is sent from it")


# ── "2× غسيل خارجي" recorded by hand, exactly like an integrated till would send it ────────────

def test_a_manual_quantity_prices_and_counts_like_the_till_path_does(client):
    import asyncio

    from app.core.models import Service
    from app.core.stores import ServiceStore

    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id="svc_wash_qty", tenant="t_qty", name="غسيل خارجي", price_minor=3000)))

    r = client.post("/api/v1/field/visits",
                    json={"phone": "0501234500", "service_ids": ["svc_wash_qty"],
                          "quantities": {"svc_wash_qty": 2}},
                    headers=_auth("operations.record", tenant="t_qty"))
    assert r.status_code == 201, r.text
    assert r.json()["visit"]["quantities"] == {"svc_wash_qty": 2}
    assert r.json()["visit"]["total_minor"] == 6000


def test_a_quantity_for_a_service_not_on_the_visit_is_silently_dropped(client):
    """Same filter `record_visit` already applies to `Visit.quantities` — a stray key for a
    service this visit does not actually hold must not survive onto the row."""
    import asyncio

    from app.core.models import Service
    from app.core.stores import ServiceStore

    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id="svc_wash_only", tenant="t_qty2", name="غسيل", price_minor=1000)))

    r = client.post("/api/v1/field/visits",
                    json={"phone": "0501234501", "service_ids": ["svc_wash_only"],
                          "quantities": {"svc_never_chosen": 5}},
                    headers=_auth("operations.record", tenant="t_qty2"))
    assert r.status_code == 201, r.text
    assert r.json()["visit"]["quantities"] == {}
    assert r.json()["visit"]["total_minor"] == 1000


def test_an_out_of_range_quantity_is_refused_before_any_visit_is_written(client):
    r = client.post("/api/v1/field/visits",
                    json={"phone": "0501234502", "service_ids": ["svc_x"],
                          "quantities": {"svc_x": 0}},
                    headers=_auth("operations.record", tenant="t_qty3"))
    assert r.status_code == 422


def test_a_negative_quantity_is_refused_too(client):
    r = client.post("/api/v1/field/visits",
                    json={"phone": "0501234503", "service_ids": ["svc_x"],
                          "quantities": {"svc_x": -3}},
                    headers=_auth("operations.record", tenant="t_qty4"))
    assert r.status_code == 422


# ── the interval is a word billing knows, and `once` is not for a recurring plan (ز-1) ─────────


def test_an_interval_billing_does_not_know_is_refused_here(client):
    """billing reads `_INTERVAL.get(interval, month)` — an unknown word is not refused, it becomes
    a MONTH. Nothing between the request and that line ever looked at the field, so «forever»,
    «day» and a typo all bought a monthly subscription nobody chose."""
    plans = _wire(client, connected=True, limits={"messages.monthly": {"limit": "unlimited"}})
    r = client.post("/api/v1/subscription",
                    json={"plan_id": "p_base", "interval": "forever", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t_int"))
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "BAD_INTERVAL"
    assert plans.subscribed == [], "and billing is never asked"


def test_a_recurring_plan_cannot_be_bought_once(client):
    """`once` sets the period end to the moment of purchase, so the plan never comes round to be
    charged again — one payment, and the shop keeps a base for ever."""
    plans = _wire(client, connected=True, limits={"messages.monthly": {"limit": "unlimited"}})
    r = client.post("/api/v1/subscription",
                    json={"plan_id": "p_base", "interval": "once", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t_once"))
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "BAD_INTERVAL"
    assert plans.subscribed == []


# ── operations-r2-006 (QA audit round 2, 2026-09-12): `ALREADY_SUBSCRIBED`/`BAD_INTERVAL` used to
# be the only refusals in this route with no audit row — every other refusal here already had one.
def test_an_already_subscribed_refusal_is_audited(client):
    from unittest.mock import AsyncMock

    # `messages.monthly` alone grants nothing in `granted_keys` (only `feature.*` keys count) —
    # a real app plan is needed to make `may_add` actually refuse the duplicate.
    plans = _wire(client, connected=True, limits={"feature.campaigns": {"limit": 1}})
    _holding(client, plans, [{"limits_snapshot": {"feature.campaigns": {"limit": 1}}}])
    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        r = client.post("/api/v1/subscription",
                        json={"plan_id": "p_campaigns", "interval": "month",
                              "payment_token": "tok_1"},
                        headers=_auth("billing.self", tenant="t_dupe"))
    finally:
        client.app.state.auditor.record = original
    assert r.status_code == 409, r.text
    assert r.json()["error"] == "ALREADY_SUBSCRIBED"
    actions = [c.args[0] for c in spy.await_args_list]
    assert "subscription.already_subscribed" in actions


def test_a_bad_interval_refusal_is_audited(client):
    from unittest.mock import AsyncMock

    _wire(client, connected=True, limits={"messages.monthly": {"limit": "unlimited"}})
    original = client.app.state.auditor.record
    spy = AsyncMock(side_effect=original)
    client.app.state.auditor.record = spy
    try:
        r = client.post("/api/v1/subscription",
                        json={"plan_id": "p_base", "interval": "forever", "payment_token": "tok_1"},
                        headers=_auth("billing.self", tenant="t_bad_int_audit"))
    finally:
        client.app.state.auditor.record = original
    assert r.status_code == 400, r.text
    assert r.json()["error"] == "BAD_INTERVAL"
    actions = [c.args[0] for c in spy.await_args_list]
    assert "subscription.bad_interval" in actions


def test_a_pack_is_still_bought_once(client):
    """The other half: a row that carries no message meter is not a base, and `once` is exactly
    how a capacity pack is sold. The guard must not close that door."""
    plans = _wire(client, connected=True, limits={"staff.seats": {"limit": 10}})
    # A pack is ADDED to a base, so the shop must already hold one — that rule is `may_add`'s and
    # is not what this test is about.
    _holding(client, plans, [{"limits_snapshot": {"messages.monthly": {"limit": "unlimited"}}}])
    r = client.post("/api/v1/subscription",
                    json={"plan_id": "p_seats", "interval": "once", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t_pack"))
    assert r.status_code < 400, r.text
    assert plans.subscribed and plans.subscribed[-1][2] == "once"


# ── GET /whatsapp/config — what the console needs to open the Embedded Signup popup ────────────
class _MetaConfig:
    def __init__(self, out):
        self._out = out

    async def read(self):
        return self._out


def test_meta_config_route_carries_no_secret_and_reports_configured(client, monkeypatch):
    from app.core import connect as connect_core
    monkeypatch.setattr(connect_core, "build_meta_config", lambda s: _MetaConfig(
        {"app_id": "123", "config_id": "456", "graph_version": "v26.0", "configured": True}))
    r = client.get("/api/v1/whatsapp/config", headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 200
    body = r.json()
    assert body == {"app_id": "123", "config_id": "456", "graph_version": "v26.0",
                    "configured": True}
    # NOT WHAT THIS ROUTE COULD LEAK IF IT READ THE WRONG FIELD — no key here is ever secret
    # (see connect.py's own docstring), but a stray "secret" surviving a copy-paste is exactly
    # the class of mistake this test would catch.
    assert "secret" not in str(body).lower()


def test_meta_config_route_reports_not_configured_never_a_broken_response(client, monkeypatch):
    from app.core import connect as connect_core
    monkeypatch.setattr(connect_core, "build_meta_config", lambda s: _MetaConfig(
        {"configured": False}))
    r = client.get("/api/v1/whatsapp/config", headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 200
    assert r.json() == {"app_id": "", "config_id": "", "graph_version": "", "configured": False}


def test_meta_config_route_requires_the_owners_own_capability(client):
    r = client.get("/api/v1/whatsapp/config")
    assert r.status_code in (401, 403)
