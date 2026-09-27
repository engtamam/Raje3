"""Booking-management-via-WhatsApp (view/cancel/reschedule an EXISTING booking) — the SAME
propose-then-real-button-confirm discipline test_tools_validation.py already proves for a NEW
booking, exercised here for the three new tools. `_FakeManagementProvider` below is a minimal
double of RealBookingProvider's booking-management surface (list_bookings/cancel_booking/
reschedule_booking) — no real HTTP peer, but the same customer-scoping contract: it resolves
"whose bookings" from (tenant, from_number) alone, exactly like _resolve_customer_id does, so a
test that never registers a phone for a tenant proves the tool layer cannot see anyone's bookings
through it either.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import pytest

from app.adapters.audit_sink.null import NullAuditSink
from app.adapters.datastore.memory import MemoryDataStore
from app.auditable_actions import AUDITABLE_ACTIONS
from app.core import tools as T
from app.core.audit import Auditor
from app.core.auditable import critical_actions, declared_actions, validate
from app.core.conversation import ConversationEngine
from app.core.models import PENDING_PROPOSALS
from app.core.points import NullPointsSummary
from app.ports.audit_sink import FAILED, AuditReceipt
from app.ports.booking_provider import Slot

TENANT = "t1"
ALLOWED = frozenset({"check_availability", "propose_booking", "get_customer_points_summary",
                     "suggest_redeemable_offer", "list_my_bookings", "propose_cancel_booking",
                     "propose_reschedule_booking"})


@dataclass
class _FakeManagementProvider:
    """bookings: id -> dict. phones: (tenant, from_number) -> customer_id. slots: available
    starts_at values a reschedule/availability check may land on."""
    bookings: dict = field(default_factory=dict)
    phones: dict = field(default_factory=dict)
    slots: set = field(default_factory=set)

    async def availability(self, *, tenant, service_id, earliest, horizon_days=0, branch_id="",
                           exclude_booking_id=""):
        # Mirrors the REAL bug this fake exists to catch: every OTHER booked booking's own slot
        # reads as busy — EXCEPT `exclude_booking_id`'s own, which must NOT count as a conflict
        # with itself (that is the entire point of the parameter: a reschedule re-checking its
        # own current/nearby time must not be told its own occupancy makes it unavailable).
        busy = {b["starts_at"] for bid, b in self.bookings.items()
               if b.get("status") == "booked" and bid != exclude_booking_id}
        return [Slot(starts_at=s, duration_minutes=30)
               for s in sorted(self.slots) if s >= earliest and s not in busy]

    def _customer(self, tenant, from_number):
        return self.phones.get((tenant, from_number))

    async def list_bookings(self, *, tenant, from_number, branch_id=""):
        cid = self._customer(tenant, from_number)
        return [dict(b) for b in self.bookings.values()
               if b["tenant"] == tenant and b["customer_id"] == cid
               and (not branch_id or b.get("branch_id") == branch_id)]

    async def cancel_booking(self, *, tenant, from_number, booking_id, reason="", branch_id=""):
        cid = self._customer(tenant, from_number)
        b = self.bookings.get(booking_id)
        if (b is None or b["tenant"] != tenant or b["customer_id"] != cid
                or (branch_id and b.get("branch_id") != branch_id)):
            raise T.ToolValidationError("not found or not yours")
        b["status"] = "cancelled"
        return dict(b)

    async def reschedule_booking(self, *, tenant, from_number, booking_id, starts_at, branch_id=""):
        cid = self._customer(tenant, from_number)
        b = self.bookings.get(booking_id)
        if (b is None or b["tenant"] != tenant or b["customer_id"] != cid
                or (branch_id and b.get("branch_id") != branch_id)):
            raise T.ToolValidationError("not found or not yours")
        if starts_at not in self.slots:
            raise T.ToolValidationError("slot no longer available")
        b["starts_at"] = starts_at
        return dict(b)


def _seed(provider: _FakeManagementProvider, *, booking_id: str, from_number: str,
         customer_id: str, starts_at: int, status: str = "booked", tenant: str = TENANT) -> None:
    provider.phones[(tenant, from_number)] = customer_id
    provider.bookings[booking_id] = {
        "id": booking_id, "tenant": tenant, "customer_id": customer_id, "branch_id": "b1",
        "service_ids": ["svc1"], "starts_at": starts_at, "status": status}


class _FakeAuditor:
    async def record(self, *a, **kw):
        pass


class _DownAuditSink:
    driver = "http"

    async def emit(self, event):
        return AuditReceipt(status=FAILED, detail="audit-service unreachable (simulated)")


def _real_auditor(*, up: bool) -> Auditor:
    """A REAL Auditor, not the no-op _FakeAuditor above — the only way to actually exercise
    auditable_actions.py's own declaration check. `_FakeAuditor` would silently mask the exact
    "action never declared" defect class (see auditable_actions.py's own note added alongside
    booking_cancelled/booking_rescheduled) since it never validates anything at all."""
    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    sink = NullAuditSink() if up else _DownAuditSink()
    return Auditor(sink=sink, service="whatsapp-assistant", critical_actions=critical_actions(actions),
                   declared_actions=declared_actions(actions), fail_closed=True)


def _engine(store, provider, **overrides):
    kwargs = dict(store=store, llm=None, booking_provider=provider,
                 points_summary=NullPointsSummary(), debounce_seconds=180,
                 session_timeout_seconds=2400, raw_window_messages=12, allowed_tools=ALLOWED)
    kwargs.update(overrides)
    return ConversationEngine(**kwargs)


# ── list_my_bookings ──────────────────────────────────────────────────────────────────────────

async def test_list_my_bookings_never_returns_another_customers_booking():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_mine", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.phones[(TENANT, "+9666")] = "cust2"
    provider.bookings["bkg_other"] = {"id": "bkg_other", "tenant": TENANT, "customer_id": "cust2",
                                      "branch_id": "b1", "service_ids": ["svc1"],
                                      "starts_at": now + 7200, "status": "booked"}
    text = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="list_my_bookings",
        args={}, allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665", booking_history_visible=True)
    assert "bkg_mine" in text
    assert "bkg_other" not in text


# ── branch scoping (a per_branch shop's number IS a branch) ─────────────────────────────────────

async def test_list_my_bookings_hides_a_booking_from_a_different_branch():
    """A customer texting branch B's number must not see her own booking at branch A — the same
    protection cross-customer isolation already gets, applied to branch too."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_branch_a", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.bookings["bkg_branch_a"]["branch_id"] = "branch-a"
    text = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="list_my_bookings",
        args={}, allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665", booking_history_visible=True, branch_id="branch-b")
    assert "bkg_branch_a" not in text
    assert "لا توجد حجوزات" in text


async def test_list_my_bookings_with_no_branch_on_the_conversation_sees_every_branch():
    """No regression for a central shop (or a session with no branch fixed yet)."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_branch_a", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.bookings["bkg_branch_a"]["branch_id"] = "branch-a"
    text = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="list_my_bookings",
        args={}, allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665", booking_history_visible=True)
    assert "bkg_branch_a" in text


async def test_propose_cancel_booking_from_a_different_branch_is_refused_like_not_found():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_branch_a", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.bookings["bkg_branch_a"]["branch_id"] = "branch-a"
    with pytest.raises(T.ToolValidationError) as exc:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
            args={"booking_id": "bkg_branch_a"}, allowed_tools=ALLOWED, store=store,
            booking_provider=provider, points_summary=NullPointsSummary(),
            proposal_ttl_seconds=1800, now=now, from_number="+9665", branch_id="branch-b")
    assert "لا يخصّك" in str(exc.value)
    # UNTOUCHED — the refused cross-branch attempt must not have cancelled it.
    assert provider.bookings["bkg_branch_a"]["status"] == "booked"


async def test_confirming_a_cancel_still_checks_branch_at_confirm_time():
    """Re-validated AGAIN at confirm time, same discipline as ownership — a proposal built while
    branch_id happened to be empty (or a stale one) must still be refused if it does not match the
    booking's real branch when the customer actually taps confirm."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_branch_a", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.bookings["bkg_branch_a"]["branch_id"] = "branch-a"
    rendered = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
        args={"booking_id": "bkg_branch_a"}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, now=now, from_number="+9665")   # no branch at propose time
    with pytest.raises(T.ToolValidationError):
        await T.execute_confirmed_proposal(
            tenant=TENANT, proposal_id=rendered.proposal_id, store=store,
            booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="idem-1", now=now,
            from_number="+9665", branch_id="branch-b")   # wrong branch at confirm time
    assert provider.bookings["bkg_branch_a"]["status"] == "booked"


async def test_list_my_bookings_always_shows_current_and_upcoming_regardless_of_history_flag():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_future", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    for flag in (True, False):
        text = await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="list_my_bookings",
            args={}, allowed_tools=ALLOWED, store=store, booking_provider=provider,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
            from_number="+9665", booking_history_visible=flag)
        assert "bkg_future" in text


async def test_a_past_booking_lookup_is_refused_not_hallucinated_when_history_flag_is_off():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_past", from_number="+9665", customer_id="cust1",
         starts_at=now - 30 * 86400, status="attended")
    text = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="list_my_bookings",
        args={"include_history": True}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665", booking_history_visible=False)
    assert "bkg_past" not in text
    # A clean, honest decline directing to a human — never a bare error, never a silent omission.
    assert "تواصل مع المحل" in text


async def test_declining_history_never_also_swallows_a_genuine_upcoming_appointment():
    """THE BUG: a customer asking a compound question ("what did I book last month, AND is
    tomorrow's appointment still on?") with history disabled must still be told about tomorrow —
    the decline is scoped to history alone, never to "everything in this reply", contradicting
    the documented contract ("current and upcoming bookings always show regardless of this
    flag") that both config.py and the LLM tool schema promise."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_past_and_future", from_number="+9665", customer_id="cust1",
         starts_at=now - 30 * 86400, status="attended")
    provider.bookings["bkg_tomorrow"] = {"id": "bkg_tomorrow", "tenant": TENANT,
                                         "customer_id": "cust1", "branch_id": "b1",
                                         "service_ids": ["svc1"], "starts_at": now + 86400,
                                         "status": "booked"}
    text = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="list_my_bookings",
        args={"include_history": True}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665", booking_history_visible=False)
    assert "bkg_past_and_future" not in text, "the past one must still be withheld"
    assert "bkg_tomorrow" in text, "but the genuine upcoming appointment must still be told"
    assert "تواصل مع المحل" in text


async def test_a_past_booking_lookup_is_answered_when_history_flag_is_on():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_past2", from_number="+9665", customer_id="cust1",
         starts_at=now - 30 * 86400, status="attended")
    text = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="list_my_bookings",
        args={"include_history": True}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665", booking_history_visible=True)
    assert "bkg_past2" in text


# ── propose_cancel_booking / propose_reschedule_booking — proposal building ─────────────────────

async def test_propose_cancel_booking_for_ones_own_booking_renders_interactive_proposal():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg1", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
        args={"booking_id": "bkg1"}, allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665")
    assert isinstance(result, T.RenderedProposal)
    assert len(result.buttons) == 2


async def test_propose_cancel_booking_belonging_to_a_different_customer_is_rejected():
    """SECURITY: the tool layer's own double-check — never trusts a booking_id the model claims
    without re-confirming, via list_bookings, that it is genuinely this phone's own booking."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_someone_elses", from_number="+9666", customer_id="cust2",
         starts_at=now + 3600)
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1",
            tool="propose_cancel_booking", args={"booking_id": "bkg_someone_elses"},
            allowed_tools=ALLOWED, store=store, booking_provider=provider,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
            from_number="+9665")   # a DIFFERENT phone than the one that owns bkg_someone_elses
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_propose_cancel_booking_for_a_nonexistent_id_is_rejected():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    provider.phones[(TENANT, "+9665")] = "cust1"
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1",
            tool="propose_cancel_booking", args={"booking_id": "bkg_never_existed"},
            allowed_tools=ALLOWED, store=store, booking_provider=provider,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
            from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_propose_cancel_booking_on_an_already_cancelled_booking_is_a_plain_reply_not_a_proposal():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_gone", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600, status="cancelled")
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
        args={"booking_id": "bkg_gone"}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665")
    assert isinstance(result, str)
    assert "ملغى" in result


async def test_propose_reschedule_booking_requires_the_new_slot_to_be_actually_available():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg2", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    # deliberately NOT added to provider.slots — the model hallucinated an open time.
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1",
            tool="propose_reschedule_booking",
            args={"booking_id": "bkg2", "new_starts_at_iso":
                 __import__("datetime").datetime.fromtimestamp(
                     now + 7200, __import__("datetime").timezone.utc).isoformat()},
            allowed_tools=ALLOWED, store=store, booking_provider=provider,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
            from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_propose_reschedule_booking_to_its_own_current_time_is_not_wrongly_refused():
    """THE BUG: without excluding the booking's own occupancy from the availability re-check, a
    reschedule "to the exact same time" (or any nearby overlapping time) reads as busy against
    ITSELF and gets wrongly refused — even though bookings-service's own route explicitly treats
    this as a harmless no-op (see services/bookings' own
    test_reschedule_to_the_exact_same_time_is_a_harmless_no_op_success). The bot must not refuse
    one hop earlier what the real write would have happily accepted."""
    import datetime as dt
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    current_time = now + 3600
    _seed(provider, booking_id="bkg_self", from_number="+9665", customer_id="cust1",
         starts_at=current_time)
    provider.slots.add(current_time)   # the booking's own current slot — nothing else free
    iso = dt.datetime.fromtimestamp(current_time, dt.timezone.utc).isoformat()
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1",
        tool="propose_reschedule_booking",
        args={"booking_id": "bkg_self", "new_starts_at_iso": iso}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, now=now, from_number="+9665")
    assert isinstance(result, T.RenderedProposal), \
        "must NOT be refused — the booking's own slot is not a conflict with itself"


async def test_propose_reschedule_booking_refuses_a_booking_from_a_different_tenant_same_phone():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_tnt_resched", from_number="+9665", customer_id="cust_a",
         starts_at=now + 3600, tenant="tnt_a")
    import datetime as dt
    iso = dt.datetime.fromtimestamp(now + 7200, dt.timezone.utc).isoformat()
    try:
        await T.validate_and_render(
            tenant="tnt_b", subject_ref="sub1", conversation_id="c1",
            tool="propose_reschedule_booking",
            args={"booking_id": "bkg_tnt_resched", "new_starts_at_iso": iso},
            allowed_tools=ALLOWED, store=store, booking_provider=provider,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
            from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_a_stale_reschedule_confirm_id_for_a_different_conversation_is_refused():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    engine = _engine(store, provider)
    now = int(time.time())
    _seed(provider, booking_id="bkg_resch_stale", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.slots.add(now + 7200)
    import datetime as dt
    iso = dt.datetime.fromtimestamp(now + 7200, dt.timezone.utc).isoformat()
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="some-other-conversation-id",
        tool="propose_reschedule_booking",
        args={"booking_id": "bkg_resch_stale", "new_starts_at_iso": iso}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, now=now, from_number="+9665")
    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id=f"{proposal.proposal_id}:confirm",
        auditor=_FakeAuditor(), now=now)
    assert "لم يعد صالحًا" in plan.text
    assert provider.bookings["bkg_resch_stale"]["starts_at"] == now + 3600


async def test_a_double_tapped_reschedule_confirm_only_moves_the_booking_once():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    engine = _engine(store, provider)
    now = int(time.time())
    _seed(provider, booking_id="bkg_resch_twice", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.slots.add(now + 7200)
    import datetime as dt
    iso = dt.datetime.fromtimestamp(now + 7200, dt.timezone.utc).isoformat()
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id=engine._key(TENANT, "sub1"),
        tool="propose_reschedule_booking",
        args={"booking_id": "bkg_resch_twice", "new_starts_at_iso": iso}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, now=now, from_number="+9665")
    conv = await engine._get(TENANT, "sub1")
    conv.pending_proposal_id = proposal.proposal_id
    conv.from_number = "+9665"
    await engine._save(conv)
    first = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id=f"{proposal.proposal_id}:confirm",
        auditor=_FakeAuditor(), now=now)
    second = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id=f"{proposal.proposal_id}:confirm",
        auditor=_FakeAuditor(), now=now)
    assert "تم نقل" in first.text
    assert "لم يعد صالحًا" in second.text
    assert provider.bookings["bkg_resch_twice"]["starts_at"] == now + 7200


async def test_propose_reschedule_booking_for_a_genuinely_open_slot_renders_interactive_proposal():
    import datetime as dt
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg3", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.slots.add(now + 7200)
    iso = dt.datetime.fromtimestamp(now + 7200, dt.timezone.utc).isoformat()
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1",
        tool="propose_reschedule_booking", args={"booking_id": "bkg3", "new_starts_at_iso": iso},
        allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665")
    assert isinstance(result, T.RenderedProposal)


# ── execution: confirm-only, via handle_button_reply, exactly like a new booking ────────────────

async def test_a_free_text_reply_never_cancels_a_booking_only_a_matching_button_does():
    """NOT just "nothing was called" — actually drives `handle_button_reply` with a reply_id that
    does NOT match the pending proposal (what a stray free-text webhook or a malformed/forged
    reply_id would produce), and proves the real code path refuses it and leaves the booking
    untouched, rather than merely observing that a button was never tapped in the test itself."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    engine = _engine(store, provider)
    now = int(time.time())
    _seed(provider, booking_id="bkg4", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id=engine._key(TENANT, "sub1"),
        tool="propose_cancel_booking", args={"booking_id": "bkg4"}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, now=now, from_number="+9665")
    conv = await engine._get(TENANT, "sub1")
    conv.pending_proposal_id = proposal.proposal_id
    conv.from_number = "+9665"
    await engine._save(conv)
    # Free text never carries a "{proposal_id}:confirm" shape — the closest a stray/malformed
    # inbound message could ever produce through this ENTRY POINT is a reply_id with no ":" at
    # all, which handle_button_reply refuses immediately, before even reading the proposal.
    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id="كم سعر الغسيل؟",
        auditor=_FakeAuditor(), now=now)
    assert plan.kind == "text" and "لم أفهم" in plan.text
    assert provider.bookings["bkg4"]["status"] == "booked"
    conv = await engine._get(TENANT, "sub1")
    assert conv.pending_proposal_id == proposal.proposal_id, "the real proposal must still stand"


async def test_confirming_the_cancel_button_actually_cancels_and_is_reported_truthfully():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    engine = _engine(store, provider)
    now = int(time.time())
    _seed(provider, booking_id="bkg5", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id=engine._key(TENANT, "sub1"),
        tool="propose_cancel_booking", args={"booking_id": "bkg5"}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, now=now, from_number="+9665")
    conv = await engine._get(TENANT, "sub1")
    conv.pending_proposal_id = proposal.proposal_id
    conv.from_number = "+9665"
    await engine._save(conv)
    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id=f"{proposal.proposal_id}:confirm",
        auditor=_FakeAuditor(), now=now)
    assert plan.kind == "text" and "تم إلغاء" in plan.text
    assert provider.bookings["bkg5"]["status"] == "cancelled"


async def test_a_stale_or_replayed_confirm_id_for_a_different_conversation_is_refused():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    engine = _engine(store, provider)
    now = int(time.time())
    _seed(provider, booking_id="bkg6", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="some-other-conversation-id",
        tool="propose_cancel_booking", args={"booking_id": "bkg6"}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, now=now, from_number="+9665")
    # This conversation was never given the proposal (conv.pending_proposal_id stays "").
    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id=f"{proposal.proposal_id}:confirm",
        auditor=_FakeAuditor(), now=now)
    assert "لم يعد صالحًا" in plan.text
    assert provider.bookings["bkg6"]["status"] == "booked"


async def test_a_double_tapped_confirm_only_cancels_once():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    engine = _engine(store, provider)
    now = int(time.time())
    _seed(provider, booking_id="bkg7", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id=engine._key(TENANT, "sub1"),
        tool="propose_cancel_booking", args={"booking_id": "bkg7"}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, now=now, from_number="+9665")
    conv = await engine._get(TENANT, "sub1")
    conv.pending_proposal_id = proposal.proposal_id
    conv.from_number = "+9665"
    await engine._save(conv)
    first = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id=f"{proposal.proposal_id}:confirm",
        auditor=_FakeAuditor(), now=now)
    # The SECOND tap replays the same reply_id — the conversation's pending_proposal_id was
    # already cleared by the first confirm, so this must read as stale, not re-execute.
    second = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id=f"{proposal.proposal_id}:confirm",
        auditor=_FakeAuditor(), now=now)
    assert "تم إلغاء" in first.text
    assert "لم يعد صالحًا" in second.text


async def test_confirming_a_cancel_is_refused_if_the_flag_was_flipped_off_after_the_proposal():
    """THE MASTER KILL-SWITCH, RE-CHECKED AT CONFIRM TIME — not just when the proposal was
    created. Proves the exact scenario the user asked about: a proposal already sitting there
    when BOOKING_MANAGEMENT_ENABLED is flipped to false must NOT still execute on a later tap."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg9", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
        args={"booking_id": "bkg9"}, allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665")
    try:
        await T.execute_confirmed_proposal(
            tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
            booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_x", now=now,
            from_number="+9665", booking_management_enabled=False)   # flipped off after proposing
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass
    assert provider.bookings["bkg9"]["status"] == "booked", "must not have executed while disabled"


async def test_a_refused_confirm_while_disabled_does_not_consume_the_proposal():
    """The refusal above must be a REFUSAL, not a burned attempt — flipping the flag back on
    within the TTL should let the SAME original confirm tap still go through, rather than forcing
    the customer to start over because an operator briefly toggled the switch."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg10", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
        args={"booking_id": "bkg10"}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665")
    try:
        await T.execute_confirmed_proposal(
            tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
            booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_x", now=now,
            from_number="+9665", booking_management_enabled=False)
    except T.ToolValidationError:
        pass
    result = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
        booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_x", now=now,
        from_number="+9665", booking_management_enabled=True)   # flag restored
    assert result["kind"] == "cancel"
    assert provider.bookings["bkg10"]["status"] == "cancelled"


async def test_confirming_a_reschedule_is_also_refused_while_the_flag_is_off():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg11", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.slots.add(now + 7200)
    import datetime as dt
    iso = dt.datetime.fromtimestamp(now + 7200, dt.timezone.utc).isoformat()
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1",
        tool="propose_reschedule_booking", args={"booking_id": "bkg11", "new_starts_at_iso": iso},
        allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665")
    try:
        await T.execute_confirmed_proposal(
            tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
            booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_x", now=now,
            from_number="+9665", booking_management_enabled=False)
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass
    assert provider.bookings["bkg11"]["starts_at"] == now + 3600, "must not have moved"


async def test_a_new_booking_confirm_is_unaffected_by_the_management_kill_switch():
    """The kill-switch is SCOPED to cancel/reschedule — it must never block a NEW booking
    (`propose_booking`), which has nothing to do with this flag."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    provider.slots.add(int(time.time()) + 3600)
    now = int(time.time())
    import datetime as dt
    iso = dt.datetime.fromtimestamp(now + 3600, dt.timezone.utc).isoformat()
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_booking",
        args={"service_id": "svc1", "starts_at_iso": iso}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665")
    # provider has no hold_and_confirm/create_booking wired — this only needs to prove the
    # kill-switch flag itself never short-circuits a propose_booking confirm before reaching
    # provider code, so any exception here must NOT be the "disabled" ToolValidationError.
    try:
        await T.execute_confirmed_proposal(
            tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
            booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_x", now=now,
            from_number="+9665", booking_management_enabled=False)
        assert False, "expected some failure (provider has no hold_and_confirm) — but not silence"
    except T.ToolValidationError as exc:
        assert "disabled" not in str(exc)


# ── graceful failure: a peer/provider error must never crash the turn silently ──────────────────

class _RaisingProvider:
    """Every management call raises — simulating an unreachable bookings-service peer, or the
    management peers never having been built at all (BOOKING_MANAGEMENT_ENABLED was off at
    booking_assignment.py::build() time — see that function). Proves list_my_bookings/
    propose_cancel_booking/propose_reschedule_booking all convert this into a graceful
    ToolValidationError rather than letting an unrelated exception type escape uncaught past
    core/conversation.py's own `except T.ToolValidationError` — the exact "silent crash" class of
    bug this module's docstring already flags for the audit step elsewhere."""

    async def list_bookings(self, *, tenant, from_number, branch_id=""):
        raise RuntimeError("peer unreachable")


async def test_list_my_bookings_fails_gracefully_not_silently_when_the_peer_is_unreachable():
    store = MemoryDataStore()
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="list_my_bookings",
            args={}, allowed_tools=ALLOWED, store=store, booking_provider=_RaisingProvider(),
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, from_number="+9665")
        assert False, "expected ToolValidationError, not a silent crash"
    except T.ToolValidationError:
        pass


async def test_propose_cancel_booking_fails_gracefully_when_ownership_cannot_be_verified():
    store = MemoryDataStore()
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1",
            tool="propose_cancel_booking", args={"booking_id": "bkg_x"}, allowed_tools=ALLOWED,
            store=store, booking_provider=_RaisingProvider(), points_summary=NullPointsSummary(),
            proposal_ttl_seconds=1800, from_number="+9665")
        assert False, "expected ToolValidationError, not a silent crash"
    except T.ToolValidationError:
        pass


# ── end-to-end: "set it to false, does it actually work?" — real Settings, real allowlist ────────

def test_settings_false_removes_the_tools_the_model_could_even_be_offered():
    """The FIRST of the two independent layers config.py documents: with the flag off, the model
    is never even told these functions exist — proven from the SAME Settings object
    container.py itself builds `allowed_tools` from, not a hand-rolled frozenset that could drift
    from the real property."""
    from app.config import Settings

    on = Settings(BOOKING_PROVIDER_DRIVER="real", BOOKING_MANAGEMENT_ENABLED=True)
    off = Settings(BOOKING_PROVIDER_DRIVER="real", BOOKING_MANAGEMENT_ENABLED=False)
    for name in ("list_my_bookings", "propose_cancel_booking", "propose_reschedule_booking"):
        assert name in on.llm_tool_allowlist
        assert name not in off.llm_tool_allowlist


async def test_settings_false_end_to_end_a_proposal_attempt_is_refused_before_touching_any_peer():
    """The SECOND layer: even calling validate_and_render directly with the real off-Settings'
    allowlist (bypassing whatever the model would or would not have been offered) is refused —
    core/tools.py's own defence-in-depth check, `tool not in allowed_tools`. The fake provider
    below has NO methods defined at all; if this refusal did not fire before touching the
    provider, the test would fail with an AttributeError instead of the expected
    ToolValidationError, proving the check happens first."""
    from app.config import Settings

    class _UntouchedProvider:
        pass

    off = Settings(BOOKING_PROVIDER_DRIVER="real", BOOKING_MANAGEMENT_ENABLED=False)
    store = MemoryDataStore()
    for tool, args in (("list_my_bookings", {}),
                      ("propose_cancel_booking", {"booking_id": "bkg1"}),
                      ("propose_reschedule_booking", {"booking_id": "bkg1",
                                                      "new_starts_at_iso": "2030-01-01T10:00:00"})):
        try:
            await T.validate_and_render(
                tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool=tool, args=args,
                allowed_tools=off.llm_tool_allowlist, store=store,
                booking_provider=_UntouchedProvider(), points_summary=NullPointsSummary(),
                proposal_ttl_seconds=1800, from_number="+9665")
            assert False, f"{tool} should have been refused while BOOKING_MANAGEMENT_ENABLED=False"
        except T.ToolValidationError as exc:
            assert "not allowlisted" in str(exc)


async def test_an_expired_proposal_cannot_be_confirmed():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg8", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
        args={"booking_id": "bkg8"}, allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=60, now=now, from_number="+9665")
    try:
        await T.execute_confirmed_proposal(
            tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
            booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_x",
            now=now + 120, from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass
    assert provider.bookings["bkg8"]["status"] == "booked"


# ── audit gap: a REAL Auditor, not the no-op fake — catches "action never declared" too ─────────

# ── store-write failure AFTER the real write already succeeded (_mark_consumed) ─────────────────

class _StoreThatFailsOnPut(MemoryDataStore):
    """Wraps a real MemoryDataStore but makes `put` raise once (then heal) — simulating a
    datastore hiccup landing at the exact instant execute_confirmed_proposal tries to persist
    `consumed=True`, AFTER the real bookings-service write has already succeeded."""

    def __init__(self):
        super().__init__()
        self.put_calls = 0
        self.fail_next_put = False

    async def put(self, collection, key, value):
        self.put_calls += 1
        if self.fail_next_put and collection == PENDING_PROPOSALS:
            self.fail_next_put = False
            raise RuntimeError("datastore hiccup (simulated)")
        return await super().put(collection, key, value)


async def test_cancel_still_reports_success_when_marking_it_consumed_fails():
    """THE BUG: `store.put` right after the real write succeeded was completely unguarded — a
    failure there would have propagated as an uncaught exception, past ToolValidationError
    handling, leaving the customer with silence despite the cancel having genuinely gone through.
    Proves the real booking is cancelled AND the customer still gets a truthful reply."""
    store = _StoreThatFailsOnPut()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_store_gap1", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
        args={"booking_id": "bkg_store_gap1"}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665")
    store.fail_next_put = True
    result = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store, booking_provider=provider,
        auditor=_FakeAuditor(), idempotency_key="btn_x", now=now, from_number="+9665")
    # NO EXCEPTION PROPAGATED, and the real state change genuinely happened.
    assert result["kind"] == "cancel"
    assert result["store_gap"] is True
    assert provider.bookings["bkg_store_gap1"]["status"] == "cancelled"


async def test_a_redelivered_confirm_after_a_store_gap_is_safe_not_a_double_action():
    """The consequence of the gap above: the proposal row was NEVER marked consumed (the write
    that would have done so is exactly what failed), so a redelivered webhook or re-entrant tap
    reaches this branch again. Proves that retry is HARMLESS — cancel is naturally idempotent —
    rather than erroring or double-acting."""
    store = _StoreThatFailsOnPut()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_store_gap2", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
        args={"booking_id": "bkg_store_gap2"}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665")
    store.fail_next_put = True
    first = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store, booking_provider=provider,
        auditor=_FakeAuditor(), idempotency_key="btn_x", now=now, from_number="+9665")
    assert first["store_gap"] is True
    # THIS retry succeeds at persisting `consumed` (fail_next_put already consumed itself above).
    second = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store, booking_provider=provider,
        auditor=_FakeAuditor(), idempotency_key="btn_x", now=now, from_number="+9665")
    assert second["kind"] == "cancel"
    assert "store_gap" not in second
    assert provider.bookings["bkg_store_gap2"]["status"] == "cancelled"
    row = await store.get(PENDING_PROPOSALS, proposal.proposal_id)
    assert row["consumed"] is True, "the SECOND, successful write must have actually persisted"


async def test_a_new_booking_confirm_still_reports_success_when_marking_it_consumed_fails():
    import datetime as dt
    store = _StoreThatFailsOnPut()
    provider = _FakeManagementProvider()
    provider.slots.add(int(time.time()) + 3600)
    now = int(time.time())
    iso = dt.datetime.fromtimestamp(now + 3600, dt.timezone.utc).isoformat()

    class _CreateOnlyProvider(_FakeManagementProvider):
        async def hold_and_confirm(self, *, tenant, subject_ref, service_id, starts_at,
                                   idempotency_key, branch_id="", from_number="",
                                   intended_reward_id="", referral_code=""):
            return {"id": "bkg_new_1", "status": "booked"}

    provider = _CreateOnlyProvider()
    provider.slots.add(now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_booking",
        args={"service_id": "svc1", "starts_at_iso": iso}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665")
    store.fail_next_put = True
    result = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store, booking_provider=provider,
        auditor=_FakeAuditor(), idempotency_key="btn_x", now=now, from_number="+9665")
    assert result["kind"] == "booking"
    assert result["store_gap"] is True
    assert result["booking"]["id"] == "bkg_new_1"


async def test_cancel_confirmed_with_a_real_healthy_auditor_reports_no_gap():
    """This is the test that would have caught the DeclarationError bug directly: _FakeAuditor
    never validates the action name against auditable_actions.py at all, so a cancel/reschedule
    confirm calling an UNDECLARED action name would have sailed through every earlier test in this
    file silently. A real Auditor is the only thing that actually exercises that check."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_audit1", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
        args={"booking_id": "bkg_audit1"}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665")
    result = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store, booking_provider=provider,
        auditor=_real_auditor(up=True), idempotency_key="btn_x", now=now, from_number="+9665")
    assert result["kind"] == "cancel"
    assert "audit_gap" not in result


async def test_cancel_confirmed_with_a_down_real_auditor_still_reports_success_with_a_gap_flag():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_audit2", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
        args={"booking_id": "bkg_audit2"}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665")
    # NO EXCEPTION PROPAGATED — the real write already happened; the customer must still get a
    # truthful reply, exactly like test_booking_confirm_audit_gap.py proves for propose_booking.
    result = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store, booking_provider=provider,
        auditor=_real_auditor(up=False), idempotency_key="btn_x", now=now, from_number="+9665")
    assert result["kind"] == "cancel"
    assert result["audit_gap"] is True
    assert provider.bookings["bkg_audit2"]["status"] == "cancelled"


async def test_reschedule_confirmed_with_a_real_healthy_auditor_reports_no_gap():
    import datetime as dt
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_audit3", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.slots.add(now + 7200)
    iso = dt.datetime.fromtimestamp(now + 7200, dt.timezone.utc).isoformat()
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1",
        tool="propose_reschedule_booking", args={"booking_id": "bkg_audit3", "new_starts_at_iso": iso},
        allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665")
    result = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store, booking_provider=provider,
        auditor=_real_auditor(up=True), idempotency_key="btn_x", now=now, from_number="+9665")
    assert result["kind"] == "reschedule"
    assert "audit_gap" not in result
    assert provider.bookings["bkg_audit3"]["starts_at"] == now + 7200


async def test_reschedule_confirmed_with_a_down_real_auditor_still_reports_success_with_a_gap_flag():
    import datetime as dt
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_audit4", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.slots.add(now + 7200)
    iso = dt.datetime.fromtimestamp(now + 7200, dt.timezone.utc).isoformat()
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1",
        tool="propose_reschedule_booking", args={"booking_id": "bkg_audit4", "new_starts_at_iso": iso},
        allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665")
    result = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store, booking_provider=provider,
        auditor=_real_auditor(up=False), idempotency_key="btn_x", now=now, from_number="+9665")
    assert result["kind"] == "reschedule"
    assert result["audit_gap"] is True


# ── cross-tenant isolation at the tool layer ─────────────────────────────────────────────────────

async def test_list_my_bookings_never_leaks_across_tenants_even_with_the_same_phone_number():
    """The SAME phone number, used by a customer of two entirely different shops (tenants) — a
    realistic case, not a contrived one. Each tenant's own booking list must be exactly its own."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_tnt_a", from_number="+9665", customer_id="cust_a",
         starts_at=now + 3600, tenant="tnt_a")
    _seed(provider, booking_id="bkg_tnt_b", from_number="+9665", customer_id="cust_b",
         starts_at=now + 3600, tenant="tnt_b")
    text_a = await T.validate_and_render(
        tenant="tnt_a", subject_ref="sub1", conversation_id="c1", tool="list_my_bookings",
        args={}, allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665", booking_history_visible=True)
    assert "bkg_tnt_a" in text_a and "bkg_tnt_b" not in text_a


async def test_propose_cancel_booking_refuses_a_booking_from_a_different_tenant_same_phone():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_tnt_c", from_number="+9665", customer_id="cust_a",
         starts_at=now + 3600, tenant="tnt_a")
    try:
        await T.validate_and_render(
            tenant="tnt_b",   # a DIFFERENT tenant than the one the booking belongs to
            subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
            args={"booking_id": "bkg_tnt_c"}, allowed_tools=ALLOWED, store=store,
            booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
            now=now, from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


# ── terminal-state and malformed-input edge cases ────────────────────────────────────────────────

async def test_propose_reschedule_booking_on_an_already_cancelled_booking_is_rejected():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_term1", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600, status="cancelled")
    import datetime as dt
    iso = dt.datetime.fromtimestamp(now + 7200, dt.timezone.utc).isoformat()
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1",
            tool="propose_reschedule_booking",
            args={"booking_id": "bkg_term1", "new_starts_at_iso": iso}, allowed_tools=ALLOWED,
            store=store, booking_provider=provider, points_summary=NullPointsSummary(),
            proposal_ttl_seconds=1800, now=now, from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_propose_cancel_booking_on_an_attended_booking_is_a_plain_reply_directing_to_a_human():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_term2", from_number="+9665", customer_id="cust1",
         starts_at=now - 3600, status="attended")
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="propose_cancel_booking",
        args={"booking_id": "bkg_term2"}, allowed_tools=ALLOWED, store=store,
        booking_provider=provider, points_summary=NullPointsSummary(), proposal_ttl_seconds=1800,
        now=now, from_number="+9665")
    assert isinstance(result, str)
    assert "تواصل مع المحل" in result


async def test_propose_cancel_booking_with_a_missing_booking_id_is_rejected():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    provider.phones[(TENANT, "+9665")] = "cust1"
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1",
            tool="propose_cancel_booking", args={}, allowed_tools=ALLOWED, store=store,
            booking_provider=provider, points_summary=NullPointsSummary(),
            proposal_ttl_seconds=1800, from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_propose_reschedule_booking_with_a_missing_new_time_is_rejected():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_malformed1", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1",
            tool="propose_reschedule_booking", args={"booking_id": "bkg_malformed1"},
            allowed_tools=ALLOWED, store=store, booking_provider=provider,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
            from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_propose_reschedule_booking_with_an_unparseable_time_string_is_rejected():
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_malformed2", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    try:
        await T.validate_and_render(
            tenant=TENANT, subject_ref="sub1", conversation_id="c1",
            tool="propose_reschedule_booking",
            args={"booking_id": "bkg_malformed2", "new_starts_at_iso": "not-a-real-date"},
            allowed_tools=ALLOWED, store=store, booking_provider=provider,
            points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
            from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass


async def test_list_my_bookings_with_history_flag_off_and_no_include_history_request_never_declines():
    """The decline text is ONLY for an explicit include_history=True request while the flag is
    off — the default (no include_history at all) must show upcoming bookings plainly, never the
    decline message, since nothing past was actually asked for."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_default", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    text = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1", tool="list_my_bookings",
        args={}, allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665", booking_history_visible=False)
    assert "تواصل مع المحل" not in text
    assert "bkg_default" in text


# ── proposal isolation across sessions, and races at confirm time ───────────────────────────────

async def test_a_proposal_cannot_be_confirmed_from_a_different_subject_refs_conversation():
    """Two different customers (subject_refs) on the SAME tenant — one's proposal id must never be
    confirmable through the other's conversation state, even if somehow guessed/replayed."""
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    engine = _engine(store, provider)
    now = int(time.time())
    _seed(provider, booking_id="bkg_iso1", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub_owner", conversation_id=engine._key(TENANT, "sub_owner"),
        tool="propose_cancel_booking", args={"booking_id": "bkg_iso1"}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, now=now, from_number="+9665")
    conv_owner = await engine._get(TENANT, "sub_owner")
    conv_owner.pending_proposal_id = proposal.proposal_id
    conv_owner.from_number = "+9665"
    await engine._save(conv_owner)
    # A DIFFERENT subject_ref (a stranger's own conversation) never had this proposal id stamped
    # onto it — confirming through their session must be refused.
    plan = await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub_stranger", reply_id=f"{proposal.proposal_id}:confirm",
        auditor=_FakeAuditor(), now=now)
    assert "لم يعد صالحًا" in plan.text
    assert provider.bookings["bkg_iso1"]["status"] == "booked"


async def test_a_reschedule_proposal_is_rejected_at_confirm_if_the_slot_filled_in_the_meantime():
    """Mirrors test_execute_confirmed_proposal_rejects_a_slot_that_filled_after_proposal for
    propose_booking — the SAME race, for a reschedule this time."""
    import datetime as dt
    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    now = int(time.time())
    _seed(provider, booking_id="bkg_race1", from_number="+9665", customer_id="cust1",
         starts_at=now + 3600)
    provider.slots.add(now + 7200)
    iso = dt.datetime.fromtimestamp(now + 7200, dt.timezone.utc).isoformat()
    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="c1",
        tool="propose_reschedule_booking", args={"booking_id": "bkg_race1", "new_starts_at_iso": iso},
        allowed_tools=ALLOWED, store=store, booking_provider=provider,
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, now=now,
        from_number="+9665")
    # SOMEONE/SOMETHING ELSE took the slot between the proposal and this customer's confirm tap —
    # simulated here by simply removing it from availability, mirroring bookings-service's own
    # 409 SlotClaimBusy at confirm time.
    provider.slots.discard(now + 7200)
    try:
        await T.execute_confirmed_proposal(
            tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
            booking_provider=provider, auditor=_FakeAuditor(), idempotency_key="btn_x", now=now,
            from_number="+9665")
        assert False, "expected ToolValidationError"
    except T.ToolValidationError:
        pass
    assert provider.bookings["bkg_race1"]["starts_at"] == now + 3600, "must not have moved"


# ── a pending management proposal blocks a NEW one from being offered, same as propose_booking ──

async def test_a_pending_cancel_proposal_is_excluded_from_what_the_model_may_propose_next():
    """core/conversation.py's own narrowing (`allowed_tools`, right before the LLM call): a
    conversation already holding an unresolved state-changing proposal must not be offered ANOTHER
    one until the customer answers the one on the table.

    Drives the REAL `compose_reply` end to end with a `StubLlm` (which records the exact
    `allowed_tools` frozenset it was called with) rather than re-implementing the exclusion logic
    inline in the test — a hand-copied duplicate would keep passing even if conversation.py's own
    exclusion tuple silently dropped one of these tool names in a future edit."""
    from app.adapters.llm.stub import StubLlm

    store = MemoryDataStore()
    provider = _FakeManagementProvider()
    llm = StubLlm()
    llm.queue_text("تفضل، كيف أقدر أساعدك؟")
    engine = _engine(store, provider, llm=llm)
    now = int(time.time())
    conv = await engine._get(TENANT, "sub1")
    conv.state = "batching"
    conv.pending_proposal_id = "prp_some_existing_one"
    conv.batch_started_at = now - 10
    conv.raw_window = [{"role": "user", "text": "وش أسويه بعد؟", "at": now}]
    await engine._save(conv)

    await engine.compose_reply(TENANT, "sub1", now=now)

    assert len(llm.calls) == 1
    offered = llm.calls[0]["allowed_tools"]
    assert "propose_cancel_booking" not in offered
    assert "propose_reschedule_booking" not in offered
    assert "propose_booking" not in offered   # the pre-existing exclusion, still honoured too
    assert "list_my_bookings" in offered, "the READ tool must stay available regardless"
