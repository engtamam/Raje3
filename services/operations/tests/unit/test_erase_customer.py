"""The erasure a shop performs for its own customer — open, verify, dispatch.

WHAT THESE PROTECT. The three calls are a sequence with a spent-once token in the middle, and the
failure that matters is silent: skip the verify and compliance refuses to dispatch, which reads to
the owner as "done" while the customer's data is still there and his thirty days are running.
"""
from __future__ import annotations

import json
import urllib.error

import pytest

from app.core import erase_customer as E


class _Resp:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._b = json.dumps(payload).encode()
        self.status = status

    def read(self) -> bytes:
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a) -> bool:
        return False


def _fake(monkeypatch, answers: dict[str, dict], seen: list[tuple[str, str]]):
    def urlopen(req, timeout=0):                                        # noqa: ARG001
        url = req.full_url
        seen.append((url, (req.headers.get("Authorization") or "")))
        for fragment, payload in answers.items():
            if fragment in url:
                return _Resp(payload)
        raise AssertionError(f"unexpected call to {url}")
    monkeypatch.setattr(E.urllib.request, "urlopen", urlopen)


def test_opens_verifies_and_dispatches_in_that_order(monkeypatch):
    seen: list[tuple[str, str]] = []
    _fake(monkeypatch, {
        "/dsar/": {"ok": True, "targets": ["operations", "reminders"]},
        "/compliance/dsar": {"id": "d1", "verification_token": "tok"},
    }, seen)

    out = E.erase_subject(compliance_url="http://compliance:8000",
                          authorization="Bearer his-own-token", subject_ref="ref-7")

    assert out["dsar_id"] == "d1"
    urls = [u for u, _ in seen]
    assert urls[0].endswith("/api/v1/compliance/dsar")
    assert "/dsar/d1/verify?token=tok" in urls[1]
    assert urls[2].endswith("/dsar/d1/process")
    # HIS TOKEN, ON EVERY LEG. An internal token here would let this service erase any customer of
    # any establishment in the fleet.
    assert {a for _, a in seen} == {"Bearer his-own-token"}


def test_a_second_press_dispatches_without_re_verifying(monkeypatch):
    """compliance returns no token the second time — the first was spent, and the request is
    already verified. Re-pressing must still dispatch rather than fail on the missing token."""
    seen: list[tuple[str, str]] = []
    _fake(monkeypatch, {
        "/dsar/": {"ok": True},
        "/compliance/dsar": {"id": "d1", "created": False},
    }, seen)

    out = E.erase_subject(compliance_url="http://c:8000", authorization="Bearer t",
                          subject_ref="ref-7")

    assert out["dsar_id"] == "d1"
    assert not any("verify" in u for u, _ in seen)


def test_a_press_on_a_dispatch_already_running_does_not_restart_it(monkeypatch):
    """ز-6 — THE SECOND PRESS USED TO ERASE THE PROOF, NOT THE CUSTOMER.

    compliance's `process` rebuilds the request's per-target acknowledgement map from the data map
    every time it is called. On a request already `in_progress` that puts every target that had
    ALREADY confirmed the erasure back to «not yet»: the request can no longer derive `completed`,
    the shop's evidence that it honoured the request is gone, and the subject's thirty-day clock
    keeps running. An impatient owner pressing «احذف نهائياً» twice is not an unusual event.

    So a request that is already fanning out is left alone — the sweeper on that side resumes from
    exactly the state we would be destroying.
    """
    seen: list[tuple[str, str]] = []
    _fake(monkeypatch, {
        "/compliance/dsar": {"id": "d1", "created": False, "status": "in_progress",
                             "targets": ["reminders", "loyalty"]},
    }, seen)

    out = E.erase_subject(compliance_url="http://c:8000", authorization="Bearer t",
                          subject_ref="ref-7")

    assert not any("process" in u for u, _ in seen), "the fan-out was restarted from scratch"
    assert out["dispatched"] is True


def test_a_request_compliance_refused_is_not_reported_as_done(monkeypatch):
    """A refused request answers `process` with `{"ok": true, "reason": "already_final"}` — true,
    and read by the branch at the bottom of `erase_subject` as «تم». The only reason compliance
    refuses an erasure is a legal hold, so the owner is told the thing actually stopping it."""
    seen: list[tuple[str, str]] = []
    _fake(monkeypatch, {
        "/compliance/dsar": {"id": "d1", "created": False, "status": "refused"},
    }, seen)

    with pytest.raises(E.EraseFailed) as err:
        E.erase_subject(compliance_url="http://c:8000", authorization="Bearer t",
                        subject_ref="ref-7")
    assert "حجزٍ نظاميّ" in str(err.value)


def test_a_status_we_do_not_recognise_still_dispatches(monkeypatch):
    """UNKNOWN IS NOT «ALREADY RUNNING». The skip is keyed on the statuses that mean the fan-out
    has started, never on the ones that mean it has not — so a status compliance adds later, or an
    answer with no status field at all, costs a round trip rather than a customer's erasure."""
    seen: list[tuple[str, str]] = []
    _fake(monkeypatch, {
        "/dsar/": {"ok": True, "targets": ["operations"]},
        "/compliance/dsar": {"id": "d1", "status": "on_hold_pending_review"},
    }, seen)

    E.erase_subject(compliance_url="http://c:8000", authorization="Bearer t", subject_ref="ref-7")
    assert any("process" in u for u, _ in seen)


def test_a_missing_capability_says_which_one(monkeypatch):
    def urlopen(req, timeout=0):                                        # noqa: ARG001
        raise urllib.error.HTTPError(req.full_url, 403, "forbidden", {}, None)  # type: ignore[arg-type]
    monkeypatch.setattr(E.urllib.request, "urlopen", urlopen)

    with pytest.raises(E.EraseFailed) as err:
        E.erase_subject(compliance_url="http://c:8000", authorization="Bearer t",
                        subject_ref="ref-7")
    # He can fix this himself on his own team page; «تعذّر الحذف» would send him to support.
    assert "صلاحية" in str(err.value)


def test_no_url_configured_is_a_refusal_not_a_silent_success(monkeypatch):
    with pytest.raises(E.EraseFailed):
        E.erase_subject(compliance_url="", authorization="Bearer t", subject_ref="ref-7")
