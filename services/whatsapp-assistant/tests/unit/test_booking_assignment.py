"""RealBookingProvider (Phase 4) — operator assignment policy (first eligible, deterministic),
and that a branch/phone is REQUIRED, never guessed, before a real slot search or a real booking
write reaches its peers."""
from app.core.booking_assignment import BookingAssignmentError, RealBookingProvider

TENANT = "t1"
BRANCH = "brn-jeddah"


class _FakePeer:
    """Duck-types `_Peer.call(payload) -> dict|None` — records every call it received."""

    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []

    def call(self, payload):
        self.calls.append(payload)
        return self._response


def _provider(*, branch_operators=None, service_eligibility=None,
             customer_id_by_phone=None, nearest_real_slot=None, create_booking=None):
    return RealBookingProvider(
        branch_operators=branch_operators or _FakePeer({"operators": []}),
        service_eligibility=service_eligibility or _FakePeer({"eligible_staff_ids": {}}),
        customer_id_by_phone=customer_id_by_phone or _FakePeer({"customer_id": ""}),
        nearest_real_slot=nearest_real_slot or _FakePeer({"starts_at": None}),
        create_booking=create_booking or _FakePeer(None))


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
