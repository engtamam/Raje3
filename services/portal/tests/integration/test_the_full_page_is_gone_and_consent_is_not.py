"""The page is closed for the first release; the two consent doors are not.

THE DECISION. The full customer page ships closed (PUBLIC_PAGE_ENABLED=false): it is a product of
its own, it is not finished, and a half-built page opened from a shop's WhatsApp message reads as a
scam rather than as a work in progress.

THE TRAP THAT DECISION SETS, and it is the reason this file exists. Marketing consent is opt-IN.
Close every route and nobody can ever grant, so no marketing message may lawfully leave — and the
campaigns engine, which is complete and sold as an app, sends nothing for the life of the release.
The closure would look like a UI decision and land as a dead product line, with no error anywhere.

So the flag closes the PAGE and leaves the two obligations open:

    GET  /p/{ref}/allow    ask, in one screen
    POST /p/{ref}/allow    record it — and report what the peer actually said
    GET  /p/{ref}/stop     withdraw in one tap, whatever else is shut (spec §8.3)

These tests run with the flag WHERE IT SHIPS. A suite that opened it to test the closure would be
proving something about a configuration nobody deploys.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.config import get_settings

    saved = dict(os.environ)
    # PUBLIC_PAGE_ENABLED is deliberately NOT set: the default is the shipped value, and a test
    # that had to set it could keep passing after somebody changed that default.
    os.environ.update({"ENV": "test", "INTERNAL_SERVICE_TOKEN": "t" * 40,
                       "PAGE_REF_SECRET": "s" * 40, "RATELIMIT_MAX": "1000"})
    os.environ.pop("PUBLIC_PAGE_ENABLED", None)
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(), raise_server_exceptions=False)
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def _ref() -> str:
    from app.core.reference import build

    return build("tnt_page", "sub_" + "a" * 24)


class _Reminders:
    """reminders as it really answers: a boolean for whether the write happened."""

    def __init__(self, granted: bool = True, stopped_ok: bool = True):
        self.granted = granted
        self.stopped_ok = stopped_ok
        self.grants = 0
        self.stops = 0

    async def prefs_for(self, tenant, subject_ref):
        return {"preferences": [{"class": "marketing", "label": "", "enabled": False}]}

    async def offers_for(self, tenant, subject_ref):
        return {"offers": []}

    async def set_prefs(self, tenant, subject_ref, *, stopped, merge=False):
        self.stops += 1
        return self.stopped_ok

    async def grant_marketing(self, tenant, subject_ref):
        self.grants += 1
        return self.granted


# ── the page itself is shut ───────────────────────────────────────────────────────────────────

def test_the_page_does_not_render_his_history(client):
    """THE CLOSURE. Visits, points and the five switches are the page, and none of them appears."""
    body = client.get(f"/p/{_ref()}").text

    assert "قيد التجهيز" in body
    # The switches are the page's whole write surface — their absence is what «closed» means here.
    assert "type='checkbox'" not in body and 'type="checkbox"' not in body


def test_the_closed_page_is_not_a_404(client):
    """A DEAD LINK IS THE WRONG ANSWER. The shop's own message sent this URL minutes ago, and a
    404 tells the customer the message was fake — a conclusion we do not get to correct later."""
    assert client.get(f"/p/{_ref()}").status_code == 200


def test_the_writes_behind_the_page_close_with_it(client):
    """A form nobody can reach must not leave an unauthenticated write open behind it."""
    reminders = _Reminders()
    client.app.state.container.reminders = reminders

    client.post(f"/p/{_ref()}/prefs", content="on=marketing")

    assert reminders.stops == 0, "the preferences write ran while the page that drives it is shut"


# ── and consent is not ────────────────────────────────────────────────────────────────────────

def test_the_grant_screen_is_served_with_the_page_closed(client):
    """WITHOUT THIS, NO MARKETING MESSAGE MAY EVER LEAVE. Opt-in with no way to opt in is a dead
    campaigns engine, and nothing would report it."""
    body = client.get(f"/p/{_ref()}/allow").text

    assert "أرسلوا لي العروض" in body


def test_the_screen_shows_the_sentence_that_gets_recorded(client):
    """WHAT MAKES IT CONSENT rather than a tap. The sender, the volume and the exit — the same
    sentence reminders stores with the grant (gated: the two are compared byte for byte)."""
    from app.core.onescreen import statement_for

    body = client.get(f"/p/{_ref()}/allow").text

    assert statement_for("") in body or "أوافق على استقبال عروض" in body


def test_asking_does_not_grant(client):
    """THE WHOLE REASON THIS IS A SCREEN AND NOT A LINK. WhatsApp fetches link previews, messages
    get forwarded, scanners crawl — and a GET that granted would turn any of those into a consent
    record for somebody who never agreed."""
    reminders = _Reminders()
    client.app.state.container.reminders = reminders

    client.get(f"/p/{_ref()}/allow")

    assert reminders.grants == 0, "opening the screen recorded a consent nobody gave"


def test_the_button_records_the_grant(client):
    reminders = _Reminders(granted=True)
    client.app.state.container.reminders = reminders

    body = client.post(f"/p/{_ref()}/allow").text

    assert reminders.grants == 1
    assert "تمّ" in body


def test_a_grant_that_did_not_save_does_not_say_it_did(client):
    """THE PEER'S ANSWER, NOT OUR OPTIMISM — the rule every write on this service follows. A
    customer told he is subscribed who receives nothing does not press again."""
    client.app.state.container.reminders = _Reminders(granted=False)

    body = client.post(f"/p/{_ref()}/allow").text

    assert "تمّ" not in body
    assert "تعذّر" in body


def test_the_stop_still_answers_with_the_page_closed(client):
    """SPEC §8.3. Withdrawal is one tap whatever else is shut — and it reports the peer's answer,
    because a stop that silently failed is how a shop loses a customer and its number together."""
    reminders = _Reminders(stopped_ok=True)
    client.app.state.container.reminders = reminders

    body = client.get(f"/p/{_ref()}/stop").text

    assert reminders.stops == 1
    assert "أُوقفت العروض" in body


def test_a_stop_that_failed_says_so_even_when_the_page_is_closed(client):
    client.app.state.container.reminders = _Reminders(stopped_ok=False)

    body = client.get(f"/p/{_ref()}/stop").text

    assert "أُوقفت العروض" not in body
    assert "تعذّر" in body
