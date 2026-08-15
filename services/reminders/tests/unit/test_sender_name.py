"""The customer's name — resolved beside the phone number, and nowhere else.

WHAT WAS WRONG. Slot 1 of every one of our templates is the customer's name, and nothing ever put
a name in it: the tick passes `customer_names={}` and the campaign path passed `""`. So every
message this product rendered opened «عميلنا العزيز» — to customers whose names the shop had typed
in itself. The greeting is the first thing read and it was the same for everybody.

WHY IT IS FIXED IN THE SENDER. reminders holds a pseudonym and no personal data. Resolving the
name any earlier would put it in a schedule row, a render, a send log and a backup. The recipient
route already returns it beside the phone number, so this costs no extra read and leaves nothing
new at rest.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from app.adapters.message_sender import HttpSender
from app.core.rendering import FALLBACK_NAME


def run(c):
    return asyncio.run(c)


def sender():
    return HttpSender(notify_url="http://notify", notify_path="/internal/notify",
                      operations_url="http://ops", recipient_path="/internal/recipient",
                      token="t")


class _Resp:
    status = 200

    def __init__(self, payload):
        self._p = json.dumps(payload).encode()

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _send(name: str, first: str):
    s = sender()
    seen: dict = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"status": "sent"})

    with patch.object(s, "_recipient", return_value=("+966500000000", name)), \
         patch("urllib.request.urlopen", _urlopen):
        run(s.send(tenant="t1", subject_ref="sub_a", template_name="svc_visit_confirmation_brief",
                   variables=[first, "مغسلة النخيل"], cls="service", idempotency_key="k1"))
    return seen["body"]["variables"]


def test_the_name_replaces_the_greeting_nobody_chose():
    assert _send("نورة", FALLBACK_NAME)["1"] == "نورة"


def test_an_empty_slot_is_filled_too():
    """The campaign path passed an empty string, which the renderer turns into the fallback — but
    a caller that skips the renderer would send a blank, and Meta rejects a blank variable."""
    assert _send("نورة", "")["1"] == "نورة"


def test_a_name_the_caller_already_knew_is_not_overruled():
    """The redemption path names the person from the visit itself. This fills a blank; it does not
    take a decision away from a caller that made one."""
    assert _send("نورة", "أبو سعد")["1"] == "أبو سعد"


def test_a_customer_with_no_name_still_gets_the_greeting():
    """Recorded by phone alone — most of them, in the first week of a shop's life."""
    assert _send("", FALLBACK_NAME)["1"] == FALLBACK_NAME
