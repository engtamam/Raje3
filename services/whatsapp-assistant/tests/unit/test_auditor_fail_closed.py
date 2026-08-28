"""Auditor fail-closed on critical actions — a booking confirm must not proceed unwitnessed. See
app/core/audit.py (copied unmodified from services/reminders — same contract) and
app/auditable_actions.py for which actions are marked critical. `points_redeemed` no longer exists
here — a reward now rides on the booking itself as `intended_reward_id` intent, never a standalone
spend of its own; see app/core/tools.py's own docstring on the change."""
import pytest

from app.adapters.audit_sink.null import NullAuditSink
from app.auditable_actions import AUDITABLE_ACTIONS
from app.core.audit import AuditUnavailable, Auditor
from app.core.auditable import critical_actions, declared_actions, validate
from app.ports.audit_sink import FAILED, AuditReceipt


class _DownAuditSink:
    """A sink that IS configured (unlike null) but cannot currently reach audit-service — the
    case fail-closed exists for: a log the service relies on, unreachable right now."""
    driver = "http"

    async def emit(self, event):
        return AuditReceipt(status=FAILED, detail="audit-service unreachable (simulated)")


def _auditor(*, fail_closed: bool, sink=None) -> Auditor:
    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    return Auditor(sink=sink or _DownAuditSink(), service="whatsapp-assistant",
                   critical_actions=critical_actions(actions),
                   declared_actions=declared_actions(actions), fail_closed=fail_closed)


async def test_booking_confirmed_is_declared_critical():
    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    assert "whatsapp_assistant.booking_confirmed" in critical_actions(actions)


async def test_critical_action_raises_when_sink_cannot_record_and_fail_closed():
    auditor = _auditor(fail_closed=True)
    with pytest.raises(AuditUnavailable):
        await auditor.record("whatsapp_assistant.booking_confirmed", tenant="t1",
                             resource="booking:b1")


async def test_non_critical_action_never_raises_even_unrecorded():
    auditor = _auditor(fail_closed=True, sink=NullAuditSink())
    receipt = await auditor.record("whatsapp_assistant.proposal_rejected", tenant="t1",
                                   resource="proposal:p1")
    assert receipt.status == "dropped"


async def test_critical_action_with_unconfigured_null_sink_does_not_block_local_dev():
    """`dropped` (the null sink, unconfigured) is distinct from `failed` (a configured log that is
    down) — blocking on the former would 503 every critical route the moment a developer runs this
    service with its zero-infrastructure defaults, punishing the safe default rather than the
    unsafe one. Production itself is barred from booting with a null sink (config.py's boot
    guard) — this is what happens for local/test runs that use it deliberately."""
    auditor = _auditor(fail_closed=True, sink=NullAuditSink())
    receipt = await auditor.record("whatsapp_assistant.booking_confirmed", tenant="t1",
                                   resource="booking:b1")
    assert receipt.status == "dropped"


async def test_undeclared_action_is_refused_at_emit_time():
    auditor = _auditor(fail_closed=True)
    with pytest.raises(Exception):
        await auditor.record("whatsapp_assistant.made_up_action", tenant="t1")
