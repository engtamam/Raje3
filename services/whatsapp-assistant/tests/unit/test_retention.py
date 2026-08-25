"""core/retention.py — the tick-driven chat data purge."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.inbound_store.datastore_backed import DataStoreInboundMessageStore
from app.auditable_actions import AUDITABLE_ACTIONS
from app.core.audit import Auditor
from app.core.auditable import critical_actions, declared_actions, validate
from app.core.models import CONVERSATIONS
from app.core.retention import run_retention_tick
from app.ports.audit_sink import ACCEPTED, AuditReceipt

TENANT = "t1"
OTHER_TENANT = "t2"
DAY = 86400
RETENTION_DAYS = 30


class _RecordingAuditSink:
    driver = "recording"

    def __init__(self) -> None:
        self.events = []

    async def emit(self, event):
        self.events.append(event)
        return AuditReceipt(status=ACCEPTED, detail="ok")


class _DownAuditSink:
    driver = "http"

    async def emit(self, event):
        from app.ports.audit_sink import FAILED
        return AuditReceipt(status=FAILED, detail="audit-service unreachable (simulated)")


def _auditor(sink) -> Auditor:
    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    return Auditor(sink=sink, service="whatsapp-assistant",
                   critical_actions=critical_actions(actions),
                   declared_actions=declared_actions(actions), fail_closed=True)


async def _seed_conversation(store, *, tenant, subject, session_closed_at, state="idle"):
    await store.put(CONVERSATIONS, f"{tenant}|{subject}", {
        "tenant": tenant, "subject_ref": subject, "state": state,
        "session_closed_at": session_closed_at, "updated": session_closed_at,
        "raw_window": [], "summary": "", "pending_proposal_id": "",
        "batch_deadline": 0, "batch_started_at": 0, "session_started_at": 0,
        "last_activity_at": session_closed_at, "input_tokens": 0, "output_tokens": 0})


async def _seed_message(store, *, tenant, subject, wamid):
    ims = DataStoreInboundMessageStore(store)
    await ims.record_if_new(tenant, wamid, {"text": "hi", "from": "+9665"})
    await ims.attach_subject_ref(tenant, wamid, subject)


async def test_purges_only_sessions_closed_past_the_cutoff():
    store = MemoryDataStore()
    now = 2_000_000_000
    old_cutoff_close = now - (RETENTION_DAYS + 1) * DAY   # past retention
    recent_close = now - (RETENTION_DAYS - 1) * DAY        # inside retention

    await _seed_conversation(store, tenant=TENANT, subject="old_subj",
                             session_closed_at=old_cutoff_close)
    await _seed_conversation(store, tenant=TENANT, subject="recent_subj",
                             session_closed_at=recent_close)
    await _seed_message(store, tenant=TENANT, subject="old_subj", wamid="w1")
    await _seed_message(store, tenant=TENANT, subject="recent_subj", wamid="w2")

    inbound = DataStoreInboundMessageStore(store)
    auditor = _auditor(_RecordingAuditSink())
    res = await run_retention_tick(TENANT, now=now, store=store, inbound_store=inbound,
                                   auditor=auditor, retention_days=RETENTION_DAYS)

    assert res.purged_conversations == 1
    assert res.purged_messages == 1
    assert await store.get(CONVERSATIONS, f"{TENANT}|old_subj") is None
    assert await store.get(CONVERSATIONS, f"{TENANT}|recent_subj") is not None
    assert await inbound.get(TENANT, "w1") is None
    assert await inbound.get(TENANT, "w2") is not None


async def test_open_sessions_are_never_candidates_however_old():
    """A conversation with no session_closed_at (still batching / awaiting confirmation, or
    reopened by a later message) must never be purged — the clock only runs on closed sessions."""
    store = MemoryDataStore()
    now = 2_000_000_000
    await _seed_conversation(store, tenant=TENANT, subject="open_subj",
                             session_closed_at=0, state="batching")

    inbound = DataStoreInboundMessageStore(store)
    auditor = _auditor(_RecordingAuditSink())
    res = await run_retention_tick(TENANT, now=now, store=store, inbound_store=inbound,
                                   auditor=auditor, retention_days=RETENTION_DAYS)

    assert res.purged_conversations == 0
    assert await store.get(CONVERSATIONS, f"{TENANT}|open_subj") is not None


async def test_respects_tenant_isolation():
    store = MemoryDataStore()
    now = 2_000_000_000
    old_close = now - (RETENTION_DAYS + 1) * DAY
    await _seed_conversation(store, tenant=TENANT, subject="s1", session_closed_at=old_close)
    await _seed_conversation(store, tenant=OTHER_TENANT, subject="s1", session_closed_at=old_close)

    inbound = DataStoreInboundMessageStore(store)
    auditor = _auditor(_RecordingAuditSink())
    res = await run_retention_tick(TENANT, now=now, store=store, inbound_store=inbound,
                                   auditor=auditor, retention_days=RETENTION_DAYS)

    assert res.purged_conversations == 1
    assert await store.get(CONVERSATIONS, f"{TENANT}|s1") is None
    # The other tenant's conversation, same subject_ref, is untouched by a sweep scoped to TENANT.
    assert await store.get(CONVERSATIONS, f"{OTHER_TENANT}|s1") is not None


async def test_idempotent_rerun_purges_nothing_the_second_time():
    store = MemoryDataStore()
    now = 2_000_000_000
    old_close = now - (RETENTION_DAYS + 1) * DAY
    await _seed_conversation(store, tenant=TENANT, subject="s1", session_closed_at=old_close)
    await _seed_message(store, tenant=TENANT, subject="s1", wamid="w1")

    inbound = DataStoreInboundMessageStore(store)
    auditor = _auditor(_RecordingAuditSink())

    first = await run_retention_tick(TENANT, now=now, store=store, inbound_store=inbound,
                                     auditor=auditor, retention_days=RETENTION_DAYS)
    second = await run_retention_tick(TENANT, now=now, store=store, inbound_store=inbound,
                                      auditor=auditor, retention_days=RETENTION_DAYS)

    assert first.purged_conversations == 1
    assert second.purged_conversations == 0
    assert second.purged_messages == 0


async def test_fails_closed_when_audit_sink_is_unreachable():
    """Critical action, fail-closed: a purge that cannot be witnessed must not happen — see
    app/core/audit.py and app/auditable_actions.py's chat_retention_purged declaration."""
    from app.core.audit import AuditUnavailable

    store = MemoryDataStore()
    now = 2_000_000_000
    old_close = now - (RETENTION_DAYS + 1) * DAY
    await _seed_conversation(store, tenant=TENANT, subject="s1", session_closed_at=old_close)

    inbound = DataStoreInboundMessageStore(store)
    auditor = _auditor(_DownAuditSink())

    try:
        await run_retention_tick(TENANT, now=now, store=store, inbound_store=inbound,
                                 auditor=auditor, retention_days=RETENTION_DAYS)
        raised = False
    except AuditUnavailable:
        raised = True

    assert raised
    # Untouched: the delete must never have happened once the audit call raised.
    assert await store.get(CONVERSATIONS, f"{TENANT}|s1") is not None


async def test_chat_retention_purged_is_declared_critical():
    actions = validate(AUDITABLE_ACTIONS, "whatsapp-assistant")
    assert "whatsapp_assistant.chat_retention_purged" in critical_actions(actions)
    assert "subject.erased" in critical_actions(actions)
