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
        # Bodies, recorded separately and in the same order as `calls` — kept apart so every
        # existing `(method, url) in methods_and_urls` assertion is untouched by this addition.
        self.bodies: list[dict] = []
        self.bearers: list[str] = []

    def call(self, url, *, method, body=None, internal=False, bearer=""):
        self.calls.append((method, url))
        self.bodies.append(body or {})
        self.bearers.append(bearer)
        for suffix, answer in self.answers:
            if url.endswith(suffix) and answer[0] is not None:
                return answer
        return 500, {}


def build(http=None, salt="s" * 16, tenants_url="", authz_url="",
         otp_deliverable=False, require_otp=False) -> OnboardingService:
    return OnboardingService(
        store=MemoryDataStore(), http=http or FakeHttp([]),
        identity_url="http://identity:8000", tenant=TENANT, pii_salt=salt,
        tenants_url=tenants_url, authz_url=authz_url,
        otp_deliverable=otp_deliverable, require_otp=require_otp)


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

    # THE ACTUAL GAP CLOSED 2026-08-22 — both roles used to bootstrap with `"capabilities": []`,
    # so no real affiliate token ever carried anything a route could gate on. Proven here rather
    # than trusted from the diff: the bootstrap BODY itself must carry `affiliates.self`.
    bootstrap_body = next(b for u, b in zip((u for _, u in http.calls), http.bodies)
                          if u.endswith("/bootstrap"))
    role_caps = {r["name"]: r["capabilities"] for r in bootstrap_body["roles"]}
    assert role_caps["affiliate_manager"] == ["affiliates.self"]
    assert role_caps["affiliate_promoter"] == ["affiliates.self"]


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


# ── spec §10's optional whole-platform revenue view — admin-only, off by default ────────────────

@pytest.mark.anyio
async def test_platform_revenue_visibility_is_off_by_default_and_admin_toggleable():
    from app.core.models import ACTIVE, Affiliate

    svc = build()
    mgr = Affiliate(id="mgr-prv-1", person_id="p-mgr-prv-1", phone="+966505550009",
                    name="مدير", role=MANAGER, status=ACTIVE)
    await svc._store.put(AFFILIATES, mgr.id, mgr.to_dict())

    me = await svc.me("p-mgr-prv-1")
    assert me["sees_platform_revenue"] is False

    out = await svc.set_platform_revenue_visibility("mgr-prv-1", enabled=True)
    assert out == {"changed": True, "sees_platform_revenue": True}
    me = await svc.me("p-mgr-prv-1")
    assert me["sees_platform_revenue"] is True

    # idempotent: setting the same value again reports no change
    out = await svc.set_platform_revenue_visibility("mgr-prv-1", enabled=True)
    assert out == {"changed": False, "sees_platform_revenue": True}


@pytest.mark.anyio
async def test_platform_revenue_visibility_refuses_for_an_unknown_affiliate():
    svc = build()
    with pytest.raises(OnboardingRefused) as exc:
        await svc.set_platform_revenue_visibility("no-such-affiliate", enabled=True)
    assert exc.value.reason == "not_found"


# ── change-password: a pure pass-through to identity, never a stored credential ────────────────
@pytest.mark.anyio
async def test_change_password_forwards_the_callers_own_bearer_to_identity():
    http = FakeHttp([("/change-password", (200, {"status": "ok"}))])
    svc = build(http)
    await svc.change_password(bearer="Bearer tok-123", old_password="old", new_password="new-strong-1")
    assert http.calls[-1] == ("POST", "http://identity:8000/api/v1/auth/change-password")
    assert http.bearers[-1] == "Bearer tok-123"
    assert http.bodies[-1] == {"old_password": "old", "new_password": "new-strong-1"}


@pytest.mark.anyio
async def test_change_password_refuses_on_a_wrong_old_password():
    http = FakeHttp([("/change-password", (400, {"detail": "INVALID_PASSWORD"}))])
    svc = build(http)
    with pytest.raises(OnboardingRefused) as exc:
        await svc.change_password(bearer="Bearer tok-123", old_password="wrong", new_password="new-strong-1")
    assert exc.value.reason == "wrong_password"


@pytest.mark.anyio
async def test_change_password_refuses_a_weak_new_password_distinctly():
    http = FakeHttp([("/change-password", (400, {"detail": "WEAK_PASSWORD"}))])
    svc = build(http)
    with pytest.raises(OnboardingRefused) as exc:
        await svc.change_password(bearer="Bearer tok-123", old_password="old", new_password="1")
    assert exc.value.reason == "weak_password"


# ── phone-ownership OTP — dormant until both flags are on ──────────────────────────────────────
@pytest.mark.anyio
async def test_apply_needs_no_code_while_the_gate_is_off():
    http = FakeHttp([("/members", (201, {"person_id": "p1"}))])
    svc = build(http, require_otp=False)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2", agreed=True)
    assert out["status"] == "pending"


@pytest.mark.anyio
async def test_apply_refuses_a_wrong_code_once_the_gate_is_on():
    http = FakeHttp([("/otp/verify", (400, {}))])
    svc = build(http, require_otp=True)
    with pytest.raises(OnboardingRefused) as exc:
        await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2",
                        agreed=True, code="000000")
    assert exc.value.reason == "bad_code"


@pytest.mark.anyio
async def test_apply_succeeds_with_a_verified_code_once_the_gate_is_on():
    http = FakeHttp([("/otp/verify", (200, {})), ("/members", (201, {"person_id": "p1"}))])
    svc = build(http, require_otp=True)
    out = await svc.apply(phone="0501234567", name="سالم", password="hunter2hunter2",
                          agreed=True, code="123456")
    assert out["status"] == "pending"


@pytest.mark.anyio
async def test_request_otp_is_refused_while_no_channel_can_actually_deliver():
    svc = build(otp_deliverable=False)
    with pytest.raises(OnboardingRefused) as exc:
        await svc.request_otp("0501234567")
    assert exc.value.reason == "undeliverable"


@pytest.mark.anyio
async def test_request_otp_reports_a_provider_failure_distinctly():
    http = FakeHttp([("/otp/request", (200, {"delivered": False}))])
    svc = build(http, otp_deliverable=True)
    with pytest.raises(OnboardingRefused) as exc:
        await svc.request_otp("0501234567")
    assert exc.value.reason == "undelivered"


@pytest.mark.anyio
async def test_request_otp_succeeds_once_a_channel_actually_delivers():
    http = FakeHttp([("/otp/request", (200, {"delivered": True, "expires_in": 300}))])
    svc = build(http, otp_deliverable=True)
    out = await svc.request_otp("0501234567")
    assert out == {"sent": True, "expires_in": 300}


# ── a manager editing a referral's application, only before an admin decides ───────────────────
@pytest.mark.anyio
async def test_the_referring_manager_may_edit_a_still_pending_application():
    http = FakeHttp([("/members", (201, {"person_id": "p-mgr"}))])
    svc = build(http)
    mgr_out = await svc.apply(phone="0501110000", name="مدير", password="hunter2hunter2", agreed=True)
    mgr = await svc.approve(mgr_out["application_id"], decided_by="admin1")
    mgr_person_id = (await svc._store.get(AFFILIATES, mgr["affiliate_id"]))["person_id"]

    app_out = await svc.apply(phone="0502223333", name="مسوّق", password="hunter2hunter2",
                              referral_code=mgr["affiliate_id"], agreed=True)
    updated = await svc.update_application(
        app_out["application_id"], editor_person_id=mgr_person_id,
        name="مسوّق مُعدَّل", cv_url="https://example.com/cv.pdf")
    assert updated["name"] == "مسوّق مُعدَّل"
    assert updated["cv_url"] == "https://example.com/cv.pdf"


@pytest.mark.anyio
async def test_editing_is_refused_once_an_admin_has_already_decided():
    http = FakeHttp([("/members", (201, {"person_id": "p-mgr"}))])
    svc = build(http)
    mgr_out = await svc.apply(phone="0501110000", name="مدير", password="hunter2hunter2", agreed=True)
    mgr = await svc.approve(mgr_out["application_id"], decided_by="admin1")
    mgr_person_id = (await svc._store.get(AFFILIATES, mgr["affiliate_id"]))["person_id"]

    app_out = await svc.apply(phone="0502223333", name="مسوّق", password="hunter2hunter2",
                              referral_code=mgr["affiliate_id"], agreed=True)
    await svc.approve(app_out["application_id"], decided_by="admin1")

    with pytest.raises(OnboardingRefused) as exc:
        await svc.update_application(app_out["application_id"], editor_person_id=mgr_person_id,
                                     name="بعد القرار")
    assert exc.value.reason == "decision_closed"


@pytest.mark.anyio
async def test_a_stranger_cannot_edit_someone_elses_referral():
    http = FakeHttp([("/members", (201, {"person_id": "p-mgr"}))])
    svc = build(http)
    mgr_out = await svc.apply(phone="0501110000", name="مدير", password="hunter2hunter2", agreed=True)
    mgr = await svc.approve(mgr_out["application_id"], decided_by="admin1")

    app_out = await svc.apply(phone="0502223333", name="مسوّق", password="hunter2hunter2",
                              referral_code=mgr["affiliate_id"], agreed=True)
    with pytest.raises(OnboardingRefused) as exc:
        await svc.update_application(app_out["application_id"], editor_person_id="someone-else",
                                     name="محاولة")
    assert exc.value.reason == "not_your_referral"
