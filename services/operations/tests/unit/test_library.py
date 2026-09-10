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


def client(**overrides):
    kwargs = dict(notify_url="http://notify",
                 register_path="/internal/whatsapp/templates",
                 drain_path="/internal/whatsapp/templates/submit-pending", token="t")
    kwargs.update(overrides)
    return HttpLibrary(**kwargs)


TEMPLATE = {"name": "svc_visit_confirm", "language": "ar", "category": "UTILITY",
            "body": "أهلاً {{1}}", "variables": ["name"], "examples": ["محمد"]}

_CAROUSEL_TEMPLATE = {
    "name": "wa_catalog_carousel", "language": "ar", "category": "MARKETING",
    "body": "شوف بعض خدماتنا:", "variables": [], "examples": [],
    "carousel": {"cards": [
        {"header_format": "IMAGE", "header_example_handle": "", "body": "{{1}} — {{2}}",
         "body_examples": ["قص شعر", "50 ريال"],
         "buttons": [{"type": "QUICK_REPLY", "text": "احجز الآن"}]},
        {"header_format": "IMAGE", "header_example_handle": "", "body": "{{1}} — {{2}}",
         "body_examples": ["قص شعر", "50 ريال"],
         "buttons": [{"type": "QUICK_REPLY", "text": "احجز الآن"}]},
    ]},
}


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


def test_a_flow_button_on_the_template_is_forwarded_to_the_registry():
    """The rating template's flow_button (flows.py provisions the per-shop Flow it names) must
    reach notification-service's register() call, or the approved template ships with no button."""
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data)
        return _Resp({"name": "svc_visit_confirmation_rating_warm"})

    with_flow = dict(TEMPLATE, flow_button={"flow_name": "rating_flow"})
    with patch("urllib.request.urlopen", _urlopen):
        assert run(client().register("t1", with_flow)) is True
    assert seen["body"]["flow_button"] == {"flow_name": "rating_flow"}


def test_a_template_with_no_flow_button_sends_none():
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data)
        return _Resp({"name": "svc_visit_confirm"})

    with patch("urllib.request.urlopen", _urlopen):
        assert run(client().register("t1", TEMPLATE)) is True
    assert "flow_button" not in seen["body"]


# ── carousel templates: a fresh placeholder handle per registration ─────────────────────────────
def test_a_carousel_template_uploads_a_placeholder_handle_then_registers_with_it():
    calls = []

    def _urlopen(req, timeout=0):
        calls.append(req.full_url)
        if req.full_url.endswith("/whatsapp/media/upload-handle"):
            return _Resp({"ok": True, "handle": "hnd_fresh_1"})
        return _Resp({"name": "wa_catalog_carousel"})

    c = client(media_upload_handle_path="/internal/whatsapp/media/upload-handle")
    with patch("urllib.request.urlopen", _urlopen):
        ok = run(c.register("t1", _CAROUSEL_TEMPLATE))

    assert ok is True
    assert calls[0].endswith("upload-handle")
    assert calls[1].endswith("/internal/whatsapp/templates")


def test_every_card_gets_the_same_freshly_uploaded_handle():
    seen = {}

    def _urlopen(req, timeout=0):
        if req.full_url.endswith("upload-handle"):
            return _Resp({"ok": True, "handle": "hnd_fresh_2"})
        seen["body"] = json.loads(req.data)
        return _Resp({"name": "wa_catalog_carousel"})

    c = client(media_upload_handle_path="/internal/whatsapp/media/upload-handle")
    with patch("urllib.request.urlopen", _urlopen):
        run(c.register("t1", _CAROUSEL_TEMPLATE))

    cards = seen["body"]["carousel"]["cards"]
    assert len(cards) == 2
    assert all(c["header_example_handle"] == "hnd_fresh_2" for c in cards)


def test_a_carousel_template_never_registers_a_static_handle_across_two_calls():
    """A handle is a live, one-time Meta artifact — never cached across registrations, even for
    the exact same template, so a shop connecting long after this row was written never inherits
    a handle minted for someone else's registration."""
    handles = iter(["hnd_a", "hnd_b"])
    seen = []

    def _urlopen(req, timeout=0):
        if req.full_url.endswith("upload-handle"):
            return _Resp({"ok": True, "handle": next(handles)})
        seen.append(json.loads(req.data)["carousel"]["cards"][0]["header_example_handle"])
        return _Resp({"name": "wa_catalog_carousel"})

    c = client(media_upload_handle_path="/internal/whatsapp/media/upload-handle")
    with patch("urllib.request.urlopen", _urlopen):
        run(c.register("t1", _CAROUSEL_TEMPLATE))
        run(c.register("t2", _CAROUSEL_TEMPLATE))

    assert seen == ["hnd_a", "hnd_b"]


def test_a_carousel_template_with_no_upload_path_configured_fails_that_one_registration():
    c = client()   # media_upload_handle_path left at its default (empty)
    assert run(c.register("t1", _CAROUSEL_TEMPLATE)) is False


def test_a_failed_placeholder_upload_fails_that_one_registration_not_a_crash():
    def _urlopen(req, timeout=0):
        return _Resp({"ok": False, "reason": "Meta rejected the upload"}, status=502)

    c = client(media_upload_handle_path="/internal/whatsapp/media/upload-handle")
    with patch("urllib.request.urlopen", _urlopen):
        assert run(c.register("t1", _CAROUSEL_TEMPLATE)) is False


def test_an_ordinary_template_never_touches_the_upload_handle_route():
    calls = []

    def _urlopen(req, timeout=0):
        calls.append(req.full_url)
        return _Resp({"name": "svc_visit_confirm"})

    c = client(media_upload_handle_path="/internal/whatsapp/media/upload-handle")
    with patch("urllib.request.urlopen", _urlopen):
        run(c.register("t1", TEMPLATE))

    assert len(calls) == 1
    assert calls[0].endswith("/internal/whatsapp/templates")


def test_a_card_that_already_carries_a_real_handle_is_left_alone():
    """Not every future carousel template needs a placeholder — one that already resolved (or
    hand-supplied) real handles skips the upload step entirely."""
    already_real = {**_CAROUSEL_TEMPLATE, "carousel": {"cards": [
        {**_CAROUSEL_TEMPLATE["carousel"]["cards"][0], "header_example_handle": "hnd_real"},
        {**_CAROUSEL_TEMPLATE["carousel"]["cards"][1], "header_example_handle": "hnd_real"},
    ]}}
    calls = []

    def _urlopen(req, timeout=0):
        calls.append(req.full_url)
        return _Resp({"name": "wa_catalog_carousel"})

    c = client(media_upload_handle_path="/internal/whatsapp/media/upload-handle")
    with patch("urllib.request.urlopen", _urlopen):
        assert run(c.register("t1", already_real)) is True

    assert len(calls) == 1   # no upload-handle call at all


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


def test_the_three_book_back_offers_carry_the_booking_flow_button_in_the_real_seed():
    """The curated library itself, not a synthetic dict — the three marketing templates whose whole
    point is getting a customer back through the door (mkt_offer, mkt_winback,
    mkt_personal_occasion) must each carry `flow_button: {"flow_name": "booking_flow"}` and a real
    button label, both tones, so a tap on the message opens the same booking Flow
    core/flows.py provisions per shop (BOOKING_FLOW_NAME) rather than leaving the customer to call.
    Every OTHER template type must NOT carry it — a booking screen on an announcement or a care tip
    is a promise the text never made."""
    import pathlib

    seed = pathlib.Path(__file__).resolve().parents[2] / "data" / "templates.seed.json"
    rows = __import__("json").loads(seed.read_text(encoding="utf-8"))["templates"]

    booking_types = {"mkt_offer", "mkt_winback", "mkt_personal_occasion"}
    seen_types = set()
    for row in rows:
        if row.get("type") in booking_types:
            seen_types.add(row["type"])
            assert row.get("flow_button") == {"flow_name": "booking_flow"}, row["name"]
            assert row.get("button"), f"{row['name']} has a flow_button but no visible button label"
        else:
            # OTHER templates may carry THEIR OWN flow (svc_visit_confirmation_rating's own
            # rating_flow) — only the booking flow specifically must never leak onto a template
            # whose text never promised an appointment screen.
            fb = row.get("flow_button") or {}
            assert fb.get("flow_name") != "booking_flow", \
                f"{row['name']} carries the booking flow it never promised"
    assert seen_types == booking_types   # all three types actually exist in the seed, none silently absent
