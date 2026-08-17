"""Rewards, and spending points — the receipt that cannot be forged."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.ledger import Ledger
from app.core.models import REDEMPTIONS, LoyaltyError, Overdraft
from app.core.notify import Notifier, receipt_text, to_next_reward
from app.core.redeem import Redeemer
from app.core.rewards import Rewards, validate_name

T = "shop"
S = "ref_abcdef123456"


def run(c):
    return asyncio.run(c)


def build():
    store = MemoryDataStore()
    ledger = Ledger(store)
    rewards = Rewards(store)
    return store, ledger, rewards, Redeemer(store, ledger, rewards)


def give(ledger, points, source="seed"):
    run(ledger.post(tenant=T, subject_ref=S, delta=points, reason="earn", source=source))


class Sender:
    """Stands in for reminders' gate — which is the only thing that decides."""

    def __init__(self, sent=True):
        self.calls = []
        self._sent = sent

    async def send(self, **kw):
        self.calls.append(kw)
        return {"sent": self._sent}


# ── the reward catalogue ───────────────────────────────────────────────────────────────────────
def test_a_reward_is_not_a_service_and_needs_no_catalogue_row():
    _, _, rewards, _ = build()
    r = run(rewards.create(T, name="قهوة", cost=50, type="item"))
    assert r.type == "item" and r.service_id == ""


def test_a_service_reward_must_name_the_service_it_is():
    """Without it, "free wash" is a name: no visit recorded, so the reminder cycle never restarts."""
    _, _, rewards, _ = build()
    with pytest.raises(LoyaltyError):
        run(rewards.create(T, name="غسلة مجانية", cost=200, type="service"))


def test_a_name_too_long_for_a_message_is_refused_at_save_with_the_limit_named():
    _, _, rewards, _ = build()
    with pytest.raises(LoyaltyError) as exc:
        run(rewards.create(T, name="غ" * 41, cost=10, type="item"))
    # The rule, not "invalid": an owner told only that his input is wrong tries again and calls
    # support.
    assert "40" in str(exc.value)


@pytest.mark.parametrize("bad", ["a\nb", "{{1}}", "wash‮", "x"])
def test_a_name_that_would_break_a_message_is_refused(bad):
    with pytest.raises(LoyaltyError):
        validate_name(bad)


def test_affordable_returns_only_what_the_balance_can_buy():
    """Showing a customer at the counter what he cannot have is worse than his not knowing."""
    _, ledger, rewards, _ = build()
    run(rewards.create(T, name="قهوة", cost=50, type="item"))
    run(rewards.create(T, name="غسلة", cost=500, type="item"))
    assert [r.name for r in run(rewards.affordable(T, 100))] == ["قهوة"]


def test_another_shops_reward_is_not_found_rather_than_forbidden():
    """A 403 would confirm the id exists — which says something about another establishment."""
    _, _, rewards, _ = build()
    r = run(rewards.create(T, name="قهوة", cost=50, type="item"))
    with pytest.raises(LoyaltyError):
        run(rewards.get("other-shop", r.id))


# ── spending ───────────────────────────────────────────────────────────────────────────────────
def test_a_redemption_deducts_and_snapshots_the_reward():
    _, ledger, rewards, red = build()
    give(ledger, 300)
    r = run(rewards.create(T, name="غسلة", cost=200, type="item"))
    rec, is_new = run(red.redeem(T, S, r.id, actor="emp-7", idem_key="k1"))
    assert is_new and rec.cost == 200 and rec.reward_name == "غسلة" and rec.actor == "emp-7"
    assert run(ledger.balance(T, S)).points == 100


def test_the_snapshot_survives_the_reward_being_repriced():
    """A receipt that restates itself when the menu changes is not a receipt."""
    _, ledger, rewards, red = build()
    give(ledger, 300)
    r = run(rewards.create(T, name="غسلة", cost=200, type="item"))
    rec, _ = run(red.redeem(T, S, r.id, idem_key="k1"))
    run(rewards.update(T, r.id, name="غسلة ممتازة", cost=400))
    stored = run(red.history(T, S))[0]
    assert stored["reward_name"] == "غسلة" and stored["cost"] == 200


def test_an_overdraft_is_refused():
    _, ledger, rewards, red = build()
    give(ledger, 50)
    r = run(rewards.create(T, name="غسلة", cost=200, type="item"))
    with pytest.raises(Overdraft):
        run(red.redeem(T, S, r.id, idem_key="k1"))
    assert run(ledger.balance(T, S)).points == 50


def test_the_same_key_twice_spends_once():
    """A phone in a service lane retries; the customer must not be charged for one reward twice."""
    _, ledger, rewards, red = build()
    give(ledger, 500)
    r = run(rewards.create(T, name="غسلة", cost=200, type="item"))
    first, new1 = run(red.redeem(T, S, r.id, idem_key="k1"))
    second, new2 = run(red.redeem(T, S, r.id, idem_key="k1"))
    assert new1 is True and new2 is False
    assert first.id == second.id
    assert run(ledger.balance(T, S)).points == 300


def test_a_reward_above_the_threshold_needs_a_manager():
    _, ledger, rewards, red = build()
    give(ledger, 900)
    r = run(rewards.create(T, name="غيار زيت", cost=800, type="item"))
    with pytest.raises(LoyaltyError):
        run(red.redeem(T, S, r.id, idem_key="k1", manager_threshold=500))
    rec, _ = run(red.redeem(T, S, r.id, idem_key="k2", manager_threshold=500,
                            approved_by="mgr-1"))
    assert rec.approved_by == "mgr-1"


def test_an_ordinary_reward_below_the_threshold_needs_nobody():
    """The operator spends. A manager on every redemption is a bottleneck, so the programme dies."""
    _, ledger, rewards, red = build()
    give(ledger, 900)
    r = run(rewards.create(T, name="قهوة", cost=50, type="item"))
    _, is_new = run(red.redeem(T, S, r.id, idem_key="k1", manager_threshold=500))
    assert is_new


def test_a_retired_reward_cannot_be_spent():
    _, ledger, rewards, red = build()
    give(ledger, 900)
    r = run(rewards.create(T, name="قهوة", cost=50, type="item"))
    run(rewards.update(T, r.id, active=False))
    with pytest.raises(LoyaltyError):
        run(red.redeem(T, S, r.id, idem_key="k1"))


def test_the_till_and_the_field_produce_the_same_entry_but_for_the_channel():
    """A fallback that records differently is a reporting bug waiting for month end."""
    _, ledger, rewards, red = build()
    give(ledger, 900)
    r = run(rewards.create(T, name="قهوة", cost=50, type="item"))
    a, _ = run(red.redeem(T, S, r.id, idem_key="k1", channel="field", actor="emp"))
    b, _ = run(red.redeem(T, S, r.id, idem_key="k2", channel="till", actor="cashier-3"))
    ignore = {"id", "idem_key", "channel", "actor", "created_at"}
    assert {k: v for k, v in a.to_dict().items() if k not in ignore} == \
           {k: v for k, v in b.to_dict().items() if k not in ignore}


# ── what the customer is told ──────────────────────────────────────────────────────────────────
def test_the_receipt_carries_three_facts_in_western_digits():
    text = receipt_text(reward_name="غسلة", cost=200, remaining=40)
    assert "200" in text and "40" in text and "غسلة" in text
    # Built from code points rather than written out: the digits guard is literal, and it is
    # right to be — a file containing them is a file somebody copies a line from.
    assert not any(0x0660 <= ord(ch) <= 0x0669 for ch in text)


def test_the_receipt_is_personal_so_it_reaches_a_customer_who_stopped_marketing():
    sender = Sender()
    run(Notifier(sender).receipt(tenant=T, subject_ref=S, redemption_id="rdm_1",
                                 reward_name="غسلة", cost=200, remaining=40))
    call = sender.calls[0]
    # PERSONAL is what makes the gate exempt it from the quiet hours and the cap. We ask; it
    # decides. Nothing here implements an exemption.
    assert call["cls"] == "personal"
    assert call["template_type"] == "per_account_notice"
    assert call["idempotency_key"] == "loyalty:receipt:rdm_1"


def test_the_expiry_warning_is_never_marketing():
    """Classed as marketing, whoever refused marketing would lose points without being told.

    AND IT IS `personal`, WHICH IS WHAT THE LIBRARY SAYS. It was sent as `service` here while the
    template declared `personal`, so the gate applied the wrong caps and the answer to "what class
    is this message" depended on which file you read."""
    sender = Sender()
    run(Notifier(sender).expiry_warning(tenant=T, subject_ref=S, points=80, days=14,
                                        cycle_key="c1"))
    assert sender.calls[0]["cls"] == "personal"
    assert sender.calls[0]["template_type"] == "per_points_expiring"


def test_nothing_to_say_when_every_reward_is_affordable():
    assert to_next_reward(500, [50, 200]) == 0
    assert to_next_reward(100, []) == 0
    assert to_next_reward(100, [50, 250, 900]) == 150


# ── who benefits, and where the programme is invisible (spec §9.9, §9.10) ──────────────────────
def test_a_customer_who_stopped_marketing_earns_and_redeems_like_anyone():
    """The points are his. What he loses is the BALANCE message, not the balance (spec §9.9)."""
    _, ledger, rewards, red = build()
    give(ledger, 300)
    r = run(rewards.create(T, name="قهوة", cost=50, type="item"))
    rec, is_new = run(red.redeem(T, S, r.id, idem_key="k1"))
    # Nothing in this path consults a marketing preference — and that absence IS the rule. The
    # receipt is `personal`, so the gate delivers it to him too (see the receipt test above).
    assert is_new and run(ledger.balance(T, S)).points == 250


def test_the_balance_is_one_across_a_chains_branches():
    """Branches share a tenant, so earn-here-redeem-there needs no code — and this proves it."""
    _, ledger, rewards, red = build()
    run(ledger.post(tenant=T, subject_ref=S, delta=200, reason="earn", source="branch-a-visit"))
    r = run(rewards.create(T, name="غسلة", cost=150, type="item"))
    run(red.redeem(T, S, r.id, idem_key="branch-b-key"))
    assert run(ledger.balance(T, S)).points == 50


def test_the_report_names_the_outstanding_obligation_and_the_warning():
    import asyncio as _a
    from app.core.report import build as build_report
    store, ledger, rewards, red = build()
    give(ledger, 300, source="v1")
    r = run(rewards.create(T, name="قهوة", cost=50, type="item"))
    run(red.redeem(T, S, r.id, idem_key="k1"))
    run(ledger.post(tenant=T, subject_ref="ref_lapsed00000", delta=100, reason="earn",
                    source="v2"))
    run(ledger.post(tenant=T, subject_ref="ref_lapsed00000", delta=-100, reason="expire",
                    source="e2"))
    rep = _a.run(build_report(store, T))
    assert rep["granted"] == 400 and rep["consumed"] == 50 and rep["expired_unredeemed"] == 100
    # The obligation still standing — the number with money behind it.
    assert rep["outstanding"] == 250
    # The warning: a quarter of everything granted died unspent, so the thresholds are out of reach.
    assert rep["expired_share"] == 0.25
    assert rep["top_rewards"] == [("قهوة", 1)]


def test_a_manager_approval_cannot_be_granted_by_the_person_redeeming():
    """THE CONTROL THAT WAS A LABEL.

    The check was «is this string non-empty», and the string is typed by the operator doing the
    redeeming. So on exactly the redemptions expensive enough to have earned a threshold, the
    approval was «type any name to continue» — granted by the person it exists to check.
    """
    _, ledger, rewards, red = build()
    give(ledger, 900)
    r = run(rewards.create(T, name="غيار زيت", cost=800, type="item"))

    with pytest.raises(LoyaltyError) as e:
        run(red.redeem(T, S, r.id, idem_key="k1", manager_threshold=500,
                       actor="سالم", approved_by="سالم"))

    assert "من الشخص نفسه" in str(e.value)


def test_the_same_name_in_a_different_case_is_still_the_same_person():
    """«Salem» and « salem » are one man with one keyboard. A control defeated by a space is a
    control somebody will defeat with a space."""
    _, ledger, rewards, red = build()
    give(ledger, 900)
    r = run(rewards.create(T, name="غيار زيت", cost=800, type="item"))

    with pytest.raises(LoyaltyError):
        run(red.redeem(T, S, r.id, idem_key="k2", manager_threshold=500,
                       actor="Salem", approved_by=" salem "))


def test_a_different_person_may_still_approve_it():
    """The control must not block the thing it exists to permit."""
    _, ledger, rewards, red = build()
    give(ledger, 900)
    r = run(rewards.create(T, name="غيار زيت", cost=800, type="item"))

    rec, _ = run(red.redeem(T, S, r.id, idem_key="k3", manager_threshold=500,
                            actor="سالم", approved_by="فهد"))

    assert rec.approved_by == "فهد"


# ── one customer's balance, one spender at a time ──────────────────────────────────────────────
def test_two_simultaneous_redemptions_cannot_overspend_one_balance():
    """THE DEFECT. `Ledger.post` reads the balance, checks the overdraft, then writes — and the
    datastore's only write is an unconditional upsert, with no compare-and-set anywhere in the
    platform's port. This product opens TWO redemption doors on purpose: the field phone and the
    integrated till. A customer with 100 points, at branch A's till while a cashier at branch B
    redeems for him in the same second, walks away with BOTH rewards — the shop gives away twice
    what he paid for, and the ledger sums to a negative number no screen can explain.

    Driven through the real `MemoryCache`, so what is under test is the adapter's own atomicity
    rather than a fake that agrees with the design."""
    from app.adapters.cache.memory import MemoryCache
    from app.core.spend_lock import SpendBusy

    st = MemoryDataStore()
    ledger, rewards = Ledger(st), Rewards(st)
    r = Redeemer(st, ledger, rewards, cache=MemoryCache())

    async def scenario():
        rw = await rewards.create(T, name="جائزة", cost=100, type="item")
        await ledger.post(tenant=T, subject_ref=S, delta=100, reason="earn", source="v1")

        held, release = asyncio.Event(), asyncio.Event()
        original = ledger.balance

        async def slow_balance(tenant, subject_ref):
            out = await original(tenant, subject_ref)
            if not held.is_set():
                held.set()
                await release.wait()          # the second caller arrives INSIDE the window
            return out

        ledger.balance = slow_balance         # type: ignore[assignment]
        first = asyncio.create_task(r.redeem(T, S, rw.id, idem_key="k-a", actor="a"))
        await held.wait()

        second = asyncio.create_task(r.redeem(T, S, rw.id, idem_key="k-b", actor="b"))
        await asyncio.sleep(0)
        release.set()
        rec, _ = await first
        assert rec.cost == 100
        with pytest.raises(SpendBusy):
            await second

        ledger.balance = original             # type: ignore[assignment]
        # AND THE LEDGER IS NOT NEGATIVE, which is the number a screen would have had to explain.
        assert (await ledger.balance(T, S)).points == 0

    run(scenario())


def test_the_lock_is_released_so_the_next_redemption_is_not_refused():
    """A lock that is not released turns one race into a customer who can never spend again."""
    from app.adapters.cache.memory import MemoryCache

    st = MemoryDataStore()
    ledger, rewards = Ledger(st), Rewards(st)
    r = Redeemer(st, ledger, rewards, cache=MemoryCache())

    async def scenario():
        rw = await rewards.create(T, name="شاي", cost=10, type="item")
        await ledger.post(tenant=T, subject_ref=S, delta=100, reason="earn", source="v1")
        await r.redeem(T, S, rw.id, idem_key="k-1", actor="a")
        await r.redeem(T, S, rw.id, idem_key="k-2", actor="a")
        assert (await ledger.balance(T, S)).points == 80

    run(scenario())


def test_a_cache_that_cannot_be_asked_refuses_rather_than_assumes_nobody_is_spending():
    """«We could not check» must never render as «nobody is»: that is the fail-open shape, and here
    it costs the shop a reward it did not sell."""
    from app.core.spend_lock import SpendBusy

    class Broken:
        driver = "broken"

        async def set_if_absent(self, key, value, ttl_seconds=None):
            raise OSError("cache is gone")

        async def delete(self, key):
            return False

    st = MemoryDataStore()
    ledger, rewards = Ledger(st), Rewards(st)
    r = Redeemer(st, ledger, rewards, cache=Broken())

    async def scenario():
        rw = await rewards.create(T, name="قهوة", cost=10, type="item")
        await ledger.post(tenant=T, subject_ref=S, delta=100, reason="earn", source="v1")
        with pytest.raises(SpendBusy):
            await r.redeem(T, S, rw.id, idem_key="k-x", actor="a")
        assert (await ledger.balance(T, S)).points == 100

    run(scenario())


# ── the crash between the deduction and the receipt ────────────────────────────────────────────
#
# THE DOUBLE DEDUCTION, ASSERTED AS A BALANCE. The ledger movement is posted first — deliberately,
# so a crash leaves points deducted with no receipt rather than a receipt for points still in the
# account. That ordering is right. What was wrong is that the retry had no way to recognise the
# earlier attempt: it looked for the receipt (absent), and the ledger compared a NEW uuid against
# the old one and waved it through.
#
# These read the BALANCE, not the return value. A test that asserted `is_new is False` would have
# passed against a version that deducted twice and reported honestly about the second one.
def test_a_crash_before_the_receipt_does_not_deduct_twice():
    store, ledger, rewards, red = build()
    give(ledger, 1000)
    r = run(rewards.create(T, name="قهوة", cost=168, type="item"))

    # Attempt one: the ledger moves, then the process dies before REDEMPTIONS is written.
    boom = RuntimeError("pod evicted between the deduction and the receipt")
    original = store.put

    async def die(collection, key, row):
        if collection == REDEMPTIONS:
            raise boom
        return await original(collection, key, row)

    store.put = die
    with pytest.raises(RuntimeError):
        run(red.redeem(T, S, r.id, idem_key="idem-1", actor="op"))
    store.put = original

    assert run(ledger.balance(T, S)).points == 832, "the first deduction should have landed"

    # Attempt two: the phone retries with the SAME key, as a field app on a bad line does.
    rec, is_new = run(red.redeem(T, S, r.id, idem_key="idem-1", actor="op"))

    assert run(ledger.balance(T, S)).points == 832, "the retry deducted a second time"
    assert is_new is False, "a second confirmation must not be sent for one redemption"
    assert rec.cost == 168

    # AND THE RECEIPT EXISTS NOW. The recovery is not «refuse and walk away» — the points went out,
    # so the customer must have a record of the reward he was handed.
    rows, _ = run(store.find(REDEMPTIONS, {"tenant": T}, limit=10))
    assert len(rows) == 1, "exactly one receipt for one deduction"


def test_the_cause_is_stable_across_attempts_and_scoped_to_the_tenant():
    """The property the whole fix rests on, stated on its own."""
    from app.core.redeem import _cause

    assert _cause(T, "idem-1") == _cause(T, "idem-1")
    assert _cause(T, "idem-1") != _cause(T, "idem-2")
    # A key that collides across tenants would let one shop's retry suppress another's redemption.
    assert _cause("shop-a", "k") != _cause("shop-b", "k")
    # No key, no derived cause — the caller is refused rather than given an undedupable movement.
    assert _cause(T, "") == ""


def test_a_redemption_with_no_idempotency_key_is_refused_not_deducted():
    store, ledger, rewards, red = build()
    give(ledger, 1000)
    r = run(rewards.create(T, name="قهوة", cost=168, type="item"))

    with pytest.raises(LoyaltyError):
        run(red.redeem(T, S, r.id, idem_key="", actor="op"))

    assert run(ledger.balance(T, S)).points == 1000, "refused, and nothing moved"
