"""Two additions to core/mutual_benefit.py, tested in isolation from the rest of the
lifecycle suite (test_mutual_benefit.py):

  1. THE CONCURRENCY CAP — `MAX_CONCURRENT_PARTNERSHIPS`, a TIME-RANGE check (sweep-line over real
     [start, end) intervals), not a raw count — including the exact half-open boundary rule
     (end exclusive: an agreement ending at T and one starting at T do not overlap).
  2. THE GIFT GRANT TYPE — a real catalogue service_id from the GRANTING shop (shop_b), validated
     at propose() time, never free text; discount stays the other, unchanged, valid type.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Service
from app.core.mutual_benefit import (AGREEMENTS, CONDITION_MIN_TOTAL, FEATURE_KEY,
                                           CATALOG_ITEM_NOT_FOUND, GRANT_DISCOUNT, GRANT_GIFT,
                                           MAX_CONCURRENT_PARTNERSHIPS, OVER_CONCURRENCY_CAP,
                                           PLATFORM, BAD_CONDITION, MutualBenefitError,
                                           MutualBenefitEngine)
from app.core.signup import PHONE_INDEX, canonical_phone
from app.core.stores import ServiceStore

CC = "966"


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
    notifier = FakeNotifier()
    authz = FakeAuthz()
    engine = MutualBenefitEngine(store=store, plans=plans, notifier=notifier, authz=authz,
                                       default_cc=CC)
    return engine, store, plans


def _propose_and_accept(engine, plans, store, *, shop_a, shop_b, duration_days=90, **kwargs):
    phone = f"05{abs(hash((shop_a, shop_b))) % 10**8:08d}"
    _register_phone(store, phone, shop_b)
    _subscribe(plans, shop_a)
    _subscribe(plans, shop_b)
    kwargs.setdefault("condition_type", CONDITION_MIN_TOTAL)
    kwargs.setdefault("condition_value", "1000")
    kwargs.setdefault("grant_validity_days", 3)
    agreement = run(engine.propose(shop_a=shop_a, shop_b_phone=phone, operator_id="op1",
                                   agreement_duration_days=duration_days, **kwargs))
    return run(engine.accept(tenant=shop_b, agreement_id=agreement.id))


def _force_interval(store, agreement_id: str, *, started_at: int, ends_at: int,
                    original_ends_at: int | None = None) -> None:
    """Directly rewrite a stored agreement's committed interval — the same technique the
    lifecycle suite already uses (test_mutual_benefit.py's own pause/resume/expiry tests)
    to place two events on either side of a boundary without sleeping."""
    row = run(store.get(AGREEMENTS, f"{PLATFORM}|{agreement_id}"))
    row["started_at"] = started_at
    row["ends_at"] = ends_at
    row["original_ends_at"] = original_ends_at if original_ends_at is not None else ends_at
    run(store.put(AGREEMENTS, f"{PLATFORM}|{agreement_id}", row))


# ── the cap itself — MAX_CONCURRENT_PARTNERSHIPS is a real, named, importable constant ──────────
def test_the_cap_constant_is_three_today():
    assert MAX_CONCURRENT_PARTNERSHIPS == 3


# ── the sweep-line math, tested directly and precisely ──────────────────────────────────────────
def test_max_concurrent_counts_the_true_peak_not_a_pairwise_sum():
    m = MutualBenefitEngine._max_concurrent
    # Three intervals, only two ever overlap at once.
    assert m([(0, 10), (5, 15), (20, 30)]) == 2
    # All three overlap at t=5.
    assert m([(0, 10), (0, 10), (0, 10)]) == 3
    assert m([]) == 0


def test_end_on_day_x_and_start_on_day_x_do_not_overlap():
    """THE DECIDED, DOCUMENTED BOUNDARY RULE: half-open, end exclusive."""
    m = MutualBenefitEngine._max_concurrent
    assert m([(0, 100), (100, 200)]) == 1          # touching endpoints: never simultaneous
    assert m([(0, 100), (99, 200)]) == 2            # one second earlier: genuinely overlapping


# ── the cap enforced through the real propose/accept flow ───────────────────────────────────────
def test_a_shop_already_at_the_cap_is_refused_a_fourth_overlapping_agreement(env):
    engine, store, plans = env
    hub = "tnt_hub"
    for i in range(MAX_CONCURRENT_PARTNERSHIPS):
        _propose_and_accept(engine, plans, store, shop_a=hub, shop_b=f"tnt_leaf_{i}")

    with pytest.raises(MutualBenefitError) as exc:
        _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_leaf_extra")
    assert exc.value.args[0] == OVER_CONCURRENCY_CAP


def test_both_roles_count_together_toward_one_shops_cap(env):
    """A shop that is shop_a in two and shop_b in one is already at three — refused a fourth in
    EITHER role."""
    engine, store, plans = env
    hub = "tnt_hub2"
    _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_leaf_a")
    _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_leaf_b")
    _propose_and_accept(engine, plans, store, shop_a="tnt_leaf_c", shop_b=hub)

    with pytest.raises(MutualBenefitError) as exc:
        _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_leaf_d")
    assert exc.value.args[0] == OVER_CONCURRENCY_CAP


def test_a_shop_at_the_cap_can_still_propose_one_that_starts_after_another_truly_ends(env):
    """The interval math, not the status label: a row can still say status=ACTIVE (not yet lazily
    synced to ENDED) while its real `ends_at` has already passed — the cap check must read the
    TIMESTAMPS, not assume `_synced` already ran."""
    engine, store, plans = env
    hub = "tnt_hub3"
    a1 = _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_leaf3_a")
    a2 = _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_leaf3_b")
    a3 = _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_leaf3_c")

    now = a1.started_at
    # a1 truly ended an hour ago, but its stored status is still literally "active".
    _force_interval(store, a1.id, started_at=now - 7200, ends_at=now - 3600)
    # a2/a3 stay genuinely open-ended (far future).

    fourth = _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_leaf3_d")
    assert fourth.status == "active"


def test_renewal_after_expiry_goes_through_the_identical_cap_check(env):
    """A 'renewal' is not a separate mechanism — a lapsed agreement between the same pair simply
    proposes/accepts again (module docstring), and hits the exact same cap math."""
    engine, store, plans = env
    hub = "tnt_hub4"
    original = _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_partner4",
                                   duration_days=1)
    # Fill the OTHER two slots with agreements that stay open.
    _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_leaf4_a")
    _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_leaf4_b")

    # Force the original partnership fully into the past (both `ends_at` AND `original_ends_at`,
    # so `_synced` reads it as genuinely, permanently over — not merely paused-and-resumable).
    past = original.started_at - 10
    _force_interval(store, original.id, started_at=past - 100, ends_at=past,
                    original_ends_at=past)
    # NO EXPLICIT SYNC CALL HERE, DELIBERATELY — `propose()` itself must recognise this stale
    # "active"-labelled row as genuinely over (its real `ends_at` has passed) without anything
    # having read it first; see propose()'s own comment on syncing candidate rows before deciding.

    # A THIRD open slot still exists (only 2 of 3 are genuinely open) — the renewal must succeed.
    renewed = _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_partner4")
    assert renewed.status == "active"
    assert renewed.id != original.id

    # NOW all three slots are genuinely open (2 leaves + the renewed one) — a further new
    # agreement must be refused, proving the renewal itself now occupies a real slot.
    with pytest.raises(MutualBenefitError) as exc:
        _propose_and_accept(engine, plans, store, shop_a=hub, shop_b="tnt_leaf4_c")
    assert exc.value.args[0] == OVER_CONCURRENCY_CAP


def test_propose_itself_refuses_early_as_a_tentative_courtesy(env):
    """The tentative check at propose() time — a courtesy refusal before a proposal even exists,
    distinct from (and in addition to) accept()'s own authoritative one."""
    engine, store, plans = env
    hub = "tnt_hub5"
    for i in range(MAX_CONCURRENT_PARTNERSHIPS):
        _propose_and_accept(engine, plans, store, shop_a=hub, shop_b=f"tnt_leaf5_{i}")

    _register_phone(store, "0599999999", "tnt_leaf5_extra")
    _subscribe(plans, hub)
    with pytest.raises(MutualBenefitError) as exc:
        run(engine.propose(shop_a=hub, shop_b_phone="0599999999", operator_id="op1",
                           condition_type=CONDITION_MIN_TOTAL, condition_value="1000",
                           grant_validity_days=3, agreement_duration_days=90))
    assert exc.value.args[0] == OVER_CONCURRENCY_CAP


# ── the gift grant type — a real catalogue item, validated against the GRANTING shop ────────────
def test_a_gift_grant_validates_against_the_granting_shops_real_catalogue(env):
    engine, store, plans = env
    shop_a, shop_b = "tnt_gift_a", "tnt_gift_b"
    run(ServiceStore(store).save(Service(id="svc_wash", tenant=shop_b, name="غسلة كاملة")))

    agreement = _propose_and_accept(
        engine, plans, store, shop_a=shop_a, shop_b=shop_b,
        grant_type=GRANT_GIFT, gift_service_id="svc_wash")
    assert agreement.grant_type == GRANT_GIFT
    assert agreement.gift_service_id == "svc_wash"
    assert agreement.gift_service_name == "غسلة كاملة"


def test_a_gift_referencing_another_tenants_service_is_refused(env):
    """The service exists — just not in shop_b's OWN catalogue (it belongs to a third tenant).
    Must be refused exactly like a service that does not exist anywhere at all."""
    engine, store, plans = env
    shop_a, shop_b = "tnt_gift2_a", "tnt_gift2_b"
    run(ServiceStore(store).save(Service(id="svc_other", tenant="tnt_someone_else",
                                         name="خدمة غريبة")))
    phone = f"05{abs(hash((shop_a, shop_b))) % 10**8:08d}"
    _register_phone(store, phone, shop_b)
    _subscribe(plans, shop_a)

    with pytest.raises(MutualBenefitError) as exc:
        run(engine.propose(shop_a=shop_a, shop_b_phone=phone, operator_id="op1",
                           condition_type=CONDITION_MIN_TOTAL, condition_value="1000",
                           grant_validity_days=3, agreement_duration_days=90,
                           grant_type=GRANT_GIFT, gift_service_id="svc_other"))
    assert exc.value.args[0] == CATALOG_ITEM_NOT_FOUND


def test_a_gift_with_no_service_id_is_refused(env):
    engine, store, plans = env
    shop_a, shop_b = "tnt_gift3_a", "tnt_gift3_b"
    phone = f"05{abs(hash((shop_a, shop_b))) % 10**8:08d}"
    _register_phone(store, phone, shop_b)
    _subscribe(plans, shop_a)

    with pytest.raises(MutualBenefitError) as exc:
        run(engine.propose(shop_a=shop_a, shop_b_phone=phone, operator_id="op1",
                           condition_type=CONDITION_MIN_TOTAL, condition_value="1000",
                           grant_validity_days=3, agreement_duration_days=90,
                           grant_type=GRANT_GIFT, gift_service_id=""))
    assert exc.value.args[0] == BAD_CONDITION


def test_an_inactive_service_is_refused_as_a_gift(env):
    engine, store, plans = env
    shop_a, shop_b = "tnt_gift4_a", "tnt_gift4_b"
    run(ServiceStore(store).save(Service(id="svc_retired", tenant=shop_b, name="خدمة متوقفة",
                                         active=False)))
    phone = f"05{abs(hash((shop_a, shop_b))) % 10**8:08d}"
    _register_phone(store, phone, shop_b)
    _subscribe(plans, shop_a)

    with pytest.raises(MutualBenefitError) as exc:
        run(engine.propose(shop_a=shop_a, shop_b_phone=phone, operator_id="op1",
                           condition_type=CONDITION_MIN_TOTAL, condition_value="1000",
                           grant_validity_days=3, agreement_duration_days=90,
                           grant_type=GRANT_GIFT, gift_service_id="svc_retired"))
    assert exc.value.args[0] == CATALOG_ITEM_NOT_FOUND


def test_discount_type_still_works_unchanged(env):
    engine, store, plans = env
    agreement = _propose_and_accept(engine, plans, store, shop_a="tnt_disc_a", shop_b="tnt_disc_b")
    assert agreement.grant_type == GRANT_DISCOUNT
    assert agreement.gift_service_id == ""


def test_a_gift_grant_flows_end_to_end_through_detection_and_redemption(env):
    engine, store, plans = env
    shop_a, shop_b = "tnt_gift5_a", "tnt_gift5_b"
    run(ServiceStore(store).save(Service(id="svc_free", tenant=shop_b, name="فحص مجاني")))
    agreement = _propose_and_accept(
        engine, plans, store, shop_a=shop_a, shop_b=shop_b,
        grant_type=GRANT_GIFT, gift_service_id="svc_free")

    run(engine.on_visit_recorded(tenant=shop_a, customer_phone="0522222222", service_ids=[],
                                total_minor=1500, visit_id="vis_gift_1"))
    elig = run(engine.eligibility(shop_b, "0522222222"))
    assert elig is not None
    assert elig["grant_type"] == GRANT_GIFT
    assert elig["gift_service_id"] == "svc_free"
    assert elig["gift_service_name"] == "فحص مجاني"
    # NEVER shop_a's identity, gift included — same privacy rule as the discount case.
    assert "shop_a" not in elig

    assert run(engine.redeem(shop_b, "0522222222", visit_id="vis_b_1")) is True
    kpis = run(engine.kpis(shop_a))
    bucket = kpis["as_referrer"]["gift_redemptions_by_service"]["svc_free"]
    assert bucket == {"service_name": "فحص مجاني", "granted": 1, "redeemed": 1}
