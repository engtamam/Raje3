"""The door — the three properties that are worth a test rather than a reading.

Not "does it call three services": that is the code restated. These are the ones that are silent
when broken — a phone that folds to two different accounts, an orphan tenant left by a failed
registration, and a refusal that answers "no such shop" differently from "wrong password".
"""
from __future__ import annotations

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


def build(http, store=None, sectors=None, roles=ROLES):
    return SignupService(
        store=store or FakeStore(), sectors=sectors or FakeSectors(), http=http,
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
        await svc.open_shop(NewShop("0501234567", "hunter2hunter2", "بنشر النور", "tyres"))

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
    out = await build(http, sectors=Broken()).open_shop(
        NewShop("0501234567", "hunter2hunter2", "بنشر النور", "tyres"))

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
    await build(http).open_shop(NewShop("0501234567", "hunter2hunter2", "بنشر النور", "tyres"))

    assert ("POST", "http://authz:8000/internal/authz/tenants/t-1/bootstrap") in http.calls


@pytest.mark.anyio
async def test_a_failed_bootstrap_leaves_nothing_behind():
    """An account that can do nothing is WORSE than no account: he cannot fix it, cannot be told
    why, and would try again with the same number and be refused for already existing."""
    http = FakeHttp([("/internal/tenants", (201, {"id": "t-1"})),
                     ("/seed-owner", (201, {"person_id": "p-9"})),
                     ("/bootstrap", (500, {}))])

    with pytest.raises(SignupRefused):
        await build(http).open_shop(NewShop("0501234567", "hunter2hunter2", "بنشر النور", "tyres"))

    assert ("DELETE", "http://tenants:8000/internal/tenants/t-1") in http.calls


@pytest.mark.anyio
async def test_no_role_definitions_refuses_rather_than_creating_a_dead_account():
    # The file failed to load at boot. Creating an account anyway would be creating exactly the
    # broken state this whole step was added to remove.
    http = FakeHttp([("/internal/tenants", (201, {"id": "t-1"})),
                     ("/seed-owner", (201, {"person_id": "p-9"}))])

    with pytest.raises(SignupRefused):
        await build(http, roles=[]).open_shop(
            NewShop("0501234567", "hunter2hunter2", "بنشر النور", "tyres"))

    assert ("DELETE", "http://tenants:8000/internal/tenants/t-1") in http.calls
