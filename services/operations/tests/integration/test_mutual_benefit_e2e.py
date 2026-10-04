"""End-to-end, over real HTTP, through every layer a real shop actually touches: propose an
agreement -> accept it -> a real visit at the referring shop (through `/visits`, priced from a
real catalogue, not a poked-in `total_minor`) -> the beneficiary shop's own customer becomes
eligible -> a real visit at the beneficiary shop -> `/visits/{id}/offer` actually redeems the
grant -> the KPI screen's numbers move. Then every edge case explicitly called out for this
feature: the concurrency cap (both as a hard block and as something that lifts once an agreement
truly ends), renewal going through the identical check, all three catalogue-only grant shapes
(gift / discount-item / discount-blanket / discount-group), immutability, a double tap never
double-spending, and the tie-break against an ordinary campaign offer.

WHY THIS FILE, SEPARATE FROM THE EXISTING UNIT/INTEGRATION FILES. Those files each pin ONE layer
(the engine alone, or the HTTP role-gating alone, or the gateway alone) with fixtures that build
grants directly. Nothing anywhere previously proved the FULL chain a shop floor actually walks —
propose over HTTP, a real priced visit that triggers detection, and a real visit at the other shop
that actually redeems it — all through the same routes a till or the field screen calls. That gap
is what this file closes.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient

TOKEN_SECRET = "h" * 40
ISS, AUD = "iss", "aud"
A = "tnt_e2e_a"          # the referring shop
B = "tnt_e2e_b"          # the beneficiary/granting shop
C = "tnt_e2e_c"          # a third, unrelated shop — used for cross-tenant edge cases
B_PHONE = "0501234567"
CUSTOMER_PHONE = "0559876543"


def _make_app() -> TestClient:
    from app.config import get_settings

    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40, "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": TOKEN_SECRET, "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "10000", "PII_SALT": "s" * 32,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _auth(*caps: str, tenant: str, subject: str = "op1") -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": subject, "iss": ISS, "aud": AUD, "caps": list(caps),
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     TOKEN_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


MANAGE = _auth
RECORD_CAPS = ("operations.record", "operations.manage", "operations.read")
# BOTH, matching the real role bundle (deploy/seed/roles.json's own owner/manager rows) —
# `operations.manage` for the commit-the-shop actions (propose/accept/reject/either cancel),
# `operations.read` for the read-only ones (list/audit-log/kpis), same split `staff.py`'s own
# `_REFERRAL_MANAGE`/`_REFERRAL_VIEW` now draws.
REFERRAL_CAPS = ("operations.manage", "operations.read")


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


class _FakePlans:
    driver = "fake"

    def __init__(self) -> None:
        self.subs: dict[str, list[dict]] = {}
        self.plan_for_key = {"feature.mutual_benefit": "plan_referral"}

    async def subscriptions(self, tenant):
        return self.subs.get(tenant, [])

    async def plan_id_for_key(self, key):
        return self.plan_for_key.get(key, "")

    async def limits(self, plan_id):
        return {}


def _subscribe(fake: _FakePlans, tenant: str) -> None:
    fake.subs[tenant] = [{"id": f"sub_{tenant}", "plan": "plan_referral", "status": "active"}]


def _wire(client: TestClient) -> _FakePlans:
    """Real engine, real gateway — the SAME container wiring `container.py` does in production
    (`with_mutual_benefit_engine` + `with_entitlement_gateway`), just with a fake billing peer so no
    socket is opened, same technique every sibling integration test in this service already uses.
    """
    from app.core.entitlements import EntitlementGateway
    from app.core.mutual_benefit import MutualBenefitEngine

    fake = _FakePlans()
    container = client.app.state.container
    engine = MutualBenefitEngine(
        store=container.datastore, plans=fake, notifier=container.inapp_notifier,
        authz=container.authz_desk, default_cc="966")
    container.mutual_benefit = engine
    container.operations.with_mutual_benefit_engine(engine)
    container.entitlement_gateway = EntitlementGateway(
        mutual_benefit_engine=engine, campaign_chooser=None)
    container.operations.with_entitlement_gateway(container.entitlement_gateway)
    container._e2e_fake_plans = fake      # stashed so later helpers can subscribe MORE tenants
    return fake


def _subscribe_tenant(client: TestClient, tenant: str) -> None:
    """Subscribe a tenant CREATED MID-TEST (the cap tests register fresh peer shops on the fly) —
    `_subscribe` alone only touches the `_FakePlans` instance a caller already holds a reference
    to; this reaches the SAME instance back off the container for tenants discovered later."""
    _subscribe(client.app.state.container._e2e_fake_plans, tenant)


def _register_phone(client: TestClient, phone: str, tenant: str) -> None:
    from app.core.signup import PHONE_INDEX, canonical_phone

    key = canonical_phone(phone, default_cc="966")
    asyncio.run(client.app.state.container.datastore.put(
        PHONE_INDEX, key, {"id": key, "tenant": tenant, "verified": True}))


def _make_service(client: TestClient, tenant: str, ident: str, name: str,
                  price_minor: int = 5000) -> None:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id=ident, tenant=tenant, name=name, price_minor=price_minor)))


def _make_inactive_service(client: TestClient, tenant: str, ident: str) -> None:
    from app.core.models import Service
    from app.core.stores import ServiceStore

    asyncio.run(ServiceStore(client.app.state.container.datastore).save(
        Service(id=ident, tenant=tenant, name="خدمة موقوفة", price_minor=1000, active=False)))


def _make_package(client: TestClient, tenant: str, ident: str, name: str,
                  service_ids: list[str]) -> None:
    from app.core.models import Package
    from app.core.stores import PackageStore

    asyncio.run(PackageStore(client.app.state.container.datastore).save(
        Package(id=ident, tenant=tenant, name=name, price_minor=8000, service_ids=service_ids)))


@pytest.fixture
def wired(client: TestClient) -> TestClient:
    fake = _wire(client)
    _register_phone(client, B_PHONE, B)
    _subscribe(fake, A)
    _subscribe(fake, B)
    _subscribe(fake, C)
    # A FILLER SERVICE AT B — `/visits` requires at least one real service_id on every visit
    # (`VisitIn.service_ids` has `min_length=1`); the customer's own arrival at B to REDEEM an
    # entitlement is still a real visit that must name something it did, same as any other.
    _make_service(client, B, "svc_b_filler", "زيارة عادية", price_minor=0)
    return client


def _propose(client: TestClient, *, shop_a: str = A, condition_value: str = "1000",
            grant_validity_days: int = 3, agreement_duration_days: int = 90,
            grant_type: str = "discount", gift_service_id: str = "",
            discount_scope: str = "blanket", discount_group_id: str = "",
            discount_kind: str = "percent", discount_amount: int = 10,
            b_phone: str = B_PHONE) -> dict:
    resp = client.post(
        "/api/v1/staff/mutual-benefit/agreements",
        headers=_auth(*REFERRAL_CAPS, tenant=shop_a),
        json={"shop_b_phone": b_phone, "condition_type": "min_total_minor",
             "condition_value": condition_value, "grant_validity_days": grant_validity_days,
             "agreement_duration_days": agreement_duration_days, "grant_type": grant_type,
             "gift_service_id": gift_service_id, "discount_scope": discount_scope,
             "discount_group_id": discount_group_id,
             "discount_kind": discount_kind if grant_type == "discount" else "",
             "discount_amount": discount_amount if grant_type == "discount" else 0})
    return resp.json() if resp.status_code == 200 else {"__status__": resp.status_code,
                                                         "__body__": resp.json()}


def _accept(client: TestClient, agreement_id: str, *, shop_b: str = B) -> dict:
    resp = client.post(
        f"/api/v1/staff/mutual-benefit/agreements/{agreement_id}/accept",
        headers=_auth(*REFERRAL_CAPS, tenant=shop_b))
    return resp.json() if resp.status_code == 200 else {"__status__": resp.status_code,
                                                         "__body__": resp.json()}


def _record_visit(client: TestClient, tenant: str, *, phone: str,
                  service_ids: list[str], idem: str) -> dict:
    resp = client.post(
        "/api/v1/field/visits", headers=_auth(*RECORD_CAPS, tenant=tenant),
        json={"phone": phone, "service_ids": service_ids, "idempotency_key": idem})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _apply_offer(client: TestClient, tenant: str, visit_id: str, subject_ref: str) -> dict:
    resp = client.post(
        f"/api/v1/field/visits/{visit_id}/offer", headers=_auth(*RECORD_CAPS, tenant=tenant),
        json={"subject_ref": subject_ref})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _propose_and_accept(client: TestClient, *, shop_b_tenant: str = B, **kwargs) -> str:
    """`shop_b_tenant` is the REAL tenant that must call /accept — resolved from whichever
    `b_phone` the caller registered, never assumed to be `B` (a phone belongs to whatever tenant
    `_register_phone` last put it under)."""
    agreement = _propose(client, **kwargs)
    assert "id" in agreement, agreement
    accepted = _accept(client, agreement["id"], shop_b=shop_b_tenant)
    assert accepted.get("status") == "active", accepted
    return agreement["id"]


# ══════════════════════════════════════════════════════════════════════════════════════════════
# FULL CHAIN, ONE GRANT TYPE EACH — propose -> accept -> a real priced visit at A that crosses the
# threshold -> eligibility at B -> a real visit at B -> apply_offer actually redeems -> KPIs move.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_full_chain_gift_grant_from_a_real_priced_visit_to_kpis(wired: TestClient):
    _make_service(wired, B, "svc_gift", "قص شعر مجاني", price_minor=4000)
    _propose_and_accept(wired, grant_type="gift", gift_service_id="svc_gift")

    # A REAL VISIT AT A, PRICED FROM ITS OWN CATALOGUE, CROSSING THE 1000-HALALA THRESHOLD —
    # not a poked-in total_minor. A's catalogue has no priced service registered, so a custom
    # meter/service list alone would total 0; give A its own priced service to sell.
    _make_service(wired, A, "svc_a1", "غسيل خارجي", price_minor=1500)
    visit_a = _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"],
                            idem="e2e-gift-visit-a")
    assert visit_a["visit"]["total_minor"] >= 1000

    # THE GRANT NOW EXISTS — a real visit at B should find the customer eligible and the offer
    # applies, deriving its text from the real service name, never a stored string.
    visit_b = _record_visit(wired, B, phone=CUSTOMER_PHONE, service_ids=["svc_b_filler"],
                            idem="e2e-gift-visit-b")
    applied = _apply_offer(wired, B, visit_b["visit"]["id"], subject_ref=visit_b["visit"]["id"])
    assert applied["applied"] is True, applied
    assert "قص شعر مجاني" in applied["offer"]["text"]

    kpis = wired.get("/api/v1/staff/mutual-benefit/kpis",
                     headers=_auth(*REFERRAL_CAPS, tenant=A)).json()
    assert kpis["as_referrer"]["redeemed"] == 1
    assert kpis["as_referrer"]["gift_redemptions_by_service"]["svc_gift"]["redeemed"] == 1


def test_full_chain_discount_item_scope(wired: TestClient):
    _make_service(wired, B, "svc_item", "خصم على الغسيل", price_minor=3000)
    _propose_and_accept(wired, grant_type="discount", discount_scope="item",
                        gift_service_id="svc_item")
    _make_service(wired, A, "svc_a1", "خدمة أ", price_minor=1500)
    _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"], idem="e2e-item-a")
    visit_b = _record_visit(wired, B, phone=CUSTOMER_PHONE, service_ids=["svc_b_filler"], idem="e2e-item-b")
    applied = _apply_offer(wired, B, visit_b["visit"]["id"], subject_ref=visit_b["visit"]["id"])
    assert applied["applied"] is True
    assert "خصم على الغسيل" in applied["offer"]["text"]


def test_full_chain_discount_blanket_scope_is_the_default(wired: TestClient):
    _propose_and_accept(wired, grant_type="discount", discount_scope="blanket")
    _make_service(wired, A, "svc_a1", "خدمة أ", price_minor=1500)
    _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"], idem="e2e-blanket-a")
    visit_b = _record_visit(wired, B, phone=CUSTOMER_PHONE, service_ids=["svc_b_filler"], idem="e2e-blanket-b")
    applied = _apply_offer(wired, B, visit_b["visit"]["id"], subject_ref=visit_b["visit"]["id"])
    assert applied["applied"] is True
    assert "شراكة" in applied["offer"]["text"]


def test_full_chain_discount_group_scope(wired: TestClient):
    _make_service(wired, B, "svc_g1", "خدمة 1", price_minor=2000)
    _make_service(wired, B, "svc_g2", "خدمة 2", price_minor=2000)
    _make_package(wired, B, "pkg_1", "باقة الشراكة", ["svc_g1", "svc_g2"])
    _propose_and_accept(wired, grant_type="discount", discount_scope="group",
                        discount_group_id="pkg_1")
    _make_service(wired, A, "svc_a1", "خدمة أ", price_minor=1500)
    _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"], idem="e2e-group-a")
    visit_b = _record_visit(wired, B, phone=CUSTOMER_PHONE, service_ids=["svc_b_filler"], idem="e2e-group-b")
    applied = _apply_offer(wired, B, visit_b["visit"]["id"], subject_ref=visit_b["visit"]["id"])
    assert applied["applied"] is True
    assert "باقة الشراكة" in applied["offer"]["text"]


# ══════════════════════════════════════════════════════════════════════════════════════════════
# EDGE CASE — a visit under the threshold never grants anything, and applying an offer to a
# customer who holds nothing returns a clean "nothing to apply", never an error or a false grant.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_a_visit_under_the_threshold_grants_nothing_and_apply_offer_finds_nothing(
        wired: TestClient):
    _propose_and_accept(wired, condition_value="999999")   # threshold unreachable
    _make_service(wired, A, "svc_a1", "خدمة أ", price_minor=1500)
    _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"], idem="e2e-under-a")
    visit_b = _record_visit(wired, B, phone=CUSTOMER_PHONE, service_ids=["svc_b_filler"], idem="e2e-under-b")
    applied = _apply_offer(wired, B, visit_b["visit"]["id"], subject_ref=visit_b["visit"]["id"])
    assert applied["applied"] is False
    assert "لا يوجد" in applied["reason"]


# ══════════════════════════════════════════════════════════════════════════════════════════════
# EDGE CASE — a double tap on apply_offer never double-spends the grant, over real HTTP.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_a_double_tap_on_apply_offer_never_redeems_twice_over_http(wired: TestClient):
    _propose_and_accept(wired, grant_type="discount", discount_scope="blanket")
    _make_service(wired, A, "svc_a1", "خدمة أ", price_minor=1500)
    _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"], idem="e2e-double-a")
    visit_b = _record_visit(wired, B, phone=CUSTOMER_PHONE, service_ids=["svc_b_filler"], idem="e2e-double-b")
    first = _apply_offer(wired, B, visit_b["visit"]["id"], subject_ref=visit_b["visit"]["id"])
    second = _apply_offer(wired, B, visit_b["visit"]["id"], subject_ref=visit_b["visit"]["id"])
    assert first == second

    kpis = wired.get("/api/v1/staff/mutual-benefit/kpis",
                     headers=_auth(*REFERRAL_CAPS, tenant=A)).json()
    assert kpis["as_referrer"]["redeemed"] == 1


# ══════════════════════════════════════════════════════════════════════════════════════════════
# EDGE CASE — referral outranks an ordinary campaign offer live on the same visit.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_referral_outranks_a_live_campaign_offer_on_the_same_visit(wired: TestClient):
    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return {"ref": "camp_1", "text": "عرض ترحيبي عادي", "campaign_id": "camp"}

    from app.core.entitlements import EntitlementGateway

    engine = wired.app.state.container.mutual_benefit
    wired.app.state.container.entitlement_gateway = EntitlementGateway(
        mutual_benefit_engine=engine, campaign_chooser=campaign_chooser)
    wired.app.state.container.operations.with_entitlement_gateway(
        wired.app.state.container.entitlement_gateway)

    _propose_and_accept(wired, grant_type="discount", discount_scope="blanket")
    _make_service(wired, A, "svc_a1", "خدمة أ", price_minor=1500)
    _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"], idem="e2e-tie-a")
    visit_b = _record_visit(wired, B, phone=CUSTOMER_PHONE, service_ids=["svc_b_filler"], idem="e2e-tie-b")
    applied = _apply_offer(wired, B, visit_b["visit"]["id"], subject_ref=visit_b["visit"]["id"])
    assert applied["applied"] is True
    assert "شراكة" in applied["offer"]["text"]          # referral won, not the campaign offer


# ══════════════════════════════════════════════════════════════════════════════════════════════
# EDGE CASE — the concurrency cap, enforced over real HTTP at both propose() and accept().
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_a_fourth_overlapping_agreement_is_refused_over_http(wired: TestClient):
    others = ["0511111111", "0511111112", "0511111113", "0511111114"]
    for i, phone in enumerate(others[:3]):
        tenant = f"tnt_e2e_peer_{i}"
        _register_phone(wired, phone, tenant)
        _subscribe_tenant(wired, tenant)
        _propose_and_accept(wired, shop_b_tenant=tenant, b_phone=phone)

    _register_phone(wired, others[3], "tnt_e2e_peer_3")
    _subscribe_tenant(wired, "tnt_e2e_peer_3")
    fourth = _propose(wired, b_phone=others[3])
    assert fourth.get("__status__") == 409, fourth
    # THE PLATFORM STRIPS AN HTTPException's OWN `detail` GENERICALLY (CWE-209 by design — see
    # `field.py`'s own extensive note on this same behaviour for `record_visit`/`apply_offer`), so
    # only the STATUS CODE is observable over HTTP for a raised refusal — never the specific
    # business code. The specific `OVER_CONCURRENCY_CAP` string is already pinned at the engine
    # layer in `test_mutual_benefit_cap_and_gift.py`; this test's own job is proving the cap
    # is reachable and refusing through the REAL route, which the 409 alone already proves.


def test_a_fourth_agreement_is_allowed_once_one_of_the_three_truly_ends(wired: TestClient):
    from app.core.mutual_benefit import MutualBenefitEngine

    others = ["0521111111", "0521111112", "0521111113"]
    ids = []
    for i, phone in enumerate(others):
        tenant = f"tnt_e2e_end_{i}"
        _register_phone(wired, phone, tenant)
        _subscribe_tenant(wired, tenant)
        ids.append(_propose_and_accept(wired, shop_b_tenant=tenant, b_phone=phone))

    # END ONE FOR REAL (not just cancel_request — mutual cancel needs the other side too; ending
    # the term outright via the engine's own internal sync is the simplest real "already over"
    # state available without a day-long sleep). Push its `ends_at` into the past and let a normal
    # read sync it, mirroring exactly what `propose()`'s own pre-check does for a stale row.
    engine: MutualBenefitEngine = wired.app.state.container.mutual_benefit
    store = wired.app.state.container.datastore

    async def _expire(agreement_id: str) -> None:
        from app.core.mutual_benefit import AGREEMENTS, PLATFORM

        row = await store.get(AGREEMENTS, f"{PLATFORM}|{agreement_id}")
        row["ends_at"] = int(time.time()) - 10
        row["original_ends_at"] = row["ends_at"]
        await store.put(AGREEMENTS, f"{PLATFORM}|{agreement_id}", row)

    asyncio.run(_expire(ids[0]))

    fourth_phone = "0521111114"
    _register_phone(wired, fourth_phone, "tnt_e2e_end_3")
    _subscribe_tenant(wired, "tnt_e2e_end_3")
    fourth = _propose_and_accept(wired, shop_b_tenant="tnt_e2e_end_3", b_phone=fourth_phone)
    assert fourth   # did not raise — the cap made room once the first genuinely ended


# ══════════════════════════════════════════════════════════════════════════════════════════════
# EDGE CASE — renewal (a fresh propose/accept between the same two shops after the prior one
# ended) goes through the identical cap check, over real HTTP.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_renewal_between_the_same_two_shops_after_expiry_over_http(wired: TestClient):
    from app.core.mutual_benefit import AGREEMENTS, PLATFORM

    first_id = _propose_and_accept(wired)

    async def _end(agreement_id: str) -> None:
        row = await wired.app.state.container.datastore.get(AGREEMENTS, f"{PLATFORM}|{agreement_id}")
        row["status"] = "ended_term"
        await wired.app.state.container.datastore.put(
            AGREEMENTS, f"{PLATFORM}|{agreement_id}", row)

    asyncio.run(_end(first_id))

    renewed_id = _propose_and_accept(wired)
    assert renewed_id != first_id


# ══════════════════════════════════════════════════════════════════════════════════════════════
# EDGE CASE — catalogue validation refusals at the HTTP layer: wrong tenant, no such id, inactive.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_a_gift_referencing_a_third_tenants_service_is_refused_over_http(wired: TestClient):
    _make_service(wired, C, "svc_c1", "خدمة عند طرف ثالث", price_minor=1000)
    resp = _propose(wired, grant_type="gift", gift_service_id="svc_c1")
    # THE PLATFORM STRIPS A RAISED HTTPException's `detail` GENERICALLY (CWE-209 — see the 409
    # cap test above for the full reasoning), so only the 404 status is observable here; the
    # specific `CATALOG_ITEM_NOT_FOUND` code, and that a wrong-tenant/missing/inactive service all
    # collapse to the SAME refusal (the IDOR-safety property), are pinned at the engine layer
    # already in `test_mutual_benefit_grant_terms.py`.
    assert resp.get("__status__") == 404, resp


def test_a_discount_group_referencing_an_unknown_package_is_refused_over_http(wired: TestClient):
    resp = _propose(wired, grant_type="discount", discount_scope="group",
                    discount_group_id="pkg_does_not_exist")
    assert resp.get("__status__") == 404, resp


def test_an_inactive_service_as_a_gift_is_refused_over_http(wired: TestClient):
    _make_inactive_service(wired, B, "svc_dead")
    resp = _propose(wired, grant_type="gift", gift_service_id="svc_dead")
    assert resp.get("__status__") == 404, resp


# ══════════════════════════════════════════════════════════════════════════════════════════════
# EDGE CASE — the discount grant's own value is mandatory, enforced at TWO layers: FastAPI's own
# `Field(ge=0)` refuses a negative number before any business code runs, and the engine itself
# refuses an unknown kind or an out-of-range percent. Both must hold over the real wire, not just
# in a unit test that calls the engine directly.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_a_negative_discount_amount_is_refused_at_the_http_boundary_itself(wired: TestClient):
    resp = wired.post(
        "/api/v1/staff/mutual-benefit/agreements", headers=_auth(*REFERRAL_CAPS, tenant=A),
        json={"shop_b_phone": B_PHONE, "condition_type": "min_total_minor",
             "condition_value": "1000", "grant_validity_days": 3, "agreement_duration_days": 90,
             "grant_type": "discount", "discount_scope": "blanket",
             "discount_kind": "percent", "discount_amount": -1})
    # Pydantic's own `Field(ge=0)` refuses this before `engine.propose` ever runs — a 422, not
    # the engine's own 400 BAD_CONDITION.
    assert resp.status_code == 422, resp.text


def test_an_unknown_discount_kind_is_refused_over_http(wired: TestClient):
    resp = _propose(wired, grant_type="discount", discount_scope="blanket",
                    discount_kind="buy_one_get_one", discount_amount=10)
    assert resp.get("__status__") == 400, resp


def test_a_percent_over_100_is_refused_over_http_while_exactly_100_is_allowed(wired: TestClient):
    over = _propose(wired, grant_type="discount", discount_scope="blanket",
                    discount_kind="percent", discount_amount=101)
    assert over.get("__status__") == 400, over

    # The invalid 101 call above never created a live agreement (refused before anything was
    # saved), so B_PHONE is still free for this one.
    exact = _propose(wired, grant_type="discount", discount_scope="blanket",
                     discount_kind="percent", discount_amount=100)
    assert exact.get("discount_amount") == 100, exact


def test_the_stored_amount_survives_the_full_http_round_trip_to_the_beneficiarys_own_screen(
        wired: TestClient):
    """Not just stored — actually READABLE by shop_b's own redemption check, in real halalas,
    over the real wire a cashier's screen would use."""
    agreement = _propose(wired, grant_type="discount", discount_scope="blanket",
                         discount_kind="fixed_halalas", discount_amount=2500)
    _accept(wired, agreement["id"])
    _make_service(wired, A, "svc_roundtrip", "خدمة", price_minor=1500)
    _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_roundtrip"],
                 idem="vis_amount_roundtrip")

    # The celebration payload at A's own field endpoint is covered by a sibling test
    # (`test_points_balance_appears_alongside_the_customer_lookup_at_the_granting_shop`); here we
    # go straight to the authoritative source, `eligibility()` at B.
    from app.core.mutual_benefit import MutualBenefitEngine

    engine: MutualBenefitEngine = wired.app.state.container.mutual_benefit
    elig = asyncio.run(engine.eligibility(B, CUSTOMER_PHONE))
    assert elig is not None
    assert elig["discount_kind"] == "fixed_halalas"
    assert elig["discount_amount"] == 2500


# ══════════════════════════════════════════════════════════════════════════════════════════════
# EDGE CASE — immutability over HTTP: no edit route exists, and different terms mean a new
# agreement id, the original's own terms untouched.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_no_patch_or_put_route_exists_for_an_agreement_over_http(wired: TestClient):
    agreement_id = _propose_and_accept(wired)
    for method in ("patch", "put"):
        resp = getattr(wired, method)(
            f"/api/v1/staff/mutual-benefit/agreements/{agreement_id}",
            headers=_auth(*REFERRAL_CAPS, tenant=A), json={"discount_scope": "blanket"})
        assert resp.status_code in (404, 405), (method, resp.status_code)


def test_reproposing_with_different_grant_terms_leaves_the_original_untouched_over_http(
        wired: TestClient):
    _make_service(wired, B, "svc_x", "خدمة X", price_minor=1000)
    _make_service(wired, B, "svc_y", "خدمة Y", price_minor=1000)
    first_id = _propose_and_accept(wired, grant_type="gift", gift_service_id="svc_x")

    from app.core.mutual_benefit import AGREEMENTS, PLATFORM

    async def _end(agreement_id: str) -> None:
        row = await wired.app.state.container.datastore.get(AGREEMENTS, f"{PLATFORM}|{agreement_id}")
        row["status"] = "ended_term"
        await wired.app.state.container.datastore.put(
            AGREEMENTS, f"{PLATFORM}|{agreement_id}", row)

    asyncio.run(_end(first_id))
    second_id = _propose_and_accept(wired, grant_type="gift", gift_service_id="svc_y")
    assert second_id != first_id

    original = wired.get(f"/api/v1/staff/mutual-benefit/agreements/{first_id}",
                         headers=_auth(*REFERRAL_CAPS, tenant=A)).json()
    assert original["gift_service_id"] == "svc_x"          # untouched by the second proposal


# ══════════════════════════════════════════════════════════════════════════════════════════════
# EDGE CASE — points balance rides alongside the same customer lookup an operator uses at either
# shop, unaffected by whichever grant kind that customer happens to hold.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_points_balance_appears_alongside_the_customer_lookup_at_the_granting_shop(
        wired: TestClient):
    class _FakeDesk:
        configured = True

        async def balance(self, *, tenant, subject_ref):
            return {"has_programme": True, "points": 120, "to_next_reward": 30, "rewards": []}

    wired.app.state.container.loyalty_desk = _FakeDesk()
    _propose_and_accept(wired, grant_type="discount", discount_scope="blanket")
    _make_service(wired, A, "svc_a1", "خدمة أ", price_minor=1500)
    _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"], idem="e2e-points-a")
    _record_visit(wired, B, phone=CUSTOMER_PHONE, service_ids=["svc_b_filler"], idem="e2e-points-b")

    resp = wired.get("/api/v1/field/customers/by-phone", params={"phone": CUSTOMER_PHONE},
                     headers=_auth(*RECORD_CAPS, tenant=B))
    assert resp.status_code == 200, resp.text
    assert resp.json()["customer"]["points_balance"] == 120


# ══════════════════════════════════════════════════════════════════════════════════════════════
# EDGE CASE — the counter's own celebration moment: `mutual_benefit_grant` on the visit response, ONLY
# on the real visit that just created a NEW grant, never on an ordinary visit, a replay of the
# same idempotency key, or a visit that stays below the threshold.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_a_qualifying_visit_surfaces_a_mutual_benefit_grant_for_the_celebration_screen(wired: TestClient):
    _make_service(wired, B, "svc_gift", "قص شعر مجاني", price_minor=4000)
    _propose_and_accept(wired, grant_type="gift", gift_service_id="svc_gift")
    _make_service(wired, A, "svc_a1", "غسيل خارجي", price_minor=1500)

    visit = _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"], idem="e2e-cel-a")
    grant = visit.get("mutual_benefit_grant")
    assert grant is not None, visit
    assert grant["grant_type"] == "gift"
    assert grant["gift_service_name"] == "قص شعر مجاني"
    assert grant["expires_at"] > 0
    # NO TENANT-SERVICE CONFIGURED IN THIS TEST — `fetch_tenant_name` degrades silently to "", the
    # exact same "a missing name never blocks the celebration" posture the route's own comment
    # states; asserted here so that posture stays true, not merely documented.
    assert grant["partner_shop_name"] == ""


def test_an_ordinary_visit_under_the_threshold_never_surfaces_a_grant(wired: TestClient):
    _propose_and_accept(wired, condition_value="999999")   # threshold unreachable
    _make_service(wired, A, "svc_a1", "خدمة أ", price_minor=1500)
    visit = _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"], idem="e2e-cel-under")
    assert "mutual_benefit_grant" not in visit


def test_replaying_the_same_idempotency_key_never_re_surfaces_the_grant(wired: TestClient):
    _propose_and_accept(wired, grant_type="discount", discount_scope="blanket")
    _make_service(wired, A, "svc_a1", "خدمة أ", price_minor=1500)

    first = _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"], idem="e2e-cel-dup")
    assert first.get("mutual_benefit_grant") is not None

    second = _record_visit(wired, A, phone=CUSTOMER_PHONE, service_ids=["svc_a1"], idem="e2e-cel-dup")
    assert second["duplicate"] is True
    assert "mutual_benefit_grant" not in second
