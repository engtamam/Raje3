"""Per-tenant app-specific tool/persona gating (core/held_apps.py, core/tools.py's own
`tools_for_held_apps`, and `PromptSection.app_keys`) — the granular sibling of
test_standalone_no_base_isolation.py's all-or-nothing `has_any_app` check.

A tenant may hold the base "واتساب الذكي" subscription (so `has_any_app` is True) while never
having bought, say, الحجوزات specifically — this must withhold propose_booking/check_availability
and the two booking-tied persona rules (staff_preference/upsell), never all-or-nothing like the
base check does.
"""
from __future__ import annotations

from unittest.mock import patch

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core import tools as T
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import build_system_prompt
from app.core.held_apps import HttpHeldApps, NullHeldApps, TOOL_APP_KEYS
from app.core.points import NullPointsSummary

TENANT = "t1"
SUBJECT = "sub1"

_ALLOWED = frozenset({"check_availability", "propose_booking", "get_customer_points_summary",
                      "suggest_redeemable_offer", "suggest_related_service",
                      "list_my_bookings", "propose_cancel_booking", "propose_reschedule_booking"})


class _FixedHeldApps:
    driver = "fake"

    def __init__(self, held: frozenset[str]) -> None:
        self._held = held

    async def held(self, tenant: str) -> frozenset[str]:
        return self._held


def _engine(store, llm, *, held_apps, **overrides):
    from app.core.conversation import ConversationEngine

    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    kwargs = dict(store=store, llm=llm, booking_provider=provider,
                 points_summary=NullPointsSummary(), debounce_seconds=180,
                 session_timeout_seconds=2400, raw_window_messages=4,
                 allowed_tools=_ALLOWED, held_apps=held_apps)
    kwargs.update(overrides)
    return ConversationEngine(**kwargs)


async def _reply(engine, tenant=TENANT, subject=SUBJECT):
    llm = engine._llm
    llm.queue_text("أهلاً!")
    await engine.on_inbound_text(tenant=tenant, subject_ref=subject, from_number="+9665",
                                 text="مرحبا", now=1000)
    await engine.compose_reply(tenant, subject, now=1200)
    return llm.calls[-1]


# ── core/tools.py::tools_for_held_apps — the pure function ────────────────────────────────────
def test_none_means_no_gating_at_all():
    """Every pre-existing caller/test that never wires a held-apps port sees the base allowlist
    completely unchanged — same convention as base_entitlement's own None-safe default."""
    assert T.tools_for_held_apps(_ALLOWED, None) == _ALLOWED


def test_a_tenant_with_no_extra_app_keeps_only_general_tools():
    # Every member of _ALLOWED is app-tagged (bookings/loyalty/insights.engine) — none untagged —
    # so a tenant holding no extra app at all is narrowed to nothing here.
    narrowed = T.tools_for_held_apps(_ALLOWED, frozenset())
    assert narrowed == frozenset()


def test_a_tenant_holding_bookings_keeps_the_booking_tools_but_not_loyalty_or_insights():
    narrowed = T.tools_for_held_apps(_ALLOWED, frozenset({"feature.bookings"}))
    assert narrowed == frozenset({
        "check_availability", "propose_booking", "list_my_bookings",
        "propose_cancel_booking", "propose_reschedule_booking"})


def test_a_tenant_holding_loyalty_keeps_the_loyalty_tools_but_not_bookings_or_insights():
    narrowed = T.tools_for_held_apps(_ALLOWED, frozenset({"feature.loyalty"}))
    assert narrowed == frozenset({"get_customer_points_summary", "suggest_redeemable_offer"})


def test_a_tenant_holding_insights_keeps_suggest_related_service_only():
    narrowed = T.tools_for_held_apps(_ALLOWED, frozenset({"feature.insights.engine"}))
    assert narrowed == frozenset({"suggest_related_service"})


def test_a_cross_app_tool_needs_only_one_of_its_keys_held():
    base = frozenset({"check_growth_opportunities"})
    assert T.tools_for_held_apps(base, frozenset({"feature.loyalty"})) == base
    assert T.tools_for_held_apps(base, frozenset({"feature.contacts"})) == frozenset()


# ── build_system_prompt's own held_apps filtering ──────────────────────────────────────────────
def test_no_held_apps_shows_every_persona_rule_as_before():
    prompt = build_system_prompt("محل الأناقة")
    assert "يوزّع حجوزاتها تلقائيًا" in prompt          # staff_preference
    assert "بتاخذين X وY" in prompt                     # upsell
    assert "بائع محترف" in prompt                       # procedure_selling


def test_a_tenant_with_no_bookings_never_sees_the_booking_tied_persona_rules():
    prompt = build_system_prompt("محل الأناقة", held_apps=frozenset({"feature.loyalty"}))
    assert "يوزّع حجوزاتها تلقائيًا" not in prompt
    assert "بتاخذين X وY" not in prompt
    assert "بائع محترف" not in prompt                   # procedure_selling
    # General rules stay — never narrowed by held_apps at all.
    assert "تقترح" in prompt
    assert "تجاهل" in prompt


def test_a_tenant_with_bookings_still_sees_the_booking_tied_persona_rules():
    prompt = build_system_prompt("محل الأناقة", held_apps=frozenset({"feature.bookings"}))
    assert "يوزّع حجوزاتها تلقائيًا" in prompt
    assert "بتاخذين X وY" in prompt
    assert "بائع محترف" in prompt                       # procedure_selling


def test_get_service_procedure_needs_bookings_like_every_other_bookings_tool():
    base = frozenset({"get_service_procedure"})
    assert T.tools_for_held_apps(base, frozenset({"feature.bookings"})) == base
    assert T.tools_for_held_apps(base, frozenset({"feature.loyalty"})) == frozenset()


# ── end-to-end through ConversationEngine ──────────────────────────────────────────────────────
async def test_a_loyalty_only_tenant_never_gets_offered_booking_tools():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, held_apps=_FixedHeldApps(frozenset({"feature.loyalty"})))

    call = await _reply(engine)

    assert call["allowed_tools"] == frozenset({
        "get_customer_points_summary", "suggest_redeemable_offer"})


async def test_no_held_apps_port_wired_degrades_open_same_as_every_other_optional_peer():
    """Pre-existing test constructors (held_apps=None, the default) must behave exactly as they
    did before this feature shipped."""
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, held_apps=None)

    call = await _reply(engine)

    assert call["allowed_tools"] == _ALLOWED


async def test_a_lapsed_app_narrows_the_very_next_reply_not_eventually():
    """Live, uncached, every turn — same posture as base_entitlement.py's own check."""
    store = MemoryDataStore()
    llm = StubLlm()

    class _Flippable:
        driver = "fake"

        def __init__(self) -> None:
            self.held_keys: frozenset[str] = frozenset({"feature.bookings"})

        async def held(self, tenant: str) -> frozenset[str]:
            return self.held_keys

    ent = _Flippable()
    engine = _engine(store, llm, held_apps=ent)

    first = await _reply(engine)
    assert "propose_booking" in first["allowed_tools"]

    ent.held_keys = frozenset()
    llm.queue_text("رد ثانٍ")
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="مرحبا مرة ثانية", now=2000)
    await engine.compose_reply(TENANT, SUBJECT, now=2200)
    second = llm.calls[-1]
    assert "propose_booking" not in second["allowed_tools"]


# ── core/held_apps.py itself ────────────────────────────────────────────────────────────────────
async def test_null_held_apps_holds_every_gated_key():
    assert await NullHeldApps().held("any_tenant") == frozenset(TOOL_APP_KEYS)


async def test_an_empty_tenant_holds_nothing():
    ent = HttpHeldApps(billing_url="http://billing", check_path="/check", token="t" * 10)
    assert await ent.held("") == frozenset()


async def test_http_held_apps_returns_exactly_the_keys_billing_confirms():
    ent = HttpHeldApps(billing_url="http://billing", check_path="/check", token="t" * 10,
                       keys=("feature.bookings", "feature.loyalty", "feature.campaigns"))

    def _fake_urlopen(req, timeout=0):
        import io
        import json as _json
        allowed = "feature.bookings" in req.full_url or "feature.campaigns" in req.full_url

        class _Resp:
            def read(self):
                return _json.dumps({"allowed": allowed}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return _Resp()

    with patch("urllib.request.urlopen", _fake_urlopen):
        held = await ent.held("t1")

    assert held == frozenset({"feature.bookings", "feature.campaigns"})
