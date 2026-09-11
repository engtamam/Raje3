"""Timeout & body-limit middleware behave correctly, in isolation."""
from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.security import BodyLimitMiddleware, TimeoutMiddleware


def _app_with(mw, **kwargs) -> FastAPI:
    app = FastAPI()
    app.add_middleware(mw, **kwargs)

    @app.get("/slow")
    async def slow():
        await asyncio.sleep(0.5)
        return {"ok": True}

    @app.post("/echo")
    async def echo():
        return {"ok": True}

    return app


def test_timeout_returns_408():
    client = TestClient(_app_with(TimeoutMiddleware, timeout_ms=50))
    resp = client.get("/slow")
    assert resp.status_code == 408
    assert resp.json() == {"error": "REQUEST_TIMEOUT"}


def test_body_limit_rejects_oversized():
    client = TestClient(_app_with(BodyLimitMiddleware, max_bytes=16))
    resp = client.post("/echo", content=b"x" * 64)
    assert resp.status_code == 413
    assert resp.json() == {"error": "PAYLOAD_TOO_LARGE"}


def test_body_limit_allows_small():
    client = TestClient(_app_with(BodyLimitMiddleware, max_bytes=1024))
    resp = client.post("/echo", content=b"x" * 8)
    assert resp.status_code == 200


def test_body_limit_rejects_an_oversized_body_with_no_content_length_header():
    """error-collector-004 (QA audit, 2026-09-12): a chunked request carries no `Content-Length`
    at all, so the header-only check used to let ANY size through untouched. A generator body
    makes httpx send `Transfer-Encoding: chunked` instead of a length header — the exact bypass
    the finding described — and this must still be refused."""
    def _chunks():
        yield b"x" * 64
    client = TestClient(_app_with(BodyLimitMiddleware, max_bytes=16))
    resp = client.post("/echo", content=_chunks())
    assert resp.status_code == 413
    assert resp.json() == {"error": "PAYLOAD_TOO_LARGE"}


def test_body_limit_still_allows_a_small_chunked_body():
    def _chunks():
        yield b"x" * 8
    client = TestClient(_app_with(BodyLimitMiddleware, max_bytes=1024))
    resp = client.post("/echo", content=_chunks())
    assert resp.status_code == 200
