"""The full customer page is gone; the two consent doors are not.

THE DECISION. The full customer page (points, visits, preferences, DSAR buttons) was never shipped
open in production and has now been deleted outright — a product of its own, not finished, and not
worth carrying forward half-built. What remains is the minimal surface spec §8.3/§8.5 require:

    GET  /p/{ref}/allow    ask, in one screen
    POST /p/{ref}/allow    record it — and report what the peer actually said
    GET  /p/{ref}/stop     withdraw in one tap, whatever else is shut (spec §8.3)

THE TRAP THAT MADE THESE TWO SURVIVE THE PAGE'S DEATH. Marketing consent is opt-IN. Delete every
route and nobody can ever grant, so no marketing message may lawfully leave — and the campaigns
engine, complete and sold as an app, sends nothing for the life of the release. Deleting the page
looks like a scope cut and lands as a dead product line, with no error anywhere, unless these two
doors are kept open on their own.
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


# ── the full page is gone ─────────────────────────────────────────────────────────────────────

def test_the_full_page_route_no_longer_exists(client):
    """GET /p/{ref} was the full page — visits, points, five switches, DSAR buttons. Deleted, not
    hidden behind a flag: a 404 here is the correct answer now, not a regression."""
    assert client.get(f"/p/{_ref()}").status_code == 404


def test_the_prefs_route_no_longer_exists(client):
    """POST /p/{ref}/prefs saved the five switches that only the full page ever showed."""
    assert client.post(f"/p/{_ref()}/prefs", content="on=marketing").status_code == 404


# ── and consent is not ────────────────────────────────────────────────────────────────────────

def test_the_grant_screen_is_served(client):
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


def test_the_stop_still_answers(client):
    """SPEC §8.3. Withdrawal is one tap — and it reports the peer's answer, because a stop that
    silently failed is how a shop loses a customer and its number together."""
    reminders = _Reminders(stopped_ok=True)
    client.app.state.container.reminders = reminders

    body = client.get(f"/p/{_ref()}/stop").text

    assert reminders.stops == 1
    assert "أُوقفت العروض" in body


def test_a_stop_that_failed_says_so(client):
    client.app.state.container.reminders = _Reminders(stopped_ok=False)

    body = client.get(f"/p/{_ref()}/stop").text

    assert "أُوقفت العروض" not in body
    assert "تعذّر" in body
