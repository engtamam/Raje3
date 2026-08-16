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
        async def exchange(self, *, tenant, code, waba_id, phone_number_id):
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
