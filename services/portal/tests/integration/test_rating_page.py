"""GET/POST /r/{ref} — the hosted rating page, [[task-service-procedure-checklists]] phase 2.
Same fake-peer-swap pattern `test_the_full_page_is_gone_and_consent_is_not.py` already uses.
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


class _Identity:
    async def get(self, tenant):
        class _Shop:
            name = "مغسلة النخيل"
            branding = {"accent": "#0F5F4E", "logo_url": "https://cdn.example/logo.png"}
        return _Shop()


class _Reminders:
    def __init__(self, *, found=True, tenant="t1", visit_id="vis_1", recorded=True):
        self.found = found
        self.tenant = tenant
        self.visit_id = visit_id
        self.recorded = recorded
        self.submits: list[dict] = []

    async def rating_anchor(self, ref):
        if not self.found:
            return {"found": False}
        return {"found": True, "tenant": self.tenant, "visit_id": self.visit_id}

    async def rating_submit(self, ref, *, rating, feedback_text, rating_issue_step_ids):
        self.submits.append({"ref": ref, "rating": rating, "feedback_text": feedback_text,
                            "rating_issue_step_ids": rating_issue_step_ids})
        return {"recorded": self.recorded, "visit_id": self.visit_id if self.recorded else ""}


class _Operations:
    def __init__(self, *, found=True, already_rated=False, service_names=None, steps=None):
        self.found = found
        self.already_rated = already_rated
        self.service_names = service_names or ["غسيل خارجي"]
        self.steps = steps or [{"id": "step_a", "text": "اغسل بالماء", "severity": "normal"}]

    async def rating_context(self, tenant, visit_id):
        if not self.found:
            return {"found": False}
        return {"found": True, "already_rated": self.already_rated,
                "service_names": self.service_names, "steps": self.steps}


def _wire(client, *, reminders=None, operations=None):
    client.app.state.container.identity = _Identity()
    client.app.state.container.reminders = reminders or _Reminders()
    client.app.state.container.operations = operations or _Operations()


def test_an_unknown_ref_shows_a_plain_refused_screen_not_a_500(client):
    _wire(client, reminders=_Reminders(found=False))
    r = client.get("/r/rate:never_existed")
    assert r.status_code == 200
    assert "تعذّر فتح الرابط" in r.text


def test_a_valid_ref_renders_the_form_with_the_shops_own_steps(client):
    _wire(client)
    r = client.get("/r/rate:vis_1")
    assert r.status_code == 200
    assert "مغسلة النخيل" in r.text
    assert "اغسل بالماء" in r.text
    assert "logo.png" in r.text


def test_an_already_rated_visit_shows_a_thank_you_not_a_form(client):
    _wire(client, operations=_Operations(already_rated=True))
    r = client.get("/r/rate:vis_1")
    assert r.status_code == 200
    assert "شكراً لك" in r.text
    assert "<form" not in r.text


def test_a_valid_submission_is_recorded_and_thanked(client):
    reminders = _Reminders()
    _wire(client, reminders=reminders)
    r = client.post("/r/rate:vis_1", data={"stars": "4", "comment": "جيد", "issue": "step_a"})
    assert r.status_code == 200
    assert "وصل تقييمك" in r.text
    assert reminders.submits == [{"ref": "rate:vis_1", "rating": 4, "feedback_text": "جيد",
                                  "rating_issue_step_ids": ["step_a"]}]


def test_five_stars_with_a_flagged_issue_is_refused_and_re_asks(client):
    """The owner's own rule (2026-09-16): 5 نجوم يعني كل شي تمام."""
    reminders = _Reminders()
    _wire(client, reminders=reminders)
    r = client.post("/r/rate:vis_1", data={"stars": "5", "comment": "", "issue": "step_a"})
    assert r.status_code == 200
    assert "خمس نجوم" in r.text
    assert "<form" in r.text
    assert reminders.submits == []


def test_five_stars_with_no_issues_is_accepted(client):
    reminders = _Reminders()
    _wire(client, reminders=reminders)
    r = client.post("/r/rate:vis_1", data={"stars": "5", "comment": ""})
    assert r.status_code == 200
    assert "وصل تقييمك" in r.text
    assert reminders.submits[0]["rating"] == 5


def test_no_stars_selected_is_refused(client):
    reminders = _Reminders()
    _wire(client, reminders=reminders)
    r = client.post("/r/rate:vis_1", data={"comment": "بدون تقييم"})
    assert r.status_code == 200
    assert "اختر تقييماً" in r.text
    assert reminders.submits == []


def test_a_refused_write_shows_a_try_again_screen(client):
    _wire(client, reminders=_Reminders(recorded=False))
    r = client.post("/r/rate:vis_1", data={"stars": "3", "comment": ""})
    assert r.status_code == 200
    assert "تعذّر إرسال تقييمك" in r.text


def test_the_selections_are_preserved_on_a_refused_submit(client):
    reminders = _Reminders()
    _wire(client, reminders=reminders)
    r = client.post("/r/rate:vis_1", data={"stars": "5", "comment": "ملاحظتي", "issue": "step_a"})
    assert "checked" in r.text
    assert "ملاحظتي" in r.text
