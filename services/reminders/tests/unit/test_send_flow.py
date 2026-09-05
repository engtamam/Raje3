"""HttpSender.send_flow — the rating app's own message, same recipient resolution and failure
handling as `send()`, posted to notification-service's interactive route with `type: "flow"`.

Foundation-phase wiring: nothing schedules a call to this yet (a later phase does). These tests
pin the shape of the call itself, so scheduling it later is a call site, not a new path to build.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from app.adapters.message_sender import (CeilingReached, HttpSender, NullSender, SendFailed,
                                         Unsendable)


def run(c):
    return asyncio.run(c)


def sender(**over):
    kwargs = dict(notify_url="http://notify", notify_path="/internal/notify",
                  operations_url="http://ops", recipient_path="/internal/recipient", token="t",
                  interactive_notify_path="/internal/notify/whatsapp/interactive")
    kwargs.update(over)
    return HttpSender(**kwargs)


class _Resp:
    status = 200

    def __init__(self, payload, status=200):
        self._p = json.dumps(payload).encode()
        self.status = status

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _flow_call(*, recipient="+966500000000", response=None, **kwargs):
    s = sender()
    seen: dict = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp(response or {"status": "sent", "delivery_id": "dlv_1"})

    with patch.object(s, "_recipient", return_value=(recipient, "نورة")), \
         patch("urllib.request.urlopen", _urlopen):
        result = run(s.send_flow(
            tenant="t1", subject_ref="sub_a", body=kwargs.pop("body", "كيف كانت زيارتك؟"),
            flow_token=kwargs.pop("flow_token", "rate:vis_1"),
            flow_id=kwargs.pop("flow_id", "123456789"),
            flow_cta=kwargs.pop("flow_cta", "قيّمنا"),
            flow_screen=kwargs.pop("flow_screen", "RATING"),
            idempotency_key=kwargs.pop("idempotency_key", "k1"), **kwargs))
    return result, seen


# ── the request shape ─────────────────────────────────────────────────────────────────────────
def test_posts_type_flow_with_every_field_to_the_interactive_path():
    _, seen = _flow_call(flow_data={"customer_name": "نورة"})
    assert seen["url"] == "http://notify/internal/notify/whatsapp/interactive"
    body = seen["body"]
    assert body["type"] == "flow"
    assert body["recipient"] == "+966500000000"
    assert body["tenant"] == "t1"
    assert body["flow_token"] == "rate:vis_1"
    assert body["flow_id"] == "123456789"
    assert body["flow_cta"] == "قيّمنا"
    assert body["flow_screen"] == "RATING"
    assert body["flow_data"] == {"customer_name": "نورة"}


def test_idempotency_key_rides_both_the_key_and_the_callback_data():
    _, seen = _flow_call(idempotency_key="rate-vis-1")
    assert seen["body"]["idempotency_key"] == "rate-vis-1"
    assert seen["body"]["biz_opaque_callback_data"] == "rate-vis-1"


def test_flow_data_defaults_to_an_empty_dict_when_omitted():
    _, seen = _flow_call()
    assert seen["body"]["flow_data"] == {}


def test_sending_identity_defaults_to_the_tenant():
    _, seen = _flow_call()
    assert seen["body"]["sending_identity"] == "t1"


def test_an_explicit_sending_identity_is_carried_through():
    _, seen = _flow_call(sending_identity="t1:branch_2")
    assert seen["body"]["sending_identity"] == "t1:branch_2"


def test_returns_the_delivery_id():
    result, _ = _flow_call()
    assert result == "dlv_1"


# ── recipient resolution — same rule as send() ────────────────────────────────────────────────
def test_an_erased_or_unknown_customer_raises_unsendable_not_sendfailed():
    s = sender()
    with patch.object(s, "_recipient", return_value=("", "")):
        with pytest.raises(Unsendable):
            run(s.send_flow(tenant="t1", subject_ref="gone", body="x", flow_token="tok",
                            flow_id="f1", flow_cta="Go", flow_screen="S1"))


def test_never_calls_the_peer_when_there_is_no_recipient():
    s = sender()
    with patch.object(s, "_recipient", return_value=("", "")), \
         patch("urllib.request.urlopen") as m:
        with pytest.raises(Unsendable):
            run(s.send_flow(tenant="t1", subject_ref="gone", body="x", flow_token="tok",
                            flow_id="f1", flow_cta="Go", flow_screen="S1"))
        m.assert_not_called()


# ── failure handling — same rule as send() ────────────────────────────────────────────────────
def test_a_non_2xx_http_status_is_sendfailed():
    s = sender()
    with patch.object(s, "_recipient", return_value=("+966500000000", "")), \
         patch("urllib.request.urlopen", return_value=_Resp({}, status=500)):
        with pytest.raises(SendFailed):
            run(s.send_flow(tenant="t1", subject_ref="sub_a", body="x", flow_token="tok",
                            flow_id="f1", flow_cta="Go", flow_screen="S1"))


def test_a_delivery_status_of_failed_is_sendfailed():
    with pytest.raises(SendFailed):
        _flow_call(response={"status": "failed", "error": "template not approved"})


def test_a_ceiling_code_is_ceilingreached_not_a_plain_sendfailed():
    with pytest.raises(CeilingReached):
        _flow_call(response={"status": "failed", "error_code": "130429"})


def test_queued_is_treated_as_delivered_like_send_does():
    result, _ = _flow_call(response={"status": "queued", "delivery_id": "dlv_q"})
    assert result == "dlv_q"


# ── not configured — fails closed, never guesses a URL ────────────────────────────────────────
def test_no_interactive_path_configured_refuses_rather_than_posting_to_notify_alone():
    s = sender(interactive_notify_path="")
    with patch("urllib.request.urlopen") as m:
        with pytest.raises(SendFailed):
            run(s.send_flow(tenant="t1", subject_ref="sub_a", body="x", flow_token="tok",
                            flow_id="f1", flow_cta="Go", flow_screen="S1"))
        m.assert_not_called()


# ── the null sender — records rather than sends ───────────────────────────────────────────────
def test_null_sender_records_the_flow_call_and_returns_a_stable_handle():
    s = NullSender()
    result = run(s.send_flow(tenant="t1", subject_ref="sub_a", body="كيف كانت زيارتك؟",
                             flow_token="rate:vis_1", flow_id="f1", flow_cta="قيّمنا",
                             flow_screen="RATING", idempotency_key="k1"))
    assert result == "dlv_k1"
    assert s.sent[0]["type"] == "flow"
    assert s.sent[0]["flow_token"] == "rate:vis_1"


def test_null_sender_returns_empty_handle_with_no_idempotency_key():
    s = NullSender()
    result = run(s.send_flow(tenant="t1", subject_ref="sub_a", body="x", flow_token="tok",
                             flow_id="f1", flow_cta="Go", flow_screen="S1"))
    assert result == ""
