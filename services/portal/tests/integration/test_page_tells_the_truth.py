"""The customer's page: two things it told him that were not checked (م · قواطع).

1. «تم حفظ تفضيلاتك» ON THE ONE-TAP STOP. The form path binds the peer's answer and renders the
   confirmation from it — and says why, in the file: «a customer who is told their choice was
   saved and keeps receiving messages does not try again, they block the number». The `/stop`
   link — the one inside every marketing message, made frictionless on purpose because somebody
   who wants out is already annoyed — threw that answer away and rendered success unconditionally.

   So the save fails, the offers keep coming, and he does not retry. He blocks the shop's number,
   and the shop loses him and its sender reputation together.

2. THE LOGO READ TURNING THE PAGE INTO A 500. `compose.py` swallows a tenant-service outage on
   purpose: the page still has his points, his visits and his switches. Then a bare `logo_url`
   read was added after it and threw straight out — so an outage there answered a customer, who
   arrived from a WhatsApp message, with an English error screen. He does not read that as «a
   service is down». He reads it as «that message was a scam».
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    os.environ.update({"ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
                       "PAGE_REF_SECRET": "s" * 40, "RATELIMIT_MAX": "1000"})
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _ref(client) -> str:
    """A reference the page will accept, minted the way the sender mints it."""
    from app.core.reference import build

    return build("tnt_page", "sub_" + "a" * 24)


class _Prefs:
    """reminders, answering the way it really does: a boolean for whether the save happened."""

    def __init__(self, ok: bool):
        self.ok = ok
        self.calls = 0

    async def set_prefs(self, tenant, subject_ref, *, stopped, merge=False):
        self.calls += 1
        return self.ok


def test_a_stop_that_did_not_save_does_not_say_it_saved(client):
    """THE DEFECT. He taps «إيقاف»، reads «تم حفظ تفضيلاتك»، and the offers keep coming."""
    client.app.state.container.reminders = _Prefs(ok=False)

    body = client.get(f"/p/{_ref(client)}/stop").text

    assert "تم حفظ" not in body, "a save that failed must not be confirmed"


def test_a_stop_that_did_save_still_confirms(client):
    """AND THE GUARD MUST NOT EAT THE HAPPY PATH — a stop that worked and says nothing sends him
    to press it again, or to block the number anyway."""
    client.app.state.container.reminders = _Prefs(ok=True)

    body = client.get(f"/p/{_ref(client)}/stop").text

    assert "تم حفظ" in body


def test_a_logo_outage_does_not_turn_his_page_into_an_error(client):
    """THE 500. Everything else on this page is composed defensively; this one read was not."""

    class _Identity:
        async def logo_url(self, tenant):
            raise RuntimeError("tenant-service is down")

    client.app.state.container.identity = _Identity()

    r = client.get(f"/p/{_ref(client)}")

    assert r.status_code == 200, r.text
    # AND THE PAGE IS THE PAGE, not a stub: he still gets what the composer could read.
    assert "<html" in r.text.lower()
