"""The door — the three properties that are worth a test rather than a reading.

Not "does it call three services": that is the code restated. These are the ones that are silent
when broken — a phone that folds to two different accounts, an orphan tenant left by a failed
registration, and a refusal that answers "no such shop" differently from "wrong password".
"""
from __future__ import annotations

import pathlib

import pytest

from app.core.signup import NewShop, SignupRefused, SignupService, canonical_phone


class FakeStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    async def get(self, collection, key):
        return self.rows.get((collection, key))

    async def put(self, collection, key, row):
        self.rows[(collection, key)] = row


class FakeSectors:
    def __init__(self) -> None:
        self.seeded: list[str] = []

    async def seed_tenant(self, *, tenant, sector_key, integrated=False):
        self.seeded.append(tenant)
        return 7


class FakeHttp:
    """Answers by (method, path-suffix), and records every call in order."""

    def __init__(self, answers) -> None:
        self.answers = answers
        self.calls: list[tuple[str, str]] = []

    def call(self, url, *, method, body=None, internal=False):
        self.calls.append((method, url))
        for suffix, answer in self.answers:
            if url.endswith(suffix) and answer[0] is not None:
                return answer
        return 500, {}


ROLES = [{"name": "owner", "capabilities": ["operations.record"], "description": ""},
         {"name": "manager", "capabilities": ["operations.read"], "description": ""}]


def build(http, store=None, roles=ROLES):
    return SignupService(
        store=store or FakeStore(), http=http,
        identity_url="http://identity:8000", tenants_url="http://tenants:8000",
        authz_url="http://authz:8000", roles=roles)


@pytest.mark.parametrize("written", ["0501234567", "+966501234567", "966501234567",
                                     "00966501234567", "050 123 4567"])
def test_one_human_however_the_number_is_written(written):
    # The failure this prevents is impossible to unpick after it happens: three spellings become
    # three accounts, each with its own shop, and no way to tell which is the real one.
    assert canonical_phone(written, default_cc="966") == "+966501234567"


@pytest.mark.anyio
async def test_a_failed_registration_leaves_no_orphan_tenant():
    http = FakeHttp([("/internal/tenants", (201, {"id": "t-1"})),
                     ("/seed-owner", (409, {"detail": "USERNAME_TAKEN"}))])
    svc = build(http)

    with pytest.raises(SignupRefused):
        await svc.open_shop(NewShop("0501234567", "hunter2hunter2", "بنشر النور"))

    # THE UNDO RAN. Without it the registry keeps a tenant no account can reach and nobody will
    # ever look for — and it is invisible, so it is permanent.
    assert ("DELETE", "http://tenants:8000/internal/tenants/t-1") in http.calls


@pytest.mark.anyio
async def test_a_seeding_failure_does_not_destroy_a_working_account():
    class Broken:
        async def seed_tenant(self, **_):
            raise RuntimeError("search is down")

    http = FakeHttp([("/internal/tenants", (201, {"id": "t-1"})),
                     ("/seed-owner", (201, {"person_id": "p1"})),
                     ("/bootstrap", (200, {}))])
    out = await build(http).open_shop(
        NewShop("0501234567", "hunter2hunter2", "بنشر النور"))

    assert out["tenant"] == "t-1"
    assert out["services"] == 0
    assert not any(m == "DELETE" for m, _ in http.calls)


@pytest.mark.anyio
async def test_an_unknown_number_is_refused_exactly_like_a_wrong_password():
    # Anything else is an enumeration oracle for every mobile number in the country, one request
    # at a time, for free.
    store = FakeStore()
    known = build(FakeHttp([("/otp/verify", (200, {})),
                            ("/auth/tenant", (401, {"detail": "INVALID_CREDENTIALS"}))]), store=store)
    await known._remember("0501234567", "t-1")           # noqa: SLF001 — the index is the fixture
    await known.prove("0501234567", "123456")            # proven, so the refusal is about the password

    with pytest.raises(SignupRefused) as wrong_password:
        await known.sign_in("0501234567", "nope")
    with pytest.raises(SignupRefused) as no_account:
        await known.sign_in("0559999999", "nope")

    assert str(wrong_password.value) == str(no_account.value)


@pytest.mark.anyio
async def test_the_login_forwards_the_tenant_the_owner_never_typed():
    http = FakeHttp([("/otp/verify", (200, {})), ("/auth/tenant", (200, {"access_token": "tok"}))])
    svc = build(http)
    await svc._remember("0501234567", "t-9")             # noqa: SLF001
    await svc.prove("0501234567", "123456")

    out = await svc.sign_in("+966501234567", "hunter2hunter2")
    assert out["tenant"] == "t-9"
    assert out["access_token"] == "tok"


@pytest.mark.anyio
async def test_an_unproven_number_cannot_sign_in():
    """THE HOLE THIS CLOSES was invisible from the code and obvious from using it: identity
    consumes an OTP and stores no verdict, so a person who closed the tab on the verification
    screen and came back through the front door was signed straight in. The step was a screen
    rather than a rule."""
    svc = build(FakeHttp([("/auth/tenant", (200, {"access_token": "tok"}))]))
    await svc._remember("0501234567", "t-1")             # noqa: SLF001

    with pytest.raises(SignupRefused) as refused:
        await svc.sign_in("0501234567", "hunter2hunter2")
    assert "أكّد" in str(refused.value)


@pytest.mark.anyio
async def test_a_verification_identity_rejects_is_not_recorded():
    """A code identity refuses must leave the row exactly as it was. Recording an attempt as a
    success would be worse than not asking at all — the rule would look enforced and let anyone in
    on any six digits."""
    svc = build(FakeHttp([("/otp/verify", (400, {"detail": "invalid or expired code"}))]))
    await svc._remember("0501234567", "t-1")             # noqa: SLF001

    with pytest.raises(SignupRefused):
        await svc.prove("0501234567", "000000")
    with pytest.raises(SignupRefused):
        await svc.sign_in("0501234567", "hunter2hunter2")


@pytest.mark.anyio
async def test_the_owner_is_given_a_role_or_the_signup_is_undone():
    """THE STEP THAT DECIDES WHETHER THE ACCOUNT IS WORTH ANYTHING.

    Capabilities come from roles; a fresh tenant has none. Before this step existed, signup
    produced a token with `caps: []` — the owner signed in and found an empty application, with
    every response a 2xx and nothing anywhere reporting a fault.
    """
    http = FakeHttp([("/internal/tenants", (201, {"id": "t-1"})),
                     ("/seed-owner", (201, {"person_id": "p-9"})),
                     ("/bootstrap", (200, {}))])
    await build(http).open_shop(NewShop("0501234567", "hunter2hunter2", "بنشر النور"))

    assert ("POST", "http://authz:8000/internal/authz/tenants/t-1/bootstrap") in http.calls


@pytest.mark.anyio
async def test_a_failed_bootstrap_leaves_nothing_behind():
    """An account that can do nothing is WORSE than no account: he cannot fix it, cannot be told
    why, and would try again with the same number and be refused for already existing."""
    http = FakeHttp([("/internal/tenants", (201, {"id": "t-1"})),
                     ("/seed-owner", (201, {"person_id": "p-9"})),
                     ("/bootstrap", (500, {}))])

    with pytest.raises(SignupRefused):
        await build(http).open_shop(NewShop("0501234567", "hunter2hunter2", "بنشر النور"))

    assert ("DELETE", "http://tenants:8000/internal/tenants/t-1") in http.calls


@pytest.mark.anyio
async def test_no_role_definitions_refuses_rather_than_creating_a_dead_account():
    # The file failed to load at boot. Creating an account anyway would be creating exactly the
    # broken state this whole step was added to remove.
    http = FakeHttp([("/internal/tenants", (201, {"id": "t-1"})),
                     ("/seed-owner", (201, {"person_id": "p-9"}))])

    with pytest.raises(SignupRefused):
        await build(http, roles=[]).open_shop(
            NewShop("0501234567", "hunter2hunter2", "بنشر النور"))

    assert ("DELETE", "http://tenants:8000/internal/tenants/t-1") in http.calls
    # AND THE MEMBERSHIP TOO — و-6. The comment on this path said «BOTH UNDONE» and the code
    # deleted the tenant alone, so the person seed-owner had just created lived on with no tenant
    # behind him. His number was then taken at identity and unknown to us: signing up again says
    # «هذا الرقم مسجّل»، signing in says «الرقم أو كلمة المرور غير صحيحة»، and no screen can repair
    # either. The number was reserved against him for ever by a failure that was ours.
    assert ("DELETE", "http://identity:8000/internal/tenancy/membership/t-1::p-9") in http.calls


def test_a_new_shop_gets_a_data_map_so_a_dsar_has_somewhere_to_go():
    """PDPL Article 18, and the reason it is at SIGNUP.

    `DsarService.dispatch` refuses on an empty map, so until this runs no export and no erasure can
    complete for a real shop. And it cannot be done later by the owner: the user-tier route needs
    `compliance.manage`, which also grants DELETE — narrowing the erasure fan-out is a worse
    posture than the honest refusal, so an owner must never hold it.

    ONE CALL PER TARGET, so one unknown name cannot cost the other sixteen.
    """
    import asyncio

    calls: list[dict] = []

    class Http:
        def call(self, url, method="GET", body=None, internal=False, **kw):
            calls.append({"url": url, "body": body})
            return 201, {}

    svc = SignupService.__new__(SignupService)
    svc._compliance = "http://compliance:8000"
    svc._data_map = ["operations:visits", "loyalty:points", "broken"]
    svc._http = Http()

    class Telemetry:
        def __init__(self): self.events = []
        def event(self, name, **kw): self.events.append((name, kw))

    svc._telemetry = Telemetry()

    failed = asyncio.run(svc._register_data_map("tnt_x"))

    assert len(calls) == 2, "a malformed entry must not become a request"
    assert calls[0]["body"] == {"tenant": "tnt_x", "service": "operations", "category": "visits"}
    # AND THE BAD ONE IS REPORTED, not swallowed: a list that drifts from what is deployed is
    # exactly the thing that leaves a shop half-covered while everything looks fine.
    assert "broken" in failed


def test_an_incomplete_data_map_is_said_out_loud_not_returned_into_a_body_nobody_reads():
    """The quietest compliance failure we have.

    Compliance is unreachable for one entry during signup. The shop is created anyway, with a map
    that omits that service FOR EVER — and every later erasure fans out to the registered targets
    only, all of them acknowledge, and `derive_completion` closes the request as COMPLETED while
    the customer's records in the missing service are never touched. He is told his data is gone.

    Before this, the only trace was a string in the signup response body. No screen read it, no
    audit row held it, no telemetry carried it. A repair is cheap; NOTICING was the missing half.
    """
    import asyncio

    class Http:
        def call(self, url, method="GET", body=None, internal=False, **kw):
            return (503, {}) if body.get("service") == "loyalty" else (201, {})

    class Telemetry:
        def __init__(self): self.events = []
        def event(self, name, **kw): self.events.append((name, kw))

    svc = SignupService.__new__(SignupService)
    svc._compliance = "http://compliance:8000"
    svc._data_map = ["operations:visits", "loyalty:points"]
    svc._http = Http()
    svc._telemetry = Telemetry()

    failed = asyncio.run(svc._register_data_map("tnt_x"))

    assert "loyalty" in failed
    assert svc._telemetry.events, "an incomplete data map that nothing reports is an absent one"
    name, kw = svc._telemetry.events[0]
    assert name == "data_map_incomplete"
    assert kw["tenant"] == "tnt_x" and kw["count"] == 1
    assert "loyalty" in kw["missing"], "the event must name WHICH service is uncovered"


def test_telemetry_is_optional_so_a_missing_seam_never_fails_a_signup():
    """Reporting a failure must not become a second failure."""
    import asyncio

    class Http:
        def call(self, url, method="GET", body=None, internal=False, **kw):
            return 503, {}

    class Angry:
        def event(self, *a, **kw): raise RuntimeError("collector down")

    for tele in (None, Angry()):
        svc = SignupService.__new__(SignupService)
        svc._compliance = "http://compliance:8000"
        svc._data_map = ["operations:visits"]
        svc._http = Http()
        svc._telemetry = tele
        assert "operations" in asyncio.run(svc._register_data_map("tnt_x"))


@pytest.mark.anyio
async def test_an_unverified_hold_is_not_called_an_account(monkeypatch):
    """و-7. Nothing stands between typing a number and an account existing on it, so a stranger
    can open a shop on somebody else's. The person who actually holds the number then arrives and
    is told «لهذا الرقم حساب بالفعل — سجّل الدخول» — with a password he never chose, and no way
    through. Both sentences are now told apart, and only one of them claims an account."""
    from app.core.signup import PHONE_INDEX

    store = FakeStore()
    await store.put(PHONE_INDEX, "+966501234567",
                    {"id": "+966501234567", "tenant": "t-old", "verified": False})
    svc = build(FakeHttp([]), store=store)

    with pytest.raises(SignupRefused) as caught:
        await svc.open_shop(NewShop("0501234567", "hunter2hunter2", "بنشر النور"))
    assert getattr(caught.value, "reason", "") == "unverified_hold"
    assert "سجّل الدخول" not in str(caught.value)


@pytest.mark.anyio
async def test_a_verified_number_still_says_sign_in():
    """The other half stays exactly as it was — a real account, and the sentence that saves him
    from trying four passwords on a door he holds the key to."""
    from app.core.signup import PHONE_INDEX

    store = FakeStore()
    await store.put(PHONE_INDEX, "+966501234567",
                    {"id": "+966501234567", "tenant": "t-old", "verified": True})
    svc = build(FakeHttp([]), store=store)

    with pytest.raises(SignupRefused) as caught:
        await svc.open_shop(NewShop("0501234567", "hunter2hunter2", "بنشر النور"))
    assert "سجّل الدخول" in str(caught.value)


# ── the erasure speaks compliance's vocabulary, not ours (ب-1) ─────────────────────────────────


def test_the_erasure_asks_for_a_type_compliance_actually_accepts():
    """EVERY ERASURE THIS PRODUCT HAS EVER BEEN ASKED FOR FAILED ON THIS ONE WORD.

    Our vocabulary for what a customer may ask his shop is («export», «erase»). compliance's is
    («access», «export», «erasure», «correction») and it VALIDATES the field — so `erase` is
    answered 422 by the first of the three calls, the request is never created, nothing fans out,
    and the owner is shown a log line while a thirty-day legal deadline runs.
    """
    from app.core import erase_customer as E

    sent: list[dict] = []

    def fake_post(url, *, authorization, body=None, timeout=10):
        sent.append({"url": url, "body": body or {}})
        return {"id": "dsar_1", "verification_token": "", "ok": True}

    original, E._post = E._post, fake_post
    try:
        E.erase_subject(compliance_url="http://compliance:8000",
                        authorization="Bearer x", subject_ref="sub_1")
    finally:
        E._post = original

    opened = sent[0]["body"]
    # THE FOUR compliance ACCEPTS, copied from its own model — not a guess, and not our word.
    assert opened["type"] in ("access", "export", "erasure", "correction")
    assert opened["type"] == "erasure"


def test_no_owner_facing_sentence_in_the_erase_path_is_a_log_line():
    """He reads these with a legal deadline running. «compliance answered 422» was one of them."""
    import re

    src = (pathlib.Path(__file__).resolve().parents[2]
           / "app" / "core" / "erase_customer.py").read_text(encoding="utf-8")
    raised = re.findall(r"raise EraseFailed\((.*?)\)\s*(?:from|$)", src, re.S)
    assert raised, "the guard itself must not go blind"
    for text in raised:
        assert re.search(r"[؀-ۿ]", text), f"not a sentence a shop owner can read: {text}"


@pytest.mark.parametrize("reply,expect_arabic", [
    ({"ok": False, "reason": "LEGAL_HOLD"}, "حجزٍ نظاميّ"),
    ({"ok": False, "reason": "WHATEVER"}, "لم يُنفَّذ الحذف"),
    ({}, "لم يُنفَّذ الحذف"),
])
def test_a_refusal_from_compliance_does_not_reach_the_owner_as_done(reply, expect_arabic):
    """د-3. compliance answers HTTP 200 with `ok: false` for every refusal except NOT_FOUND, so
    nothing raises. The reply was read as `.get("ok", True)` — a refusal set `dispatched` False
    while the route above still answered `ok: True`, which is the field the screen reads. He was
    told his customer's data was erased, on a legal deadline, and had no reason to look again."""
    from app.core import erase_customer as E

    def fake_post(url, *, authorization, body=None, timeout=10):
        if url.endswith("/dsar"):
            return {"id": "dsar_1", "verification_token": ""}
        return reply

    original, E._post = E._post, fake_post
    try:
        with pytest.raises(E.EraseFailed) as caught:
            E.erase_subject(compliance_url="http://compliance:8000",
                            authorization="Bearer x", subject_ref="sub_1")
    finally:
        E._post = original
    assert expect_arabic in str(caught.value)


def test_a_dispatched_erasure_still_reports_success():
    """The other half: the guard must not refuse what actually happened."""
    from app.core import erase_customer as E

    def fake_post(url, *, authorization, body=None, timeout=10):
        if url.endswith("/dsar"):
            return {"id": "dsar_9", "verification_token": ""}
        return {"ok": True, "targets": ["loyalty", "reminders"]}

    original, E._post = E._post, fake_post
    try:
        out = E.erase_subject(compliance_url="http://compliance:8000",
                              authorization="Bearer x", subject_ref="sub_9")
    finally:
        E._post = original
    assert out["dispatched"] is True
