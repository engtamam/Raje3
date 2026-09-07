"""list_due_services / list_lapsed_services — Phase 2 of "customer behavior learning": real,
already-learned per-customer rhythm (reminders/core/adaptive.py, read via RhythmProvider) turned
into a suggestion INPUT, never a sentence about the customer. See core/conversation.py's
`personalization` persona section and its sanitizer backstop for the other half of that rule."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary
from app.ports.rhythm_provider import RhythmEntry

TENANT = "t1"
SUBJECT = "sub1"
DAY = 86400


class _FakeCatalog:
    driver = "fake"

    def __init__(self, by_tenant: dict[str, list[dict]]) -> None:
        self._by = by_tenant

    async def list_active(self, tenant: str) -> list[dict]:
        return self._by.get(tenant, [])


class _FakeRhythmProvider:
    driver = "fake"

    def __init__(self, by_tenant: dict[str, list[RhythmEntry]]) -> None:
        self._by = by_tenant

    async def for_subject(self, *, tenant: str, subject_ref: str) -> list[RhythmEntry]:
        return self._by.get(tenant, [])


def _provider(store):
    return ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))


async def _ask(tool: str, rhythm: list[RhythmEntry], now: int,
              catalog: dict | None = None) -> str:
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call(tool)
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=frozenset({tool}),
        service_catalog=_FakeCatalog({TENANT: catalog and catalog.get(TENANT, []) or []}),
        rhythm_provider=_FakeRhythmProvider({TENANT: rhythm}))
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=now - 10)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=now - 9)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="؟", now=now - 8)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=now)
    assert plan.kind == "text"
    return plan.text


async def test_list_due_services_matches_a_service_right_at_its_learned_interval():
    now = 1_000_000 * DAY
    rhythm = [RhythmEntry(service_id="svc_a", interval_days=30.0,
                          last_visit_at=now - int(30 * DAY), observations=5, is_learned=True)]
    text = await _ask("list_due_services", rhythm, now,
                      {TENANT: [{"id": "svc_a", "name": "قص شعر"}]})
    assert "قص شعر" in text


async def test_list_due_services_excludes_a_service_not_due_yet():
    now = 1_000_000 * DAY
    rhythm = [RhythmEntry(service_id="svc_a", interval_days=30.0,
                          last_visit_at=now - int(5 * DAY), observations=5, is_learned=True)]
    text = await _ask("list_due_services", rhythm, now,
                      {TENANT: [{"id": "svc_a", "name": "قص شعر"}]})
    assert "قص شعر" not in text


async def test_list_lapsed_services_matches_a_service_well_past_double_the_interval():
    now = 1_000_000 * DAY
    rhythm = [RhythmEntry(service_id="svc_a", interval_days=30.0,
                          last_visit_at=now - int(100 * DAY), observations=5, is_learned=True)]
    text = await _ask("list_lapsed_services", rhythm, now,
                      {TENANT: [{"id": "svc_a", "name": "قص شعر"}]})
    assert "قص شعر" in text


async def test_list_lapsed_services_excludes_a_service_only_recently_due():
    """Right at the interval belongs to list_due_services, not list_lapsed_services — the two
    tools' bands must never overlap."""
    now = 1_000_000 * DAY
    rhythm = [RhythmEntry(service_id="svc_a", interval_days=30.0,
                          last_visit_at=now - int(30 * DAY), observations=5, is_learned=True)]
    text = await _ask("list_lapsed_services", rhythm, now,
                      {TENANT: [{"id": "svc_a", "name": "قص شعر"}]})
    assert "قص شعر" not in text


async def test_a_below_warmup_estimate_is_never_presented_as_a_pattern():
    """is_learned=False (below reminders' own warmup floor) must be excluded from BOTH tools —
    presenting a defaulted guess as a real rhythm is exactly what adaptive.py's own doctrine
    forbids, one layer removed."""
    now = 1_000_000 * DAY
    rhythm = [RhythmEntry(service_id="svc_a", interval_days=30.0,
                          last_visit_at=now - int(100 * DAY), observations=1, is_learned=False)]
    for tool in ("list_due_services", "list_lapsed_services"):
        text = await _ask(tool, rhythm, now, {TENANT: [{"id": "svc_a", "name": "قص شعر"}]})
        assert "قص شعر" not in text


async def test_no_rhythm_provider_wired_says_so_plainly_not_an_error():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("list_due_services")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=frozenset({"list_due_services"}))
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="؟", now=1002)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1200)
    assert "لا تتوفر بيانات كافية" in plan.text


async def test_empty_rhythm_says_so_plainly_not_an_error():
    text = await _ask("list_due_services", [], 1_000_000 * DAY)
    assert "لا يوجد شيء هنا الآن" in text


async def test_no_proposal_no_button_for_either_tool():
    store = MemoryDataStore()
    now = 1_000_000 * DAY
    rhythm = [RhythmEntry(service_id="svc_a", interval_days=30.0,
                          last_visit_at=now - int(30 * DAY), observations=5, is_learned=True)]
    llm = StubLlm()
    llm.queue_tool_call("list_due_services")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=frozenset({"list_due_services"}),
        service_catalog=_FakeCatalog({TENANT: [{"id": "svc_a", "name": "قص شعر"}]}),
        rhythm_provider=_FakeRhythmProvider({TENANT: rhythm}))
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=now - 10)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=now - 9)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="؟", now=now - 8)
    await engine.compose_reply(TENANT, SUBJECT, now=now)
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.pending_proposal_id == ""
