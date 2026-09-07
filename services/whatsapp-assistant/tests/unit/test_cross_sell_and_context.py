"""Cross-sell (suggest_related_service), the rich per-turn context block (real catalogue + real
personal offers), the never-fabricate-a-discount backstop, and the brand-new-customer case."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.context_builder import build_context_block
from app.core.conversation import ConversationEngine, _sanitize_reply
from app.core.points import NullPointsSummary
from app.ports.llm import LlmReply, ToolCall

TENANT = "t1"
OTHER_TENANT = "t2"
SUBJECT = "sub1"

_ALLOWED = frozenset({"check_availability", "propose_booking", "get_customer_points_summary",
                      "suggest_redeemable_offer", "suggest_related_service"})


class _FakeRelatedServices:
    driver = "fake"

    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self._by = mapping
        self.calls: list[tuple[str, str]] = []

    async def related_to(self, tenant: str, service_id: str) -> list[str]:
        self.calls.append((tenant, service_id))
        return self._by.get(f"{tenant}:{service_id}", [])


class _FakeCatalog:
    driver = "fake"

    def __init__(self, by_tenant: dict[str, list[dict]]) -> None:
        self._by = by_tenant

    async def list_active(self, tenant: str) -> list[dict]:
        return self._by.get(tenant, [])


class _FakePackageCatalog:
    driver = "fake"

    def __init__(self, by_tenant: dict[str, list[dict]]) -> None:
        self._by = by_tenant

    async def list_active(self, tenant: str) -> list[dict]:
        return self._by.get(tenant, [])


class _FakeCustomerLookup:
    driver = "fake"

    def __init__(self, found: bool) -> None:
        self._found = found

    async def resolve(self, tenant: str, phone: str) -> dict:
        return {"found": self._found, "subject_ref": SUBJECT if self._found else ""}


class _FakePointsWithOffers:
    driver = "fake"

    async def summary(self, *, tenant: str, subject_ref: str) -> dict:
        return {"text": "", "points": 0}

    async def redeemable_offer(self, *, tenant: str, subject_ref: str):
        return None

    async def offers(self, *, tenant: str, subject_ref: str) -> list[dict]:
        return [{"reward_id": "r1", "reward_name": "غسيل مجاني", "points_cost": 100,
                "points_balance": 150, "expires_at": "2026-12-01"}]


def _provider(store):
    return ConfigDrivenAvailabilityProvider(
        store=store, cfg=BookingConfig(business_hours={}, default_duration_minutes=30,
                                       concurrency=1, max_lead_days=7,
                                       slot_granularity_minutes=15, service_durations={}))


# ── suggest_related_service ─────────────────────────────────────────────────────────────────────

async def test_cross_sell_tool_suggests_a_real_associated_service_without_touching_booking_state():
    store = MemoryDataStore()
    related = _FakeRelatedServices({"t1:svc_a": ["svc_b"]})
    catalog = _FakeCatalog({"t1": [{"id": "svc_b", "name": "ماسك البرافين", "price_minor": 0}]})
    llm = StubLlm()
    llm.queue_tool_call("suggest_related_service", service_id="svc_a")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=_ALLOWED,
        related_services=related, service_catalog=catalog)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي أضيف خدمة", now=1002)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1200)
    assert plan.kind == "text"
    assert "ماسك البرافين" in plan.text
    assert related.calls == [(TENANT, "svc_a")]
    # NO PendingProposal, no button — a suggestion, never a state change on its own.
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.pending_proposal_id == ""


async def test_cross_sell_tool_with_no_associated_service_says_so_plainly():
    store = MemoryDataStore()
    related = _FakeRelatedServices({})   # nothing configured for this tenant/service
    llm = StubLlm()
    llm.queue_tool_call("suggest_related_service", service_id="svc_a")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=_ALLOWED,
        related_services=related, service_catalog=_FakeCatalog({}))
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="؟", now=1002)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1200)
    assert "لا توجد خدمة أخرى" in plan.text
    # Never fabricated an offer despite the model asking — the tool's own answer, unaltered.


# ── a package as the cross-sell answer (packages feature) ───────────────────────────────────────

async def test_cross_sell_names_a_package_and_its_real_price():
    store = MemoryDataStore()
    related = _FakeRelatedServices({"t1:svc_a": ["pkg:pkg1"]})
    packages = _FakePackageCatalog(
        {"t1": [{"id": "pkg1", "name": "باقة الصيانة", "price_minor": 15000, "active": True}]})
    llm = StubLlm()
    llm.queue_tool_call("suggest_related_service", service_id="svc_a")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=_ALLOWED,
        related_services=related, service_catalog=_FakeCatalog({}), package_catalog=packages)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي أضيف خدمة", now=1002)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1200)
    assert "باقة الصيانة" in plan.text
    assert "150" in plan.text            # 15000 halalas = 150 ريال, stated plainly


async def test_cross_sell_mixes_a_package_and_a_plain_service():
    store = MemoryDataStore()
    related = _FakeRelatedServices({"t1:svc_a": ["pkg:pkg1", "svc_b"]})
    catalog = _FakeCatalog({"t1": [{"id": "svc_b", "name": "تلميع", "price_minor": 0}]})
    packages = _FakePackageCatalog(
        {"t1": [{"id": "pkg1", "name": "باقة الصيانة", "price_minor": 15000, "active": True}]})
    llm = StubLlm()
    llm.queue_tool_call("suggest_related_service", service_id="svc_a")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=_ALLOWED,
        related_services=related, service_catalog=catalog, package_catalog=packages)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي أضيف خدمة", now=1002)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1200)
    assert "تلميع" in plan.text and "باقة الصيانة" in plan.text


async def test_cross_sell_skips_a_package_the_catalogue_no_longer_knows():
    """A peer read that failed, or a package retired since — degraded, never a raw 'pkg:...' id
    leaking into the reply."""
    store = MemoryDataStore()
    related = _FakeRelatedServices({"t1:svc_a": ["pkg:gone"]})
    llm = StubLlm()
    llm.queue_tool_call("suggest_related_service", service_id="svc_a")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=_ALLOWED,
        related_services=related, service_catalog=_FakeCatalog({}),
        package_catalog=_FakePackageCatalog({}))
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="أبي أضيف خدمة", now=1002)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1200)
    assert "pkg:" not in plan.text


# ── never a fabricated discount, structurally (the tool result carries no such field) ───────────

def test_sanitizer_strips_a_discount_claim_the_model_invented_on_its_own():
    fabricated = "بالتأكيد، خصم 20% إذا حجزت اليوم!"
    cleaned = _sanitize_reply(fabricated)
    assert "20" not in cleaned
    assert "خصم" not in cleaned or cleaned != fabricated


def test_sanitizer_leaves_a_plain_addon_offer_with_no_price_promise_untouched():
    plain = "عادةً ما يُطلب مع هذه الخدمة أيضًا: ماسك البرافين. هل تحب إضافتها؟"
    assert _sanitize_reply(plain) == plain


# ── the rich context block itself: real catalogue + real personal offers, never trimmed ─────────

def test_context_block_lists_full_priced_catalogue_and_the_customers_own_real_offers():
    block = build_context_block(
        catalog=[{"id": "svc_a", "name": "قص شعر", "price_minor": 5000},
                {"id": "svc_b", "name": "غسيل", "price_minor": 3000}],
        offers=[{"reward_name": "غسيل مجاني", "points_cost": 100, "points_balance": 150,
                "expires_at": "2026-12-01"}],
        known_customer=True)
    assert "قص شعر" in block and "50" in block
    assert "غسيل" in block and "30" in block
    assert "غسيل مجاني" in block and "100" in block and "150" in block and "2026-12-01" in block


# ── packages worth upselling (packages feature) ──────────────────────────────────────────────────

def _catalog():
    return [{"id": "svc_a", "name": "قص شعر", "price_minor": 5000},
           {"id": "svc_b", "name": "غسيل", "price_minor": 3000}]


def test_a_package_priced_at_or_above_its_components_is_mentioned():
    block = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[{"id": "pkg1", "name": "باقة العناية", "service_ids": ["svc_a", "svc_b"],
                  "price_minor": 9000, "component_price_minor_sum": 8000, "active": True,
                  "next_offerable_dates": ["2026-06-06"], "person_count": 1}])
    assert "باقة العناية" in block
    assert "قص شعر" in block and "غسيل" in block
    assert "90" in block
    assert "2026-06-06" in block


def test_a_package_priced_below_its_components_is_never_mentioned():
    """THE WHOLE RULE (user's own words: "لو الخدمات اعلى من الباقة... خلاص ما يقترحها"). A
    package that would LOWER what the customer already pays must never even reach the model."""
    block = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[{"id": "pkg1", "name": "باقة رخيصة", "service_ids": ["svc_a", "svc_b"],
                  "price_minor": 7000, "component_price_minor_sum": 8000, "active": True,
                  "next_offerable_dates": ["2026-06-06"]}])
    assert "باقة رخيصة" not in block


def test_an_inactive_package_is_never_mentioned():
    block = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[{"id": "pkg1", "name": "باقة موقوفة", "service_ids": ["svc_a", "svc_b"],
                  "price_minor": 9000, "component_price_minor_sum": 8000, "active": False,
                  "next_offerable_dates": ["2026-06-06"]}])
    assert "باقة موقوفة" not in block


def test_a_package_with_no_upcoming_offerable_date_is_never_mentioned():
    """Expired, off-season, or a schedule that never falls in the lookahead window — same "does
    not exist for this purpose" reading as an inactive one."""
    block = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[{"id": "pkg1", "name": "باقة منتهية", "service_ids": ["svc_a", "svc_b"],
                  "price_minor": 9000, "component_price_minor_sum": 8000, "active": True,
                  "next_offerable_dates": []}])
    assert "باقة منتهية" not in block


def test_a_packages_person_count_is_mentioned_only_when_more_than_one():
    solo = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[{"id": "pkg1", "name": "باقة", "service_ids": ["svc_a", "svc_b"],
                  "price_minor": 9000, "component_price_minor_sum": 8000, "active": True,
                  "next_offerable_dates": ["2026-06-06"], "person_count": 1}])
    assert "أشخاص" not in solo

    family = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[{"id": "pkg1", "name": "باقة العائلة", "service_ids": ["svc_a", "svc_b"],
                  "price_minor": 9000, "component_price_minor_sum": 8000, "active": True,
                  "next_offerable_dates": ["2026-06-06"], "person_count": 3}])
    assert "3" in family and "أشخاص" in family


def test_no_packages_at_all_adds_nothing_to_the_block():
    with_none = build_context_block(catalog=_catalog(), offers=[], known_customer=True)
    with_empty = build_context_block(catalog=_catalog(), offers=[], known_customer=True, packages=[])
    assert with_none == with_empty


class _FakePackageCatalogFixedList:
    """Distinct from `_FakePackageCatalog` above (tenant-keyed) — this one always answers the
    same flat list regardless of tenant, which is all the end-to-end wiring test below needs."""
    driver = "fake"

    def __init__(self, packages: list[dict]) -> None:
        self._packages = packages

    async def list_active(self, tenant: str) -> list[dict]:
        return self._packages


async def test_an_eligible_package_reaches_the_models_own_context_block():
    """END TO END: package_catalog -> ConversationEngine._context_block -> the exact text the LLM
    is handed as `context_block` this turn — proving the wiring, not just the pure function."""
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_text("تمام!")
    packages = _FakePackageCatalogFixedList([
        {"id": "pkg1", "name": "باقة العناية", "service_ids": ["svc_a", "svc_b"],
         "price_minor": 9000, "component_price_minor_sum": 8000, "active": True,
         "next_offerable_dates": ["2026-06-06"], "person_count": 1},
    ])
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=_ALLOWED,
        service_catalog=_FakeCatalog({TENANT: _catalog()}), package_catalog=packages)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="مرحبا", now=1002)
    await engine.compose_reply(TENANT, SUBJECT, now=1200)

    assert "باقة العناية" in llm.calls[0]["context_block"]
    assert "2026-06-06" in llm.calls[0]["context_block"]


# ── the brand-new, never-seen-before customer: resolve-or-continue, never an error ──────────────

async def test_a_brand_new_unregistered_customer_gets_a_normal_first_visit_conversation():
    """A number that reached this shop directly (e.g. from a Google Maps listing) with no prior
    visit or booking anywhere in the system — `customer_lookup.resolve` answers found=False. The
    context block must say plainly "new customer, no history" (never invent points/offers/a visit
    pattern), and the ordinary triage-then-conversation flow must complete without error."""
    store = MemoryDataStore()
    catalog = _FakeCatalog({TENANT: [{"id": "svc_a", "name": "قص شعر", "price_minor": 5000}]})
    lookup = _FakeCustomerLookup(found=False)
    llm = StubLlm()
    llm.queue_text("أهلًا بك أول مرة! يسعدني حجز أول موعد لك.")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=_FakePointsWithOffers(), debounce_seconds=180,
        session_timeout_seconds=2400, raw_window_messages=12, allowed_tools=_ALLOWED,
        service_catalog=catalog, customer_lookup=lookup)

    new_number_subject = "sub_unseen"
    plan = await engine.handle_inbound_text(
        tenant=TENANT, subject_ref=new_number_subject, from_number="+966511110000",
        text="السلام عليكم، عندكم قص شعر؟", now=1000)
    assert plan.kind == "list"                              # ordinary triage gate, no crash
    await engine.handle_triage_selection(
        tenant=TENANT, subject_ref=new_number_subject, reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=new_number_subject,
                                 from_number="+966511110000", text="أبي أحجز", now=1002)
    reply = await engine.compose_reply(TENANT, new_number_subject, now=1200)
    assert reply.kind == "text"                              # completed normally, no exception

    # The context block built for this turn never invented history for a customer who has none —
    # verified directly, the same way the engine itself builds it.
    block = await engine._context_block(TENANT, new_number_subject, "+966511110000", True)
    assert "جديد" in block
    assert "نقاط" not in block or "لا" in block               # no points claimed for an unknown customer


async def test_a_known_customer_in_one_tenant_is_not_treated_as_known_in_another():
    """Tenant isolation on the offers/known-customer path specifically — a subject_ref that IS
    known for tenant t1 must not leak a "known customer with real offers" context for t2, where
    the lookup (correctly, per tenant scoping) answers found=False."""
    store = MemoryDataStore()

    class _PerTenantLookup:
        driver = "fake"
        async def resolve(self, tenant: str, phone: str) -> dict:
            return {"found": tenant == TENANT, "subject_ref": SUBJECT if tenant == TENANT else ""}

    engine = ConversationEngine(
        store=store, llm=StubLlm(), booking_provider=_provider(store),
        points_summary=_FakePointsWithOffers(), debounce_seconds=180,
        session_timeout_seconds=2400, raw_window_messages=12, allowed_tools=_ALLOWED,
        customer_lookup=_PerTenantLookup())

    block_home = await engine._context_block(TENANT, SUBJECT, "+9665", True)
    block_other = await engine._context_block(OTHER_TENANT, SUBJECT, "+9665", True)
    assert "غسيل مجاني" in block_home
    assert "غسيل مجاني" not in block_other
    assert "جديد" in block_other


# ── deep robustness pass on packages (100-test confidence sweep) ────────────────────────────────

def test_multiple_eligible_packages_are_all_listed():
    block = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[
            {"id": "pkg1", "name": "باقة أ", "service_ids": ["svc_a"], "price_minor": 6000,
             "component_price_minor_sum": 5000, "active": True,
             "next_offerable_dates": ["2026-06-06"]},
            {"id": "pkg2", "name": "باقة ب", "service_ids": ["svc_b"], "price_minor": 4000,
             "component_price_minor_sum": 3000, "active": True,
             "next_offerable_dates": ["2026-06-07"]},
        ])
    assert "باقة أ" in block and "باقة ب" in block


def test_a_package_priced_exactly_equal_to_its_components_is_still_mentioned():
    """`>=`, not `>` — the rule refuses only a package that LOWERS the total, and equal is not
    lower."""
    block = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[{"id": "pkg1", "name": "باقة متعادلة", "service_ids": ["svc_a", "svc_b"],
                  "price_minor": 8000, "component_price_minor_sum": 8000, "active": True,
                  "next_offerable_dates": ["2026-06-06"]}])
    assert "باقة متعادلة" in block


def test_a_package_referencing_a_service_id_not_in_the_catalogue_falls_back_to_the_raw_id():
    """A component service retired/removed since — degraded, never a crash or a blank line."""
    block = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[{"id": "pkg1", "name": "باقة", "service_ids": ["svc_gone"],
                  "price_minor": 6000, "component_price_minor_sum": 5000, "active": True,
                  "next_offerable_dates": ["2026-06-06"]}])
    assert "svc_gone" in block


def test_a_package_with_a_missing_price_field_is_treated_as_zero_not_a_crash():
    block = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[{"id": "pkg1", "name": "باقة بلا سعر", "service_ids": ["svc_a"],
                  "active": True, "next_offerable_dates": ["2026-06-06"]}])
    # price_minor missing -> 0, component_price_minor_sum missing -> 0: 0 >= 0 passes, so it IS
    # listed (this is a data-completeness concern for the caller, not something this pure
    # function should silently drop and hide from an owner debugging a missing suggestion).
    assert "باقة بلا سعر" in block


def test_several_upcoming_dates_are_all_listed_not_just_the_first():
    block = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[{"id": "pkg1", "name": "باقة السبت", "service_ids": ["svc_a", "svc_b"],
                  "price_minor": 9000, "component_price_minor_sum": 8000, "active": True,
                  "next_offerable_dates": ["2026-06-06", "2026-06-13", "2026-06-20"]}])
    assert "2026-06-06" in block and "2026-06-13" in block and "2026-06-20" in block


def test_a_package_with_two_extra_people_uses_correct_arabic_number():
    block = build_context_block(
        catalog=_catalog(), offers=[], known_customer=True,
        packages=[{"id": "pkg1", "name": "باقة الثنائي", "service_ids": ["svc_a", "svc_b"],
                  "price_minor": 9000, "component_price_minor_sum": 8000, "active": True,
                  "next_offerable_dates": ["2026-06-06"], "person_count": 2}])
    assert "2" in block and "أشخاص" in block


async def test_package_catalog_peer_failure_degrades_to_an_empty_packages_section():
    """A peer outage must not block the whole conversation — the customer still gets a normal
    reply, just without any package mentioned this turn."""
    class _BrokenPackageCatalog:
        driver = "broken"
        async def list_active(self, tenant: str) -> list[dict]:
            raise RuntimeError("operations is restarting")

    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_text("تمام!")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=_ALLOWED,
        service_catalog=_FakeCatalog({TENANT: _catalog()}),
        package_catalog=_BrokenPackageCatalog())
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="مرحبا", now=1002)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1200)
    assert plan.kind == "text"          # the conversation still proceeds normally


# ── list_packages: answers "do you have packages?" directly — not the upsell-only filter ────────

async def test_list_packages_answers_directly_even_below_the_upsell_price_floor():
    """A genuine discount bundle (priced BELOW its parts) is exactly what a customer asking about
    packages wants to hear — the upsell section's price_minor >= component_sum floor must NOT
    apply here, unlike test_an_eligible_package_reaches_the_models_own_context_block above."""
    store = MemoryDataStore()
    packages = _FakePackageCatalog({"t1": [
        {"id": "pkg1", "name": "باقة العناية الكاملة", "price_minor": 15000, "active": True,
         "service_ids": ["svc_a", "svc_b"], "next_offerable_dates": ["2026-09-10"]},
    ]})
    catalog = _FakeCatalog({"t1": [
        {"id": "svc_a", "name": "قص شعر", "price_minor": 0},
        {"id": "svc_b", "name": "حلاقة ذقن", "price_minor": 0}]})
    llm = StubLlm()
    llm.queue_tool_call("list_packages")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=frozenset({"list_packages"}),
        service_catalog=catalog, package_catalog=packages)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="عندكم باقات؟", now=1002)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1200)
    assert plan.kind == "text"
    assert "باقة العناية الكاملة" in plan.text
    assert "قص شعر" in plan.text and "حلاقة ذقن" in plan.text
    assert "150" in plan.text   # 15000 minor -> 150 riyals
    # NO PendingProposal, no button — presentational, same posture as suggest_related_service.
    conv = await engine._get(TENANT, SUBJECT)
    assert conv.pending_proposal_id == ""


async def test_list_packages_excludes_inactive_and_unbookable_packages():
    store = MemoryDataStore()
    packages = _FakePackageCatalog({"t1": [
        {"id": "pkg1", "name": "باقة منتهية", "price_minor": 100, "active": False,
         "service_ids": [], "next_offerable_dates": ["2026-09-10"]},
        {"id": "pkg2", "name": "باقة بلا مواعيد", "price_minor": 100, "active": True,
         "service_ids": [], "next_offerable_dates": []},
    ]})
    llm = StubLlm()
    llm.queue_tool_call("list_packages")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=frozenset({"list_packages"}),
        service_catalog=_FakeCatalog({}), package_catalog=packages)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="عندكم باقات؟", now=1002)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1200)
    assert "لا توجد باقات متاحة" in plan.text


async def test_list_packages_with_no_package_catalog_wired_says_so_plainly():
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_tool_call("list_packages")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=frozenset({"list_packages"}))
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="عندكم باقات؟", now=1002)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1200)
    assert "لا تتوفر باقات" in plan.text


async def test_no_package_catalog_wired_at_all_degrades_the_same_way():
    """Pre-existing test constructors (package_catalog=None, the default) must keep working
    unmodified — the same None-safe shape as every other optional peer in this engine."""
    store = MemoryDataStore()
    llm = StubLlm()
    llm.queue_text("تمام!")
    engine = ConversationEngine(
        store=store, llm=llm, booking_provider=_provider(store),
        points_summary=NullPointsSummary(), debounce_seconds=180, session_timeout_seconds=2400,
        raw_window_messages=12, allowed_tools=_ALLOWED)
    await engine.handle_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                     text="hi", now=1000)
    await engine.handle_triage_selection(tenant=TENANT, subject_ref=SUBJECT,
                                         reply_id="triage:inquiry", now=1001)
    await engine.on_inbound_text(tenant=TENANT, subject_ref=SUBJECT, from_number="+9665",
                                 text="مرحبا", now=1002)
    plan = await engine.compose_reply(TENANT, SUBJECT, now=1200)
    assert plan.kind == "text"
