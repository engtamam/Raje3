"""ConversationEngine actually reads its live-override values (app/runtime_policy.py) through
`runtime_config` at the point of use — not just accepting the constructor argument. A test that
only checked the constructor default would pass even if `_runtime_int` were never called."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine

TENANT = "t1"
SUBJECT = "sub1"


class _FakeRuntimeConfig:
    """Scripted per-key overrides — the shape core/runtime_config.py::RuntimeConfig.get() answers,
    without needing a real datastore round trip for this unit test."""

    def __init__(self, overrides: dict[str, object]) -> None:
        self._overrides = overrides
        self.calls: list[str] = []

    async def get(self, *, tenant: str, key: str, default):
        self.calls.append(key)
        return self._overrides.get(key, default)


def _provider(store):
    return ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))


async def test_soft_decline_threshold_is_read_from_runtime_config_not_the_constructor_default():
    """Constructor says 2 (the default); the live override says 5 — the override must win, proving
    the value is actually re-read per turn rather than frozen at construction."""
    store = MemoryDataStore()
    rc = _FakeRuntimeConfig({"SOFT_DECLINE_THRESHOLD": 5})
    llm = StubLlm()
    llm.queue_text("تمام!")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store), points_summary=None,
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=25,
        allowed_tools=frozenset(), soft_decline_threshold=2, runtime_config=rc)

    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    conv = await engine._get(TENANT, SUBJECT)
    conv.awaiting_promo_response = True
    # 3 -> 4 after this turn's decline: trips the constructor default (2) but NOT the live
    # override (5) — the only value of promo_declines that actually distinguishes which one ran.
    conv.promo_declines = 3
    await engine._save(conv)

    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="لا", now=1002)
    await engine.compose_reply(TENANT, SUBJECT, now=1200)

    assert "SOFT_DECLINE_THRESHOLD" in rc.calls
    conv2 = await engine._get(TENANT, SUBJECT)
    assert conv2.promo_declines == 4
    assert conv2.promo_suppressed is False   # 4 < 5 (the live override) — proves 5 was used, not 2


async def test_no_runtime_config_wired_falls_back_to_the_constructor_default():
    """None (no panel wired yet, or an older test) must behave exactly as before this field
    existed — the None-safe shape every other optional peer in this engine already follows."""
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_text("تمام!")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store), points_summary=None,
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=25,
        allowed_tools=frozenset(), soft_decline_threshold=2)   # runtime_config left at its None default

    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    conv = await engine._get(TENANT, SUBJECT)
    conv.awaiting_promo_response = True
    conv.promo_declines = 1
    await engine._save(conv)

    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="لا", now=1002)
    await engine.compose_reply(TENANT, SUBJECT, now=1200)

    conv2 = await engine._get(TENANT, SUBJECT)
    assert conv2.promo_declines == 2
    assert conv2.promo_suppressed is True   # the constructor default (2) applied, no crash
