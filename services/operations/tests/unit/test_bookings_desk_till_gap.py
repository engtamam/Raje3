"""What `BookingsDesk.attend()`/`.bookings_for_customer()` actually PUT ON THE WIRE — the till's
own new door into `bookings` (2026-09-14, closing the largest gap both till-integration audits
named). Same discipline as `test_loyalty_desk_body.py` beside this file: the route tests replace
`container.bookings_desk` with a stand-in and prove nothing about the real request shape, so this
keeps the real `BookingsDesk` and intercepts only the wire-level `_post`/`_get`.
"""
from __future__ import annotations

import asyncio

from app.adapters.bookings_desk import BookingsDesk


def _desk() -> BookingsDesk:
    return BookingsDesk(base_url="http://bookings.invalid", path="/internal/working-hours",
                        token="t" * 40)


def test_attend_posts_to_the_right_path_with_the_right_body():
    captured: dict = {}

    def _fake_post(path, body):
        captured["path"] = path
        captured["body"] = body
        return {"_status": 200, "id": "bkg_1", "status": "attended"}

    desk = _desk()
    desk._post = _fake_post                              # noqa: SLF001 — the seam under test
    out = asyncio.run(desk.attend("t1", "bkg_1", customer_id="cus_1", branch_id="brn_a",
                                  occurred_at=123))
    assert captured["path"] == "/internal/bookings/bkg_1/attend"
    assert captured["body"] == {"tenant": "t1", "customer_id": "cus_1", "branch_id": "brn_a",
                                "occurred_at": 123}
    assert out == {"_status": 200, "id": "bkg_1", "status": "attended"}


def test_attend_when_not_configured_never_touches_the_wire():
    desk = BookingsDesk(base_url="", path="/internal/working-hours", token="t" * 40)

    def _boom(*a, **kw):
        raise AssertionError("must not be called when unconfigured")

    desk._post = _boom                                    # noqa: SLF001
    out = asyncio.run(desk.attend("t1", "bkg_1", customer_id="cus_1"))
    assert out is None


def test_bookings_for_customer_posts_tenant_customer_and_branch():
    captured: dict = {}

    def _fake_post(path, body):
        captured["path"] = path
        captured["body"] = body
        return {"_status": 200, "bookings": [{"id": "bkg_1"}]}

    desk = _desk()
    desk._post = _fake_post                               # noqa: SLF001
    out = asyncio.run(desk.bookings_for_customer("t1", "cus_1", branch_id="brn_a"))
    assert captured["path"] == "/internal/bookings/for-customer"
    assert captured["body"] == {"tenant": "t1", "customer_id": "cus_1", "branch_id": "brn_a"}
    assert out == [{"id": "bkg_1"}]


def test_bookings_for_customer_treats_an_error_status_as_unreachable_not_empty():
    """`[]` (genuinely no bookings) and `None` (could not tell) must never collapse into the same
    answer — the caller (till.py) reports one as "you have none" and the other as "try again"."""
    desk = _desk()
    desk._post = lambda path, body: {"_status": 500, "error": "INTERNAL_ERROR"}   # noqa: SLF001
    out = asyncio.run(desk.bookings_for_customer("t1", "cus_1"))
    assert out is None


def test_bookings_for_customer_when_the_peer_is_totally_unreachable_returns_none():
    desk = _desk()
    desk._post = lambda path, body: None                  # noqa: SLF001
    out = asyncio.run(desk.bookings_for_customer("t1", "cus_1"))
    assert out is None


def test_post_turns_an_http_error_body_into_a_tagged_status_and_generic_code():
    """A real 400/404 from `bookings` still comes back as a usable dict (never `None`) — only a
    transport-level failure (timeout, DNS, connection refused) collapses to `None`."""
    import io
    import json
    import urllib.error

    desk = _desk()

    def _urlopen(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url, 404, "Not Found", {},
            io.BytesIO(json.dumps({"error": "NOT_FOUND"}).encode()))

    import app.adapters.bookings_desk as mod
    original = mod.urllib.request.urlopen
    mod.urllib.request.urlopen = _urlopen
    try:
        out = desk._post("/internal/bookings/x/attend", {"tenant": "t1"})   # noqa: SLF001
    finally:
        mod.urllib.request.urlopen = original
    assert out == {"_status": 404, "error": "NOT_FOUND"}


def test_post_on_total_transport_failure_returns_none():
    desk = _desk()

    def _urlopen(req, timeout):
        raise OSError("connection refused")

    import app.adapters.bookings_desk as mod
    original = mod.urllib.request.urlopen
    mod.urllib.request.urlopen = _urlopen
    try:
        out = desk._post("/internal/bookings/x/attend", {"tenant": "t1"})   # noqa: SLF001
    finally:
        mod.urllib.request.urlopen = original
    assert out is None
