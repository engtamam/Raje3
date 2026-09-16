"""Giving a shop its own copy of a clone-per-shop Flow — mirrors test_library.py's own structure.

WHAT WAS BROKEN. A template with a Flow button referencing a Flow this shop's WABA never got a
copy of is refused by Meta at submission. Something has to provision that copy — cloned from the
one master, named the same on every shop — right where the template library itself is registered.

`flow_name`/`categories` HAVE NO DEFAULT (2026-09-16, [[task-service-procedure-checklists]]) — the
rating Flow these used to default to is gone (the rating screen moved off native Flow entirely),
so every call in this file names its own generic test values (`"test_flow"`/`["OTHER"]`) rather
than relying on a removed constant.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.core.flows import HttpFlows, NullFlows, build_flows, provision_shop_flow, \
    provision_shop_flow_encryption

FLOW_NAME = "test_flow"
FLOW_CATEGORIES = ["OTHER"]


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
    return HttpFlows(notify_url="http://notify",
                     provision_path="/internal/whatsapp/flows/provision", token="t",
                     encryption_ensure_path="/internal/whatsapp/flow-encryption/ensure")


# ── NullFlows: honest about being unconfigured ──────────────────────────────────────────────────
def test_null_flows_says_it_is_not_configured_rather_than_pretend_success():
    null = NullFlows()
    out = run(null.provision("t1", clone_flow_id="mf1", flow_name=FLOW_NAME,
                             categories=FLOW_CATEGORIES))
    assert out == {"ok": False, "reason": "flow provisioning is not configured"}
    assert null.provisioned == ["t1"]


# ── HttpFlows: the shape of the call ────────────────────────────────────────────────────────────
def test_a_shop_clone_is_requested_with_the_caller_named_flow_and_the_master_id():
    seen = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data)
        return _Resp({"ok": True, "flow_id": "clone-1", "name": FLOW_NAME,
                     "status": "PUBLISHED", "created": True, "published": True})

    with patch("urllib.request.urlopen", _urlopen):
        out = run(client().provision("t1", clone_flow_id="master-1", flow_name=FLOW_NAME,
                                     categories=FLOW_CATEGORIES))
    assert seen["url"].endswith("/internal/whatsapp/flows/provision")
    assert seen["body"] == {
        "tenant": "t1", "name": FLOW_NAME, "categories": FLOW_CATEGORIES,
        "clone_flow_id": "master-1", "publish": True,
    }
    assert out["ok"] is True and out["flow_id"] == "clone-1"


def test_no_master_id_is_refused_before_any_call_is_made():
    """An empty clone_flow_id is not "author from scratch" — it means the bootstrap script has
    not run yet, and asking Meta to clone nothing would either be refused there or, worse,
    misread by some future manager as a create-from-scratch request."""
    def _urlopen(req, timeout=0):
        raise AssertionError("must not call Meta with no master flow configured")

    with patch("urllib.request.urlopen", _urlopen):
        out = run(client().provision("t1", clone_flow_id="", flow_name=FLOW_NAME,
                                     categories=FLOW_CATEGORIES))
    assert out == {"ok": False, "reason": "no master test flow configured"}


def test_a_refused_provision_is_reported_rather_than_raised():
    boom = urllib.error.HTTPError("u", 422, "bad", None, None)

    def _urlopen(req, timeout=0):
        raise boom

    with patch("urllib.request.urlopen", _urlopen):
        out = run(client().provision("t1", clone_flow_id="master-1", flow_name=FLOW_NAME,
                                     categories=FLOW_CATEGORIES))
    assert out["ok"] is False and "reason" in out


def test_an_unreachable_peer_is_a_failure_that_says_so():
    down = urllib.error.URLError("connection refused")

    def _urlopen(req, timeout=0):
        raise down

    with patch("urllib.request.urlopen", _urlopen):
        out = run(client().provision("t1", clone_flow_id="master-1", flow_name=FLOW_NAME,
                                     categories=FLOW_CATEGORIES))
    assert out["ok"] is False and out["reason"]


# ── HttpFlows.ensure_encryption — the Flow's other connect-time step (base-services v0.18.55) ──
def test_ensure_encryption_posts_to_its_own_path_not_provision():
    seen = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data)
        return _Resp({"ok": True, "created": True, "uploaded": True,
                     "phone_number_id": "pn1", "status": "VALID"})

    with patch("urllib.request.urlopen", _urlopen):
        out = run(client().ensure_encryption("t1"))
    assert seen["url"].endswith("/internal/whatsapp/flow-encryption/ensure")
    assert seen["body"] == {"tenant": "t1"}
    assert out["ok"] is True
    assert out["status"] == "VALID"


def test_ensure_encryption_sends_an_explicit_phone_number_id_when_given():
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data)
        return _Resp({"ok": True, "created": False, "uploaded": True})

    with patch("urllib.request.urlopen", _urlopen):
        run(client().ensure_encryption("t1", phone_number_id="pn_explicit"))
    assert seen["body"] == {"tenant": "t1", "phone_number_id": "pn_explicit"}


def test_ensure_encryption_with_no_path_configured_refuses_without_a_call():
    """A client built before this feature existed (encryption_ensure_path="") must not crash —
    same 'no master configured' discipline `provision` already holds for a missing clone id."""
    def _urlopen(req, timeout=0):
        raise AssertionError("must not call anything with no path configured")

    bare = HttpFlows(notify_url="http://notify",
                     provision_path="/internal/whatsapp/flows/provision", token="t")
    with patch("urllib.request.urlopen", _urlopen):
        out = run(bare.ensure_encryption("t1"))
    assert out["ok"] is False


def test_null_flows_ensure_encryption_is_honest_too():
    null = NullFlows()
    out = run(null.ensure_encryption("t1"))
    assert out == {"ok": False, "reason": "flow encryption provisioning is not configured"}
    assert null.provisioned == ["t1"]


def test_provision_shop_flow_encryption_forwards_to_the_driver():
    null = NullFlows()
    out = run(provision_shop_flow_encryption(null, "t1"))
    assert out["ok"] is False
    assert null.provisioned == ["t1"]


def test_build_flows_wires_the_encryption_path_too():
    class S:
        NOTIFICATION_SERVICE_URL = "http://notification-service:8000"
        WHATSAPP_FLOW_PROVISION_PATH = "/internal/whatsapp/flows/provision"
        WHATSAPP_FLOW_ENCRYPTION_ENSURE_PATH = "/internal/whatsapp/flow-encryption/ensure"
        INTERNAL_SERVICE_TOKEN = "t"
        PEER_TIMEOUT_SECONDS = 8

    flows = build_flows(S())
    assert flows.driver == "http"
    assert flows._encryption_ensure.endswith("/internal/whatsapp/flow-encryption/ensure")


# ── the factory ──────────────────────────────────────────────────────────────────────────────────
def test_no_peer_configured_gives_the_null_driver():
    class S:
        NOTIFICATION_SERVICE_URL = ""
        WHATSAPP_FLOW_PROVISION_PATH = "/internal/whatsapp/flows/provision"
        INTERNAL_SERVICE_TOKEN = ""
        PEER_TIMEOUT_SECONDS = 8

    flows = build_flows(S())
    assert flows.driver == "null"
    assert run(flows.provision("t1", clone_flow_id="mf", flow_name=FLOW_NAME,
                               categories=FLOW_CATEGORIES))["ok"] is False


def test_a_wired_peer_gives_the_http_client():
    class S:
        NOTIFICATION_SERVICE_URL = "http://notification-service:8000"
        WHATSAPP_FLOW_PROVISION_PATH = "/internal/whatsapp/flows/provision"
        INTERNAL_SERVICE_TOKEN = "t"
        PEER_TIMEOUT_SECONDS = 8

    assert build_flows(S()).driver == "http"


# ── the free function connect.py's background task calls ───────────────────────────────────────
def test_provision_shop_flow_forwards_to_the_driver():
    null = NullFlows()
    out = run(provision_shop_flow(null, "t1", "master-1", flow_name=FLOW_NAME,
                                  categories=FLOW_CATEGORIES))
    assert out["ok"] is False
    assert null.provisioned == ["t1"]
