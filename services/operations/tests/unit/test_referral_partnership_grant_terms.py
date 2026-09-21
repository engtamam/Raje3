"""The owner's own correction after the first cap/gift pass: NO FREE TEXT ANYWHERE for what a
grant is, for either kind. A discount is now catalogue-driven too, with three scopes ("item",
"blanket", "group" — a `Package`, this codebase's own existing grouping concept, reused rather
than invented). Every reference is validated against the GRANTING shop's (shop_b's) own real
catalogue at propose() time, and the whole set of terms is IMMUTABLE once the agreement exists —
different terms are a new agreement, never an edit.
"""
from __future__ import annotations

import asyncio
import inspect

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Package, Service
from app.core.referral_partnership import (BAD_CONDITION, CATALOG_GROUP_NOT_FOUND,
                                           CATALOG_ITEM_NOT_FOUND, CONDITION_MIN_TOTAL,
                                           DISCOUNT_SCOPE_BLANKET, DISCOUNT_SCOPE_GROUP,
                                           DISCOUNT_SCOPE_ITEM, FEATURE_KEY, GRANT_DISCOUNT,
                                           GRANT_GIFT, ReferralError, ReferralPartnershipEngine)
from app.core.signup import PHONE_INDEX, canonical_phone
from app.core.stores import PackageStore, ServiceStore

CC = "966"
A = "tnt_terms_a"
B = "tnt_terms_b"
C = "tnt_terms_c"
PHONE = "0501112222"


def run(coro):
    return asyncio.run(coro)


class FakePlans:
    driver = "fake"

    def __init__(self) -> None:
        self.subs: dict[str, list[dict]] = {}
        self.plan_for_key = {FEATURE_KEY: "plan_referral"}

    async def subscriptions(self, tenant):
        return self.subs.get(tenant, [])

    async def plan_id_for_key(self, key):
        return self.plan_for_key.get(key, "")

    async def limits(self, plan_id):
        return {}


class FakeAuthz:
    async def list_assignments(self, tenant: str):
        return []

    async def effective_capabilities(self, tenant, subject, roles):
        return set()


class FakeNotifier:
    async def send(self, **kwargs):
        return True


def _subscribe(plans: FakePlans, tenant: str) -> None:
    plans.subs.setdefault(tenant, []).append(
        {"id": f"sub_{tenant}", "plan": "plan_referral", "status": "active"})


def _register_phone(store, phone: str, tenant: str) -> None:
    key = canonical_phone(phone, default_cc=CC)
    run(store.put(PHONE_INDEX, key, {"id": key, "tenant": tenant, "verified": True}))


@pytest.fixture()
def env():
    store = MemoryDataStore()
    plans = FakePlans()
    engine = ReferralPartnershipEngine(store=store, plans=plans, notifier=FakeNotifier(),
                                       authz=FakeAuthz(), default_cc=CC)
    _register_phone(store, PHONE, B)
    _subscribe(plans, A)
    _subscribe(plans, B)
    return engine, store, plans


def _propose(engine, **overrides):
    kwargs = dict(shop_a=A, shop_b_phone=PHONE, operator_id="op1",
                 condition_type=CONDITION_MIN_TOTAL, condition_value="1000",
                 grant_validity_days=3, agreement_duration_days=90)
    kwargs.update(overrides)
    return run(engine.propose(**kwargs))


# ── discount, scope "blanket" — the explicit "all" choice, never an empty field ─────────────────
def test_blanket_is_the_default_and_a_real_deliberate_value_not_an_empty_one(env):
    engine, _store, _plans = env
    agreement = _propose(engine)
    assert agreement.grant_type == GRANT_DISCOUNT
    assert agreement.discount_scope == DISCOUNT_SCOPE_BLANKET
    assert agreement.discount_scope != ""


def test_blanket_can_also_be_chosen_explicitly(env):
    engine, _store, _plans = env
    agreement = _propose(engine, discount_scope=DISCOUNT_SCOPE_BLANKET)
    assert agreement.discount_scope == DISCOUNT_SCOPE_BLANKET


# ── discount, scope "item" — a real service, same validation as a gift ──────────────────────────
def test_discount_item_scope_validates_against_the_granting_shops_catalogue(env):
    engine, store, _plans = env
    run(ServiceStore(store).save(Service(id="svc_1", tenant=B, name="تغيير زيت")))
    agreement = _propose(engine, discount_scope=DISCOUNT_SCOPE_ITEM, gift_service_id="svc_1")
    assert agreement.discount_scope == DISCOUNT_SCOPE_ITEM
    assert agreement.gift_service_id == "svc_1"
    assert agreement.gift_service_name == "تغيير زيت"


def test_discount_item_scope_refuses_a_service_from_another_tenant(env):
    engine, store, _plans = env
    run(ServiceStore(store).save(Service(id="svc_foreign", tenant=C, name="خدمة غريبة")))
    with pytest.raises(ReferralError) as exc:
        _propose(engine, discount_scope=DISCOUNT_SCOPE_ITEM, gift_service_id="svc_foreign")
    assert exc.value.args[0] == CATALOG_ITEM_NOT_FOUND


def test_discount_item_scope_with_no_service_id_is_refused(env):
    engine, _store, _plans = env
    with pytest.raises(ReferralError) as exc:
        _propose(engine, discount_scope=DISCOUNT_SCOPE_ITEM, gift_service_id="")
    assert exc.value.args[0] == BAD_CONDITION


# ── discount, scope "group" — a real Package, this codebase's own reused grouping concept ───────
def test_discount_group_scope_validates_against_the_granting_shops_packages(env):
    engine, store, _plans = env
    run(PackageStore(store).save(Package(id="pkg_1", tenant=B, name="باقة العناية الكاملة",
                                         service_ids=["a", "b"])))
    agreement = _propose(engine, discount_scope=DISCOUNT_SCOPE_GROUP, discount_group_id="pkg_1")
    assert agreement.discount_scope == DISCOUNT_SCOPE_GROUP
    assert agreement.discount_group_id == "pkg_1"
    assert agreement.discount_group_name == "باقة العناية الكاملة"


def test_discount_group_scope_refuses_a_package_from_another_tenant(env):
    engine, store, _plans = env
    run(PackageStore(store).save(Package(id="pkg_foreign", tenant=C, name="باقة غريبة",
                                         service_ids=["a", "b"])))
    with pytest.raises(ReferralError) as exc:
        _propose(engine, discount_scope=DISCOUNT_SCOPE_GROUP, discount_group_id="pkg_foreign")
    assert exc.value.args[0] == CATALOG_GROUP_NOT_FOUND


def test_discount_group_scope_refuses_an_inactive_package(env):
    engine, store, _plans = env
    run(PackageStore(store).save(Package(id="pkg_dead", tenant=B, name="باقة متوقفة",
                                         service_ids=["a", "b"], active=False)))
    with pytest.raises(ReferralError) as exc:
        _propose(engine, discount_scope=DISCOUNT_SCOPE_GROUP, discount_group_id="pkg_dead")
    assert exc.value.args[0] == CATALOG_GROUP_NOT_FOUND


def test_discount_group_scope_with_no_group_id_is_refused(env):
    engine, _store, _plans = env
    with pytest.raises(ReferralError) as exc:
        _propose(engine, discount_scope=DISCOUNT_SCOPE_GROUP, discount_group_id="")
    assert exc.value.args[0] == BAD_CONDITION


def test_an_unknown_discount_scope_is_refused(env):
    engine, _store, _plans = env
    with pytest.raises(ReferralError) as exc:
        _propose(engine, discount_scope="half-price-tuesdays")
    assert exc.value.args[0] == BAD_CONDITION


# ── the entitlement text, derived from real catalogue data, never authored text ─────────────────
def test_entitlement_text_is_derived_per_scope_never_stored_free_text():
    from app.core.entitlements import EntitlementGateway

    async def go():
        store = MemoryDataStore()
        plans = FakePlans()
        engine = ReferralPartnershipEngine(store=store, plans=plans, notifier=FakeNotifier(),
                                           authz=FakeAuthz(), default_cc=CC)
        gateway = EntitlementGateway(referral_engine=engine, campaign_chooser=None)
        await ServiceStore(store).save(Service(id="svc_wash", tenant=B, name="غسلة كاملة"))
        await PackageStore(store).save(Package(id="pkg_care", tenant=B, name="باقة العناية",
                                               service_ids=["a", "b"]))

        cases = [
            (dict(grant_type=GRANT_GIFT, gift_service_id="svc_wash"), "غسلة كاملة"),
            (dict(grant_type=GRANT_DISCOUNT, discount_scope=DISCOUNT_SCOPE_BLANKET), "خصم شامل"),
            (dict(grant_type=GRANT_DISCOUNT, discount_scope=DISCOUNT_SCOPE_ITEM,
                 gift_service_id="svc_wash"), "غسلة كاملة"),
            (dict(grant_type=GRANT_DISCOUNT, discount_scope=DISCOUNT_SCOPE_GROUP,
                 discount_group_id="pkg_care"), "باقة العناية"),
        ]
        for i, (kwargs, expect_substr) in enumerate(cases):
            # A DISTINCT shop_a PER CASE — the engine allows only ONE live agreement per
            # (shop_a, shop_b) pair at a time (by design), so four independent cases against the
            # SAME shop_b need four independent referring shops, not four proposals to one pair.
            shop_a = f"tnt_terms_referrer_{i}"
            _subscribe(plans, shop_a)
            _subscribe(plans, B)
            key = canonical_phone(PHONE, default_cc=CC)
            # INLINE `store.put`, NOT THE SYNC `_register_phone` HELPER — that helper wraps its
            # own `asyncio.run`, and this whole test already runs inside ONE (`run(go())` below);
            # nesting a second `asyncio.run` on the SAME shared loop (tests/conftest.py's
            # single-loop fixture) raises "this event loop is already running".
            await store.put(PHONE_INDEX, key, {"id": key, "tenant": B, "verified": True})

            agreement = await engine.propose(
                shop_a=shop_a, shop_b_phone=PHONE, operator_id="op1",
                condition_type=CONDITION_MIN_TOTAL, condition_value="1000",
                grant_validity_days=3, agreement_duration_days=90, **kwargs)
            await engine.accept(tenant=B, agreement_id=agreement.id)
            phone = f"05000000{i:02d}"
            await engine.on_visit_recorded(tenant=shop_a, customer_phone=phone, service_ids=[],
                                          total_minor=1500, visit_id=f"vis_{i}")
            entitlement = await gateway.choose(tenant=B, subject_ref="sub_x", phone=phone,
                                               service_ids=[])
            assert entitlement is not None
            assert expect_substr in entitlement.text
            assert shop_a not in entitlement.text

            # FREE B'S SLOT BEFORE THE NEXT CASE — B is the granting shop in all four cases, and
            # the concurrency cap (round 3) is real: four AT ONCE would refuse the fourth. Mutual
            # cancel is the only way to end one early, exactly as production requires.
            await engine.cancel_request(tenant=shop_a, agreement_id=agreement.id)
            await engine.cancel_confirm(tenant=B, agreement_id=agreement.id)

    run(go())


# ── immutability — decided once, no edit path, ever ──────────────────────────────────────────────
def test_no_method_on_the_engine_can_change_an_existing_agreements_grant_terms():
    """Structural proof, not just behavioural: enumerate every public method the engine exposes
    and confirm none of them is shaped like an update/edit of grant terms."""
    public_methods = [name for name, _ in inspect.getmembers(
        ReferralPartnershipEngine, predicate=inspect.isfunction) if not name.startswith("_")]
    forbidden_substrings = ("update", "edit", "patch", "modify", "set_grant", "change")
    offending = [m for m in public_methods
                if any(bad in m.lower() for bad in forbidden_substrings)]
    assert offending == [], f"found a method shaped like a grant-terms editor: {offending}"


def test_no_http_route_exists_to_edit_an_existing_agreements_grant_terms():
    """Same proof at the API layer — read straight off the router, not a memory of what was
    wired, so a future PATCH/PUT slipped in without a corresponding engine change is still
    caught."""
    from app.api.v1.staff import router

    referral_routes = [r for r in router.routes
                       if "/referral-partnership/agreements" in getattr(r, "path", "")]
    assert referral_routes, "the referral-partnership routes moved or were renamed"
    for route in referral_routes:
        methods = getattr(route, "methods", set()) or set()
        assert "PATCH" not in methods and "PUT" not in methods, (
            f"found an edit method on {route.path}: {methods}")


def test_reproposing_with_different_terms_creates_a_new_agreement_not_an_edit(env):
    """The ONLY way to get different terms — a fresh propose/accept, never a change in place — and
    it produces a DIFFERENT agreement id, the original untouched."""
    engine, store, plans = env
    run(ServiceStore(store).save(Service(id="svc_a", tenant=B, name="خدمة أ")))
    run(ServiceStore(store).save(Service(id="svc_b", tenant=B, name="خدمة ب")))

    first = _propose(engine, discount_scope=DISCOUNT_SCOPE_ITEM, gift_service_id="svc_a")
    run(engine.accept(tenant=B, agreement_id=first.id))
    run(engine.cancel_request(tenant=A, agreement_id=first.id))
    run(engine.cancel_confirm(tenant=B, agreement_id=first.id))

    second = _propose(engine, discount_scope=DISCOUNT_SCOPE_ITEM, gift_service_id="svc_b")
    assert second.id != first.id
    # THE ORIGINAL, ALREADY-ENDED AGREEMENT KEEPS EXACTLY WHAT IT WAS PROPOSED WITH — nothing
    # about `first` was ever rewritten by the second proposal.
    refetched_first = run(engine.get(A, first.id))
    assert refetched_first.gift_service_id == "svc_a"
