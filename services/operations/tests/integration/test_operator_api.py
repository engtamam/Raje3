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


def test_the_config_surface_offers_exactly_what_something_reads(client, operator_auth):
    """One knob, because exactly one is wired.

    A key enters RUNTIME_POLICY in the same change that wires the read — the retention horizon is
    read per tenant by core/retention.py on every sweep. Everything else stays unavailable, which
    is honest: an advertised knob nothing consults reports a change that never happened, with an
    audit entry to prove it.
    """
    h = {"headers": operator_auth}
    assert list(client.get("/api/v1/operator/config", **h).json()["config"]) == [
        "RETENTION_CUSTOMER_YEARS"]
    r = client.put("/api/v1/operator/config", json={"key": "RATELIMIT_MAX", "value": 250}, **h)
    assert r.status_code == 400, "an undeclared knob was accepted and would have been inert"


def test_a_shop_may_shorten_its_own_retention(client, operator_auth):
    """It is the controller of its customers' data — the horizon is its decision to tighten."""
    h = {"headers": operator_auth}
    r = client.put("/api/v1/operator/config",
                   json={"key": "RETENTION_CUSTOMER_YEARS", "value": 2}, **h)
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/operator/config", **h).json()["config"][
        "RETENTION_CUSTOMER_YEARS"] == 2


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
    def __init__(self, trial: int = 0, limits=None):
        self.trial = trial
        self.subscribed = []
        # READABLE BY DEFAULT, and this used to be None — «could not read». Every test here was
        # therefore written in an outage, which is exactly the state the guard now refuses; the
        # default state of a test must be the normal one, and the outage must be asked for.
        # A REAL BASE ROW BY DEFAULT — an empty dict is not a plan at all, and `may_add` rightly
        # refuses it («apps need a base first»). What these tests buy is a subscription.
        self.plan_limits = {"messages.monthly": {"limit": "unlimited"}} if limits is None else limits
        self.held: list | None = []

    async def trial_days(self, plan_id):
        return self.trial

    async def limits(self, plan_id):
        return self.plan_limits

    async def subscriptions(self, tenant):
        return self.held

    async def subscribe(self, *, tenant, plan_id, interval="month", payment_token=""):
        # THE TOKEN IS RECORDED, because "did money change hands" is the question these tests now
        # exist to answer — a subscription that reached billing without one is a free plan.
        self.subscribed.append((tenant, plan_id, interval))
        self.tokens = getattr(self, "tokens", []) + [payment_token]
        return 201, {"id": "sub_1", "tenant": tenant, "plan_id": plan_id}


class FakeConnections:
    def __init__(self, connected: bool):
        self._c = connected

    async def connected(self, tenant):
        return self._c


def _wire(client, *, connected: bool, trial: int = 0, limits=None):
    plans = FakePlans(trial, limits)
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


def test_a_second_base_is_refused_before_billing_is_touched(client):
    """NOT ABOUT DOUBLE CHARGING. Entitlements merge and numbers SUM, so two bases make
    `messages.monthly` -1 + -1 = -2 — «unlimited» becomes a number that means nothing, and the
    meter that catches our own runaway loop is gone."""
    plans = _wire(client, connected=True, trial=0, limits=_BASE_LIMITS)
    _holding(client, plans, [{"limits_snapshot": _BASE_LIMITS}])
    r = client.post("/api/v1/subscription",
                    json={"plan_id": "plan_base", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 409
    assert r.json()["message"]
    assert plans.subscribed == [], "nothing may reach billing when the pair is impossible"


def test_an_app_without_a_base_is_refused(client):
    plans = _wire(client, connected=True, trial=0, limits=_APP_LIMITS)
    _holding(client, plans, [])
    r = client.post("/api/v1/subscription",
                    json={"plan_id": "plan_campaigns", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 409 and "الأساس" in r.json()["message"]
    assert plans.subscribed == []


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

    async def exchange(self, *, tenant, code, waba_id, phone_number_id):
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


# ── د-14 · the approval, across our door ───────────────────────────────────────────────────────


def test_the_till_door_carries_the_approval_in_both_directions(client):
    """THE OTHER HALF OF THE CHAIN. loyalty refuses a reward above the shop's threshold without a
    manager's name — and this door had no field to carry one, and stripped the flag saying which
    rewards need it out of `/till/customer`. So an integrated shop was offered every affordable
    reward as available and could not satisfy the refusal from any request it was able to make.

    Asserted at BOTH ends: the flag the cashier's screen reads, and the name the ledger records.
    """
    seen: dict = {}

    class _Desk:
        configured = True

        async def balance(self, **kw):
            return {"has_programme": True, "points": 400, "to_next_reward": 0,
                    "manager_threshold": 100,
                    "rewards": [{"id": "rw_big", "name": "خصم كبير", "cost": 150,
                                 "needs_approval": True},
                                {"id": "rw_small", "name": "خصم صغير", "cost": 20,
                                 "needs_approval": False}]}

        async def redeem(self, **kw):
            seen.update(kw)
            return {"transaction_ref": "rdm_1", "balance": 250}

    saved = client.app.state.container.loyalty_desk
    client.app.state.container.loyalty_desk = _Desk()
    try:
        h = _auth("operations.record", tenant="t_appr")
        # A REAL CUSTOMER FIRST — the read answers `found: False` for a stranger, and a test that
        # asserts on that answer proves nothing about the projection below it.
        client.post("/api/v1/till/visits", headers=h, json={"visits": [
            {"phone": "0500000051", "invoice_id": "INV-APPR", "branch_id": branches.MAIN,
             "lines": [{"product_id": "P-1", "name": "غسيل", "qty": 1, "amount_minor": 5000}]}]})
        got = client.get("/api/v1/till/customer?phone=0500000051", headers=h).json()
        assert got.get("found") is True, got
        assert got["manager_threshold"] == 100, got
        flags = {r["id"]: r["needs_approval"] for r in got["rewards"]}
        assert flags == {"rw_big": True, "rw_small": False}, flags

        r = client.post("/api/v1/till/redeem",
                        json={"phone": "0500000051", "reward_id": "rw_big",
                              "branch_id": branches.MAIN,
                              "idempotency_key": "k-appr", "approved_by": "خالد المدير"},
                        headers=h)
        assert r.status_code == 200, r.text
        assert seen.get("approved_by") == "خالد المدير", seen
    finally:
        client.app.state.container.loyalty_desk = saved
