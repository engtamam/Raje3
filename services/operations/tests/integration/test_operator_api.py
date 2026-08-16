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

    monkeypatch.setattr(client.app.state.container, "gauges", Full())
    r = client.post("/api/v1/staff/operators",
                    json={"name": "موظف", "pin": "1234"},
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

    monkeypatch.setattr(client.app.state.container, "gauges", Counting())
    r = client.post("/api/v1/staff/operators",
                    json={"name": "موظف جديد", "pin": "4321"},
                    headers=_auth("operations.manage", tenant="t1"))
    assert r.status_code == 201, r.text
    assert seen and seen[-1][0] == "staff.seats"
    assert seen[-1][1] >= 1


# ── our own subscribe path ─────────────────────────────────────────────────────────────────────
class FakePlans:
    def __init__(self, trial: int = 0, limits=None):
        self.trial = trial
        self.subscribed = []
        # None is «could not read», which makes the base/duplicate rules stand aside — the state
        # most of these tests are in, and the one they were written under.
        self.plan_limits = limits
        self.held: list | None = None

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
    plans = _wire(client, connected=True, trial=0)
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
    return {"visits": [{"idempotency_key": "inv-1", "phone": "0500000001",
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
        {"idempotency_key": "keyed-1", "phone": "0500000021",
         "lines": [{"service_id": "svc_1", "qty": 1}]},
        {"phone": "0500000022", "lines": [{"service_id": "svc_1", "qty": 1}]},
        {"invoice_id": "inv-77", "phone": "0500000023",
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
    body = {"visits": [{"phone": "0500000031", "lines": [{"service_id": "svc_1", "qty": 1}]}]}
    r = client.post("/api/v1/till/visits", json=body,
                    headers=_auth("operations.record", tenant="t_batch_none"))
    out = r.json()
    assert out["accepted"] == 0 and out["total"] == 1
    assert out["results"][0]["status"] == "rejected"


def test_a_shop_without_the_link_cannot_spend_points_or_offers_from_a_till(client):
    """THE DEFECT. `feature.api` gates the machine link, and only the VISITS route checked it. A
    shop whose subscription excludes «ربط برمجي» had its visits refused and its REDEMPTIONS
    accepted: the loyalty ledger was debited and a customer receipt went out on a channel nobody
    was billed for. The licence file's own justification for exempting a machine — that it «only
    READS» — does not reach a ledger write."""
    from app.core.licence import NOT_INCLUDED, NullApiLicence

    client.app.state.container.api_licence = NullApiLicence(False)
    try:
        r = client.post("/api/v1/till/redeem",
                        json={"phone": "0500000041", "reward_id": "rw_1",
                              "idempotency_key": "k-1"},
                        headers=_auth("operations.record", tenant="t_nolink"))
        assert r.status_code == 200 and r.json()["message"] == NOT_INCLUDED

        r = client.post("/api/v1/till/offer/apply",
                        json={"phone": "0500000041", "visit_id": "vis_1"},
                        headers=_auth("operations.record", tenant="t_nolink"))
        assert r.status_code == 200 and r.json()["reason"] == NOT_INCLUDED

        # AND THE READ STAYS OPEN — it is the one the exemption was written for.
        r = client.get("/api/v1/till/customer?phone=0500000041",
                       headers=_auth("operations.record", tenant="t_nolink"))
        assert r.status_code == 200 and r.json().get("message") != NOT_INCLUDED
    finally:
        client.app.state.container.api_licence = NullApiLicence(True)


# ── one base per shop, and an app bought once ─────────────────────────────────────────────────
_BASE_LIMITS = {"messages.monthly": {"kind": "counter", "limit": -1},
                "feature.campaigns": {"kind": "boolean", "limit": 0}}
_APP_LIMITS = {"feature.campaigns": {"kind": "boolean", "limit": 1}}


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


def test_a_billing_outage_does_not_block_a_legitimate_purchase(client):
    """THE RULES STAND ASIDE WHEN THEY CANNOT BE DECIDED. Refusing on an unreadable answer would
    stop a shop buying during an outage it did not cause; the entitlement gates in the services
    still hold whatever happens here."""
    plans = _wire(client, connected=True, trial=0, limits=_APP_LIMITS)
    _holding(client, plans, None)     # None is «could not read», not «holds nothing»
    r = client.post("/api/v1/subscription",
                    json={"plan_id": "plan_campaigns", "payment_token": "tok_1"},
                    headers=_auth("billing.self", tenant="t1"))
    assert r.status_code == 201 and plans.subscribed


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
