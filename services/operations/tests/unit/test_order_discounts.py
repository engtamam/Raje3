"""WhatsApp Direct Ordering's own campaign discount (core/orders.py, 2026-10-04) — a reward a
customer is holding from a reminders campaign send, applied to `discount_minor` on the order but
never consumed before the order is actually paid. See `orders.py`'s own notes on `create()`'s
discount block and `confirm_payment()` for why the timing is the single most important rule here.
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import Branch, Service
from app.core.operations import Operations
from app.core.orders import CONFIRMED, OrderService
from app.core.stores import BranchStore, ServiceStore

TENANT = "tnt_disc_1"
PHONE = "0501234567"
LAT, LNG = 24.7136, 46.6753


def run(c):
    return asyncio.run(c)


class FakePaymentsDesk:
    async def create_request(self, *, tenant, reference, amount_minor, metadata=None):
        return {"ok": True, "request_id": f"preq_{reference}",
               "pay_url": f"https://pay.example/{reference}"}

    async def reconcile(self, *, tenant, request_id):
        return None


class FakeDiscountDesk:
    """Mirrors `adapters/discount_desk.py`'s own `{find, redeem}` shape without any network call.

    `redeemed` RECORDS EVERY CALL, so a test can assert it was never made at all — the exact
    failure mode ("spent at creation, not at payment") this module exists to catch.
    """

    def __init__(self, discount: dict | None = None) -> None:
        self.discount = discount
        self.redeemed: list[dict] = []
        self.find_calls = 0
        self.unavailable = False

    async def find(self, *, tenant, subject_ref):
        self.find_calls += 1
        if self.unavailable:
            raise RuntimeError("peer down")
        return self.discount

    async def redeem(self, *, tenant, ref, redeemed_by):
        self.redeemed.append({"tenant": tenant, "ref": ref, "redeemed_by": redeemed_by})
        return True

    def as_dict(self) -> dict:
        return {"find": self.find, "redeem": self.redeem}


async def _seed(store, *, price_minor: int = 10_000) -> tuple[str, str]:
    services = ServiceStore(store)
    branches = BranchStore(store)
    sid = "svc_item"
    await services.save(Service(id=sid, tenant=TENANT, name="غسيل خارجي",
                                price_minor=price_minor, active=True))
    bid = "br_main"
    await branches.save(Branch(id=bid, tenant=TENANT, name="الفرع الرئيسي", active=True))
    return sid, bid


class FakeReferralEngine:
    """Mirrors `ReferralRedemptionEngine`'s own `{eligibility, redeem}` shape — see
    `core/operations.py::Operations.referral_discount_for`/`redeem_referral_discount`'s own
    passthrough docstrings for why `redeem`'s `visit_id` is really just an opaque, idempotent
    reference string for this engine, never resolved back to a real Visit row."""

    def __init__(self, grant: dict | None = None) -> None:
        self.grant = grant
        self.redeemed: list[dict] = []

    async def eligibility(self, tenant, phone):
        return self.grant

    async def redeem(self, tenant, phone, *, visit_id):
        self.redeemed.append({"tenant": tenant, "phone": phone, "visit_id": visit_id})
        return True


def _service(store, discount_desk=None, *, referral_engine=None) -> OrderService:
    ops = Operations(store=store, pii_salt="s" * 32)
    if referral_engine is not None:
        ops.with_referral_redemption_engine(referral_engine)
    return OrderService(store=store, services=ServiceStore(store), branches=BranchStore(store),
                        operations=ops, payments=FakePaymentsDesk(),
                        discounts=discount_desk.as_dict() if discount_desk else None)


# ── applying the discount at creation ──────────────────────────────────────────────────────────
def test_a_live_percent_discount_is_applied_to_the_order():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    desk = FakeDiscountDesk({"ref": "snd_1", "reward_kind": "percent", "reward_amount": 20,
                             "scope_service_ids": [], "expires_at": 9_999_999_999})
    s = _service(store, desk)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt1"))
    assert order.total_minor == 10_000
    assert order.discount_minor == 2_000                 # 20% of 10,000
    assert order.discount_source == "campaign:snd_1"


def test_a_fixed_discount_is_capped_at_the_order_total():
    """A discount can make an order free, never negative."""
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=5_00))
    desk = FakeDiscountDesk({"ref": "snd_2", "reward_kind": "fixed_halalas",
                             "reward_amount": 50_00, "scope_service_ids": [],
                             "expires_at": 9_999_999_999})
    s = _service(store, desk)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt2"))
    assert order.discount_minor == order.total_minor == 5_00


def test_a_scoped_discount_only_covers_its_own_services():
    store = MemoryDataStore()
    services = ServiceStore(store)
    bid = "br_main"
    run(BranchStore(store).save(Branch(id=bid, tenant=TENANT, name="فرع", active=True)))
    run(services.save(Service(id="svc_a", tenant=TENANT, name="أ", price_minor=10_000,
                              active=True)))
    run(services.save(Service(id="svc_b", tenant=TENANT, name="ب", price_minor=5_000,
                              active=True)))
    desk = FakeDiscountDesk({"ref": "snd_3", "reward_kind": "percent", "reward_amount": 50,
                             "scope_service_ids": ["svc_a"], "expires_at": 9_999_999_999})
    s = _service(store, desk)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[("svc_a", 1), ("svc_b", 1)], lat=LAT, lng=LNG,
                        idempotency_key="evt3"))
    assert order.total_minor == 15_000
    assert order.discount_minor == 5_000                  # 50% of svc_a's 10,000 only


def test_no_discount_held_means_an_ordinary_order():
    store = MemoryDataStore()
    sid, bid = run(_seed(store))
    desk = FakeDiscountDesk(None)
    s = _service(store, desk)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt4"))
    assert order.discount_minor == 0 and order.discount_source == ""


def test_an_unreachable_discount_peer_still_lets_the_order_through():
    """A failure to ask means "no discount this attempt", never a refused order."""
    store = MemoryDataStore()
    sid, bid = run(_seed(store))
    desk = FakeDiscountDesk(None)
    desk.unavailable = True
    s = _service(store, desk)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt5"))
    assert order.discount_minor == 0


# ── THE CENTRAL GUARANTEE: redeemed only on confirmed payment, never on creation ───────────────
def test_creating_the_order_never_redeems_the_discount():
    """If this ever regresses to redeeming in `create()`, this is the test that catches it."""
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    desk = FakeDiscountDesk({"ref": "snd_4", "reward_kind": "percent", "reward_amount": 20,
                             "scope_service_ids": [], "expires_at": 9_999_999_999})
    s = _service(store, desk)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt6"))
    assert order.discount_minor == 2_000
    assert desk.redeemed == [], "the discount must not be spent before the order is paid"


def test_confirming_payment_in_full_redeems_the_discount():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    desk = FakeDiscountDesk({"ref": "snd_5", "reward_kind": "percent", "reward_amount": 20,
                             "scope_service_ids": [], "expires_at": 9_999_999_999})
    s = _service(store, desk)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt7"))
    # THE AMOUNT ACTUALLY DUE — `amount_due_minor` (total MINUS the discount already shown to the
    # customer), never the pre-discount `total_minor`: `confirm_payment` checks the gateway's
    # reported amount against `amount_due_minor`, the same figure `request_payment` quoted the
    # gateway for in the first place.
    assert order.amount_due_minor == order.total_minor - 2_000
    confirmed = run(s.confirm_payment(TENANT, order.id,
                                      paid_amount_minor=order.amount_due_minor,
                                      payment_ref="pay_ref_1"))
    assert confirmed.status == CONFIRMED
    assert len(desk.redeemed) == 1
    assert desk.redeemed[0]["ref"] == "snd_5"
    assert desk.redeemed[0]["redeemed_by"] == f"order:{order.id}"


def test_resolving_a_payment_mismatch_also_redeems_the_discount():
    """`resolve_mismatch()` is the OTHER path that can land an order on CONFIRMED -- a human
    override, not the gateway's own exact-amount match -- and must spend the same single-use
    discount the same way `confirm_payment()`'s own exact-match branch does. Missing this would
    let the discount be promised to a second order even though this one already used it."""
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    desk = FakeDiscountDesk({"ref": "snd_mismatch", "reward_kind": "percent", "reward_amount": 20,
                             "scope_service_ids": [], "expires_at": 9_999_999_999})
    s = _service(store, desk)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_mismatch"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=order.total_minor - 1,
                         payment_ref="pay_ref_mismatch"))
    assert desk.redeemed == [], "a mismatch must not redeem anything until a human resolves it"

    resolved = run(s.resolve_mismatch(TENANT, order.id, actor="op_1"))
    assert resolved.status == CONFIRMED
    assert len(desk.redeemed) == 1
    assert desk.redeemed[0]["ref"] == "snd_mismatch"
    assert desk.redeemed[0]["redeemed_by"] == f"order:{order.id}"


def test_cancelling_an_unpaid_order_never_redeems_the_discount():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    desk = FakeDiscountDesk({"ref": "snd_6", "reward_kind": "percent", "reward_amount": 20,
                             "scope_service_ids": [], "expires_at": 9_999_999_999})
    s = _service(store, desk)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt8"))
    run(s.cancel(TENANT, order.id, reason="غيّر رأيه"))
    assert desk.redeemed == [], "a cancelled order must leave the discount for a future attempt"


def test_a_second_order_cannot_claim_the_same_single_use_discount_while_the_first_is_unpaid():
    """THE LOCK: two in-flight unpaid orders for the same customer must not both believe they will
    get the same single-use discount — only the first to ask gets it reserved."""
    store = MemoryDataStore()
    services = ServiceStore(store)
    bid = "br_main"
    run(BranchStore(store).save(Branch(id=bid, tenant=TENANT, name="فرع", active=True)))
    run(services.save(Service(id="svc_a", tenant=TENANT, name="أ", price_minor=10_000,
                              active=True)))
    desk = FakeDiscountDesk({"ref": "snd_7", "reward_kind": "percent", "reward_amount": 20,
                             "scope_service_ids": [], "expires_at": 9_999_999_999})
    s = _service(store, desk)

    first = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[("svc_a", 1)], lat=LAT, lng=LNG, idempotency_key="evt9a"))
    second = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                         items=[("svc_a", 1)], lat=LAT, lng=LNG, idempotency_key="evt9b"))
    assert first.discount_minor == 2_000 and first.discount_source == "campaign:snd_7"
    assert second.discount_minor == 0 and second.discount_source == "", (
        "the first unpaid order already holds the reservation on this single-use discount")


# ── the unified consultation: referral discounts, and picking the better of two ────────────────

def test_a_referral_welcome_discount_is_applied_when_no_campaign_discount_is_held():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    referral = FakeReferralEngine({"eligible": True, "new_customer_reward_type": "discount_percent",
                                   "new_customer_reward_params": {"percent": 10}})
    s = _service(store, referral_engine=referral)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_ref1"))
    assert order.discount_minor == 1_000
    assert order.discount_source == f"referral:+966501234567"


def test_the_higher_value_offer_wins_campaign_over_referral():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    desk = FakeDiscountDesk({"ref": "snd_hi", "reward_kind": "percent", "reward_amount": 30,
                             "scope_service_ids": [], "expires_at": 9_999_999_999})
    referral = FakeReferralEngine({"eligible": True, "new_customer_reward_type": "discount_percent",
                                   "new_customer_reward_params": {"percent": 10}})
    s = _service(store, desk, referral_engine=referral)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_both1"))
    # 30% (3,000) beats 10% (1,000) -- the campaign wins, never both at once.
    assert order.discount_minor == 3_000
    assert order.discount_source == "campaign:snd_hi"


def test_the_higher_value_offer_wins_referral_over_campaign():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    desk = FakeDiscountDesk({"ref": "snd_lo", "reward_kind": "percent", "reward_amount": 5,
                             "scope_service_ids": [], "expires_at": 9_999_999_999})
    referral = FakeReferralEngine({"eligible": True, "new_customer_reward_type": "discount_percent",
                                   "new_customer_reward_params": {"percent": 25}})
    s = _service(store, desk, referral_engine=referral)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_both2"))
    assert order.discount_minor == 2_500
    assert order.discount_source == f"referral:+966501234567"


def test_confirming_payment_redeems_a_referral_discount_through_operations():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    referral = FakeReferralEngine({"eligible": True, "new_customer_reward_type": "discount_percent",
                                   "new_customer_reward_params": {"percent": 10}})
    s = _service(store, referral_engine=referral)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_ref2"))
    assert referral.redeemed == [], "a referral discount must not be spent before payment lands"
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=order.amount_due_minor,
                          payment_ref="pay_ref_ref2"))
    assert len(referral.redeemed) == 1
    assert referral.redeemed[0]["phone"] == "+966501234567"
    assert referral.redeemed[0]["visit_id"] == f"order:{order.id}"


def test_a_customer_not_eligible_for_a_referral_discount_gets_an_ordinary_order():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    referral = FakeReferralEngine(None)
    s = _service(store, referral_engine=referral)

    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_ref3"))
    assert order.discount_minor == 0
    assert order.discount_source == ""


# ── loyalty points rewards -- discount-type only, customer's own explicit choice ────────────────

class FakeLoyaltyDesk:
    """Mirrors LoyaltyDesk's own {balance, redeem} shape."""

    def __init__(self, rewards=None):
        self.rewards = rewards or []
        self.redeemed = []
        self._redeemed_keys = {}

    async def balance(self, *, tenant, subject_ref):
        return {"has_programme": True, "points": 500, "rewards": self.rewards,
               "to_next_reward": 0, "expires_at": 0}

    async def redeem(self, *, tenant, subject_ref, reward_id, idempotency_key, actor="",
                     branch_id=""):
        if idempotency_key in self._redeemed_keys:
            return self._redeemed_keys[idempotency_key]
        reward = next((r for r in self.rewards if r["id"] == reward_id), None)
        if reward is None:
            return {"_status": 404}
        out = {"redemption": {"reward_name": reward["name"], "reward_type": reward["type"],
                              "cost": reward["cost"],
                              "discount_halalas": reward.get("discount_halalas", 0)},
              "balance": 500 - reward["cost"], "duplicate": False}
        self.redeemed.append({"tenant": tenant, "subject_ref": subject_ref,
                              "reward_id": reward_id, "idempotency_key": idempotency_key})
        self._redeemed_keys[idempotency_key] = out
        return out


def _service_with_loyalty(store, *, loyalty=None) -> OrderService:
    ops = Operations(store=store, pii_salt="s" * 32)
    return OrderService(store=store, services=ServiceStore(store), branches=BranchStore(store),
                        operations=ops, payments=FakePaymentsDesk(), loyalty=loyalty)


def test_a_discount_type_reward_is_offered_when_affordable():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_1", "name": "خصم 10 ريال", "cost": 50, "type": "discount",
         "discount_halalas": 1_000, "active": True},
    ])
    s = _service_with_loyalty(store, loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts1"))

    offer = run(s.available_points_reward(TENANT, order.id))
    assert offer == {"id": "rwd_1", "name": "خصم 10 ريال", "cost": 50, "minor": 1_000}


def test_service_and_item_type_rewards_are_never_offered_to_an_order():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_svc", "name": "غسيل مجاني", "cost": 50, "type": "service",
         "service_id": sid, "active": True},
        {"id": "rwd_item", "name": "عطر مجاني", "cost": 30, "type": "item", "active": True},
    ])
    s = _service_with_loyalty(store, loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts2"))
    assert run(s.available_points_reward(TENANT, order.id)) is None


def test_redeeming_a_points_reward_suppresses_an_already_held_campaign_discount():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    desk = FakeDiscountDesk({"ref": "snd_pts", "reward_kind": "percent", "reward_amount": 20,
                            "scope_service_ids": [], "expires_at": 9_999_999_999})
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_2", "name": "خصم 15 ريال", "cost": 80, "type": "discount",
         "discount_halalas": 1_500, "active": True},
    ])
    ops = Operations(store=store, pii_salt="s" * 32)
    s = OrderService(store=store, services=ServiceStore(store), branches=BranchStore(store),
                     operations=ops, payments=FakePaymentsDesk(),
                     discounts=desk.as_dict(), loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts3"))
    assert order.discount_minor == 2_000

    redeemed = run(s.redeem_points_reward(TENANT, order.id, reward_id="rwd_2"))
    assert redeemed.points_reward_minor == 1_500
    assert redeemed.points_reward_name == "خصم 15 ريال"
    assert redeemed.discount_minor == 0 and redeemed.discount_source == ""
    assert redeemed.amount_due_minor == 10_000 - 1_500


def test_redeeming_points_releases_the_campaign_discount_claim_for_a_future_order():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    desk = FakeDiscountDesk({"ref": "snd_release", "reward_kind": "percent", "reward_amount": 20,
                            "scope_service_ids": [], "expires_at": 9_999_999_999})
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_3", "name": "خصم 5 ريال", "cost": 20, "type": "discount",
         "discount_halalas": 500, "active": True},
    ])
    ops = Operations(store=store, pii_salt="s" * 32)
    s = OrderService(store=store, services=ServiceStore(store), branches=BranchStore(store),
                     operations=ops, payments=FakePaymentsDesk(),
                     discounts=desk.as_dict(), loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts4a"))
    run(s.redeem_points_reward(TENANT, order.id, reward_id="rwd_3"))

    second = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                         items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts4b"))
    assert second.discount_minor == 2_000


def test_an_unaffordable_reward_is_never_offered():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))

    class _PoorLoyalty(FakeLoyaltyDesk):
        async def balance(self, *, tenant, subject_ref):
            return {"has_programme": True, "points": 10, "rewards": [], "to_next_reward": 40,
                   "expires_at": 0}

    loyalty = _PoorLoyalty()
    s = _service_with_loyalty(store, loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts5"))
    assert run(s.available_points_reward(TENANT, order.id)) is None


def test_redeeming_a_reward_is_refused_once_the_order_is_already_paid():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_4", "name": "خصم 5 ريال", "cost": 20, "type": "discount",
         "discount_halalas": 500, "active": True},
    ])
    s = _service_with_loyalty(store, loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts6"))
    run(s.confirm_payment(TENANT, order.id, paid_amount_minor=order.amount_due_minor,
                          payment_ref="pay_ref_pts6"))

    from app.core.orders import OrderError
    try:
        run(s.redeem_points_reward(TENANT, order.id, reward_id="rwd_4"))
        assert False, "must refuse once the order is no longer awaiting payment"
    except OrderError:
        pass
    assert loyalty.redeemed == []


# ── deeper edge cases: insufficient points, malformed rewards, caps, concurrency ─────────────────

class _OverdraftLoyalty(FakeLoyaltyDesk):
    """Mirrors the real `loyalty_desk.py::_call()`'s own shape for a genuine 409 refusal
    (insufficient points) -- `_status`/`_reason` present, never a bare `None` (peer-down)."""

    async def redeem(self, *, tenant, subject_ref, reward_id, idempotency_key, actor="",
                     branch_id=""):
        return {"_status": 409, "_reason": "الرصيد 10 نقطة، والمكافأة 50 — لا يكفي"}


def test_insufficient_points_relays_the_real_refusal_sentence_not_a_generic_one():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    loyalty = _OverdraftLoyalty()
    s = _service_with_loyalty(store, loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts7"))

    from app.core.orders import OrderError
    try:
        run(s.redeem_points_reward(TENANT, order.id, reward_id="rwd_x"))
        assert False, "insufficient points must refuse"
    except OrderError as exc:
        assert "لا يكفي" in str(exc), "the real loyalty refusal sentence must reach the customer"


def test_redeeming_an_unknown_reward_id_is_refused_cleanly():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    loyalty = FakeLoyaltyDesk([{"id": "rwd_real", "name": "خصم", "cost": 10, "type": "discount",
                               "discount_halalas": 500, "active": True}])
    s = _service_with_loyalty(store, loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts8"))

    from app.core.orders import OrderError
    try:
        run(s.redeem_points_reward(TENANT, order.id, reward_id="rwd_does_not_exist"))
        assert False, "an unknown reward_id must be refused, never silently accepted"
    except OrderError:
        pass


def test_a_fixed_halalas_reward_worth_more_than_the_order_is_capped_not_overcharged_negative():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=1_000))  # a cheap order, 10 ريال
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_big", "name": "خصم 50 ريال", "cost": 10, "type": "discount",
         "discount_halalas": 5_000, "active": True},
    ])
    s = _service_with_loyalty(store, loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts9"))

    offer = run(s.available_points_reward(TENANT, order.id))
    assert offer["minor"] == 1_000, "the offer itself must already be capped at the order total"

    redeemed = run(s.redeem_points_reward(TENANT, order.id, reward_id="rwd_big"))
    assert redeemed.points_reward_minor == 1_000
    assert redeemed.amount_due_minor == 0, "never negative"


def test_the_cheapest_of_several_affordable_discount_rewards_is_offered():
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_expensive", "name": "خصم كبير", "cost": 200, "type": "discount",
         "discount_halalas": 3_000, "active": True},
        {"id": "rwd_cheap", "name": "خصم صغير", "cost": 20, "type": "discount",
         "discount_halalas": 500, "active": True},
    ])
    s = _service_with_loyalty(store, loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts10"))

    offer = run(s.available_points_reward(TENANT, order.id))
    assert offer["id"] == "rwd_cheap", "cheapest (fewest points spent) is offered, not biggest"


def test_a_reward_with_zero_discount_halalas_is_never_offered_even_if_typed_discount():
    """A malformed/misconfigured reward row (`type == "discount"` but no real amount) must never
    be surfaced as if it were worth something."""
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_broken", "name": "خصم معطّل", "cost": 5, "type": "discount",
         "discount_halalas": 0, "active": True},
    ])
    s = _service_with_loyalty(store, loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts11"))
    assert run(s.available_points_reward(TENANT, order.id)) is None


def test_redeeming_points_is_a_genuine_no_op_release_when_no_discount_was_ever_held():
    """`redeem_points_reward`'s own discount-claim release must never raise or behave oddly when
    the order held no discount at all to begin with -- the common case."""
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_only", "name": "خصم 5 ريال", "cost": 20, "type": "discount",
         "discount_halalas": 500, "active": True},
    ])
    s = _service_with_loyalty(store, loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts12"))
    assert order.discount_source == ""

    redeemed = run(s.redeem_points_reward(TENANT, order.id, reward_id="rwd_only"))
    assert redeemed.points_reward_minor == 500
    assert redeemed.discount_source == ""


def test_retrying_the_same_points_redemption_settles_on_the_same_outcome_not_a_second_charge():
    """loyalty's OWN idempotency key (`order:{id}`) is what actually prevents a double-spend -- a
    retried call (a webhook redelivery of the button tap, or a flaky connection) must settle on
    the identical result, never charge the customer's points twice."""
    store = MemoryDataStore()
    sid, bid = run(_seed(store, price_minor=10_000))
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_retry", "name": "خصم 10 ريال", "cost": 50, "type": "discount",
         "discount_halalas": 1_000, "active": True},
    ])
    s = _service_with_loyalty(store, loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts13"))

    first = run(s.redeem_points_reward(TENANT, order.id, reward_id="rwd_retry"))
    second = run(s.redeem_points_reward(TENANT, order.id, reward_id="rwd_retry"))
    assert first.points_reward_minor == second.points_reward_minor == 1_000
    assert len(loyalty.redeemed) == 1, "loyalty's own idempotency key must stop a second charge"


def test_available_points_reward_with_no_subject_ref_is_silently_none():
    """An order resolved with no `Operations` peer at all (no customer resolution) has no
    `subject_ref` -- the same `None`, no-gap posture every optional peer here already takes."""
    store = MemoryDataStore()
    sid, bid = run(_seed(store))
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_1", "name": "خصم", "cost": 10, "type": "discount",
         "discount_halalas": 500, "active": True},
    ])
    s = OrderService(store=store, services=ServiceStore(store), branches=BranchStore(store),
                     operations=None, payments=FakePaymentsDesk(), loyalty=loyalty)
    order = run(s.create(tenant=TENANT, branch_id=bid, phone=PHONE, customer_name="سالم",
                        items=[(sid, 1)], lat=LAT, lng=LNG, idempotency_key="evt_pts14"))
    assert order.subject_ref == ""
    assert run(s.available_points_reward(TENANT, order.id)) is None
