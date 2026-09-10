"""FlowBookingBackend — the WhatsApp Flow (structured screens) counterpart to RealBookingProvider.
Same fake-peer discipline as test_booking_assignment.py beside it."""
from app.core.booking_assignment import RealBookingProvider
from app.core.flow_booking_backend import FlowBookingBackend

TENANT = "t1"
BRANCH = "brn-jeddah"


class _FakePeer:
    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []

    def call(self, payload, path_params=None):
        self.calls.append(payload)
        return self._response


class _FakeCatalog:
    def __init__(self, services):
        self._services = services

    async def list_active(self, tenant):
        return self._services


class _FakeBranches:
    def __init__(self, branches):
        self._branches = branches

    async def list_open(self, tenant):
        return self._branches


def _real(*, branch_operators=None, service_eligibility=None, nearest_any_real_slot=None,
         create_booking=None, customer_id_by_phone=None) -> RealBookingProvider:
    return RealBookingProvider(
        branch_operators=branch_operators or _FakePeer({"operators": []}),
        service_eligibility=service_eligibility or _FakePeer({"eligible_staff_ids": {}}),
        customer_id_by_phone=customer_id_by_phone or _FakePeer({"customer_id": "cust_1"}),
        nearest_real_slot=_FakePeer({"starts_at": None}),
        nearest_any_real_slot=nearest_any_real_slot or _FakePeer({"slots": []}),
        create_booking=create_booking or _FakePeer(None))


class _FakeCustomerLookup:
    def __init__(self, found: bool, subject_ref: str = "sub_1"):
        self._found, self._subject_ref = found, subject_ref

    async def resolve(self, tenant, phone):
        return {"found": self._found, "subject_ref": self._subject_ref if self._found else ""}


class _FakePointsSummary:
    def __init__(self, offers: list[dict]):
        self._offers = offers

    async def offers(self, *, tenant, subject_ref):
        return self._offers


def _backend(*, catalog=None, branches=None, day_slots=None, real=None,
            customer_lookup=None, points_summary=None) -> FlowBookingBackend:
    return FlowBookingBackend(
        real=real or _real(), catalog=catalog or _FakeCatalog([]),
        branch_directory=branches or _FakeBranches([{"id": BRANCH}]),
        day_slots=day_slots or _FakePeer({"starts_at": []}),
        working_hours_url="http://bookings", working_hours_path="/internal/working-hours",
        token="tok", timeout=5,
        customer_lookup=customer_lookup, points_summary=points_summary)


# ── options(dimension="service") ─────────────────────────────────────────────────────────────

async def test_options_service_lists_the_real_priced_catalogue():
    catalog = _FakeCatalog([{"id": "svc1", "name": "قص شعر", "assignment_mode": "auto"}])
    backend = _backend(catalog=catalog)
    options = await backend.options(tenant=TENANT, dimension="service", chosen={})
    assert options == [{"id": "svc1", "title": "قص شعر"}]


# ── options(dimension="staff") — the conditional-skip contract (v0.18.53) ──────────────────────

async def test_options_staff_skips_for_an_auto_mode_service():
    """An `auto` service must return an EMPTY list — never an "any available" placeholder — so
    the platform's engine skips the step silently (v0.18.53's own contract)."""
    catalog = _FakeCatalog([{"id": "svc1", "name": "قص شعر", "assignment_mode": "auto"}])
    backend = _backend(catalog=catalog)
    options = await backend.options(tenant=TENANT, dimension="staff", chosen={"service": "svc1"})
    assert options == []


async def test_options_staff_lists_real_names_for_a_named_mode_service():
    catalog = _FakeCatalog([{"id": "svc1", "name": "قص شعر", "assignment_mode": "named"}])
    ops = _FakePeer({"operators": [{"id": "op1", "name": "أحمد"}, {"id": "op2", "name": "سعيد"}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None}})   # unrestricted = every field operator
    real = _real(branch_operators=ops, service_eligibility=elig)
    backend = _backend(catalog=catalog, real=real)
    options = await backend.options(tenant=TENANT, dimension="staff", chosen={"service": "svc1"})
    assert {"id": "op1", "title": "أحمد"} in options
    assert {"id": "op2", "title": "سعيد"} in options


async def test_options_staff_skips_when_service_is_unknown_or_missing():
    backend = _backend(catalog=_FakeCatalog([]))
    assert await backend.options(tenant=TENANT, dimension="staff", chosen={}) == []
    assert await backend.options(
        tenant=TENANT, dimension="staff", chosen={"service": "ghost"}) == []


async def test_options_staff_skips_without_a_single_resolvable_branch():
    """A central shop with 0 or 2+ open branches — the documented single-branch-only limitation —
    must skip rather than guess a branch."""
    catalog = _FakeCatalog([{"id": "svc1", "name": "قص شعر", "assignment_mode": "named"}])
    backend = _backend(catalog=catalog, branches=_FakeBranches([]))
    assert await backend.options(
        tenant=TENANT, dimension="staff", chosen={"service": "svc1"}) == []
    backend2 = _backend(catalog=catalog,
                        branches=_FakeBranches([{"id": "b1"}, {"id": "b2"}]))
    assert await backend2.options(
        tenant=TENANT, dimension="staff", chosen={"service": "svc1"}) == []


async def test_options_unknown_dimension_is_empty():
    backend = _backend()
    assert await backend.options(tenant=TENANT, dimension="party_size", chosen={}) == []


# ── options(dimension="reward") — loyalty-in-booking ────────────────────────────────────────────

async def test_options_reward_skips_when_peers_are_not_wired():
    """The default, unconfigured state — never a crash, never a fake offer."""
    backend = _backend(customer_lookup=None, points_summary=None)
    assert await backend.options(
        tenant=TENANT, dimension="reward", chosen={}, customer="+9665") == []


async def test_options_reward_skips_without_a_customer_seeded():
    backend = _backend(customer_lookup=_FakeCustomerLookup(True),
                       points_summary=_FakePointsSummary([{"reward_id": "r1"}]))
    assert await backend.options(tenant=TENANT, dimension="reward", chosen={}, customer="") == []


async def test_options_reward_skips_when_the_customer_cannot_be_resolved():
    backend = _backend(customer_lookup=_FakeCustomerLookup(False),
                       points_summary=_FakePointsSummary([{"reward_id": "r1"}]))
    assert await backend.options(
        tenant=TENANT, dimension="reward", chosen={}, customer="+9665") == []


async def test_options_reward_skips_when_nothing_is_affordable():
    backend = _backend(customer_lookup=_FakeCustomerLookup(True),
                       points_summary=_FakePointsSummary([]))
    assert await backend.options(
        tenant=TENANT, dimension="reward", chosen={}, customer="+9665") == []


async def test_options_reward_lists_real_affordable_offers():
    offers = [{"reward_id": "r1", "reward_name": "قهوة مجانية", "points_cost": 500},
             {"reward_id": "r2", "reward_name": "خصم 10٪", "points_cost": 200}]
    backend = _backend(customer_lookup=_FakeCustomerLookup(True),
                       points_summary=_FakePointsSummary(offers))
    options = await backend.options(
        tenant=TENANT, dimension="reward", chosen={}, customer="+9665")
    assert {"id": "r1", "title": "قهوة مجانية — 500 نقطة"} in options
    assert {"id": "r2", "title": "خصم 10٪ — 200 نقطة"} in options


# ── calendar() ───────────────────────────────────────────────────────────────────────────────

async def test_calendar_excludes_closed_weekdays():
    class _WHPeer:
        async def _get(self):
            pass

    backend = _backend()

    async def _fake_working_hours(tenant):
        # Sunday (index 6) closed, everything else open.
        return {str(i): {"closed": i == 6} for i in range(7)}

    backend._working_hours = _fake_working_hours   # type: ignore[method-assign]
    cal = await backend.calendar(tenant=TENANT, chosen={})
    assert "Sun" not in cal["include_days"]
    assert "Mon" in cal["include_days"] and "Sat" in cal["include_days"]
    assert cal["unavailable_dates"] == []


async def test_calendar_degrades_to_no_restriction_when_working_hours_peer_is_unreachable():
    backend = _backend()

    async def _empty(tenant):
        return {}

    backend._working_hours = _empty   # type: ignore[method-assign]
    cal = await backend.calendar(tenant=TENANT, chosen={})
    assert len(cal["include_days"]) == 7   # nothing marked closed -> nothing excluded


# ── slots() ──────────────────────────────────────────────────────────────────────────────────

async def test_slots_returns_formatted_times_for_the_eligible_pool():
    catalog = _FakeCatalog([{"id": "svc1", "name": "قص", "assignment_mode": "auto"}])
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None}})
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    day_slots = _FakePeer({"starts_at": [1893456000, 1893459600]})   # two epoch times
    real = _real(branch_operators=ops, service_eligibility=elig)
    backend = _backend(catalog=catalog, day_slots=day_slots, real=real)
    slots = await backend.slots(tenant=TENANT, chosen={"service": "svc1"}, date="2030-01-01")
    assert [s["id"] for s in slots] == ["1893456000", "1893459600"]
    assert all(":" in s["title"] for s in slots)


async def test_slots_pins_the_pool_to_a_chosen_named_staff_member():
    catalog = _FakeCatalog([{"id": "svc1", "name": "قص", "assignment_mode": "named"}])
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None}})
    ops = _FakePeer({"operators": [{"id": "op1"}, {"id": "op2"}]})
    day_slots = _FakePeer({"starts_at": []})
    real = _real(branch_operators=ops, service_eligibility=elig)
    backend = _backend(catalog=catalog, day_slots=day_slots, real=real)
    await backend.slots(tenant=TENANT, chosen={"service": "svc1", "staff": "op2"}, date="2030-01-01")
    assert day_slots.calls[-1]["operator_ids"] == ["op2"]


async def test_slots_empty_when_chosen_staff_is_not_actually_eligible():
    """A stale/tampered `staff` choice must not silently fall back to the whole pool."""
    catalog = _FakeCatalog([{"id": "svc1", "name": "قص", "assignment_mode": "named"}])
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None}})
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    real = _real(branch_operators=ops, service_eligibility=elig)
    backend = _backend(catalog=catalog, real=real)
    slots = await backend.slots(
        tenant=TENANT, chosen={"service": "svc1", "staff": "not_eligible"}, date="2030-01-01")
    assert slots == []


async def test_slots_empty_without_service_or_date():
    backend = _backend()
    assert await backend.slots(tenant=TENANT, chosen={}, date="2030-01-01") == []
    assert await backend.slots(tenant=TENANT, chosen={"service": "svc1"}, date="") == []


# ── reserve() ────────────────────────────────────────────────────────────────────────────────

async def test_reserve_refuses_without_a_customer():
    backend = _backend()
    result = await backend.reserve(
        tenant=TENANT, selection={"service": "svc1", "time": "1893456000"},
        idempotency_key="idem1", customer="")
    assert result["ok"] is False


async def test_reserve_creates_a_real_booking_and_returns_its_ref():
    create = _FakePeer({"id": "bk_123"})
    merge = _FakePeer({"slots": [{"operator_id": "op1", "starts_at": 1893456000}]})
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    real = _real(nearest_any_real_slot=merge, create_booking=create, branch_operators=ops)
    backend = _backend(real=real)
    result = await backend.reserve(
        tenant=TENANT, selection={"service": "svc1", "time": "1893456000"},
        idempotency_key="idem1", customer="+966500000000")
    assert result == {"ok": True, "ref": "bk_123"}


async def test_reserve_honours_a_named_staff_pick():
    create = _FakePeer({"id": "bk_456"})
    merge = _FakePeer({"slots": [{"operator_id": "op2", "starts_at": 1893456000}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None}})
    ops = _FakePeer({"operators": [{"id": "op1"}, {"id": "op2"}]})
    real = _real(nearest_any_real_slot=merge, create_booking=create,
                branch_operators=ops, service_eligibility=elig)
    backend = _backend(real=real)
    await backend.reserve(
        tenant=TENANT, selection={"service": "svc1", "time": "1893456000", "staff": "op2"},
        idempotency_key="idem1", customer="+966500000000")
    assert merge.calls[-1]["operator_ids"] == ["op2"]


async def test_reserve_passes_the_chosen_reward_as_intended_reward_id():
    """LOYALTY-IN-BOOKING — the chosen reward books AND redeems atomically via the same
    intended_reward_id field Phase 4 already built (INTENT only, spent at attend() time)."""
    create = _FakePeer({"id": "bk_789"})
    merge = _FakePeer({"slots": [{"operator_id": "op1", "starts_at": 1893456000}]})
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    real = _real(nearest_any_real_slot=merge, create_booking=create, branch_operators=ops)
    backend = _backend(real=real)
    result = await backend.reserve(
        tenant=TENANT, selection={"service": "svc1", "time": "1893456000", "reward": "r1"},
        idempotency_key="idem1", customer="+966500000000")
    assert result == {"ok": True, "ref": "bk_789"}
    assert create.calls[-1]["intended_reward_id"] == "r1"


async def test_reserve_without_a_chosen_reward_sends_no_intended_reward_id():
    create = _FakePeer({"id": "bk_790"})
    merge = _FakePeer({"slots": [{"operator_id": "op1", "starts_at": 1893456000}]})
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    real = _real(nearest_any_real_slot=merge, create_booking=create, branch_operators=ops)
    backend = _backend(real=real)
    await backend.reserve(
        tenant=TENANT, selection={"service": "svc1", "time": "1893456000"},
        idempotency_key="idem1", customer="+966500000000")
    assert "intended_reward_id" not in create.calls[-1]


async def test_reserve_reports_a_readable_reason_on_refusal():
    merge = _FakePeer({"slots": []})   # nothing free -> BookingAssignmentError
    real = _real(nearest_any_real_slot=merge)
    backend = _backend(real=real)
    result = await backend.reserve(
        tenant=TENANT, selection={"service": "svc1", "time": "1893456000"},
        idempotency_key="idem1", customer="+966500000000")
    assert result["ok"] is False
    assert result["reason"]


async def test_reserve_refuses_incomplete_selection():
    backend = _backend()
    assert (await backend.reserve(tenant=TENANT, selection={}, idempotency_key="i",
                                  customer="+9665")) == {
        "ok": False, "reason": "الاختيار غير مكتمل."}


# ── multi-select (platform v0.19.16's CheckboxGroup Flow steps) ───────────────────────────────
async def test_reserve_with_a_multi_select_service_list_sends_all_of_them():
    create = _FakePeer({"id": "bk_multi1"})
    merge = _FakePeer({"slots": [{"operator_id": "op1", "starts_at": 1893456000}]})
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None, "svc2": None}})
    real = _real(nearest_any_real_slot=merge, create_booking=create, branch_operators=ops,
                service_eligibility=elig)
    backend = _backend(real=real)
    result = await backend.reserve(
        tenant=TENANT, selection={"service": ["svc1", "svc2"], "time": "1893456000"},
        idempotency_key="idem_multi1", customer="+966500000000")
    assert result == {"ok": True, "ref": "bk_multi1"}
    assert create.calls[0]["service_ids"] == ["svc1", "svc2"]


async def test_options_staff_asks_when_any_chosen_service_is_named_even_if_not_all():
    """The strictest chosen service decides — one `named` service among several `auto` ones
    still means an operator must be picked, since whoever is assigned has to do ALL of them."""
    catalog = _FakeCatalog([
        {"id": "svc1", "name": "قص", "assignment_mode": "auto"},
        {"id": "svc2", "name": "صبغة", "assignment_mode": "named"},
    ])
    ops = _FakePeer({"operators": [{"id": "op1", "name": "سارة"}]})
    backend = _backend(catalog=catalog, real=_real(branch_operators=ops))
    options = await backend.options(
        tenant=TENANT, dimension="staff", chosen={"service": ["svc1", "svc2"]})
    assert options == [{"id": "op1", "title": "سارة"}]


async def test_options_staff_skips_when_every_chosen_service_is_auto():
    catalog = _FakeCatalog([
        {"id": "svc1", "name": "قص", "assignment_mode": "auto"},
        {"id": "svc2", "name": "تنظيف", "assignment_mode": "auto"},
    ])
    backend = _backend(catalog=catalog)
    options = await backend.options(
        tenant=TENANT, dimension="staff", chosen={"service": ["svc1", "svc2"]})
    assert options == []


async def test_slots_for_a_multi_select_service_list_asks_the_pool_eligible_for_all():
    ops = _FakePeer({"operators": [{"id": "op1"}, {"id": "op2"}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": ["op1", "op2"], "svc2": ["op2"]}})
    day_slots = _FakePeer({"starts_at": [1893456000]})
    real = _real(branch_operators=ops, service_eligibility=elig)
    backend = _backend(real=real, day_slots=day_slots)
    slots = await backend.slots(
        tenant=TENANT, chosen={"service": ["svc1", "svc2"]}, date="2030-01-01")
    assert len(slots) == 1
    assert day_slots.calls[0]["service_ids"] == ["svc1", "svc2"]
    assert day_slots.calls[0]["operator_ids"] == ["op2"]
