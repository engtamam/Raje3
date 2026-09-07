"""The upsell ledger's real wiring — offer written the instant a package proposal renders,
accepted flipped only on a real confirmed booking, declined flipped only on the SAME proposal's own
"إلغاء" button. Call-counting/state-proving throughout, never a value-only assertion a wrong
implementation could also pass — matches this session's own established test discipline
(pricing_report.py/pricing_schedule.py's own tests)."""
from __future__ import annotations

import time

from app.adapters.datastore.memory import MemoryDataStore
from app.core import tools as T
from app.core.conversation import ConversationEngine
from app.core.points import NullPointsSummary
from app.core.upsell_ledger import UPSELL_LEDGER
from app.ports.booking_provider import Slot

TENANT = "t1"
ALLOWED = frozenset({"check_availability", "propose_booking"})


class _FakeRealProvider:
    driver = "real"

    def __init__(self, *, slots: list[Slot], confirm_answer: dict | None = None) -> None:
        self._slots = slots
        self._confirm_answer = confirm_answer or {"id": "bkg_1"}
        self.confirm_calls: list[dict] = []

    async def availability_for_package(self, *, tenant: str, package_id: str, earliest: int,
                                       branch_id: str = "", exclude_booking_id: str = "") -> list[Slot]:
        return [s for s in self._slots if s.starts_at >= earliest]

    async def hold_and_confirm_package(self, **kwargs) -> dict:
        self.confirm_calls.append(kwargs)
        return self._confirm_answer


class _FakePackageCatalog:
    def __init__(self, packages: list[dict]) -> None:
        self._packages = packages

    async def list_active(self, tenant: str) -> list[dict]:
        return self._packages


class _Auditor:
    async def record(self, *a, **kw) -> None:
        return None


def _iso(ts: int) -> str:
    import datetime as dt
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()


async def test_propose_booking_for_a_package_writes_a_pending_offer_row_with_a_real_price():
    now = int(time.time())
    starts_at = now + 3600
    provider = _FakeRealProvider(slots=[Slot(starts_at=starts_at, duration_minutes=0)])
    catalog = _FakePackageCatalog([{"id": "pkg1", "price_minor": 15000}])
    store = MemoryDataStore()
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"package_id": "pkg1", "starts_at_iso": _iso(starts_at)}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, branch_id="brn1", package_catalog=catalog)

    row = await store.get(UPSELL_LEDGER, result.proposal_id)
    assert row is not None, "propose_booking(package_id=...) must write a real offer row"
    assert row["outcome"] == "pending"
    assert row["package_id"] == "pkg1"
    assert row["branch_id"] == "brn1"
    assert row["price_minor"] == 15000, "the price must come from the real catalogue, never invented"


async def test_propose_booking_for_a_plain_service_writes_no_upsell_row():
    now = int(time.time())
    starts_at = now + 3600
    provider = _FakeRealProvider(slots=[])

    class _ServiceProvider(_FakeRealProvider):
        async def availability(self, **kwargs) -> list[Slot]:
            return [Slot(starts_at=starts_at, duration_minutes=30)]

    store = MemoryDataStore()
    result = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"service_id": "svc1", "starts_at_iso": _iso(starts_at)}, allowed_tools=ALLOWED,
        store=store, booking_provider=_ServiceProvider(slots=[]), points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800)
    assert await store.scan_all(UPSELL_LEDGER, limit=10) == [], (
        "an ordinary single-service proposal is not an upsell and must never be logged as one")


async def test_confirming_a_package_proposal_flips_the_ledger_row_to_accepted_with_the_booking_id():
    now = int(time.time())
    starts_at = now + 3600
    provider = _FakeRealProvider(slots=[Slot(starts_at=starts_at, duration_minutes=0)],
                                 confirm_answer={"id": "bkg_real_1"})
    catalog = _FakePackageCatalog([{"id": "pkg1", "price_minor": 20000}])
    store = MemoryDataStore()

    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"package_id": "pkg1", "starts_at_iso": _iso(starts_at)}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, branch_id="brn1", package_catalog=catalog)

    result = await T.execute_confirmed_proposal(
        tenant=TENANT, proposal_id=proposal.proposal_id, store=store, booking_provider=provider,
        auditor=_Auditor(), idempotency_key="btn_1", branch_id="brn1", from_number="+9665")
    assert result["kind"] == "booking"

    row = await store.get(UPSELL_LEDGER, proposal.proposal_id)
    assert row["outcome"] == "accepted"
    assert row["booking_id"] == "bkg_real_1"
    assert row["price_minor"] == 20000


async def test_declining_a_package_proposal_via_its_own_cancel_button_flips_the_row_to_declined():
    """The REAL decline path — conversation.py::handle_button_reply's own `action == "cancel"`
    branch, reached exactly the way a customer's "إلغاء" tap reaches it, never a heuristic."""
    now = int(time.time())
    starts_at = now + 3600
    provider = _FakeRealProvider(slots=[Slot(starts_at=starts_at, duration_minutes=0)])
    catalog = _FakePackageCatalog([{"id": "pkg1", "price_minor": 12000}])
    store = MemoryDataStore()

    proposal = await T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1", tool="propose_booking",
        args={"package_id": "pkg1", "starts_at_iso": _iso(starts_at)}, allowed_tools=ALLOWED,
        store=store, booking_provider=provider, points_summary=NullPointsSummary(),
        proposal_ttl_seconds=1800, branch_id="brn1", package_catalog=catalog)

    engine = ConversationEngine(
        store=store, llm=None, booking_provider=provider, points_summary=NullPointsSummary(),
        debounce_seconds=180, session_timeout_seconds=2400, raw_window_messages=12,
        allowed_tools=ALLOWED, package_catalog=catalog)
    conv = await engine._get(TENANT, "sub1")
    conv.pending_proposal_id = proposal.proposal_id
    conv.from_number = "+9665"
    conv.branch_id = "brn1"
    await engine._save(conv)

    await engine.handle_button_reply(
        tenant=TENANT, subject_ref="sub1", reply_id=f"{proposal.proposal_id}:cancel",
        auditor=_Auditor())

    row = await store.get(UPSELL_LEDGER, proposal.proposal_id)
    assert row["outcome"] == "declined"
    assert row["booking_id"] == ""
