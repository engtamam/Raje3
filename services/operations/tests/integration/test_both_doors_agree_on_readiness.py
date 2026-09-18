"""د-16 · the finish said «ready to send» about a number that was never registered.

TWO DOORS, ONE QUESTION, TWO ANSWERS. `GET /whatsapp/connect` computed readiness properly — our
channel open AND the number registered with Meta. `POST /whatsapp/connect` returned
`SIGNUP_OTP_DELIVERABLE` alone.

And the SCREEN READS THE POST FIRST: `Connect.tsx` renders the whole PIN form behind
`connected && can_send === false`. So the moment the flag was raised, the owner finished signup,
read «جاهز للإرسال», never saw the code field at all — and every message bounced 133010 because his
number was never registered. Green, and mute, with no next step anywhere on the screen.

The readiness rule now lives in one function that both doors call, so there is no second place to
forget and no table of which door computes what.
"""
from __future__ import annotations

import datetime as dt
import os

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core import connect

PATH = "/api/v1/whatsapp/connect"
SECRET = "h" * 40
ISS, AUD = "iss", "aud"
TENANT = "tnt_ready"


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({
        "ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
        "TOKEN_VERIFIER_DRIVER": "hs256", "TOKEN_HS256_SECRET": SECRET,
        "TOKEN_ISSUER": ISS, "TOKEN_AUDIENCE": AUD, "RATELIMIT_MAX": "1000",
        # THE FLAG RAISED — which is exactly the state the defect needed. With it down, the POST's
        # wrong answer and the right one happen to agree, which is why this went unseen.
        "SIGNUP_OTP_DELIVERABLE": "true", "SIGNUP_REQUIRE_OTP": "false",
    })
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _headers(tenant=TENANT):
    now = dt.datetime.now(dt.timezone.utc)
    tok = jwt.encode({"sub": "u1", "iss": ISS, "aud": AUD, "caps": ["billing.self"],
                      "tenant": tenant, "exp": now + dt.timedelta(minutes=5), "iat": now},
                     SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {tok}"}


class _Registration:
    """Meta's answer about the number."""

    def __init__(self, verified: str) -> None:
        self._verified = verified

    @property
    def configured(self) -> bool:
        return True

    async def status(self, tenant, phone_number_id=""):
        return {"code_verification_status": self._verified} if self._verified else {}


def _exchange_succeeds(monkeypatch):
    class _Ex:
        async def exchange(self, *, tenant, code, waba_id, phone_number_id, branch_id="", root_tenant=""):
            return True, ""
    monkeypatch.setattr(connect, "build_exchange", lambda s: _Ex())


def _finish(client):
    return client.post(PATH, json={"event": "FINISH", "phone_number_id": "pn_1",
                                   "waba_id": "wa_1", "code": "c" * 20},
                       headers=_headers())


def test_the_finish_does_not_claim_a_number_can_send_before_it_is_registered(client, monkeypatch):
    """THE DEFECT ITSELF, on the response the screen actually reads."""
    _exchange_succeeds(monkeypatch)
    monkeypatch.setattr(connect, "build_registration", lambda s: _Registration("NOT_VERIFIED"))

    out = _finish(client).json()

    assert out["state"] == connect.STATE_CONNECTED
    assert out["can_send"] is False, (
        "«جاهز للإرسال» hides the PIN form, and without the PIN every message bounces 133010")


def test_both_doors_give_the_same_answer(client, monkeypatch):
    """ONE RULE, ASKED TWICE. The two doors disagreeing is the defect; agreeing on the wrong
    answer would be the next one, so the status door is read in the same breath."""
    _exchange_succeeds(monkeypatch)
    monkeypatch.setattr(connect, "build_registration", lambda s: _Registration("NOT_VERIFIED"))

    finished = _finish(client).json()
    status = client.get(PATH, headers=_headers()).json()

    assert finished["can_send"] == status["can_send"] is False


def test_a_registered_number_is_told_it_can_send(client, monkeypatch):
    """The guard must not eat the good case: a shop whose number Meta has verified is ready, and
    showing it a code field it does not need is its own kind of lie."""
    _exchange_succeeds(monkeypatch)
    monkeypatch.setattr(connect, "build_registration", lambda s: _Registration("VERIFIED"))

    assert _finish(client).json()["can_send"] is True


def test_an_unreadable_status_does_not_invent_a_fault(client, monkeypatch):
    """«We could not ask» is not «his number is unverified». A screen that invents a fault sends
    an owner chasing one, so the answer falls back to our own flag."""
    _exchange_succeeds(monkeypatch)
    monkeypatch.setattr(connect, "build_registration", lambda s: _Registration(""))

    assert _finish(client).json()["can_send"] is True


# ── the SAME defect, one door over: a branch's own number, checked under the wrong identity ──────
class _RecordingRegistration:
    """Meta's answer, plus WHICH identity it was actually asked about — the one fact both `_can_send`
    call sites got wrong for a branch's own connection before this fix (asked about the bare
    tenant, sealed under `tenant:branch`)."""

    def __init__(self, verified: str) -> None:
        self._verified = verified
        self.asked_about: list[str] = []

    async def status(self, tenant, phone_number_id=""):
        self.asked_about.append(tenant)
        return {"code_verification_status": self._verified} if self._verified else {}


def _set_per_branch(client, tenant):
    import asyncio
    from app.core.shop_mode import ModeStore
    asyncio.run(ModeStore(client.app.state.container.datastore).set(tenant, "per_branch", available=True))


def _add_branch(client, tenant, branch_id):
    """A REAL branch row — connect.py now validates `branch_id` against this tenant's actual
    branches (operations-r2-005, 2026-09-12) before it becomes half of a sealed sending identity,
    so a test naming a branch that was never created would now see it silently dropped."""
    import asyncio
    from app.core.models import Branch
    from app.core.stores import BranchStore
    asyncio.run(BranchStore(client.app.state.container.datastore).save(
        Branch(id=branch_id, tenant=tenant, name="فرع", created=1)))


def test_a_branchs_readiness_is_asked_under_its_own_sending_identity(client, monkeypatch):
    """د-16, one door over: the finish route used to ask Meta about the bare tenant even for a
    branch's own connection — sealed under `tenant:branch`, asked about under `tenant` alone, so a
    branch's real registration was invisible to the one check that decides «جاهز للإرسال»."""
    _set_per_branch(client, TENANT)
    _add_branch(client, TENANT, "brn_jed")
    _exchange_succeeds(monkeypatch)
    reg = _RecordingRegistration("VERIFIED")
    monkeypatch.setattr(connect, "build_registration", lambda s: reg)

    r = client.post(PATH, json={"event": "FINISH", "phone_number_id": "pn_brn",
                                "waba_id": "wa_1", "code": "c" * 20, "branch_id": "brn_jed"},
                    headers=_headers())
    assert r.json()["can_send"] is True
    assert reg.asked_about == [f"{TENANT}:brn_jed"], (
        "asked about the wrong identity — a branch's real registration would never be seen")


def test_a_branchs_own_status_door_answers_for_that_branch_not_the_establishment(client, monkeypatch):
    """The GET door used to accept no `branch_id` at all — a chain's second branch had no way to
    ask «is MY number connected» and always read the establishment's own status (or nothing)."""
    _set_per_branch(client, TENANT)
    _add_branch(client, TENANT, "brn_jed")
    _exchange_succeeds(monkeypatch)
    monkeypatch.setattr(connect, "build_registration", lambda s: _Registration("VERIFIED"))

    client.post(PATH, json={"event": "FINISH", "phone_number_id": "pn_brn",
                            "waba_id": "wa_1", "code": "c" * 20, "branch_id": "brn_jed"},
               headers=_headers())

    same_branch = client.get(PATH, params={"branch_id": "brn_jed"}, headers=_headers()).json()
    assert same_branch["state"] == connect.STATE_CONNECTED

    other_branch = client.get(PATH, params={"branch_id": "brn_riy"}, headers=_headers()).json()
    assert other_branch["state"] != connect.STATE_CONNECTED, (
        "a second branch that never connected read the first branch's own status"
    )
