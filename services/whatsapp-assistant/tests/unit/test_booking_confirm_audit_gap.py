"""A booking confirm whose WRITE already succeeded must never leave the customer without a reply
just because the audit witness failed at that exact instant. Found by a 5-agent research pass:
`redeemer.redeem()`/`hold_and_confirm()` ran, THEN `auditor.record()` raised `AuditUnavailable`
unhandled — the booking was real, but the customer got silence and the PendingProposal row was
never marked consumed. Fixed by marking consumed BEFORE the audit call, and catching
`AuditUnavailable` specifically around it (see core/tools.py::execute_confirmed_proposal)."""
import time

from app.adapters.audit_sink.null import NullAuditSink
from app.adapters.datastore.memory import MemoryDataStore
from app.auditable_actions import AUDITABLE_ACTIONS
from app.core import tools as T
from app.core.audit import Auditor
from app.core.auditable import critical_actions, declared_actions, validate
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.models import PENDING_PROPOSALS
from app.ports.audit_sink import FAILED, AuditReceipt

TENANT = "t1"


class _DownAuditSink:
    """Configured, but unreachable right now — same fixture shape as test_auditor_fail_closed.py."""
    driver = "http"

    async def emit(self, event):
        return AuditReceipt(status=FAILED, detail="audit-service unreachable (simulated)")


def _down_auditor() -> Auditor:
    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    return Auditor(sink=_DownAuditSink(), service="whatsapp-assistant",
                   critical_actions=critical_actions(actions),
                   declared_actions=declared_actions(actions), fail_closed=True)


def _up_auditor() -> Auditor:
    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    return Auditor(sink=NullAuditSink(), service="whatsapp-assistant",
                   critical_actions=critical_actions(actions),
                   declared_actions=declared_actions(actions), fail_closed=True)


def _cfg() -> BookingConfig:
    return BookingConfig(
        business_hours={d: ["09:00-11:00"] for d in
                        ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
        default_duration_minutes=30, concurrency=1, max_lead_days=7,
        slot_granularity_minutes=30, service_durations={})


async def _proposed(store, provider):
    now = int(time.time())
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=now,
                                        horizon_days=7)
    target = slots[0]
    import datetime as dt
    iso = dt.datetime.fromtimestamp(target.starts_at, dt.timezone.utc).isoformat()
    from app.core.points import NullPointsSummary
    return await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"service_id": "svc1", "starts_at_iso": iso}, allowed_tools=frozenset({"propose_booking"}),
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800)


async def test_a_real_booking_is_reported_even_when_the_audit_sink_is_down():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    proposal = await _proposed(store, provider)

    result = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
        booking_provider=provider, auditor=_down_auditor(), idempotency_key="btn_1",
        branch_id="brn-main", from_number="+9665")

    # NO EXCEPTION PROPAGATED — the caller (handle_button_reply) gets a real result to answer
    # with, never an unhandled AuditUnavailable leaving the customer without any reply at all.
    assert result["kind"] == "booking"
    assert result["audit_gap"] is True
    assert result["booking"]["state"] == "confirmed"


async def test_the_proposal_is_still_marked_consumed_despite_the_audit_gap():
    """THE bug this fixes: a proposal left un-consumed because only the AUDIT step failed lets a
    retried button tap reach the real write a second time."""
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    proposal = await _proposed(store, provider)

    await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
        booking_provider=provider, auditor=_down_auditor(), idempotency_key="btn_1",
        branch_id="brn-main", from_number="+9665")

    row = await store.get(PENDING_PROPOSALS, proposal.proposal_id)
    assert row["consumed"] is True

    # A retried tap on the SAME (now-consumed) proposal is refused, not re-executed.
    try:
        await T.execute_confirmed_proposal(
            tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
            booking_provider=provider, auditor=_down_auditor(), idempotency_key="btn_1",
            branch_id="brn-main", from_number="+9665")
        assert False, "expected ToolValidationError — proposal already consumed"
    except T.ToolValidationError as exc:
        assert "already consumed" in str(exc)


async def test_a_healthy_audit_sink_reports_no_gap_at_all():
    store = MemoryDataStore()
    provider = ConfigDrivenAvailabilityProvider(store=store, cfg=_cfg())
    proposal = await _proposed(store, provider)

    result = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store,
        booking_provider=provider, auditor=_up_auditor(), idempotency_key="btn_1",
        branch_id="brn-main", from_number="+9665")

    assert result["kind"] == "booking"
    assert "audit_gap" not in result
