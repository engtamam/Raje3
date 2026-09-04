"""The real `PeerCaller` (core/dispute_report.py's own Protocol) — thin, and deliberately NOT
folded into this package's own `Peers`/`HttpPeers` (that port is shaped for the dashboard's
existing needs; six new unrelated methods on it would widen a contract every dashboard test also
depends on). Reuses the same `adapters/internal_http.py` primitives every other peer call here
already does.
"""
from __future__ import annotations

import urllib.parse
from typing import Any

from app.adapters import internal_http
from app.core.dispute_report import PeerCallFailed


class HttpPeerCaller:
    def __init__(self, *, token: str, timeout: float) -> None:
        self._token = token
        self._timeout = timeout

    def get(self, base_url: str, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
        if not base_url:
            raise PeerCallFailed("لا يوجد عنوان مُعدّ لهذه الخدمة")
        url = base_url.rstrip("/") + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        try:
            return internal_http.get_json(url, self._token, self._timeout)
        except Exception as exc:                                       # noqa: BLE001
            raise PeerCallFailed(str(exc)) from exc

    def post(self, base_url: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if not base_url:
            raise PeerCallFailed("لا يوجد عنوان مُعدّ لهذه الخدمة")
        url = base_url.rstrip("/") + path
        try:
            return internal_http.post_json(url, body, self._token, self._timeout)
        except Exception as exc:                                       # noqa: BLE001
            raise PeerCallFailed(str(exc)) from exc
