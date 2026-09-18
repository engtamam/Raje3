"""Has this shop bought the AI assistant — `feature.whatsapp` — and what happens when we cannot ask.

Mirrors services/campaigns/tests/unit/test_licence.py: same client shape, same failure modes. This
service has no `require`/`LicenceError` of its own — the refusal text lives in conversation.py,
right where the two call sites (handle_inbound_text, compose_reply) already need one each.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.core.licence import HttpLicence, KEY, NullLicence, ToggleGatedLicence, build_licence


def run(c):
    return asyncio.run(c)


class _Resp:
    def __init__(self, payload):
        self._p = json.dumps(payload).encode()

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def client():
    return HttpLicence(billing_url="http://billing",
                       check_path="/internal/billing/entitlements/check", token="t")


def _answer(payload=None, raise_with=None):
    def _urlopen(req, timeout=0):
        if raise_with is not None:
            raise raise_with
        _answer.seen = req.full_url
        return _Resp(payload or {})
    return _urlopen


# ── the shop that bought it ────────────────────────────────────────────────────────────────────
def test_a_shop_that_bought_the_assistant_is_allowed():
    with patch("urllib.request.urlopen", _answer({"allowed": True})):
        assert run(client().allowed("t1")) is True


def test_the_question_asked_is_the_key_on_the_price_list():
    with patch("urllib.request.urlopen", _answer({"allowed": True})):
        run(client().allowed("t1"))
    assert "key=feature.whatsapp" in _answer.seen and KEY == "feature.whatsapp"
    assert "tenant=t1" in _answer.seen


# ── the shop that did not ──────────────────────────────────────────────────────────────────────
def test_a_shop_without_the_app_is_refused():
    with patch("urllib.request.urlopen", _answer({"allowed": False})):
        assert run(client().allowed("t1")) is False


# ── the failure modes, which are the whole point ───────────────────────────────────────────────
def test_it_fails_CLOSED_when_billing_cannot_be_reached():
    """A shop that has not bought this must never receive an AI reply that looks like it — a
    refusal during an outage is a customer told to wait, which resolves itself."""
    down = urllib.error.URLError("connection refused")
    with patch("urllib.request.urlopen", _answer(raise_with=down)):
        assert run(client().allowed("t1")) is False


def test_a_billing_error_is_a_refusal_not_a_pass():
    boom = urllib.error.HTTPError("u", 500, "boom", None, None)
    with patch("urllib.request.urlopen", _answer(raise_with=boom)):
        assert run(client().allowed("t1")) is False


def test_a_malformed_answer_is_a_refusal():
    with patch("urllib.request.urlopen", _answer({})):
        assert run(client().allowed("t1")) is False


def test_an_empty_tenant_never_reaches_billing():
    called = {"n": 0}

    def _urlopen(req, timeout=0):
        called["n"] += 1
        return _Resp({"allowed": True})

    with patch("urllib.request.urlopen", _urlopen):
        assert run(client().allowed("")) is False
    assert called["n"] == 0


# ── how it is built ────────────────────────────────────────────────────────────────────────────
def test_without_billing_configured_it_allows_and_the_boot_guard_refuses_that_in_production():
    class S:
        BILLING_SERVICE_URL = ""
        BILLING_CHECK_PATH = "/internal/billing/entitlements/check"

    licence = build_licence(S())
    assert licence.driver == "null"
    assert run(licence.allowed("t1")) is True


def test_configured_billing_gives_the_http_client():
    class S:
        BILLING_SERVICE_URL = "http://billing-service:8000"
        BILLING_CHECK_PATH = "/internal/billing/entitlements/check"
        INTERNAL_SERVICE_TOKEN = "t"
        PEER_TIMEOUT_SECONDS = 8

    assert build_licence(S()).driver == "http"


def test_null_licence_always_allows():
    assert run(NullLicence().allowed("t1")) is True


# ── ToggleGatedLicence — the owner's own kill switch, ANDed with the real entitlement ──────────
class _ShopIdentity:
    def __init__(self, ai_enabled: bool) -> None:
        self.ai_enabled = ai_enabled
        self.asked: list[str] = []

    async def resolve(self, tenant: str):
        self.asked.append(tenant)
        class _Ctx:
            pass
        ctx = _Ctx()
        ctx.ai_enabled = self.ai_enabled
        return ctx


def test_bought_it_and_switch_is_on_is_allowed():
    gated = ToggleGatedLicence(NullLicence(), shop_identity=_ShopIdentity(True))
    assert run(gated.allowed("t1")) is True


def test_bought_it_but_switched_off_reads_exactly_like_not_bought_at_all():
    """The one behaviour this whole class exists for — off is not a softer state, it is the SAME
    False every unsubscribed shop's `.allowed()` already returns."""
    gated = ToggleGatedLicence(NullLicence(), shop_identity=_ShopIdentity(False))
    assert run(gated.allowed("t1")) is False


class _NeverAllowed:
    async def allowed(self, tenant: str) -> bool:
        return False


def test_a_shop_that_never_bought_it_never_reaches_the_toggle_check_at_all():
    """The billing check short-circuits — a shop with no entitlement has nothing to ask
    operations about, so the extra peer call is skipped on the (much more common) unsubscribed
    case."""
    identity = _ShopIdentity(True)
    gated = ToggleGatedLicence(_NeverAllowed(), shop_identity=identity)
    assert run(gated.allowed("t1")) is False
    assert identity.asked == []


def test_no_shop_identity_wired_at_all_falls_back_to_the_real_licences_own_answer():
    gated = ToggleGatedLicence(NullLicence(), shop_identity=None)
    assert run(gated.allowed("t1")) is True


# ── the platform-wide switch (2026-09-19) — every shop, ANDed in first, over both of the above ──
def test_platform_switch_off_refuses_even_a_bought_and_shop_enabled_assistant():
    """The one behaviour THIS flag exists for — off beats a real entitlement AND an owner who left
    his own toggle on, same "reads exactly like unsubscribed" discipline as the per-shop toggle."""
    gated = ToggleGatedLicence(NullLicence(), shop_identity=_ShopIdentity(True),
                               ai_assistant_enabled=False)
    assert run(gated.allowed("t1")) is False


def test_platform_switch_off_never_even_asks_billing_or_the_shop_toggle():
    identity = _ShopIdentity(True)
    gated = ToggleGatedLicence(_NeverAllowed(), shop_identity=identity, ai_assistant_enabled=False)
    assert run(gated.allowed("t1")) is False
    assert identity.asked == []


def test_platform_switch_defaults_to_on_so_every_existing_caller_is_unaffected():
    gated = ToggleGatedLicence(NullLicence(), shop_identity=_ShopIdentity(True))
    assert run(gated.allowed("t1")) is True
