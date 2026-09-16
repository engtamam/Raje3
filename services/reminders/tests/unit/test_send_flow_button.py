"""HttpSender.send's own url_button_param — the rating app's URL-button-in-a-template send
([[task-service-procedure-checklists]] phase 2, base-services v0.24.4). Distinct from send_flow
(the in-session interactive Flow, 24h window) — this is the business-initiated path, an ordinary
template call with one extra optional field. REPLACES the old flow_token/flow_action_data pair
(same send() method, same rating caller, moved off native Flow entirely to a hosted web page).
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from app.adapters.message_sender import HttpSender, NullSender


def run(c):
    return asyncio.run(c)


def sender():
    return HttpSender(notify_url="http://notify", notify_path="/internal/notify",
                      operations_url="http://ops", recipient_path="/internal/recipient", token="t")


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


def _call(**over):
    s = sender()
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"status": "sent", "delivery_id": "dlv_1"})

    kwargs = dict(tenant="t1", subject_ref="sub_a", template_name="svc_visit_confirmation_rating_warm",
                 variables=["أحمد", "مغسلة النخيل", "شاركنا رأيك بزيارتك واكسب 5 نقطة", "invite"],
                 cls="service", idempotency_key="k1")
    kwargs.update(over)
    with patch.object(s, "_recipient", return_value=("+966500000000", "أحمد")), \
         patch("urllib.request.urlopen", _urlopen):
        run(s.send(**kwargs))
    return seen["body"]


def test_no_url_button_param_means_no_such_field_on_the_wire_at_all():
    body = _call()
    assert "url_button_param" not in body


def test_a_url_button_param_is_carried_onto_the_wire():
    body = _call(url_button_param="rate:vis_1")
    assert body["url_button_param"] == "rate:vis_1"


def test_the_ordinary_template_fields_are_unaffected():
    body = _call(url_button_param="rate:vis_1")
    assert body["template_key"] == "svc_visit_confirmation_rating_warm"
    assert body["tenant"] == "t1"
    assert body["variables"]["1"] == "أحمد"


def test_null_sender_records_the_field_too():
    s = NullSender()
    run(s.send(tenant="t1", subject_ref="sub_a", template_name="x", variables=[], cls="service",
              idempotency_key="k1", url_button_param="rate:vis_1"))
    assert s.sent[0]["url_button_param"] == "rate:vis_1"


def test_null_sender_defaults_to_no_url_button_param():
    s = NullSender()
    run(s.send(tenant="t1", subject_ref="sub_a", template_name="x", variables=[], cls="service",
              idempotency_key="k1"))
    assert s.sent[0]["url_button_param"] == ""
