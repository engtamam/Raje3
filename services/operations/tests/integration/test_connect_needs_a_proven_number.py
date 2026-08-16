"""و-7 — a shop opened on somebody else's number must not bind that shop's WhatsApp.

THE HOLE. Nothing stands between typing a phone number and an account existing on it: the proof is
deferred to sign-in, so a stranger can open a shop on a number he does not hold. The real owner is
then told «سجّل الدخول» with a password he never chose, and has no way through.

BINDING WHATSAPP IS WHERE THAT TURNS INTO A LOSS. It is the account a real business sends from —
every message afterwards goes out in its name and is billed to it by Meta. So the refusal lives on
that act: the whole thing cannot be closed here (a number is reserved before it is proven, and
un-reserving it is a deletion that is not ours to make — see task #167), but the damage can.

GATED ON THE SAME RULE AS SIGN-IN. Where no code can be delivered at all nobody could satisfy this,
and a requirement no one can meet closes the product instead of protecting it.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/whatsapp/connect"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_unproven"


def _client(require_otp: str):
    from app.config import get_settings

    os.environ.update({
        "ENV": "test",
        "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256",
        "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS,
        "TOKEN_AUDIENCE": AUD,
        "RATELIMIT_MAX": "1000",
        "SIGNUP_REQUIRE_OTP": require_otp,
    })
    get_settings.cache_clear()
    from app.main import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture()
def saved_env():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    from app.config import get_settings
    get_settings.cache_clear()


def _headers(tenant=TENANT):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


def _remember(client, phone: str, tenant: str):
    """A signup, as the saga leaves it: a number claimed and nobody has proved it."""
    import asyncio
    asyncio.run(client.app.state.container.signup._remember(phone, tenant))   # noqa: SLF001


async def _canonical(signup, phone: str) -> str:
    from app.core.signup import canonical_phone
    return canonical_phone(phone, default_cc=signup._cc)                      # noqa: SLF001


def _prove(client, phone: str):
    import asyncio

    from app.core.signup import PHONE_INDEX
    signup = client.app.state.container.signup

    async def go():
        # THE SAGA'S OWN KEY. The index is keyed by the canonical form, and a test that writes the
        # raw string proves the fixture works rather than the code.
        key = await _canonical(signup, phone)
        row = await signup._store.get(PHONE_INDEX, key)                       # noqa: SLF001
        assert row is not None, "the signup row this test is about was never written"
        await signup._store.put(PHONE_INDEX, key, {**row, "verified": True})  # noqa: SLF001
        await signup._mark_proven(str(row["tenant"]), key)                    # noqa: SLF001

    asyncio.run(go())


def test_an_unproven_number_cannot_bind_the_shops_whatsapp(saved_env):
    """THE DEFECT ITSELF. The exchange ran for anybody holding a session, and a session is what
    opening a shop on a stranger's number hands you."""
    client = _client("true")
    _remember(client, "966500000001", TENANT)

    r = client.post(PATH, json={"event": "FINISH", "phone_number_id": "pn_1",
                                "waba_id": "wa_1", "code": "c" * 20},
                    headers=_headers())

    assert r.status_code == 403, r.text
    # A SENTENCE HE CAN ACT ON, not «غير مصرّح». The step he is missing is one he can complete.
    assert "أكّد رقم جوالك" in r.json()["message"], r.text


def test_the_same_shop_connects_once_the_number_is_proven(saved_env):
    """AND THE RULE LETS THE REAL OWNER THROUGH — a guard that refuses everybody is an outage."""
    client = _client("true")
    _remember(client, "966500000002", "tnt_proven")
    _prove(client, "966500000002")

    r = client.post(PATH, json={"event": "FINISH", "phone_number_id": "pn_2",
                                "waba_id": "wa_2", "code": "c" * 20},
                    headers=_headers("tnt_proven"))

    # It gets PAST this gate — what happens next is Meta's exchange, which has no credentials in a
    # test and fails on its own terms. The assertion is only that the refusal is not ours.
    assert r.status_code != 403 or "أكّد رقم جوالك" not in r.text


def test_a_shop_that_predates_this_index_is_not_locked_out(saved_env):
    """NO ROW IS NOT «NOT PROVEN». Every shop created before this index existed has no row, and
    reading that as a refusal would lock working shops out of connecting — a fault we would have
    invented, in the name of a rule about strangers."""
    client = _client("true")

    r = client.post(PATH, json={"event": "FINISH", "phone_number_id": "pn_3",
                                "waba_id": "wa_3", "code": "c" * 20},
                    headers=_headers("tnt_never_seen"))

    assert "أكّد رقم جوالك" not in r.text


def test_where_no_code_can_be_delivered_the_rule_stands_down(saved_env):
    """A REQUIREMENT NOBODY CAN MEET IS NOT A CONTROL. Until a code can actually be sent
    (task #167) no owner could ever prove his number, and enforcing this would mean no shop in the
    pilot could connect at all. It follows the same switch sign-in follows."""
    client = _client("false")
    _remember(client, "966500000004", "tnt_nootp")

    r = client.post(PATH, json={"event": "FINISH", "phone_number_id": "pn_4",
                                "waba_id": "wa_4", "code": "c" * 20},
                    headers=_headers("tnt_nootp"))

    assert "أكّد رقم جوالك" not in r.text
