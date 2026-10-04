"""The "جماعي" milestone peer — campaigns is a separate service, reached over HTTP, fire-and-
forget: unlike `evidence_peer.py`'s own fail-hard posture, nothing here may ever surface to the
caller (`record_visit`, tested separately in test_milestone_hook.py)."""
from __future__ import annotations

import asyncio
import urllib.error

from app.adapters import internal_http
from app.adapters.milestone_peer import (
    HttpMilestonePeer,
    NullMilestonePeer,
    build_milestone_peer,
)


def run(c):
    return asyncio.run(c)


class _Settings:
    def __init__(self, url="", path="/internal/campaigns/milestone/visit-recorded",
                token="tok", timeout=5):
        self.CAMPAIGNS_SERVICE_URL = url
        self.CAMPAIGNS_MILESTONE_VISIT_PATH = path
        self.INTERNAL_SERVICE_TOKEN = token
        self.PEER_TIMEOUT_SECONDS = timeout


def test_no_url_configured_builds_a_null_peer():
    peer = build_milestone_peer(_Settings(url=""))
    assert isinstance(peer, NullMilestonePeer)


def test_a_null_peer_is_a_harmless_no_op():
    run(NullMilestonePeer().on_visit_recorded(tenant="t1", subject_ref="s1"))


def test_a_configured_url_builds_a_real_http_peer():
    peer = build_milestone_peer(_Settings(url="http://campaigns:8000"))
    assert isinstance(peer, HttpMilestonePeer)


def test_the_http_peer_posts_the_real_payload(monkeypatch):
    calls = []

    def fake_send(url, *, timeout, **kw):
        calls.append({"url": url, "timeout": timeout, **kw})
        return 200, b"{}"

    monkeypatch.setattr(internal_http, "send", fake_send)
    peer = HttpMilestonePeer(campaigns_url="http://campaigns:8000",
                             path="/internal/campaigns/milestone/visit-recorded",
                             token="tok", timeout=5)
    run(peer.on_visit_recorded(tenant="t1", subject_ref="s1", service_ids=["svc_1"],
                              package_id="", occurred_at=100))
    assert len(calls) == 1
    assert calls[0]["url"] == "http://campaigns:8000/internal/campaigns/milestone/visit-recorded"
    assert calls[0]["token"] == "tok"


def test_an_empty_url_never_calls_send(monkeypatch):
    def fake_send(*a, **kw):
        raise AssertionError("must not be called with no url configured")

    monkeypatch.setattr(internal_http, "send", fake_send)
    peer = HttpMilestonePeer(campaigns_url="", path="/x", token="tok", timeout=5)
    run(peer.on_visit_recorded(tenant="t1", subject_ref="s1"))


def test_an_unreachable_peer_swallows_its_own_failure(monkeypatch):
    def fake_send(*a, **kw):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(internal_http, "send", fake_send)
    peer = HttpMilestonePeer(campaigns_url="http://campaigns:8000", path="/x",
                             token="tok", timeout=5)
    # Must not raise.
    run(peer.on_visit_recorded(tenant="t1", subject_ref="s1"))


def test_an_http_error_status_swallows_its_own_failure(monkeypatch):
    def fake_send(*a, **kw):
        raise urllib.error.HTTPError("http://x", 500, "boom", {}, None)

    monkeypatch.setattr(internal_http, "send", fake_send)
    peer = HttpMilestonePeer(campaigns_url="http://campaigns:8000", path="/x",
                             token="tok", timeout=5)
    run(peer.on_visit_recorded(tenant="t1", subject_ref="s1"))
