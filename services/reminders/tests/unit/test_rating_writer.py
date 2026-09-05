"""HttpRatingWriter — the one write reminders makes to a visit it does not own."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from app.core.rating_writer import HttpRatingWriter


def run(c):
    return asyncio.run(c)


def writer():
    return HttpRatingWriter(operations_url="http://ops",
                            path="/internal/operations/visits/{}/rating", token="t")


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


def test_posts_to_the_visit_specific_url():
    w = writer()
    seen = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"recorded": True, "changed": True})

    with patch("urllib.request.urlopen", _urlopen):
        ok = run(w.write(tenant="t1", visit_id="vis_1", rating=5, feedback_text="ممتاز"))
    assert ok is True
    assert seen["url"] == "http://ops/internal/operations/visits/vis_1/rating"
    assert seen["body"] == {"tenant": "t1", "rating": 5, "feedback_text": "ممتاز"}


def test_recorded_false_from_operations_is_reported_as_false():
    w = writer()
    with patch("urllib.request.urlopen", return_value=_Resp({"recorded": False})):
        assert run(w.write(tenant="t1", visit_id="vis_ghost", rating=5, feedback_text="")) is False


def test_a_non_2xx_status_is_reported_as_false_not_raised():
    w = writer()
    with patch("urllib.request.urlopen", return_value=_Resp({}, status=500)):
        assert run(w.write(tenant="t1", visit_id="vis_1", rating=5, feedback_text="")) is False


def test_an_unreachable_peer_is_reported_as_false_not_raised():
    import urllib.error
    w = writer()

    def _boom(req, timeout=0):
        raise urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", _boom):
        assert run(w.write(tenant="t1", visit_id="vis_1", rating=5, feedback_text="")) is False


def test_changed_false_already_rated_still_reports_true_recorded():
    # operations' own idempotency: an already-rated visit answers recorded=True, changed=False —
    # the writer only cares about `recorded`.
    w = writer()
    with patch("urllib.request.urlopen", return_value=_Resp({"recorded": True, "changed": False})):
        assert run(w.write(tenant="t1", visit_id="vis_1", rating=5, feedback_text="")) is True
