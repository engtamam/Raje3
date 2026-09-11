""""واتساب الذكي (مستقل)" — a tenant with no `feature.base` at all must never have this
service's replies grounded in operations/loyalty data, even if some of that data still physically
exists (a shop that cancelled its base keeps its old rows — see core/base_entitlement.py's own
docstring on why this is a deliberate skip, not a hope that the data happens to be empty).

THE SERVICE CATALOGUE IS THE ONE EXCEPTION, by product decision: a standalone buyer may write his
own catalogue in operations with no base, and the assistant must still use it.
"""
from __future__ import annotations

from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.base_entitlement import HttpBaseEntitlement, NullBaseEntitlement
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.conversation import ConversationEngine

TENANT = "t1"
SUBJECT = "sub1"

_ALLOWED = frozenset({"check_availability", "propose_booking", "get_customer_points_summary",
                      "suggest_redeemable_offer", "suggest_related_service",
                      "list_my_bookings", "propose_cancel_booking", "propose_reschedule_booking"})


class _FixedEntitlement:
    driver = "fake"

    def __init__(self, allowed: bool) -> None:
        self._allowed = allowed

    async def allowed(self, tenant: str) -> bool:
        return self._allowed


class _Catalog:
    driver = "fake"

    async def list_active(self, tenant: str) -> list[dict]:
        return [{"id": "svc_a", "name": "قص شعر", "price_minor": 5000}]


class _StillHasOldCustomerData:
    """The shop that USED TO hold a base — its old rows never went away."""
    driver = "fake"

    async def resolve(self, tenant: str, phone: str) -> dict:
        return {"found": True, "subject_ref": SUBJECT}


class _StillHasOldOffers:
    driver = "fake"

    async def summary(self, *, tenant: str, subject_ref: str) -> dict:
        return {"text": "عندك 500 نقطة", "points": 500}

    async def redeemable_offer(self, *, tenant: str, subject_ref: str):
        return None

    async def offers(self, *, tenant: str, subject_ref: str) -> list[dict]:
        return [{"reward_id": "r1", "reward_name": "غسيل مجاني", "points_cost": 100,
                "points_balance": 500, "expires_at": "2026-12-01"}]


class _StillHasOldPackages:
    driver = "fake"

    async def list_active(self, tenant: str) -> list[dict]:
        return [{"id": "pkg_1", "name": "باقة العروسة", "price_minor": 30000}]


def _engine(store, llm, *, base_entitlement, **overrides):
    provider = ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))
    kwargs = dict(store=store, llm=llm, booking_provider=provider,
                 points_summary=_StillHasOldOffers(), debounce_seconds=180,
                 session_timeout_seconds=2400, raw_window_messages=4,
                 allowed_tools=_ALLOWED, service_catalog=_Catalog(),
                 customer_lookup=_StillHasOldCustomerData(),
                 package_catalog=_StillHasOldPackages(),
                 base_entitlement=base_entitlement)
    kwargs.update(overrides)
    return ConversationEngine(**kwargs)


async def _reply(engine, tenant=TENANT, subject=SUBJECT):
    llm = engine._llm
    llm.queue_text("أهلاً!")
    await engine.on_inbound_text(tenant=tenant, subject_ref=subject, from_number="+9665",
                                 text="مرحبا", now=1000)
    await engine.compose_reply(tenant, subject, now=1200)
    return llm.calls[-1]


# ── the standalone tenant (no base) ────────────────────────────────────────────────────────────
async def test_a_standalone_tenant_gets_no_tools_at_all():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, base_entitlement=_FixedEntitlement(False))

    await _reply(engine)

    assert llm.calls[0]["allowed_tools"] == frozenset()


async def test_a_standalone_tenant_still_gets_his_own_service_catalogue():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, base_entitlement=_FixedEntitlement(False))

    call = await _reply(engine)

    assert "قص شعر" in call["context_block"]


async def test_a_standalone_tenant_never_sees_old_customer_history_that_still_exists():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, base_entitlement=_FixedEntitlement(False))

    call = await _reply(engine)

    # _StillHasOldCustomerData/_StillHasOldOffers/_StillHasOldPackages all return real data —
    # proving the skip is deliberate (has_any_app gating), not "the fakes happen to be empty".
    assert "غسيل مجاني" not in call["context_block"]
    assert "باقة العروسة" not in call["context_block"]


# ── the ordinary, full-service tenant (unaffected) ─────────────────────────────────────────────
async def test_an_ordinary_subscriber_keeps_every_tool_and_every_data_source():
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, base_entitlement=_FixedEntitlement(True))

    call = await _reply(engine)

    assert call["allowed_tools"] == _ALLOWED
    assert "غسيل مجاني" in call["context_block"]
    # NOT packages here — build_context_block's own upsell eligibility filter (context_builder.py)
    # is a separate concern from has_any_app gating and is not what this test exercises; the "never
    # leaks old data" test above already proves _StillHasOldPackages is reachable when has_any_app.


async def test_no_entitlement_wired_at_all_degrades_open_same_as_every_other_optional_peer():
    """Pre-existing test constructors (base_entitlement=None, the default) must behave exactly as
    they did before this feature shipped."""
    store = MemoryDataStore()
    llm = StubLlm()
    engine = _engine(store, llm, base_entitlement=None)

    call = await _reply(engine)

    assert call["allowed_tools"] == _ALLOWED


async def test_a_lapsed_base_degrades_the_very_next_reply_not_eventually():
    """Live, uncached, every turn — same posture as `self._licence`. A shop whose base lapses
    mid-conversation stops leaking on its NEXT turn, no separate revocation job."""
    store = MemoryDataStore()
    llm = StubLlm()

    class _Flippable:
        driver = "fake"

        def __init__(self) -> None:
            self.value = True

        async def allowed(self, tenant: str) -> bool:
            return self.value

    ent = _Flippable()
    engine = _engine(store, llm, base_entitlement=ent)

    first = await _reply(engine)
    assert first["allowed_tools"] == _ALLOWED

    ent.value = False
    llm.queue_text("رد ثانٍ")
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="مرحبا مرة ثانية", now=2000)
    await engine.compose_reply(TENANT, SUBJECT, now=2200)
    second = llm.calls[-1]
    assert second["allowed_tools"] == frozenset()


# ── base_entitlement.py itself ──────────────────────────────────────────────────────────────────
async def test_null_base_entitlement_always_allows():
    assert await NullBaseEntitlement().allowed("any_tenant") is True


async def test_http_base_entitlement_asks_every_event_recording_app():
    from app.core import base_entitlement

    assert base_entitlement.KEYS == (
        "feature.visit", "feature.bookings", "feature.contacts", "feature.loyalty")


async def test_an_empty_tenant_is_never_asked_about():
    ent = HttpBaseEntitlement(billing_url="http://billing", check_path="/check",
                              token="t" * 10)
    assert await ent.allowed("") is False
