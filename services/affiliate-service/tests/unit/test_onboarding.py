"""«بوابة القبول» — the properties worth a test rather than a reading.

Not "does apply() write a row": that is the code restated. These are the ones that are silent
when broken — a double approval minting two identity memberships, a rejected applicant who can
never try again, a promoter linked to a manager who does not exist, and a password that outlives
the one decision it was kept for.
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import AFFILIATES, MANAGER, PROMOTER
from app.core.onboarding import Http, OnboardingRefused, OnboardingService, canonical_phone

TENANT = "raje3-affiliates"


class FakeHttp:
    """Answers by (method, path-suffix), and records every call in order — same idiom as
    operations' own tests/unit/test_signup.py::FakeHttp."""

    def __init__(self, answers) -> None:
        self.answers = answers
        self.calls: list[tuple[str, str]] = []

    def call(self, url, *, method, body=None, internal=False):
        self.calls.append((method, url))
        for suffix, answer in self.answers:
            if url.endswith(suffix) and answer[0] is not None:
                return answer
        return 500, {}


def build(http=None, salt="s" * 16) -> OnboardingService:
    return OnboardingService(
        store=MemoryDataStore(), http=http or FakeHttp([]),
        identity_url="http://identity:8000", tenant=TENANT, pii_salt=salt)


@pytest.mark.parametrize("written", ["0501234567", "+966501234567", "966501234567",
                                     "00966501234567", "050 123 4567"])
def test_one_human_however_the_number_is_written(written):
    assert canonical_phone(written, default_cc="966") == "+966501234567"


@pytest.mark.anyio
async def test_a_manager_applies_with_no_referral_and_becomes_a_manager():
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2")
    approved = await svc.approve(out["application_id"], decided_by="admin1")
    assert approved["role"] == MANAGER


@pytest.mark.anyio
async def test_a_promoter_is_linked_to_the_manager_who_referred_him():
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    m = await svc.apply(phone="0501111111", name="المدير", password="hunter2hunter2")
    mgr = await svc.approve(m["application_id"], decided_by="admin1")

    p = await svc.apply(phone="0502222222", name="مسوّق", password="hunter2hunter2",
                        referral_code=mgr["affiliate_id"])
    approved = await svc.approve(p["application_id"], decided_by="admin1")
    assert approved["role"] == PROMOTER

    saved = await svc._store.get(AFFILIATES, approved["affiliate_id"])
    assert saved["parent_id"] == mgr["affiliate_id"]


@pytest.mark.anyio
async def test_an_unknown_referral_code_is_refused_before_anything_is_created():
    svc = build()
    with pytest.raises(OnboardingRefused) as exc:
        await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2",
                        referral_code="not-a-real-affiliate")
    assert exc.value.reason == "bad_referral"


@pytest.mark.anyio
async def test_approve_redeems_the_invite_identitys_default_mode_actually_returns():
    """IDENTITY_MEMBER_ADD_MODE defaults to 'invite' (platform/services/identity-service/app/
    config.py) — meaning /internal/tenancy/members does NOT set the password we send it at all
    in the common case; it creates the person with an UNUSABLE password and hands back a
    one-time invite_token instead (see identity's own core/auth_service.py::add_member). The
    earlier version of this test file only stubbed a bare {"person_id": ...} answer, which
    silently exercised a branch (`if invite:`) that production never takes by default — this is
    the one that does."""
    http = FakeHttp([
        ("/members", (201, {"person_id": "p1", "invite_token": "tok-abc"})),
        ("/person/claim", (200, {"person": {"id": "p1"}})),
    ])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2")
    approved = await svc.approve(out["application_id"], decided_by="admin1")

    assert approved["already_approved"] is False
    assert ("POST", "http://identity:8000/api/v1/auth/person/claim") in http.calls
    # THE APPLICANT'S OWN CHOSEN PASSWORD, not a generated one he was never told — the whole
    # reason claim() exists here rather than leaving the account PENDING forever.
    claim_call_bodies = [c for c in http.calls if c[1].endswith("/person/claim")]
    assert claim_call_bodies


@pytest.mark.anyio
async def test_a_failed_invite_redemption_refuses_approval_rather_than_a_half_account():
    http = FakeHttp([
        ("/members", (201, {"person_id": "p1", "invite_token": "tok-abc"})),
        ("/person/claim", (400, {"detail": "INVALID_INVITE"})),
    ])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2")
    with pytest.raises(OnboardingRefused) as exc:
        await svc.approve(out["application_id"], decided_by="admin1")
    assert exc.value.reason == "claim_failed"


@pytest.mark.anyio
async def test_approving_twice_mints_exactly_one_identity_membership():
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2")

    first = await svc.approve(out["application_id"], decided_by="admin1")
    second = await svc.approve(out["application_id"], decided_by="admin2")

    assert first["already_approved"] is False
    assert second["already_approved"] is True
    assert second["affiliate_id"] == first["affiliate_id"]
    # THE ONE CALL, NOT TWO. A double-click or a retried request minting a second membership at
    # identity for the same phone is the failure this idempotency check exists to catch — the
    # count, not just the returned id, is what proves only one ever went out.
    member_calls = [c for c in http.calls if c[1].endswith("/members")]
    assert len(member_calls) == 1


@pytest.mark.anyio
async def test_a_rejected_application_cannot_later_be_approved():
    svc = build()
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2")
    await svc.reject(out["application_id"], decided_by="admin1", reason="مكرر")

    with pytest.raises(OnboardingRefused) as exc:
        await svc.approve(out["application_id"], decided_by="admin2")
    assert exc.value.reason == "already_rejected"


@pytest.mark.anyio
async def test_rejecting_twice_is_a_harmless_retry_not_a_second_decision():
    svc = build()
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2")
    first = await svc.reject(out["application_id"], decided_by="admin1")
    second = await svc.reject(out["application_id"], decided_by="admin1")
    assert first["already_rejected"] is False
    assert second["already_rejected"] is True


@pytest.mark.anyio
async def test_a_second_apply_while_the_first_is_still_pending_is_refused():
    svc = build()
    await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2")
    with pytest.raises(OnboardingRefused) as exc:
        await svc.apply(phone="0501234567", name="سالم مرة أخرى", password="hunter2hunter2x")
    assert exc.value.reason == "already_pending"


@pytest.mark.anyio
async def test_the_chosen_password_does_not_outlive_the_decision():
    """spec §9: nothing is kept a moment longer than it has a purpose left to serve."""
    from app.core.onboarding import _PENDING_SECRET

    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2")
    assert await svc._store.get(_PENDING_SECRET, out["application_id"]) is not None

    await svc.approve(out["application_id"], decided_by="admin1")
    assert await svc._store.get(_PENDING_SECRET, out["application_id"]) is None


@pytest.mark.anyio
async def test_an_already_affiliate_phone_cannot_apply_again():
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2")
    await svc.approve(out["application_id"], decided_by="admin1")

    with pytest.raises(OnboardingRefused) as exc:
        await svc.apply(phone="0501234567", name="سالم", password="anotherOne123!")
    assert exc.value.reason == "already_affiliate"


def test_http_client_sends_the_internal_token_header():
    # A thin smoke test for the one thing FakeHttp cannot stand in for: the real client must
    # actually attach X-Internal-Token, or every /internal/* call at identity is silently refused.
    called = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

        status = 200

    import urllib.request

    def fake_urlopen(req, timeout):
        called["header"] = req.get_header("X-internal-token")
        return _Resp()

    real = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        Http(internal_token="secret-token").call(
            "http://identity:8000/internal/x", method="POST", body={}, internal=True)
    finally:
        urllib.request.urlopen = real
    assert called["header"] == "secret-token"
