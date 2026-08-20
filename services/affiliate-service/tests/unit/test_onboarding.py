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


class ByIdentifierHttp:
    """Same idiom, but the /members answer depends on WHICH phone is being minted — needed once a
    test mints more than one real person (a manager, then someone he invites) and each must get
    identity's OWN distinct person_id/invite_token rather than replaying the first response."""

    def __init__(self, by_identifier: dict[str, tuple[int, dict]],
                claim_answer: tuple[int, dict] = (200, {})) -> None:
        self._by_identifier = by_identifier
        self._claim_answer = claim_answer
        self.calls: list[tuple[str, str]] = []

    def call(self, url, *, method, body=None, internal=False):
        self.calls.append((method, url))
        if url.endswith("/members"):
            return self._by_identifier[(body or {})["identifier"]]
        if url.endswith("/person/claim"):
            return self._claim_answer
        return 500, {}


def build(http=None, salt="s" * 16, tenants_url="", authz_url="") -> OnboardingService:
    return OnboardingService(
        store=MemoryDataStore(), http=http or FakeHttp([]),
        identity_url="http://identity:8000", tenant=TENANT, pii_salt=salt,
        tenants_url=tenants_url, authz_url=authz_url)


@pytest.mark.parametrize("written", ["0501234567", "+966501234567", "966501234567",
                                     "00966501234567", "050 123 4567"])
def test_one_human_however_the_number_is_written(written):
    assert canonical_phone(written, default_cc="966") == "+966501234567"


@pytest.mark.anyio
async def test_a_manager_applies_with_no_referral_and_becomes_a_manager():
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    approved = await svc.approve(out["application_id"], decided_by="admin1")
    assert approved["role"] == MANAGER


@pytest.mark.anyio
async def test_a_promoter_is_linked_to_the_manager_who_referred_him():
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    m = await svc.apply(phone="0501111111", name="المدير", password="hunter2hunter2", agreed=True)
    mgr = await svc.approve(m["application_id"], decided_by="admin1")

    p = await svc.apply(phone="0502222222", name="مسوّق", password="hunter2hunter2",
                        referral_code=mgr["affiliate_id"], agreed=True)
    approved = await svc.approve(p["application_id"], decided_by="admin1")
    assert approved["role"] == PROMOTER

    saved = await svc._store.get(AFFILIATES, approved["affiliate_id"])
    assert saved["parent_id"] == mgr["affiliate_id"]


@pytest.mark.anyio
async def test_an_unknown_referral_code_is_refused_before_anything_is_created():
    svc = build()
    with pytest.raises(OnboardingRefused) as exc:
        await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2",
                        referral_code="not-a-real-affiliate", agreed=True)
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
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
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
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    with pytest.raises(OnboardingRefused) as exc:
        await svc.approve(out["application_id"], decided_by="admin1")
    assert exc.value.reason == "claim_failed"


@pytest.mark.anyio
async def test_approving_twice_mints_exactly_one_identity_membership():
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)

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
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    await svc.reject(out["application_id"], decided_by="admin1", reason="مكرر")

    with pytest.raises(OnboardingRefused) as exc:
        await svc.approve(out["application_id"], decided_by="admin2")
    assert exc.value.reason == "already_rejected"


@pytest.mark.anyio
async def test_rejecting_twice_is_a_harmless_retry_not_a_second_decision():
    svc = build()
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    first = await svc.reject(out["application_id"], decided_by="admin1")
    second = await svc.reject(out["application_id"], decided_by="admin1")
    assert first["already_rejected"] is False
    assert second["already_rejected"] is True


@pytest.mark.anyio
async def test_a_second_apply_while_the_first_is_still_pending_is_refused():
    svc = build()
    await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    with pytest.raises(OnboardingRefused) as exc:
        await svc.apply(phone="0501234567", name="سالم مرة أخرى", password="hunter2hunter2x", agreed=True)
    assert exc.value.reason == "already_pending"


@pytest.mark.anyio
async def test_the_chosen_password_does_not_outlive_the_decision():
    """spec §9: nothing is kept a moment longer than it has a purpose left to serve."""
    from app.core.onboarding import _PENDING_SECRET

    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    assert await svc._store.get(_PENDING_SECRET, out["application_id"]) is not None

    await svc.approve(out["application_id"], decided_by="admin1")
    assert await svc._store.get(_PENDING_SECRET, out["application_id"]) is None


@pytest.mark.anyio
async def test_an_already_affiliate_phone_cannot_apply_again():
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    await svc.approve(out["application_id"], decided_by="admin1")

    with pytest.raises(OnboardingRefused) as exc:
        await svc.apply(phone="0501234567", name="سالم", password="anotherOne123!", agreed=True)
    assert exc.value.reason == "already_affiliate"


# ── a manager inviting somebody directly ─────────────────────────────────────────────────────
def _invite_http() -> ByIdentifierHttp:
    """A manager minted first (self-apply, password mode), a promoter minted second (invite
    mode) — two DIFFERENT identity people, so each phone must get its own person_id/invite_token
    rather than replaying whichever answer a plain FakeHttp saw first."""
    return ByIdentifierHttp({
        "+966501110000": (201, {"person_id": "p-manager"}),
        "+966502223333": (201, {"person_id": "p-promoter", "invite_token": "tok-1"}),
    })


async def _make_active_manager(svc) -> str:
    """Returns the manager's person_id (also his identity `sub`, so it doubles as the token
    subject a real invite() call would authenticate with)."""
    out = await svc.apply(phone="0501110000", name="مدير", password="hunter2hunter2", agreed=True)
    approved = await svc.approve(out["application_id"], decided_by="admin1")
    saved = await svc._store.get(AFFILIATES, approved["affiliate_id"])
    return saved["person_id"]


@pytest.mark.anyio
async def test_a_manager_invites_and_no_password_is_asked_of_him():
    svc = build(_invite_http())
    manager_person_id = await _make_active_manager(svc)

    out = await svc.invite(inviter_person_id=manager_person_id, phone="0502223333",
                           name="مسوّق مدعو")
    approved = await svc.approve(out["application_id"], decided_by="admin1")
    assert approved["status"] == "invited"

    saved = await svc._store.get(AFFILIATES, approved["affiliate_id"])
    assert saved["invite_token"] == "tok-1"
    assert saved["role"] == PROMOTER


@pytest.mark.anyio
async def test_a_promoter_cannot_invite():
    svc = build(_invite_http())
    manager_person_id = await _make_active_manager(svc)

    out = await svc.invite(inviter_person_id=manager_person_id, phone="0502223333",
                           name="مسوّق مدعو")
    approved = await svc.approve(out["application_id"], decided_by="admin1")
    accepted = await svc.accept_invite(token="tok-1", password="hunter2hunter2", agreed=True)
    promoter_person_id = (await svc._store.get(AFFILIATES, accepted["affiliate_id"]))["person_id"]

    with pytest.raises(OnboardingRefused) as exc:
        await svc.invite(inviter_person_id=promoter_person_id, phone="0509998888",
                         name="محاولة")
    assert exc.value.reason == "managers_only"
    assert approved["affiliate_id"] != ""   # sanity: the setup above actually worked


@pytest.mark.anyio
async def test_accepting_an_invite_activates_the_account_with_the_persons_own_password():
    svc = build(_invite_http())
    manager_person_id = await _make_active_manager(svc)

    out = await svc.invite(inviter_person_id=manager_person_id, phone="0502223333",
                           name="مسوّق مدعو")
    approved = await svc.approve(out["application_id"], decided_by="admin1")

    accepted = await svc.accept_invite(token="tok-1", password="somePassword123!", agreed=True)
    saved = await svc._store.get(AFFILIATES, accepted["affiliate_id"])
    assert saved["status"] == "active"
    assert saved["invite_token"] == ""   # spent
    assert accepted["affiliate_id"] == approved["affiliate_id"]


@pytest.mark.anyio
async def test_a_spent_or_unknown_invite_token_is_refused_the_same_way():
    svc = build()
    with pytest.raises(OnboardingRefused) as exc:
        await svc.accept_invite(token="never-issued", password="hunter2hunter2", agreed=True)
    assert exc.value.reason == "invalid_invite"


@pytest.mark.anyio
async def test_an_inactive_affiliate_cannot_invite():
    svc = build()
    with pytest.raises(OnboardingRefused) as exc:
        await svc.invite(inviter_person_id="nobody", phone="0501234567", name="أحد")
    assert exc.value.reason == "not_an_active_affiliate"


# ── who am I ──────────────────────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_me_returns_his_own_id_as_the_referral_code_never_the_invite_token():
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    approved = await svc.approve(out["application_id"], decided_by="admin1")

    me = await svc.me("p1")
    assert me["id"] == approved["affiliate_id"]
    assert me["role"] == MANAGER
    assert "invite_token" not in me


@pytest.mark.anyio
async def test_me_is_none_for_a_person_with_no_affiliate_row():
    svc = build()
    assert await svc.me("nobody") is None


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


# ── consent (spec §2) ─────────────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_apply_without_agreeing_is_refused_before_any_lookup():
    svc = build()
    with pytest.raises(OnboardingRefused) as exc:
        await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=False)
    assert exc.value.reason == "must_agree"


@pytest.mark.anyio
async def test_a_self_applicant_carries_his_agreement_onto_the_affiliate_row():
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    approved = await svc.approve(out["application_id"], decided_by="admin1")
    saved = await svc._store.get(AFFILIATES, approved["affiliate_id"])
    assert saved["agreed_terms_version"] == "v1"
    assert saved["agreed_at"] > 0


@pytest.mark.anyio
async def test_an_invited_affiliate_has_no_agreement_until_he_accepts_it_himself():
    """The manager's OWN agreement (made when he applied) must never stand in for the person he
    invites — nobody but that person can consent on his behalf."""
    svc = build(_invite_http())
    manager_person_id = await _make_active_manager(svc)
    out = await svc.invite(inviter_person_id=manager_person_id, phone="0502223333", name="مسوّق مدعو")
    approved = await svc.approve(out["application_id"], decided_by="admin1")
    saved = await svc._store.get(AFFILIATES, approved["affiliate_id"])
    assert saved["agreed_terms_version"] == ""
    assert saved["agreed_at"] == 0


@pytest.mark.anyio
async def test_accepting_an_invite_without_agreeing_is_refused():
    svc = build(_invite_http())
    manager_person_id = await _make_active_manager(svc)
    out = await svc.invite(inviter_person_id=manager_person_id, phone="0502223333", name="مسوّق مدعو")
    await svc.approve(out["application_id"], decided_by="admin1")
    with pytest.raises(OnboardingRefused) as exc:
        await svc.accept_invite(token="tok-1", password="hunter2hunter2", agreed=False)
    assert exc.value.reason == "must_agree"


@pytest.mark.anyio
async def test_accepting_an_invite_records_his_own_agreement():
    svc = build(_invite_http())
    manager_person_id = await _make_active_manager(svc)
    out = await svc.invite(inviter_person_id=manager_person_id, phone="0502223333", name="مسوّق مدعو")
    await svc.approve(out["application_id"], decided_by="admin1")
    accepted = await svc.accept_invite(token="tok-1", password="hunter2hunter2", agreed=True)
    saved = await svc._store.get(AFFILIATES, accepted["affiliate_id"])
    assert saved["agreed_terms_version"] == "v1"
    assert saved["agreed_at"] > 0


# ── suspend / reactivate (spec §10: «تعليق لا حذف») ──────────────────────────────────────────
@pytest.mark.anyio
async def test_suspending_revokes_identity_access_and_flips_the_status():
    http = FakeHttp([("/members", (201, {"person_id": "p1"})),
                     (f"/tenancy/membership/{TENANT}::p1", (200, {}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    approved = await svc.approve(out["application_id"], decided_by="admin1")

    result = await svc.suspend(approved["affiliate_id"], decided_by="admin1")
    assert result["already_suspended"] is False
    saved = await svc._store.get(AFFILIATES, approved["affiliate_id"])
    assert saved["status"] == "suspended"
    assert any(m == "DELETE" for m, _ in http.calls)


@pytest.mark.anyio
async def test_suspending_twice_is_idempotent():
    http = FakeHttp([("/members", (201, {"person_id": "p1"})),
                     (f"/tenancy/membership/{TENANT}::p1", (200, {}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    approved = await svc.approve(out["application_id"], decided_by="admin1")

    await svc.suspend(approved["affiliate_id"], decided_by="admin1")
    second = await svc.suspend(approved["affiliate_id"], decided_by="admin1")
    assert second["already_suspended"] is True


@pytest.mark.anyio
async def test_a_failed_revoke_refuses_the_suspension_rather_than_lying_about_it():
    http = FakeHttp([("/members", (201, {"person_id": "p1"})),
                     (f"/tenancy/membership/{TENANT}::p1", (500, {}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    approved = await svc.approve(out["application_id"], decided_by="admin1")

    with pytest.raises(OnboardingRefused) as exc:
        await svc.suspend(approved["affiliate_id"], decided_by="admin1")
    assert exc.value.reason == "revoke_failed"
    saved = await svc._store.get(AFFILIATES, approved["affiliate_id"])
    assert saved["status"] == "active"   # NOT suspended — the lie this test guards against


@pytest.mark.anyio
async def test_reactivating_re_grants_membership_with_no_password_sent():
    http = FakeHttp([("/members", (201, {"person_id": "p1"})),
                     (f"/tenancy/membership/{TENANT}::p1", (200, {}))])
    svc = build(http)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    approved = await svc.approve(out["application_id"], decided_by="admin1")
    await svc.suspend(approved["affiliate_id"], decided_by="admin1")

    result = await svc.reactivate(approved["affiliate_id"], decided_by="admin1")
    assert result["already_active"] is False
    saved = await svc._store.get(AFFILIATES, approved["affiliate_id"])
    assert saved["status"] == "active"


@pytest.mark.anyio
async def test_suspending_an_unknown_affiliate_is_a_clean_refusal():
    svc = build()
    with pytest.raises(OnboardingRefused) as exc:
        await svc.suspend("no-such-affiliate", decided_by="admin1")
    assert exc.value.reason == "not_found"


# ── the shared tenant's own provisioning (lazy, idempotent, self-healing) ───────────────────────
@pytest.mark.anyio
async def test_provisioning_is_a_no_op_when_no_tenants_url_is_configured():
    """The default in every test above this one — proves that default stays inert."""
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http)   # tenants_url="" by default
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    await svc.approve(out["application_id"], decided_by="admin1")
    assert not any("/internal/tenants" in u or "/bootstrap" in u for _, u in http.calls)


@pytest.mark.anyio
async def test_a_missing_tenant_is_created_then_roles_are_bootstrapped():
    http = FakeHttp([
        ("/members", (201, {"person_id": "p1"})),
        (f"/internal/tenants/{TENANT}", (404, {})),
        ("/internal/tenants", (201, {"id": TENANT})),
        (f"/authz/tenants/{TENANT}/bootstrap", (200, {})),
    ])
    svc = build(http, tenants_url="http://tenants:8000", authz_url="http://authz:8000")
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    await svc.approve(out["application_id"], decided_by="admin1")

    methods_and_urls = http.calls
    assert ("GET", f"http://tenants:8000/internal/tenants/{TENANT}") in methods_and_urls
    assert ("POST", "http://tenants:8000/internal/tenants") in methods_and_urls
    assert ("POST", f"http://authz:8000/internal/authz/tenants/{TENANT}/bootstrap") in methods_and_urls


@pytest.mark.anyio
async def test_an_already_existing_tenant_skips_creation_but_still_bootstraps():
    http = FakeHttp([
        ("/members", (201, {"person_id": "p1"})),
        (f"/internal/tenants/{TENANT}", (200, {"id": TENANT})),
        (f"/authz/tenants/{TENANT}/bootstrap", (200, {})),
    ])
    svc = build(http, tenants_url="http://tenants:8000", authz_url="http://authz:8000")
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    await svc.approve(out["application_id"], decided_by="admin1")
    assert not any(m == "POST" and u.endswith("/internal/tenants") for m, u in http.calls)


@pytest.mark.anyio
async def test_a_409_on_create_is_treated_as_already_provisioned_not_a_failure():
    """Two approvals racing each other — the second's create loses the race, and that must not
    refuse an otherwise-correct approval."""
    http = FakeHttp([
        ("/members", (201, {"person_id": "p1"})),
        (f"/internal/tenants/{TENANT}", (404, {})),
        ("/internal/tenants", (409, {})),
        (f"/authz/tenants/{TENANT}/bootstrap", (200, {})),
    ])
    svc = build(http, tenants_url="http://tenants:8000", authz_url="http://authz:8000")
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    approved = await svc.approve(out["application_id"], decided_by="admin1")
    assert approved["already_approved"] is False


@pytest.mark.anyio
async def test_a_bootstrap_failure_refuses_the_approval():
    http = FakeHttp([
        ("/members", (201, {"person_id": "p1"})),
        (f"/internal/tenants/{TENANT}", (200, {"id": TENANT})),
        (f"/authz/tenants/{TENANT}/bootstrap", (500, {})),
    ])
    svc = build(http, tenants_url="http://tenants:8000", authz_url="http://authz:8000")
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    with pytest.raises(OnboardingRefused) as exc:
        await svc.approve(out["application_id"], decided_by="admin1")
    assert exc.value.reason == "role_bootstrap_failed"


@pytest.mark.anyio
async def test_provisioning_only_happens_once_per_process_even_across_two_approvals():
    http = FakeHttp([
        ("/members", (201, {"person_id": "p1"})),
        (f"/internal/tenants/{TENANT}", (200, {"id": TENANT})),
        (f"/authz/tenants/{TENANT}/bootstrap", (200, {})),
    ])
    svc = build(http, tenants_url="http://tenants:8000", authz_url="http://authz:8000")

    first = await svc.apply(phone="0501234567", name="الأول", password="hunter2hunter2", agreed=True)
    await svc.approve(first["application_id"], decided_by="admin1")
    calls_after_first = len(http.calls)

    second = await svc.apply(phone="0509998888", name="الثاني", password="hunter2hunter2", agreed=True)
    await svc.approve(second["application_id"], decided_by="admin1")

    # ONE more call for the second approval's own /members mint — NOT two more for a repeated
    # tenant GET + bootstrap POST. The per-process cache is what saves those.
    assert len(http.calls) == calls_after_first + 1


# ── spec §10: a manager's own team roster ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_team_lists_only_direct_children_of_the_given_manager():
    from app.core.models import ACTIVE, Affiliate

    svc = build()
    manager = Affiliate(id="mgr-1", person_id="p-mgr", phone="+966501111111", name="المدير",
                        role=MANAGER, status=ACTIVE)
    child_a = Affiliate(id="prm-1", person_id="p-a", phone="+966502222222", name="أ",
                        role=PROMOTER, parent_id="mgr-1", status=ACTIVE)
    child_b = Affiliate(id="prm-2", person_id="p-b", phone="+966503333333", name="ب",
                        role=PROMOTER, parent_id="mgr-1", status=ACTIVE)
    other = Affiliate(id="prm-3", person_id="p-c", phone="+966504444444", name="ج",
                      role=PROMOTER, parent_id="some-other-manager", status=ACTIVE)
    for a in (manager, child_a, child_b, other):
        await svc._store.put(AFFILIATES, a.id, a.to_dict())

    team = await svc.team("mgr-1")
    assert {m["id"] for m in team} == {"prm-1", "prm-2"}
    assert all("phone" not in m for m in team)   # names + status only, never PII the caller has no reason to see here


@pytest.mark.anyio
async def test_team_is_empty_for_a_manager_with_nobody_under_him():
    svc = build()
    assert await svc.team("mgr-with-no-one") == []
