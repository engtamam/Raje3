"""Phase 3 — central-number branch-selection gate: asked only when it must be, never guessed,
free text never resolves it, and a stale/closed-since pick is refused rather than trusted."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary

TENANT = "t1"
SUBJECT = "sub1"


class _StaticBranchDirectory:
    driver = "static"

    def __init__(self, branches):
        self._branches = branches
        self.calls: list[str] = []

    async def list_open(self, tenant: str):
        self.calls.append(tenant)
        return list(self._branches)


def _engine(store, llm=None, branch_directory=None, **overrides):
    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    kwargs = dict(store=store, llm=llm or StubLlm(), booking_provider=provider,
                 points_summary=NullPointsSummary(), debounce_seconds=180,
                 session_timeout_seconds=2400, raw_window_messages=12,
                 allowed_tools=frozenset(), branch_directory=branch_directory)
    kwargs.update(overrides)
    return ConversationEngine(**kwargs)


async def _through_triage(engine, now=1000):
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="مرحبا", now=now)
    return await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="triage:inquiry", now=now + 10)


async def test_a_per_branch_shops_customer_is_never_asked_branch_id_already_set():
    store = MemoryDataStore()
    directory = _StaticBranchDirectory([{"id": "b1", "name": "الفرع الأول", "city": "جدة"},
                                        {"id": "b2", "name": "الفرع الثاني", "city": "الرياض"}])
    engine = _engine(store, branch_directory=directory)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="مرحبا", branch_id="b1", now=1000)
    plan = await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="triage:inquiry", now=1010)
    assert plan.kind == "text"                   # never gated — went straight to normal flow
    assert directory.calls == []                  # never even asked
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "idle"
    assert conv.branch_id == "b1"


async def test_a_central_shop_with_zero_or_one_open_branch_is_never_asked():
    store = MemoryDataStore()
    directory = _StaticBranchDirectory([{"id": "only", "name": "الفرع", "city": ""}])
    engine = _engine(store, branch_directory=directory)
    plan = await _through_triage(engine)
    assert plan.kind == "text"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "idle"
    assert conv.branch_id == "only"               # auto-set, zero friction — the only real answer


async def test_a_central_shop_with_no_directory_configured_is_never_asked():
    store = MemoryDataStore()
    engine = _engine(store, branch_directory=None)
    plan = await _through_triage(engine)
    assert plan.kind == "text"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "idle"
    assert conv.branch_id == ""


async def test_a_central_shop_with_two_plus_branches_is_gated_and_never_touches_the_llm():
    store = MemoryDataStore()
    llm = StubLlm()
    directory = _StaticBranchDirectory([{"id": "b1", "name": "الفرع الأول", "city": "جدة"},
                                        {"id": "b2", "name": "الفرع الثاني", "city": "الرياض"}])
    engine = _engine(store, llm, branch_directory=directory)
    plan = await _through_triage(engine)
    assert plan.kind == "list"
    assert len(plan.list_rows) == 2
    assert plan.list_rows[0]["id"] == "branch:b1"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "awaiting_branch"
    assert conv.triage_resolved is True

    # Free text before a pick never reaches the LLM and just re-sends the same list.
    free = await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                            text="جدة أفضل", now=1030)
    assert free.kind == "list"
    assert llm.calls == []
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "awaiting_branch"


async def test_picking_a_branch_stamps_it_and_resumes_normal_flow():
    store = MemoryDataStore()
    directory = _StaticBranchDirectory([{"id": "b1", "name": "الفرع الأول", "city": "جدة"},
                                        {"id": "b2", "name": "الفرع الثاني", "city": "الرياض"}])
    engine = _engine(store, branch_directory=directory)
    await _through_triage(engine)
    plan = await engine.handle_branch_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="branch:b2", now=1040)
    assert plan.kind == "text"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "idle"
    assert conv.branch_id == "b2"

    text_plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=SUBJECT, from_number="+9665", text="أبي أحجز", now=1050)
    assert text_plan.kind == "none"               # forwarded into batching, normal flow resumed


async def test_a_closed_since_branch_id_is_refused_not_trusted():
    store = MemoryDataStore()
    directory = _StaticBranchDirectory([{"id": "b1", "name": "الفرع الأول", "city": "جدة"},
                                        {"id": "b2", "name": "الفرع الثاني", "city": "الرياض"}])
    engine = _engine(store, branch_directory=directory)
    await _through_triage(engine)
    # b2 closed between the list being sent and the tap — no longer in the fresh fetch.
    directory._branches = [{"id": "b1", "name": "الفرع الأول", "city": "جدة"}]
    plan = await engine.handle_branch_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="branch:b2", now=1040)
    assert plan.kind == "list"                    # refused, re-sent — not accepted on faith
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "awaiting_branch"
    assert conv.branch_id == ""


async def test_a_stale_branch_reply_for_a_conversation_not_awaiting_branch_is_refused():
    store = MemoryDataStore()
    directory = _StaticBranchDirectory([{"id": "b1", "name": "1", "city": ""},
                                        {"id": "b2", "name": "2", "city": ""}])
    engine = _engine(store, branch_directory=directory)
    # Never entered awaiting_branch at all — a fresh, never-seen conversation.
    plan = await engine.handle_branch_selection(
        tenant=TENANT, subject_ref=SUBJECT, reply_id="branch:b1", now=1000)
    assert plan.kind == "list"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.state == "idle"


async def test_tenant_isolation_the_directory_is_asked_for_the_real_tenant_only():
    store = MemoryDataStore()
    directory = _StaticBranchDirectory([{"id": "b1", "name": "1", "city": ""},
                                        {"id": "b2", "name": "2", "city": ""}])
    engine = _engine(store, branch_directory=directory)
    await _through_triage(engine)
    assert directory.calls == [TENANT]
