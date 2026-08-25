"""Cross-sell (suggest_related_service), the rich per-turn context block (real catalogue + real
personal offers), the never-fabricate-a-discount backstop, and the brand-new-customer case."""
from app.adapters.datastore.memory import MemoryDataStore
from app.adapters.llm.stub import StubLlm
from app.adapters.ticket_client import NullTicketClient
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
        raw_window_messages=12, allowed_tools=_ALLOWED, ticket_client=NullTicketClient(),
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
        raw_window_messages=12, allowed_tools=_ALLOWED, ticket_client=NullTicketClient(),
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
        ticket_client=NullTicketClient(), service_catalog=catalog, customer_lookup=lookup)

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
    block = await engine._context_block(TENANT, new_number_subject, "+966511110000")
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
        ticket_client=NullTicketClient(), customer_lookup=_PerTenantLookup())

    block_home = await engine._context_block(TENANT, SUBJECT, "+9665")
    block_other = await engine._context_block(OTHER_TENANT, SUBJECT, "+9665")
    assert "غسيل مجاني" in block_home
    assert "غسيل مجاني" not in block_other
    assert "جديد" in block_other
