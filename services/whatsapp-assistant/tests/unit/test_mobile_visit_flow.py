"""The mobile/on-the-go service-request flow end to end at the engine layer: the model calls
`request_mobile_visit` (a real, deliberate decision — core/tools.py re-validates it against the
shop's real catalogue), the engine asks for a location deterministically, and only the customer's
NEXT inbound location (never any other message) actually creates the request — core/conversation.py
::handle_location, mirroring the mandatory-triage/branch-selection gates' own "code decides when a
free-form model turn hands off to a deterministic step" shape."""
from __future__ import annotations

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary
from app.ports.mobile_requests import CreatedMobileRequest, MobileRequestFailed

TENANT = "t1"
SUBJECT = "sub1"
ALLOWED = frozenset({"request_mobile_visit"})


class _FakeServiceCatalog:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    async def list_active(self, tenant: str) -> list[dict]:
        return [{"id": sid, "name": sid} for sid in self._ids]


class _FakeMobileRequests:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self._fail = fail

    async def create(self, **kwargs) -> CreatedMobileRequest:
        self.calls.append(kwargs)
        if self._fail:
            raise MobileRequestFailed("no services chosen")
        return CreatedMobileRequest(request_id="mreq_test1")

    async def hours(self, tenant: str) -> dict | None:
        # None (fail-open, same as an unconfigured/unreachable BookingsDesk) — the working-hours
        # check itself is test_tools_validation.py's own concern; this file is about the location
        # hand-off, not the time-validation math.
        return None


def _engine(store, llm, *, mobile_requests=None, service_catalog=None):
    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    return ConversationEngine(
        store=store, llm=llm, booking_provider=provider, points_summary=NullPointsSummary(),
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=4,
        allowed_tools=ALLOWED, service_catalog=service_catalog or _FakeServiceCatalog(["svc_wash"]),
        mobile_requests=mobile_requests or _FakeMobileRequests())


async def test_the_model_calling_the_tool_asks_for_a_location_not_a_button():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("request_mobile_visit", service_ids=["svc_wash"],
                       starts_at_iso="2026-09-14T12:00:00+03:00")
    engine = _engine(store, llm)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي غسيل سيارتي عندي بالبيت", now=1000)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1000 + 180)

    assert plan.kind == "request_location"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_mobile_location is True
    assert conv.mobile_request_service_ids == ["svc_wash"]
    assert conv.mobile_request_time == 1789376400


async def test_sharing_the_location_afterward_creates_the_real_request():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("request_mobile_visit", service_ids=["svc_wash"],
                       starts_at_iso="2026-09-14T12:00:00+03:00")
    mobile = _FakeMobileRequests()
    engine = _engine(store, llm, mobile_requests=mobile)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي غسيل سيارتي عندي بالبيت", now=1000)
    await engine.compose_reply(TENANT, SUBJECT, now=1000 + 180)

    plan = await engine.handle_location(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                        text="24.7136,46.6753", now=2000)

    assert plan.kind == "text"
    assert len(mobile.calls) == 1
    call = mobile.calls[0]
    assert call["tenant"] == TENANT and call["phone"] == "+9665"
    assert call["service_ids"] == ["svc_wash"]
    assert call["lat"] == 24.7136 and call["lng"] == 46.6753

    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_mobile_location is False
    assert conv.mobile_request_service_ids == []


async def test_a_referral_code_offered_with_the_request_is_carried_to_the_real_create_call():
    """The customer's referral code is offered when `request_mobile_visit` was validated, and
    survives the whole location hand-off — the request may not become real (and register the
    code) until the shop marks it complete, days later, so nothing here can validate it, only
    carry it faithfully to the one real write."""
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("request_mobile_visit", service_ids=["svc_wash"],
                       starts_at_iso="2026-09-14T12:00:00+03:00", referral_code="ab123")
    mobile = _FakeMobileRequests()
    engine = _engine(store, llm, mobile_requests=mobile)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي غسيل سيارتي عندي بالبيت وعندي كود إحالة ab123", now=1000)
    await engine.compose_reply(TENANT, SUBJECT, now=1000 + 180)

    conv = await engine._get(TENANT, SUBJECT)
    assert conv.mobile_request_referral_code == "ab123"

    await engine.handle_location(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="24.7136,46.6753", now=2000)
    assert mobile.calls[0]["referral_code"] == "ab123"

    conv = await engine._get(TENANT, SUBJECT)
    assert conv.mobile_request_referral_code == ""


async def test_no_referral_code_offered_sends_an_empty_one_never_a_missing_key():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("request_mobile_visit", service_ids=["svc_wash"],
                       starts_at_iso="2026-09-14T12:00:00+03:00")
    mobile = _FakeMobileRequests()
    engine = _engine(store, llm, mobile_requests=mobile)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي غسيل سيارتي عندي بالبيت", now=1000)
    await engine.compose_reply(TENANT, SUBJECT, now=1000 + 180)
    await engine.handle_location(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="24.7136,46.6753", now=2000)
    assert mobile.calls[0]["referral_code"] == ""


async def test_a_location_arriving_unprompted_is_never_acted_on():
    store = MemoryDataStore()
    mobile = _FakeMobileRequests()
    engine = _engine(store, StubLlm(), mobile_requests=mobile)
    plan = await engine.handle_location(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                        text="24.7136,46.6753", now=1000)
    assert plan.kind == "text"
    assert mobile.calls == []


async def test_a_second_location_after_the_first_already_consumed_it_is_not_a_duplicate():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("request_mobile_visit", service_ids=["svc_wash"],
                       starts_at_iso="2026-09-14T12:00:00+03:00")
    mobile = _FakeMobileRequests()
    engine = _engine(store, llm, mobile_requests=mobile)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي غسيل", now=1000)
    await engine.compose_reply(TENANT, SUBJECT, now=1000 + 180)
    await engine.handle_location(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="24.7,46.6", now=2000)
    # Customer re-shares their pin a second time — the state was already cleared, so this is
    # answered plainly, never treated as a second request.
    await engine.handle_location(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="24.8,46.7", now=2001)
    assert len(mobile.calls) == 1


async def test_a_malformed_location_text_is_refused_not_a_crash():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("request_mobile_visit", service_ids=["svc_wash"],
                       starts_at_iso="2026-09-14T12:00:00+03:00")
    mobile = _FakeMobileRequests()
    engine = _engine(store, llm, mobile_requests=mobile)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي غسيل", now=1000)
    await engine.compose_reply(TENANT, SUBJECT, now=1000 + 180)
    plan = await engine.handle_location(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                        text="not-a-coordinate", now=2000)
    assert plan.kind == "text"
    assert mobile.calls == []


async def test_a_peer_failure_on_create_is_apologised_not_silenced():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("request_mobile_visit", service_ids=["svc_wash"],
                       starts_at_iso="2026-09-14T12:00:00+03:00")
    mobile = _FakeMobileRequests(fail=True)
    engine = _engine(store, llm, mobile_requests=mobile)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي غسيل", now=1000)
    await engine.compose_reply(TENANT, SUBJECT, now=1000 + 180)
    plan = await engine.handle_location(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                        text="24.7,46.6", now=2000)
    assert plan.kind == "text"
    assert plan.text
    assert len(mobile.calls) == 1


async def test_the_model_naming_an_unknown_service_never_reaches_the_location_step():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("request_mobile_visit", service_ids=["svc_does_not_exist"])
    engine = _engine(store, llm, service_catalog=_FakeServiceCatalog(["svc_wash"]))
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي غسيل", now=1000)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1000 + 180)
    assert plan.kind == "text"
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.awaiting_mobile_location is False
