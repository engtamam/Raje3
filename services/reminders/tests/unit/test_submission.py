"""Handing his text to Meta — the button the draft never had.

«قوالبي» WAS A NOTEPAD. Writing a text was reachable; submitting it was not, because registering
and submitting were user-tier routes needing a JWT whose signing key must stay in identity-service.
So every text an owner ever wrote sat as a draft, for ever, and no screen said why.
"""
from __future__ import annotations

import asyncio
import io
import json
import urllib.error
from unittest.mock import patch

from app.core.submission import HttpSubmitter, NullSubmitter, build_submitter


def run(c):
    return asyncio.run(c)


class _Resp:
    def __init__(self, payload, status=200):
        self._p = json.dumps(payload).encode()
        self.status = status

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def client():
    return HttpSubmitter(
        notify_url="http://notify", register_path="/internal/whatsapp/templates",
        submit_path="/internal/whatsapp/templates/{name}/{language}/submit", token="t")


DRAFT = {"name": "salon_visit_confirmation_1", "language": "ar", "cls": "service",
         "body": "أهلاً {{1}}، موعدك {{2}}", "variables": [1, 2], "examples": ["محمد", "الأحد"]}


def test_it_registers_the_body_before_asking_meta_to_read_it():
    """SUBMITTING A NAME THAT WAS NEVER REGISTERED is a 404 from the peer — and the owner would
    read that as Meta rejecting his text."""
    calls = []

    def _urlopen(req, timeout=0):
        calls.append(req.full_url)
        return _Resp({"status": "pending"})

    with patch("urllib.request.urlopen", _urlopen):
        out = run(client().submit("t1", DRAFT))
    assert out["ok"] is True
    assert calls[0].endswith("/internal/whatsapp/templates")
    assert "salon_visit_confirmation_1/ar/submit" in calls[1]


def test_a_marketing_text_is_submitted_as_marketing():
    """THE CLASS IS ALREADY THE AUTHORITY on consent, the quiet window and the monthly cap, so
    this is a translation into Meta's vocabulary and never a second decision."""
    seen = {}

    def _urlopen(req, timeout=0):
        if req.data:
            body = json.loads(req.data)
            if "category" in body:
                seen["category"] = body["category"]
        return _Resp({"status": "pending"})

    with patch("urllib.request.urlopen", _urlopen):
        run(client().submit("t1", {**DRAFT, "cls": "marketing"}))
    assert seen["category"] == "MARKETING"

    with patch("urllib.request.urlopen", _urlopen):
        run(client().submit("t1", DRAFT))
    assert seen["category"] == "UTILITY"


def test_meta_s_own_words_come_back_untouched():
    """RE-WORDING A REJECTION sends him looking for a problem we invented. «ساعدوني» turns this
    exact sentence into a request a human answers."""
    said = "Template contains a URL shortener, which is not allowed"

    def _urlopen(req, timeout=0):
        if "submit" in req.full_url:
            raise urllib.error.HTTPError(
                "u", 400, "bad", None, io.BytesIO(json.dumps({"detail": said}).encode()))
        return _Resp({"name": "x"})

    with patch("urllib.request.urlopen", _urlopen):
        out = run(client().submit("t1", DRAFT))
    assert out["ok"] is False
    assert said in out["reason"]


def test_a_failed_registration_never_reaches_meta():
    calls = []

    def _urlopen(req, timeout=0):
        calls.append(req.full_url)
        raise urllib.error.HTTPError("u", 422, "bad", None, io.BytesIO(b"{}"))

    with patch("urllib.request.urlopen", _urlopen):
        out = run(client().submit("t1", DRAFT))
    assert out["ok"] is False
    assert len(calls) == 1, "a body that would not register must not be submitted"


def test_an_unconfigured_peer_refuses_rather_than_claiming_success():
    """A DRAFT REPORTED AS SUBMITTED is the worst answer available: he stops waiting for a verdict
    that will never come, and his text reaches nobody while the screen says «قيد المراجعة»."""
    out = run(NullSubmitter().submit("t1", DRAFT))
    assert out["ok"] is False and out["reason"]


# ── the establishment example must be his shop, not Meta's placeholder (ح-8) ───────────────────


def test_examples_use_the_real_shop_name_when_given():
    from app.core.submission import _examples

    tpl = {"name": "svc_visit_confirmation_brief", "variables": [1, 2],
           "fills": ["customer", "shop"]}
    got = _examples({**tpl, "establishment": "مغسلة النخيل"})
    assert "مغسلة النخيل" in got


def test_examples_fall_back_to_the_generic_form_only_when_none_is_given():
    """`"محلّك"` is the exact placeholder shape our own comments say a review rejects — it must be
    the LAST resort, reached only when nobody supplied the real name."""
    from app.core.submission import _examples

    tpl = {"name": "svc_visit_confirmation_brief", "variables": [1, 2],
           "fills": ["customer", "shop"]}
    got = _examples(tpl)
    assert "محلّك" in got


def test_the_owner_route_passes_his_shops_own_name_to_submission():
    """ح-8. `submit_custom_template` used to call `c.submitter.submit(tenant, row)` where `row` is
    `CustomTemplate.to_dict()` — no `establishment` key — so `_examples` fell back to «محلّك» for
    EVERY submission, not only the rare one with no identity to ask. A guard on the source, in the
    style already used for `send_log`'s branch scope: full request/container wiring for one route
    is heavier than the property this test actually needs."""
    import inspect

    from app.api.v1 import owner as O

    src = inspect.getsource(O.submit_custom_template)
    # ASSERTED ON WHAT IS ASKED AND WHAT IS HANDED OVER, not on how the tenant is spelled. The
    # first version pinned `c.identity.get(principal.tenant)` letter for letter, and broke the day
    # that read went through the module's `_tenant()` guard — an edit that STRENGTHENED the very
    # property this test is about, since a submission can no longer be filed under no shop at all.
    # A test that fails when the code improves is a test that argues against improving it.
    assert "c.identity.get(" in src, "the shop's own name must be read"
    assert "tenant(principal)" in src, "and read for THIS request's shop, established at the door"
    assert '"establishment": shop.name' in src, "and handed to the submitter, not left to default"


def test_it_is_null_until_both_paths_are_wired():
    class S:
        NOTIFICATION_SERVICE_URL = "http://notify"
        NOTIFICATION_TEMPLATE_REGISTER_PATH = "/internal/whatsapp/templates"
        NOTIFICATION_TEMPLATE_SUBMIT_PATH = ""

    assert build_submitter(S()).driver == "null"
    S.NOTIFICATION_TEMPLATE_SUBMIT_PATH = "/internal/whatsapp/templates/{name}/{language}/submit"
    S.INTERNAL_SERVICE_TOKEN = "t"
    S.PEER_TIMEOUT_SECONDS = 8
    assert build_submitter(S()).driver == "http"
