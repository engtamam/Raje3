"""RealBookingProvider (Phase 4) — operator assignment policy (first eligible, deterministic),
and that a branch/phone is REQUIRED, never guessed, before a real slot search or a real booking
write reaches its peers."""
from app.core.booking_assignment import BookingAssignmentError, RealBookingProvider

TENANT = "t1"
BRANCH = "brn-jeddah"


class _FakePeer:
    """Duck-types `_Peer.call(payload, path_params=None) -> dict|None` — records every call it
    received (payload and any path_params, since the booking-management peers below format a
    `{booking_id}` placeholder per-call rather than at construction — see _Peer.call's own note)."""

    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []
        self.path_params: list[dict] = []

    def call(self, payload, path_params=None):
        self.calls.append(payload)
        self.path_params.append(path_params or {})
        return self._response


def _provider(*, branch_operators=None, service_eligibility=None,
             customer_id_by_phone=None, nearest_real_slot=None, create_booking=None,
             bookings_for_customer=None, cancel_booking=None, reschedule_booking=None,
             package_eligibility=None):
    return RealBookingProvider(
        branch_operators=branch_operators or _FakePeer({"operators": []}),
        service_eligibility=service_eligibility or _FakePeer({"eligible_staff_ids": {}}),
        customer_id_by_phone=customer_id_by_phone or _FakePeer({"customer_id": ""}),
        nearest_real_slot=nearest_real_slot or _FakePeer({"starts_at": None}),
        create_booking=create_booking or _FakePeer(None),
        bookings_for_customer=bookings_for_customer, cancel_booking=cancel_booking,
        reschedule_booking=reschedule_booking, package_eligibility=package_eligibility)


async def test_availability_with_no_branch_never_calls_any_peer():
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    provider = _provider(branch_operators=ops)
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=1000,
                                        horizon_days=0, branch_id="")
    assert slots == []
    assert ops.calls == []


async def test_availability_picks_the_first_eligible_operator_deterministically():
    ops = _FakePeer({"operators": [{"id": "op2"}, {"id": "op1"}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None}})   # None = unrestricted, everyone eligible
    slot = _FakePeer({"starts_at": 5000})
    provider = _provider(branch_operators=ops, service_eligibility=elig, nearest_real_slot=slot)
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=1000,
                                        horizon_days=0, branch_id=BRANCH)
    assert [s.starts_at for s in slots] == [5000]
    # "op1" sorts before "op2" — the deterministic tie-break.
    assert slot.calls[0]["operator_id"] == "op1"


async def test_availability_narrows_to_the_restricted_eligible_set():
    ops = _FakePeer({"operators": [{"id": "op1"}, {"id": "op2"}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": ["op2"]}})
    slot = _FakePeer({"starts_at": 5000})
    provider = _provider(branch_operators=ops, service_eligibility=elig, nearest_real_slot=slot)
    await provider.availability(tenant=TENANT, service_id="svc1", earliest=1000,
                                horizon_days=0, branch_id=BRANCH)
    assert slot.calls[0]["operator_id"] == "op2"


async def test_availability_forwards_exclude_booking_id_to_the_peer_payload_when_given():
    """The end of the exclude_booking_id chain that test_booking_management.py's fully-faked
    _FakeManagementProvider CANNOT prove, because it bypasses RealBookingProvider/_Peer entirely —
    this is the one test that would actually catch a regression in booking_assignment.py's own
    payload-building (a deleted line, a typo'd key) even though every other test in the suite,
    including the reschedule-to-own-time ones, would keep passing regardless."""
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None}})
    slot = _FakePeer({"starts_at": 5000})
    provider = _provider(branch_operators=ops, service_eligibility=elig, nearest_real_slot=slot)
    await provider.availability(tenant=TENANT, service_id="svc1", earliest=1000,
                                horizon_days=0, branch_id=BRANCH, exclude_booking_id="bkg1")
    assert slot.calls[0]["exclude_booking_id"] == "bkg1"


async def test_availability_omits_exclude_booking_id_from_the_payload_when_not_given():
    """The other half — a NEW booking's own availability check (check_availability/propose_booking,
    which never pass exclude_booking_id) must not accidentally send an empty-string exclusion that
    bookings-service's own filter would need to special-case; omitting the key entirely is the
    contract `_Peer`'s payload-building relies on (see booking_assignment.py's own `if
    exclude_booking_id:` guard)."""
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None}})
    slot = _FakePeer({"starts_at": 5000})
    provider = _provider(branch_operators=ops, service_eligibility=elig, nearest_real_slot=slot)
    await provider.availability(tenant=TENANT, service_id="svc1", earliest=1000,
                                horizon_days=0, branch_id=BRANCH)
    assert "exclude_booking_id" not in slot.calls[0]


async def test_availability_with_zero_eligible_operators_returns_empty_not_an_error():
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": []}})   # restricted to nobody
    provider = _provider(branch_operators=ops, service_eligibility=elig)
    slots = await provider.availability(tenant=TENANT, service_id="svc1", earliest=1000,
                                        horizon_days=0, branch_id=BRANCH)
    assert slots == []


async def test_hold_and_confirm_refuses_without_a_branch():
    provider = _provider()
    try:
        await provider.hold_and_confirm(tenant=TENANT, subject_ref="sub1", service_id="svc1",
                                        starts_at=5000, idempotency_key="k1",
                                        branch_id="", from_number="+9665")
        assert False, "expected BookingAssignmentError"
    except BookingAssignmentError:
        pass


async def test_hold_and_confirm_refuses_without_a_phone():
    provider = _provider()
    try:
        await provider.hold_and_confirm(tenant=TENANT, subject_ref="sub1", service_id="svc1",
                                        starts_at=5000, idempotency_key="k1",
                                        branch_id=BRANCH, from_number="")
        assert False, "expected BookingAssignmentError"
    except BookingAssignmentError:
        pass


async def test_hold_and_confirm_resolves_a_real_customer_id_and_creates_the_booking():
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None}})
    cust = _FakePeer({"customer_id": "cus_real1"})
    created = _FakePeer({"id": "bkg_1", "status": "booked"})
    provider = _provider(branch_operators=ops, service_eligibility=elig,
                         customer_id_by_phone=cust, create_booking=created)
    booking = await provider.hold_and_confirm(
        tenant=TENANT, subject_ref="sub1", service_id="svc1", starts_at=5000,
        idempotency_key="k1", branch_id=BRANCH, from_number="+9665")
    assert booking["id"] == "bkg_1"
    assert created.calls[0]["customer_id"] == "cus_real1"
    assert created.calls[0]["operator_id"] == "op1"
    assert created.calls[0]["branch_id"] == BRANCH
    assert created.calls[0]["idempotency_key"] == "k1"
    # THE PHONE NUMBER ITSELF NEVER REACHES bookings-service — only the resolved customer_id.
    assert "from_number" not in created.calls[0] and "phone" not in created.calls[0]
    # ATTRIBUTION — every AI-made booking is stamped with the service's own actor constant, never
    # left blank (which would read, downstream, as indistinguishable from a staff-made booking).
    assert created.calls[0]["created_by"] == "whatsapp-assistant"


async def test_hold_and_confirm_package_stamps_the_ai_actor_as_created_by():
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    cust = _FakePeer({"customer_id": "cus_real1"})
    created = _FakePeer({"id": "bkg_1", "status": "booked"})
    provider = _provider(branch_operators=ops, customer_id_by_phone=cust, create_booking=created)
    await provider.hold_and_confirm_package(
        tenant=TENANT, subject_ref="sub1", package_id="pkg1", starts_at=5000,
        idempotency_key="k1", branch_id=BRANCH, from_number="+9665")
    assert created.calls[0]["created_by"] == "whatsapp-assistant"


async def test_hold_and_confirm_refuses_when_the_phone_resolves_to_no_customer():
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None}})
    cust = _FakePeer({"customer_id": ""})
    provider = _provider(branch_operators=ops, service_eligibility=elig, customer_id_by_phone=cust)
    try:
        await provider.hold_and_confirm(tenant=TENANT, subject_ref="sub1", service_id="svc1",
                                        starts_at=5000, idempotency_key="k1",
                                        branch_id=BRANCH, from_number="+9665")
        assert False, "expected BookingAssignmentError"
    except BookingAssignmentError:
        pass


# ── packages (book a PACKAGE instead of a single service) ───────────────────────────────────────

async def test_availability_for_package_picks_the_first_eligible_operator():
    ops = _FakePeer({"operators": [{"id": "op2"}, {"id": "op1"}]})
    elig = _FakePeer({"eligible_staff_ids": None})   # unrestricted
    slot = _FakePeer({"starts_at": 5000})
    provider = _provider(branch_operators=ops, package_eligibility=elig, nearest_real_slot=slot)
    slots = await provider.availability_for_package(
        tenant=TENANT, package_id="pkg1", earliest=1000, branch_id=BRANCH)
    assert [s.starts_at for s in slots] == [5000]
    assert slot.calls[0]["operator_id"] == "op1"
    assert slot.calls[0]["package_id"] == "pkg1"
    assert "service_ids" not in slot.calls[0]


async def test_availability_for_package_with_no_branch_never_calls_any_peer():
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    provider = _provider(branch_operators=ops)
    slots = await provider.availability_for_package(
        tenant=TENANT, package_id="pkg1", earliest=1000, branch_id="")
    assert slots == []
    assert ops.calls == []


async def test_availability_for_package_narrows_to_the_restricted_eligible_set():
    ops = _FakePeer({"operators": [{"id": "op1"}, {"id": "op2"}]})
    elig = _FakePeer({"eligible_staff_ids": ["op2"]})
    slot = _FakePeer({"starts_at": 5000})
    provider = _provider(branch_operators=ops, package_eligibility=elig, nearest_real_slot=slot)
    slots = await provider.availability_for_package(
        tenant=TENANT, package_id="pkg1", earliest=1000, branch_id=BRANCH)
    assert [s.starts_at for s in slots] == [5000]
    assert slot.calls[0]["operator_id"] == "op2"


async def test_availability_for_package_with_no_eligible_operator_returns_empty():
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    elig = _FakePeer({"eligible_staff_ids": ["op9"]})
    provider = _provider(branch_operators=ops, package_eligibility=elig)
    slots = await provider.availability_for_package(
        tenant=TENANT, package_id="pkg1", earliest=1000, branch_id=BRANCH)
    assert slots == []


async def test_hold_and_confirm_package_resolves_a_real_customer_id_and_creates_the_booking():
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    elig = _FakePeer({"eligible_staff_ids": None})
    cust = _FakePeer({"customer_id": "cus_real1"})
    created = _FakePeer({"id": "bkg_1", "status": "booked"})
    provider = _provider(branch_operators=ops, package_eligibility=elig,
                        customer_id_by_phone=cust, create_booking=created)
    booking = await provider.hold_and_confirm_package(
        tenant=TENANT, subject_ref="sub1", package_id="pkg1", starts_at=5000,
        idempotency_key="k1", branch_id=BRANCH, from_number="+9665")
    assert booking["id"] == "bkg_1"
    assert created.calls[0]["customer_id"] == "cus_real1"
    assert created.calls[0]["package_id"] == "pkg1"
    assert "service_ids" not in created.calls[0]


async def test_hold_and_confirm_package_refuses_without_a_branch():
    provider = _provider()
    try:
        await provider.hold_and_confirm_package(
            tenant=TENANT, subject_ref="sub1", package_id="pkg1", starts_at=5000,
            idempotency_key="k1", branch_id="", from_number="+9665")
        assert False, "expected BookingAssignmentError"
    except BookingAssignmentError:
        pass


async def test_hold_and_confirm_package_refuses_when_the_phone_resolves_to_no_customer():
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    cust = _FakePeer({"customer_id": ""})
    provider = _provider(branch_operators=ops, customer_id_by_phone=cust)
    try:
        await provider.hold_and_confirm_package(
            tenant=TENANT, subject_ref="sub1", package_id="pkg1", starts_at=5000,
            idempotency_key="k1", branch_id=BRANCH, from_number="+9665")
        assert False, "expected BookingAssignmentError"
    except BookingAssignmentError:
        pass


async def test_package_eligibility_not_wired_defaults_to_the_first_operator_sorted():
    """No `package_eligibility` peer at all — degrade to the same deterministic pick as an
    unrestricted service, never a crash."""
    ops = _FakePeer({"operators": [{"id": "op2"}, {"id": "op1"}]})
    slot = _FakePeer({"starts_at": 5000})
    provider = _provider(branch_operators=ops, nearest_real_slot=slot)
    slots = await provider.availability_for_package(
        tenant=TENANT, package_id="pkg1", earliest=1000, branch_id=BRANCH)
    assert [s.starts_at for s in slots] == [5000]
    assert slot.calls[0]["operator_id"] == "op1"


# ── booking management (list/cancel/reschedule an EXISTING booking) — the master kill-switch ────

async def test_list_bookings_raises_when_the_peer_was_never_built_the_flag_was_off():
    """No `bookings_for_customer` peer at all (BOOKING_MANAGEMENT_ENABLED=False at build() time,
    see that function's own note) — must refuse loudly, never silently return an empty list that
    could be misread as "no bookings"."""
    provider = _provider()
    try:
        await provider.list_bookings(tenant=TENANT, from_number="+9665")
        assert False, "expected BookingAssignmentError"
    except BookingAssignmentError:
        pass


async def test_list_bookings_resolves_customer_id_from_phone_never_from_a_caller_supplied_id():
    cust = _FakePeer({"customer_id": "cus_real1"})
    for_customer = _FakePeer({"bookings": [{"id": "bkg_1"}]})
    provider = _provider(customer_id_by_phone=cust, bookings_for_customer=for_customer)
    result = await provider.list_bookings(tenant=TENANT, from_number="+9665")
    assert result == [{"id": "bkg_1"}]
    assert for_customer.calls[0]["customer_id"] == "cus_real1"
    # No caller-supplied customer id parameter exists on list_bookings at all — the phone is the
    # only input, so there is no argument here a customer or the model could use to name someone
    # else's bookings.


async def test_cancel_booking_stamps_the_booking_id_into_the_url_not_the_body():
    cust = _FakePeer({"customer_id": "cus_real1"})
    cancel = _FakePeer({"id": "bkg_1", "status": "cancelled"})
    provider = _provider(customer_id_by_phone=cust, cancel_booking=cancel)
    result = await provider.cancel_booking(tenant=TENANT, from_number="+9665",
                                           booking_id="bkg_1", reason="غيّر رأيه")
    assert result["status"] == "cancelled"
    assert cancel.path_params[0] == {"booking_id": "bkg_1"}
    assert cancel.calls[0]["customer_id"] == "cus_real1"
    assert cancel.calls[0]["reason"] == "غيّر رأيه"


async def test_cancel_booking_refuses_when_the_phone_resolves_to_no_customer():
    cust = _FakePeer({"customer_id": ""})
    cancel = _FakePeer({"id": "bkg_1", "status": "cancelled"})
    provider = _provider(customer_id_by_phone=cust, cancel_booking=cancel)
    try:
        await provider.cancel_booking(tenant=TENANT, from_number="+9665", booking_id="bkg_1")
        assert False, "expected BookingAssignmentError"
    except BookingAssignmentError:
        pass
    assert cancel.calls == []   # never even reached bookings-service


async def test_cancel_booking_surfaces_a_peer_refusal_rather_than_a_fake_success():
    cust = _FakePeer({"customer_id": "cus_real1"})
    refused = _FakePeer(None)   # e.g. bookings-service's own 404 (not this customer's booking)
    provider = _provider(customer_id_by_phone=cust, cancel_booking=refused)
    try:
        await provider.cancel_booking(tenant=TENANT, from_number="+9665", booking_id="bkg_1")
        assert False, "expected BookingAssignmentError"
    except BookingAssignmentError:
        pass


async def test_reschedule_booking_stamps_the_booking_id_and_the_new_time():
    cust = _FakePeer({"customer_id": "cus_real1"})
    resched = _FakePeer({"id": "bkg_1", "starts_at": 9999})
    provider = _provider(customer_id_by_phone=cust, reschedule_booking=resched)
    result = await provider.reschedule_booking(tenant=TENANT, from_number="+9665",
                                               booking_id="bkg_1", starts_at=9999)
    assert result["starts_at"] == 9999
    assert resched.path_params[0] == {"booking_id": "bkg_1"}
    assert resched.calls[0]["starts_at"] == 9999


async def test_build_does_not_construct_management_peers_when_the_flag_is_off():
    """The OTHER half of the master kill-switch: config.py's llm_tool_allowlist already drops the
    tool names, but build() itself must ALSO never even construct the peers when
    BOOKING_MANAGEMENT_ENABLED is false — belt and suspenders, see build()'s own note."""
    from app.core.booking_assignment import build

    class _Settings:
        OPERATIONS_SERVICE_URL = "http://ops"
        BOOKINGS_SERVICE_URL = "http://bkg"
        OPERATIONS_BRANCH_OPERATORS_PATH = "/x"
        OPERATIONS_SERVICE_ELIGIBILITY_PATH = "/x"
        OPERATIONS_PACKAGE_ELIGIBILITY_PATH = "/x"
        OPERATIONS_CUSTOMER_ID_BY_PHONE_PATH = "/x"
        BOOKINGS_NEAREST_REAL_SLOT_PATH = "/x"
        BOOKINGS_CREATE_PATH = "/x"
        BOOKINGS_FOR_CUSTOMER_PATH = "/x"
        BOOKINGS_CANCEL_PATH = "/x/{booking_id}"
        BOOKINGS_RESCHEDULE_PATH = "/x/{booking_id}"
        PEER_TIMEOUT_SECONDS = 8
        INTERNAL_SERVICE_TOKEN = "tok"
        BOOKING_MANAGEMENT_ENABLED = False

    provider = build(_Settings())
    try:
        await provider.list_bookings(tenant=TENANT, from_number="+9665")
        assert False, "expected BookingAssignmentError"
    except BookingAssignmentError:
        pass


async def test_hold_and_confirm_surfaces_a_peer_refusal_rather_than_a_fake_success():
    ops = _FakePeer({"operators": [{"id": "op1"}]})
    elig = _FakePeer({"eligible_staff_ids": {"svc1": None}})
    cust = _FakePeer({"customer_id": "cus_real1"})
    refused = _FakePeer(None)   # peer unreachable, or bookings-service refused
    provider = _provider(branch_operators=ops, service_eligibility=elig,
                         customer_id_by_phone=cust, create_booking=refused)
    try:
        await provider.hold_and_confirm(tenant=TENANT, subject_ref="sub1", service_id="svc1",
                                        starts_at=5000, idempotency_key="k1",
                                        branch_id=BRANCH, from_number="+9665")
        assert False, "expected BookingAssignmentError"
    except BookingAssignmentError:
        pass
