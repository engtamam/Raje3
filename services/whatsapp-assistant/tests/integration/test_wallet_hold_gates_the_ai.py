"""ConversationEngine wired to a real (fake) atomic wallet — the reserve happens right before the
one action that costs money (the LLM call), never before the free triage list, and confirm/hold
sequencing can never let the balance go negative, even under concurrent turns for the same tenant.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.assistant_service import LlmUnavailable
from app.adapters.llm.stub import StubLlm
from app.auditable_actions import AUDITABLE_ACTIONS
from app.core.audit import Auditor
from app.core.auditable import critical_actions, declared_actions, validate
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary

TENANT = "shop1"


def _provider(store):
    cfg = BookingConfig(business_hours={}, default_duration_minutes=30, concurrency=1,
                        max_lead_days=7, slot_granularity_minutes=15, service_durations={})
    return ConfigDrivenAvailabilityProvider(store=store, cfg=cfg)


def _auditor():
    class _Sink:
        driver = "http"

        def __init__(self):
            self.events = []

        async def emit(self, event):
            from app.ports.audit_sink import ACCEPTED, AuditReceipt
            self.events.append(event)
            return AuditReceipt(status=ACCEPTED, seq=len(self.events), hash="deadbeef")

    sink = _Sink()
    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    auditor = Auditor(sink=sink, service="whatsapp-assistant",
                      critical_actions=critical_actions(actions),
                      declared_actions=declared_actions(actions), fail_closed=True)
    return auditor, sink


class _AtomicFakeWallet:
    """Mirrors wallet-service's own real guarantee (core/wallet_service.py::reserve/confirm — a
    single compare-and-set against the held balance) closely enough to prove the property this
    task cares about: TWO CONCURRENT reserves for the same tenant can never both succeed past the
    available balance. An `asyncio.Lock` around the check-and-hold stands in for wallet-service's
    real atomic store write — the SHAPE under test is "check and hold happen as one step", not
    the storage engine behind it.
    """
    driver = "fake"

    def __init__(self, balance_halalas: int) -> None:
        self.balance = balance_halalas
        self.held = 0
        self._lock = asyncio.Lock()
        self.holds: dict[str, int] = {}
        self.reserve_calls = 0

    async def reserve(self, *, tenant: str, amount_halalas: int, source: str):
        self.reserve_calls += 1
        async with self._lock:
            if self.balance - self.held < amount_halalas:
                return None                      # exactly wallet-service's 402 INSUFFICIENT_FUNDS
            self.held += amount_halalas
            hold_id = f"hld_{source}"
            self.holds[hold_id] = amount_halalas
            return hold_id

    async def confirm(self, hold_id: str, *, final_net: int | None = None) -> None:
        # Mirrors wallet-service v0.19.2's own real confirm(final_net=...): the WHOLE reservation
        # is dropped either way, but the balance only falls by the REAL spend (final_net, when
        # given) — the unspent remainder is auto-released back, never charged.
        async with self._lock:
            reserved = self.holds.pop(hold_id, 0)
            spent = reserved if final_net is None else min(final_net, reserved)
            self.balance -= spent
            self.held -= reserved

    async def release(self, hold_id: str) -> None:
        async with self._lock:
            amount = self.holds.pop(hold_id, 0)
            self.held -= amount


def _engine(store, llm, wallet, auditor=None, **overrides):
    kwargs = dict(store=store, llm=llm, booking_provider=_provider(store),
                 points_summary=NullPointsSummary(), debounce_seconds=180,
                 session_timeout_seconds=2400, raw_window_messages=12,
                 allowed_tools=frozenset({"check_availability", "propose_booking",
                                         "get_customer_points_summary",
                                         "suggest_redeemable_offer"}),
                 auditor=auditor, wallet_balance=wallet,
                 wallet_estimated_tokens=1000, wallet_rate_halalas_per_1k=100,
                 wallet_margin_halalas=50)
    kwargs.update(overrides)
    return ConversationEngine(**kwargs)


async def _through_triage(engine, subject: str, now: int) -> None:
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=subject, from_number="+9665",
                                     text="hi", now=now)
    await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=subject, reply_id="triage:inquiry", now=now + 1)


async def test_the_triage_list_itself_never_touches_the_wallet():
    store = MemoryDataStore()
    wallet = _AtomicFakeWallet(balance_halalas=0)     # ZERO balance
    engine = _engine(store, StubLlm(), wallet)
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref="sub1", from_number="+9665", text="hi", now=1000)
    assert plan.kind == "list"          # the free menu still shows, even with an empty wallet
    assert wallet.reserve_calls == 0


async def test_a_sufficient_balance_reserves_calls_the_llm_and_confirms_the_hold():
    store = MemoryDataStore()
    wallet = _AtomicFakeWallet(balance_halalas=1000)
    llm = StubLlm()
    engine = _engine(store, llm, wallet)
    await _through_triage(engine, "sub1", now=1000)
    await engine.on_inbound_text(tenant=TENANT, subject_ref="sub1", from_number="+9665",
                                 text="أبي أحجز غسيل", now=1010)
    reply = await engine.compose_reply(TENANT, "sub1", now=1200)

    assert reply.kind == "text"
    assert len(llm.calls) == 1
    # 1000 tokens @ 100 halalas/1k = 100, + 50 margin = 150 reserved and fully confirmed.
    assert wallet.balance == 1000 - 150
    assert wallet.held == 0             # nothing left outstanding after confirm
    assert wallet.holds == {}


class _FailingLlm:
    """Simulates a genuine provider failure (timeout, 5xx, a hung call) — the same class of thing
    Google's own Gemini API billing docs describe: `ai.google.dev/gemini-api/docs/billing` says
    plainly that only a successful (200) response is ever billed; a failed request "won't be
    charged for the tokens used" on their side. This proves OUR OWN wallet mirrors that — a
    failure must never itself be the thing that spends a shop's balance."""
    driver = "failing"

    def __init__(self):
        self.calls = 0

    async def respond(self, **kwargs):
        self.calls += 1
        raise LlmUnavailable("simulated provider timeout")


async def test_a_failed_llm_call_never_confirms_or_charges_the_hold():
    """THE REAL-MONEY GUARANTEE: if the model call itself fails (timeout, provider error — Gemini
    "froze" and never answered), the reserved hold must NEVER be confirmed. It is left exactly as
    reserved, to expire unspent on wallet-service's own HOLD_TTL_SECONDS sweep (see
    core/wallet_balance.py's module docstring) — matching Google's own billing behaviour: no
    charge for a call that never actually produced a usable response."""
    store = MemoryDataStore()
    wallet = _AtomicFakeWallet(balance_halalas=1000)
    llm = _FailingLlm()
    engine = _engine(store, llm, wallet)
    await _through_triage(engine, "sub1", now=1000)
    await engine.on_inbound_text(tenant=TENANT, subject_ref="sub1", from_number="+9665",
                                 text="أبي أحجز غسيل", now=1010)

    with pytest.raises(LlmUnavailable):
        await engine.compose_reply(TENANT, "sub1", now=1200)

    assert llm.calls == 1                     # the call really happened, and really failed
    assert wallet.balance == 1000              # UNTOUCHED — confirm() was never reached
    assert wallet.held == 150                  # still reserved, exactly as before the failed call
    assert len(wallet.holds) == 1              # sitting there, unconfirmed — expires via TTL, unspent


async def test_an_insufficient_balance_stops_the_ai_before_any_llm_call():
    store = MemoryDataStore()
    wallet = _AtomicFakeWallet(balance_halalas=10)    # less than the 150 that would be reserved
    llm = StubLlm()
    auditor, sink = _auditor()
    engine = _engine(store, llm, wallet, auditor=auditor)
    await _through_triage(engine, "sub1", now=1000)
    await engine.on_inbound_text(tenant=TENANT, subject_ref="sub1", from_number="+9665",
                                 text="أبي أحجز غسيل", now=1010)
    reply = await engine.compose_reply(TENANT, "sub1", now=1200)

    assert reply.kind == "text"
    assert llm.calls == []              # the model was never called
    assert wallet.balance == 10         # untouched — reserve refused, nothing was held or spent
    conv = await engine._get(TENANT, "sub1")
    assert conv.state == "closed"
    assert conv.wallet_stopped is True
    stops = [e for e in sink.events if e.action == "whatsapp_assistant.stopped_wallet_depleted"]
    assert len(stops) == 1
    assert stops[0].tenant == TENANT

    # A further tick for the same session does not re-record the same fact.
    again = await engine.compose_reply(TENANT, "sub1", now=1400)
    assert again.kind == "none"
    stops_after = [e for e in sink.events if e.action == "whatsapp_assistant.stopped_wallet_depleted"]
    assert len(stops_after) == 1


async def test_balance_never_goes_negative_under_concurrent_turns_for_the_same_tenant():
    """THE HARD RULE: two conversations for the SAME tenant, each needing a 150-halala hold,
    racing against a wallet that can only ever afford ONE of them (200 available). Both call
    compose_reply concurrently via asyncio.gather; exactly one must get a real LLM reply and be
    charged, the other must be stopped with the balance untouched by it — and the balance must
    never dip below zero regardless of interleaving."""
    store = MemoryDataStore()
    wallet = _AtomicFakeWallet(balance_halalas=200)   # room for exactly one 150-halala hold
    llm = StubLlm()
    engine = _engine(store, llm, wallet)

    await _through_triage(engine, "subA", now=1000)
    await _through_triage(engine, "subB", now=1000)
    await engine.on_inbound_text(tenant=TENANT, subject_ref="subA", from_number="+9665",
                                 text="أبي أحجز غسيل", now=1010)
    await engine.on_inbound_text(tenant=TENANT, subject_ref="subB", from_number="+9666",
                                 text="أبي أحجز غسيل", now=1010)

    replies = await asyncio.gather(
        engine.compose_reply(TENANT, "subA", now=1200),
        engine.compose_reply(TENANT, "subB", now=1200))

    texts = [r.text for r in replies]
    stopped_count = sum(1 for t in texts if "متوقفة" in t)
    served_count = sum(1 for t in texts if "متوقفة" not in t)
    assert stopped_count == 1
    assert served_count == 1
    assert len(llm.calls) == 1          # exactly one turn actually reached the model
    assert wallet.balance == 200 - 150  # exactly one hold was ever confirmed
    assert wallet.balance >= 0          # THE hard rule, checked directly
    assert wallet.held == 0
