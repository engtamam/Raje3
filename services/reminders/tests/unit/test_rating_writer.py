"""HttpRatingWriter — the one write reminders makes to a visit it does not own."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

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
    assert seen["body"] == {"tenant": "t1", "rating": 5, "feedback_text": "ممتاز",
                            "subject_ref": "", "rating_points": 0}


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


def test_a_301_redirect_status_is_reported_as_false_not_followed_blindly():
    w = writer()
    with patch("urllib.request.urlopen", return_value=_Resp({}, status=301)):
        assert run(w.write(tenant="t1", visit_id="vis_1", rating=5, feedback_text="")) is False


def test_an_unparseable_response_body_does_not_raise():
    class _BadResp:
        status = 200

        def read(self):
            return b"not json"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    w = writer()
    with patch("urllib.request.urlopen", return_value=_BadResp()):
        with pytest.raises(Exception):     # json.loads raising IS the current contract — pinned
            run(w.write(tenant="t1", visit_id="vis_1", rating=5, feedback_text=""))


def test_the_visit_id_is_interpolated_into_the_configured_path_exactly_once():
    w = writer()
    seen = {}

    def _urlopen(req, timeout=0):
        seen["url"] = req.full_url
        return _Resp({"recorded": True})

    with patch("urllib.request.urlopen", _urlopen):
        run(w.write(tenant="t1", visit_id="vis_with_underscores_9", rating=3, feedback_text=""))
    assert seen["url"].count("vis_with_underscores_9") == 1


def test_feedback_text_rides_through_untouched_by_the_writer():
    w = writer()
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"recorded": True})

    with patch("urllib.request.urlopen", _urlopen):
        run(w.write(tenant="t1", visit_id="vis_1", rating=5, feedback_text="نص عربي طويل جداً"))
    assert seen["body"]["feedback_text"] == "نص عربي طويل جداً"


def test_an_empty_feedback_text_is_sent_as_an_empty_string_not_omitted():
    w = writer()
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"recorded": True})

    with patch("urllib.request.urlopen", _urlopen):
        run(w.write(tenant="t1", visit_id="vis_1", rating=1, feedback_text=""))
    assert seen["body"]["feedback_text"] == ""


def test_the_tenant_is_sent_exactly_as_given(monkeypatch=None):
    w = writer()
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"recorded": True})

    with patch("urllib.request.urlopen", _urlopen):
        run(w.write(tenant="tenant_with_underscore_1", visit_id="vis_1", rating=5,
                    feedback_text=""))
    assert seen["body"]["tenant"] == "tenant_with_underscore_1"


def test_two_different_operations_urls_never_cross_talk():
    a = HttpRatingWriter(operations_url="http://ops-a",
                        path="/internal/operations/visits/{}/rating", token="t")
    b = HttpRatingWriter(operations_url="http://ops-b",
                        path="/internal/operations/visits/{}/rating", token="t")
    seen = []

    def _urlopen(req, timeout=0):
        seen.append(req.full_url)
        return _Resp({"recorded": True})

    with patch("urllib.request.urlopen", _urlopen):
        run(a.write(tenant="t1", visit_id="vis_1", rating=5, feedback_text=""))
        run(b.write(tenant="t1", visit_id="vis_1", rating=5, feedback_text=""))
    assert seen == ["http://ops-a/internal/operations/visits/vis_1/rating",
                    "http://ops-b/internal/operations/visits/vis_1/rating"]


def test_subject_ref_and_rating_points_ride_along_when_given():
    w = writer()
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"recorded": True})

    with patch("urllib.request.urlopen", _urlopen):
        run(w.write(tenant="t1", visit_id="vis_1", rating=5, feedback_text="",
                    subject_ref="sub_abc", rating_points=25))
    assert seen["body"]["subject_ref"] == "sub_abc"
    assert seen["body"]["rating_points"] == 25


def test_subject_ref_and_rating_points_default_to_blank_and_zero():
    w = writer()
    seen = {}

    def _urlopen(req, timeout=0):
        seen["body"] = json.loads(req.data or b"{}")
        return _Resp({"recorded": True})

    with patch("urllib.request.urlopen", _urlopen):
        run(w.write(tenant="t1", visit_id="vis_1", rating=5, feedback_text=""))
    assert seen["body"]["subject_ref"] == ""
    assert seen["body"]["rating_points"] == 0
