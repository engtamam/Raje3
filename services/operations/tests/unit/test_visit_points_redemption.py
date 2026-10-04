"""The till/field screen's own «استبدال نقاط» door — the second "old app" migrated to the
unified discounts/points system (2026-10-04), mirroring `core/orders.py::OrderService`'s own
points methods, but mutually exclusive with `apply_offer` by occupying the SAME one-slot
`offer_ref` rather than a separate reserve/suppress phase (see `redeem_points_reward`'s own
docstring for exactly why a visit cannot use the order side's "reserve now, spend at payment"
shape at all).
"""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.operations import OperationError, Operations
from app.core.stores import VisitStore

TENANT = "tnt_pts"
PHONE = "0533334444"


def run(coro):
    return asyncio.run(coro)


class FakeLoyaltyDesk:
    """Mirrors LoyaltyDesk's own {balance, redeem} shape — same double test_order_discounts.py
    already uses for the identical peer contract."""

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
            return {"_status": 404, "_reason": "رصيدك لا يكفي لهذه المكافأة."}
        out = {"redemption": {"reward_name": reward["name"], "reward_type": reward["type"],
                              "cost": reward["cost"],
                              "discount_halalas": reward.get("discount_halalas", 0)},
              "balance": 500 - reward["cost"], "duplicate": False}
        self.redeemed.append({"tenant": tenant, "subject_ref": subject_ref,
                              "reward_id": reward_id, "idempotency_key": idempotency_key})
        self._redeemed_keys[idempotency_key] = out
        return out


def _ops_with_loyalty(store, *, loyalty=None) -> Operations:
    ops = Operations(store=store, pii_salt="s" * 32)
    if loyalty is not None:
        ops.with_loyalty_desk(loyalty)
    return ops


def test_a_discount_type_reward_is_offered_when_affordable():
    store = MemoryDataStore()
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_1", "name": "خصم 10 ريال", "cost": 50, "type": "discount",
         "discount_halalas": 1_000, "active": True}])
    ops = _ops_with_loyalty(store, loyalty=loyalty)
    v = run(ops.record_visit(tenant=TENANT, phone=PHONE, service_ids=["srv_1"],
                             total_minor=5_000))

    offer = run(ops.available_points_reward(TENANT, v.visit.id))
    assert offer == {"id": "rwd_1", "name": "خصم 10 ريال", "cost": 50, "minor": 1_000}


def test_service_and_item_type_rewards_are_never_offered_to_a_visit():
    """Same structural exclusion `OrderService.available_points_reward` already documents —
    redeeming either makes `services/loyalty` itself record a visit, and this visit already IS
    one."""
    store = MemoryDataStore()
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_svc", "name": "غسيل مجاني", "cost": 50, "type": "service", "active": True},
        {"id": "rwd_item", "name": "عطر مجاني", "cost": 30, "type": "item", "active": True}])
    ops = _ops_with_loyalty(store, loyalty=loyalty)
    v = run(ops.record_visit(tenant=TENANT, phone=PHONE, service_ids=["srv_1"],
                             total_minor=5_000))
    assert run(ops.available_points_reward(TENANT, v.visit.id)) is None


def test_no_loyalty_desk_wired_answers_nothing_not_a_refusal():
    store = MemoryDataStore()
    ops = Operations(store=store, pii_salt="s" * 32)          # no with_loyalty_desk at all
    v = run(ops.record_visit(tenant=TENANT, phone=PHONE, service_ids=["srv_1"]))
    assert run(ops.available_points_reward(TENANT, v.visit.id)) is None


def test_the_offered_discount_is_capped_by_the_real_invoice_when_one_is_known():
    store = MemoryDataStore()
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_big", "name": "خصم ضخم", "cost": 50, "type": "discount",
         "discount_halalas": 50_000, "active": True}])
    ops = _ops_with_loyalty(store, loyalty=loyalty)
    v = run(ops.record_visit(tenant=TENANT, phone=PHONE, service_ids=["srv_1"],
                             total_minor=3_000))
    offer = run(ops.available_points_reward(TENANT, v.visit.id))
    assert offer["minor"] == 3_000


def test_redeeming_a_points_reward_stamps_the_visits_one_offer_slot():
    store = MemoryDataStore()
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_1", "name": "قهوة مجانية", "cost": 50, "type": "discount",
         "discount_halalas": 1_000, "active": True}])
    ops = _ops_with_loyalty(store, loyalty=loyalty)
    v = run(ops.record_visit(tenant=TENANT, phone=PHONE, service_ids=["srv_1"],
                             total_minor=5_000))

    applied = run(ops.redeem_points_reward(TENANT, v.visit.id, reward_id="rwd_1"))
    assert "قهوة مجانية" in applied["text"]
    assert "10.00 ريال" in applied["text"]
    assert applied["ref"].startswith("points:rwd_1:")

    stored = run(VisitStore(store).get(TENANT, v.visit.id))
    assert stored.offer_ref == applied["ref"]


def test_a_second_tap_on_points_replays_the_same_redemption_never_a_second_spend():
    store = MemoryDataStore()
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_1", "name": "قهوة مجانية", "cost": 50, "type": "discount",
         "discount_halalas": 1_000, "active": True}])
    ops = _ops_with_loyalty(store, loyalty=loyalty)
    v = run(ops.record_visit(tenant=TENANT, phone=PHONE, service_ids=["srv_1"]))

    first = run(ops.redeem_points_reward(TENANT, v.visit.id, reward_id="rwd_1"))
    second = run(ops.redeem_points_reward(TENANT, v.visit.id, reward_id="rwd_1"))
    assert first == second
    assert len(loyalty.redeemed) == 1


def test_points_arriving_after_apply_offer_already_stamped_the_visit_finds_the_slot_taken():
    """`apply_offer` already consumed ITS chosen entitlement the instant it was tapped (no later
    "reserve, then confirm" phase a visit could suppress) — so a cashier reaching for points
    AFTER that tap must get back the offer that already won, never a second discount stacked on
    top of the first."""
    store = MemoryDataStore()
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_1", "name": "قهوة مجانية", "cost": 50, "type": "discount",
         "discount_halalas": 1_000, "active": True}])
    ops = _ops_with_loyalty(store, loyalty=loyalty)

    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return {"ref": "camp_1", "text": "خصم حملة", "campaign_id": "camp"}

    ops.with_offer_chooser(campaign_chooser)
    v = run(ops.record_visit(tenant=TENANT, phone=PHONE, service_ids=["srv_1"]))

    campaign_applied = run(ops.apply_offer(tenant=TENANT, visit_id=v.visit.id,
                                           subject_ref="sub_x"))
    assert campaign_applied["ref"] == "camp_1"

    points_attempt = run(ops.redeem_points_reward(TENANT, v.visit.id, reward_id="rwd_1"))
    assert points_attempt["ref"] == "camp_1"            # the slot was already taken
    assert len(loyalty.redeemed) == 0                   # points were never actually spent


def test_apply_offer_after_points_already_stamped_the_visit_finds_the_slot_taken_too():
    """The exact symmetric case — whichever of the two is tapped FIRST wins the one slot."""
    store = MemoryDataStore()
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_1", "name": "قهوة مجانية", "cost": 50, "type": "discount",
         "discount_halalas": 1_000, "active": True}])
    ops = _ops_with_loyalty(store, loyalty=loyalty)

    async def campaign_chooser(*, tenant, subject_ref, service_ids):
        return {"ref": "camp_1", "text": "خصم حملة", "campaign_id": "camp"}

    ops.with_offer_chooser(campaign_chooser)
    v = run(ops.record_visit(tenant=TENANT, phone=PHONE, service_ids=["srv_1"]))

    points_applied = run(ops.redeem_points_reward(TENANT, v.visit.id, reward_id="rwd_1"))
    assert points_applied["ref"].startswith("points:")

    campaign_attempt = run(ops.apply_offer(tenant=TENANT, visit_id=v.visit.id,
                                           subject_ref="sub_x"))
    assert campaign_attempt["ref"] == points_applied["ref"]     # the slot was already taken


def test_insufficient_points_relays_the_real_refusal_sentence_not_a_generic_one():
    store = MemoryDataStore()
    loyalty = FakeLoyaltyDesk([])                        # the reward id below does not exist
    ops = _ops_with_loyalty(store, loyalty=loyalty)
    v = run(ops.record_visit(tenant=TENANT, phone=PHONE, service_ids=["srv_1"]))

    try:
        run(ops.redeem_points_reward(TENANT, v.visit.id, reward_id="rwd_missing"))
        assert False, "expected an OperationError"
    except OperationError as exc:
        assert "رصيدك لا يكفي" in str(exc)

    stored = run(VisitStore(store).get(TENANT, v.visit.id))
    assert stored.offer_ref == ""                        # never stamped on a real refusal


def test_a_service_or_item_type_reward_id_is_refused_not_silently_applied():
    """A cashier (or a stale client) sending the id of a service/item reward must be refused —
    the backend never trusts the TYPE off the caller's own earlier read."""
    store = MemoryDataStore()
    loyalty = FakeLoyaltyDesk([
        {"id": "rwd_svc", "name": "غسيل مجاني", "cost": 50, "type": "service", "active": True}])
    ops = _ops_with_loyalty(store, loyalty=loyalty)
    v = run(ops.record_visit(tenant=TENANT, phone=PHONE, service_ids=["srv_1"]))

    try:
        run(ops.redeem_points_reward(TENANT, v.visit.id, reward_id="rwd_svc"))
        assert False, "expected an OperationError"
    except OperationError:
        pass
    stored = run(VisitStore(store).get(TENANT, v.visit.id))
    assert stored.offer_ref == ""
