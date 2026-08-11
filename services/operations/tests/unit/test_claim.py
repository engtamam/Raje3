"""The shop that arrives through its till — and the password nobody but its owner holds.

The properties here are commercial and security ones in equal measure: who can open a shop, whose
commission a claim carries, and what an attacker learns by guessing a phone number.
"""
from __future__ import annotations

import time

import pytest

from app.core import claim as CL
from app.core.signup import SignupRefused, SignupService
from app.core.sectors import UNSPECIFIED

NOW = int(time.time())


class FakeStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    async def get(self, collection, key):
        return self.rows.get((collection, key))

    async def put(self, collection, key, row):
        self.rows[(collection, key)] = row

    async def delete(self, collection, key):
        return self.rows.pop((collection, key), None) is not None


class FakeSectors:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def seed_tenant(self, *, tenant, sector_key, integrated=False):
        self.calls.append({"tenant": tenant, "sector": sector_key, "integrated": integrated})
        return 1


class FakePartners:
    def __init__(self) -> None:
        self.stamped: list[tuple[str, str]] = []

    async def stamp(self, tenant, *, key=""):
        self.stamped.append((tenant, key))
        return {}


class FakeHttp:
    def __init__(self, answers) -> None:
        self.answers = answers
        self.calls: list[tuple[str, str]] = []

    def call(self, url, *, method, body=None, internal=False):
        self.calls.append((method, url))
        for suffix, answer in self.answers:
            if url.endswith(suffix):
                return answer
        return 500, {}


HAPPY = [("/otp/request", (200, {"delivered": True})),
         ("/otp/verify", (200, {})),
         ("/internal/tenants", (201, {"id": "t-1"})),
         ("/seed-owner", (201, {"person_id": "p-1"})),
         ("/bootstrap", (200, {}))]

ROLES = [{"name": "owner", "capabilities": ["operations.record"], "description": ""}]


def build(http=None, store=None, sectors=None, partners=None):
    return SignupService(
        store=store or FakeStore(), sectors=sectors or FakeSectors(),
        http=http or FakeHttp(HAPPY),
        identity_url="http://identity:8000", tenants_url="http://tenants:8000",
        authz_url="http://authz:8000", roles=ROLES, partners=partners or FakePartners(),
        otp_deliverable=True)


# ── the invitation ────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_the_invitation_creates_no_account():
    """THE WHOLE DESIGN. If the partner's call created the account, the partner would have chosen
    the password — and whoever holds it can connect the shop's WhatsApp, subscribe it, and message
    its customers in its name."""
    http = FakeHttp(HAPPY)
    svc = build(http)

    out = await svc.invite_partner_shop(phone="0501234567", shop_name="بنشر النور",
                                        partner_key="pk_1")

    assert out["invited"] is True
    assert not any("/seed-owner" in url for _, url in http.calls)
    assert not any("/internal/tenants" in url for _, url in http.calls)


@pytest.mark.anyio
async def test_a_failed_message_does_not_lose_the_invitation():
    """The record is durable and the message is not. He can ask for a code from the claim screen,
    so a provider hiccup must not cost the till company its enrolment."""
    http = FakeHttp([("/otp/request", (500, {}))])
    store = FakeStore()
    svc = build(http, store=store)

    out = await svc.invite_partner_shop(phone="0501234567", shop_name="بنشر", partner_key="pk_1")

    assert out["delivered"] is False
    assert await svc._claims.get("+966501234567") is not None      # noqa: SLF001


@pytest.mark.anyio
async def test_a_number_that_already_has_a_shop_is_refused_plainly():
    """Internal tier, so it may say what it means: the till company needs to know it enrolled a
    shop that is already ours, rather than wait for a claim that never comes."""
    svc = build()
    await svc._remember("0501234567", "t-old")                     # noqa: SLF001

    with pytest.raises(SignupRefused):
        await svc.invite_partner_shop(phone="0501234567", shop_name="بنشر", partner_key="pk_1")


# ── the claim ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_the_owner_opens_it_with_a_password_of_his_own():
    sectors, partners = FakeSectors(), FakePartners()
    svc = build(sectors=sectors, partners=partners)
    await svc.invite_partner_shop(phone="0501234567", shop_name="بنشر النور", partner_key="pk_1")

    out = await svc.claim("0501234567", "123456", "his-own-passphrase")

    assert out["tenant"] == "t-1"
    # THE SECTOR IS «غير محدَّد» AND THE CATALOGUE IS NOT SEEDED FULL: his invoices build it, and
    # seventeen names his till never mentions would leave him unable to tell which are real.
    assert sectors.calls == [{"tenant": "t-1", "sector": UNSPECIFIED, "integrated": True}]
    # AND THE COMMISSION FOLLOWS THE INVITATION, not the request.
    assert partners.stamped == [("t-1", "pk_1")]


@pytest.mark.anyio
async def test_the_number_is_proven_before_the_shop_exists():
    """Without it the invitation is a shop anybody who learned the number could open — and the
    message carrying the code is the only thing tying this claim to the person enrolled."""
    http = FakeHttp([("/otp/request", (200, {"delivered": True})),
                     ("/otp/verify", (400, {"detail": "invalid"}))])
    svc = build(http)
    await svc.invite_partner_shop(phone="0501234567", shop_name="بنشر", partner_key="pk_1")

    with pytest.raises(SignupRefused):
        await svc.claim("0501234567", "000000", "his-own-passphrase")

    assert not any("/internal/tenants" in url for _, url in http.calls)


@pytest.mark.anyio
async def test_an_invitation_is_single_use():
    """One that worked twice would be a password reset for anybody who ever saw the message."""
    svc = build()
    await svc.invite_partner_shop(phone="0501234567", shop_name="بنشر", partner_key="pk_1")
    await svc.claim("0501234567", "123456", "his-own-passphrase")

    with pytest.raises(SignupRefused):
        await svc.claim("0501234567", "123456", "another-passphrase")


@pytest.mark.anyio
async def test_it_is_consumed_only_after_the_shop_exists():
    """Consuming first would burn the invitation on a signup that then failed, and the owner would
    need the till company to issue another one for a mistake that was ours."""
    http = FakeHttp([("/otp/request", (200, {"delivered": True})),
                     ("/otp/verify", (200, {})),
                     ("/internal/tenants", (500, {}))])
    svc = build(http)
    await svc.invite_partner_shop(phone="0501234567", shop_name="بنشر", partner_key="pk_1")

    with pytest.raises(SignupRefused):
        await svc.claim("0501234567", "123456", "his-own-passphrase")

    assert await svc._claims.get("+966501234567") is not None      # noqa: SLF001


# ── what a stranger learns ────────────────────────────────────────────────────────────────────

def test_unknown_expired_and_claimed_are_one_answer():
    """Told apart, they answer "has a till company registered this number" to anyone who asks —
    and the person who legitimately holds an invitation is not helped by knowing which, because in
    all three his next step is the same: ask the till company again."""
    expired = CL.Invitation(phone="+966501234567", shop_name="x", partner_key="k",
                            created=NOW - 40 * 86400, expires=NOW - 30 * 86400)
    messages = set()
    for inv in (None, expired):
        with pytest.raises(CL.ClaimError) as exc:
            CL.check(inv, now=NOW)
        messages.add(str(exc.value))

    assert len(messages) == 1


def test_an_invitation_expires():
    """One that never expires is a way into a shop nobody remembers issuing — the till company
    changes staff, the record survives, and a claim arrives a year later."""
    inv = CL.Invitation(phone="+966501234567", shop_name="x", partner_key="k",
                        created=NOW, expires=NOW + CL.TTL_SECONDS)

    assert inv.alive(NOW + 6 * 86400)
    assert not inv.alive(NOW + 8 * 86400)
