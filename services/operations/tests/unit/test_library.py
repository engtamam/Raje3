"""Putting a shop's library where Meta can approve it — the step that was a manual script.

THE DEFECT. A shop finished Embedded Signup, was recorded `connected`, and owned no templates
anywhere. Somebody had to run a script by hand for each new establishment; until they did, the send
path had no approved template to choose and refused every message with a sentence about a review
that had never been asked for. Connected, green, and mute — and nothing logged as wrong.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.core.library import HttpLibrary, NullLibrary, build_library, publish


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
    return HttpLibrary(notify_url="http://notify",
                       register_path="/internal/whatsapp/templates",
                       drain_path="/internal/whatsapp/templates/submit-pending", token="t")


TEMPLATE = {"name": "svc_visit_confirm", "language": "ar", "category": "UTILITY",
            "body": "أهلاً {{1}}", "variables": ["name"], "examples": ["محمد"]}


# ── registering ───────────────────────────────────────────────────────────────────────────────
def test_a_template_is_registered_with_the_tenant_and_its_examples():
    """META REQUIRES AN EXAMPLE FOR EVERY PLACEHOLDER. A template submitted without them is
    rejected by the review rather than by us, which costs a day and looks like our fault."""
    seen = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data)
        return _Resp({"name": "svc_visit_confirm"})

    with patch("urllib.request.urlopen", _urlopen):
        assert run(client().register("t1", TEMPLATE)) is True
    assert seen["body"]["tenant"] == "t1"
    assert seen["body"]["examples"] == ["محمد"]
    assert seen["body"]["variables"] == ["name"]
    assert seen["url"].endswith("/internal/whatsapp/templates")


def test_a_refused_registration_is_reported_rather_than_raised():
    boom = urllib.error.HTTPError("u", 422, "bad", None, None)

    def _urlopen(req, timeout=0):
        raise boom

    with patch("urllib.request.urlopen", _urlopen):
        assert run(client().register("t1", TEMPLATE)) is False


# ── draining to Meta ──────────────────────────────────────────────────────────────────────────
def test_the_drain_names_the_tenant_and_reports_what_moved():
    seen = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        return _Resp({"submitted": 12, "failed": 0, "remaining": 54})

    with patch("urllib.request.urlopen", _urlopen):
        out = run(client().drain("t1"))
    assert "tenant=t1" in seen["url"]
    assert out == {"ok": True, "submitted": 12, "failed": 0, "remaining": 54}


def test_an_unreachable_peer_is_a_failure_that_says_so():
    """NOT A SILENT ZERO. «0 submitted» from a peer that never answered reads exactly like a shop
    with nothing left to submit — the shape of the bug this whole module exists to end."""
    down = urllib.error.URLError("connection refused")

    def _urlopen(req, timeout=0):
        raise down

    with patch("urllib.request.urlopen", _urlopen):
        out = run(client().drain("t1"))
    assert out["ok"] is False and out["reason"]


# ── the whole library, for one shop ───────────────────────────────────────────────────────────
def test_publishing_registers_every_template_then_asks_for_a_drain():
    null = NullLibrary()
    out = run(publish(null, [TEMPLATE, {**TEMPLATE, "name": "svc_reminder"}], "t1"))
    assert out["registered"] == 2 and out["failed"] == 0
    assert [n for _, n in null.registered] == ["svc_visit_confirm", "svc_reminder"]


def test_one_bad_template_does_not_cost_the_shop_the_others():
    """«65 of 66» is a number somebody can act on; a raised exception is a pass that did nothing
    and left the shop exactly as mute as before."""
    class _Half(NullLibrary):
        async def register(self, tenant, template):
            return template.get("name") != "broken"

    out = run(publish(_Half(), [TEMPLATE, {"name": "broken"}, {**TEMPLATE, "name": "ok2"}], "t1"))
    assert out["registered"] == 2 and out["failed"] == 1


def test_nothing_registered_means_nothing_is_asked_of_meta():
    """A drain after zero registrations spends a call on an empty queue and, worse, reports a
    successful pass for a shop whose library never arrived."""
    class _None(NullLibrary):
        async def register(self, tenant, template):
            return False

    out = run(publish(_None(), [TEMPLATE], "t1"))
    assert out["registered"] == 0
    assert out["drain"]["ok"] is False


# ── how it is built ───────────────────────────────────────────────────────────────────────────
def test_without_the_peer_wired_it_publishes_nothing_and_says_so():
    class S:
        NOTIFICATION_SERVICE_URL = ""
        NOTIFICATION_TEMPLATE_REGISTER_PATH = "/internal/whatsapp/templates"
        NOTIFICATION_TEMPLATE_DRAIN_PATH = "/internal/whatsapp/templates/submit-pending"

    lib = build_library(S())
    assert lib.driver == "null"
    assert run(lib.drain("t1"))["ok"] is False


def test_a_wired_peer_gives_the_http_client():
    class S:
        NOTIFICATION_SERVICE_URL = "http://notification-service:8000"
        NOTIFICATION_TEMPLATE_REGISTER_PATH = "/internal/whatsapp/templates"
        NOTIFICATION_TEMPLATE_DRAIN_PATH = "/internal/whatsapp/templates/submit-pending"
        INTERNAL_SERVICE_TOKEN = "t"
        PEER_TIMEOUT_SECONDS = 8

    assert build_library(S()).driver == "http"
