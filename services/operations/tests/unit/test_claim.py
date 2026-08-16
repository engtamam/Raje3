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
    def __init__(self, known: dict[str, dict] | None = None) -> None:
        self.stamped: list[tuple[str, str]] = []
        self.stamped_by_id: list[tuple[str, str]] = []
        # key -> partner row, so `resolve` can behave like the real registry's key lookup.
        # "pk_1" is every test's key here — resolving to a stable id so the ك-5 flow (resolve at
        # invite time, stamp by id at claim time) has something real to resolve against.
        self._known = known if known is not None else {
            "pk_1": {"id": "partner-1", "name": "Partner One",
                     "commission_rate": 0.1, "active": True}}

    async def resolve(self, key: str):
        return self._known.get(key)

    async def stamp(self, tenant, *, key=""):
        self.stamped.append((tenant, key))
        return {}

    async def stamp_by_partner_id(self, tenant, *, partner_id=""):
        self.stamped_by_id.append((tenant, partner_id))
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


class FakeTelemetry:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def event(self, name, **kw):
        self.events.append((name, kw))


def build(http=None, store=None, sectors=None, partners=None, telemetry=None):
    return SignupService(
        store=store or FakeStore(), sectors=sectors or FakeSectors(),
        http=http or FakeHttp(HAPPY),
        identity_url="http://identity:8000", tenants_url="http://tenants:8000",
        authz_url="http://authz:8000", roles=ROLES, partners=partners or FakePartners(),
        otp_deliverable=True, telemetry=telemetry)


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


@pytest.mark.anyio
async def test_an_unknown_partner_key_is_refused_at_invite_time_not_at_claim_time():
    """ك-4 / ك-5: resolving at invite time means the TILL COMPANY learns its typo immediately,
    while it can still fix the call — instead of the failure surfacing days later on the OWNER's
    claim, where nobody who could act on it ever sees it."""
    svc = build(partners=FakePartners(known={}))          # nothing resolves

    with pytest.raises(SignupRefused):
        await svc.invite_partner_shop(phone="0501234567", shop_name="بنشر",
                                      partner_key="typo_key")


@pytest.mark.anyio
async def test_the_invitation_never_stores_the_raw_partner_key():
    """ك-5: `partners.py` states its own rule — a partner key is «shown once, stored hashed». This
    row used to hold the raw key in plaintext for up to seven days. Only the resolved id may
    appear anywhere in the stored row."""
    store = FakeStore()
    svc = build(store=store)
    await svc.invite_partner_shop(phone="0501234567", shop_name="بنشر", partner_key="pk_1")

    row = store.rows[("partner_claims", "+966501234567")]
    assert row.get("partner_id") == "partner-1"
    assert "pk_1" not in row.values()
    assert "partner_key" not in row


@pytest.mark.anyio
async def test_a_stamp_failure_is_telemetried_for_an_operator_to_act_on():
    """ك-4, core half: `open_shop`'s stamp failure must reach telemetry — the only place an
    operator who can actually repair it will see it. The route layer (api/v1/signup.py) is what
    keeps it off the owner's screen; see the sibling test there."""

    class _RejectingPartners(FakePartners):
        async def stamp_by_partner_id(self, tenant, *, partner_id=""):
            raise Exception("partner is not active")               # noqa: BLE001

    telemetry = FakeTelemetry()
    partners = _RejectingPartners()
    svc = build(partners=partners, telemetry=telemetry)
    await svc.invite_partner_shop(phone="0501234567", shop_name="بنشر", partner_key="pk_1")

    out = await svc.claim("0501234567", "123456", "his-own-passphrase")

    assert out["stamp_error"]                                  # core dict still carries it
    assert any(name == "partner_stamp_failed" for name, _ in telemetry.events)


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
    # AND THE COMMISSION FOLLOWS THE INVITATION, not the request — by the RESOLVED id, since
    # `invite_partner_shop` resolved the key at invite time (ك-5) and never stores it raw.
    assert partners.stamped == []
    assert partners.stamped_by_id == [("t-1", "partner-1")]


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
    expired = CL.Invitation(phone="+966501234567", shop_name="x", partner_id="k",
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
    inv = CL.Invitation(phone="+966501234567", shop_name="x", partner_id="k",
                        created=NOW, expires=NOW + CL.TTL_SECONDS)

    assert inv.alive(NOW + 6 * 86400)
    assert not inv.alive(NOW + 8 * 86400)
