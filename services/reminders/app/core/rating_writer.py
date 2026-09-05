"""Hand a resolved rating reply to operations — the one write this service makes about a visit
it does not own.

`NullRatingWriter` records rather than posts (tests, and any deployment that has not configured
`OPERATIONS_VISIT_RATING_PATH` yet — a missing path fails closed here exactly the same way
`HttpSender.send_flow` fails closed on a missing interactive path, never a guessed URL).
"""
from __future__ import annotations

import json
import urllib.error
from typing import Any

from app.adapters import internal_http


class NullRatingWriter:
    driver = "null"

    def __init__(self) -> None:
        self.written: list[dict[str, Any]] = []

    async def write(self, *, tenant: str, visit_id: str, rating: int, feedback_text: str) -> bool:
        self.written.append({"tenant": tenant, "visit_id": visit_id, "rating": rating,
                             "feedback_text": feedback_text})
        return True


class HttpRatingWriter:
    driver = "http"

    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def write(self, *, tenant: str, visit_id: str, rating: int, feedback_text: str) -> bool:
        """`True` iff the visit now carries a rating (this write or an earlier one) — the caller
        (the bus consumer) logs a mismatch but never retries: operations' own route is already
        idempotent on "already rated", so a `False` here means the visit itself was never found,
        which no retry fixes."""
        url = self._url.format(visit_id)
        body = json.dumps({"tenant": tenant, "rating": rating,
                           "feedback_text": feedback_text}).encode()
        try:
            status, raw = internal_http.send(
                url, timeout=self._timeout, method="POST", body=body,
                content_type=internal_http.JSON, token=self._token)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return False
        if not 200 <= status < 300:
            return False
        result = json.loads(raw or b"{}")
        return bool(result.get("recorded"))
