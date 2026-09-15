"""HttpMobileRequests — the two calls app/ports/mobile_requests.py's docstring describes, against
operations' internal doors. Same stdlib-urllib/X-Internal-Token/asyncio.to_thread idiom as
core/service_catalog.py::HttpServiceCatalog and core/customer_lookup.py — the house pattern for
every peer call this service makes."""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.ports.mobile_requests import CreatedMobileRequest, MobileRequestFailed, NullMobileRequests


class HttpMobileRequests:
    driver = "http"

    def __init__(self, *, url: str, path: str, hours_path: str, token: str, timeout: int = 8) -> None:
        self._url = url.rstrip("/") + path
        self._hours_url = url.rstrip("/") + hours_path
        self._token = token
        self._timeout = timeout

    async def create(self, *, tenant: str, phone: str, customer_name: str,
                     service_ids: list[str], requested_time: int,
                     lat: float, lng: float) -> CreatedMobileRequest:
        return await asyncio.to_thread(
            self._create_sync, tenant, phone, customer_name, service_ids, requested_time,
            lat, lng)

    def _create_sync(self, tenant: str, phone: str, customer_name: str, service_ids: list[str],
                     requested_time: int, lat: float, lng: float) -> CreatedMobileRequest:
        body = json.dumps({
            "tenant": tenant, "phone": phone, "customer_name": customer_name,
            "service_ids": service_ids, "requested_time": requested_time,
            "lat": lat, "lng": lng}).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    raise MobileRequestFailed(f"operations returned {resp.status}")
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            # A 422 here is operations' own Pydantic validation refusing a malformed body — this
            # service already validates service_ids against the real catalogue and lat/lng's own
            # range before ever reaching here (core/tools.py), so a 422 at this point is this
            # service's own bug, surfaced honestly rather than silently swallowed.
            raise MobileRequestFailed(f"operations returned {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise MobileRequestFailed(f"operations unreachable: {exc}") from exc
        # operations' own door returns the refusal rather than raising it — see api/internal.py's
        # `internal_create_mobile_request` docstring ("no services chosen", "outside working
        # hours") — surfaced here the same way every other real failure is.
        if not data.get("created"):
            raise MobileRequestFailed(str(data.get("reason") or "operations refused the request"))
        return CreatedMobileRequest(request_id=str(data.get("request_id") or ""))

    async def hours(self, tenant: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._hours_sync, tenant)

    def _hours_sync(self, tenant: str) -> dict[str, Any] | None:
        q = urllib.parse.urlencode({"tenant": tenant})
        req = urllib.request.Request(
            f"{self._hours_url}?{q}", method="GET", headers={"X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return None
                data: dict[str, Any] = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, OSError, ValueError):
            # Degrades to "cannot verify" — same fail-open posture operations' own
            # `validate_requested_time()` documents for this exact peer being unreachable, never
            # a failed turn.
            return None
        weekly = data.get("weekly")
        return weekly if isinstance(weekly, dict) else None


def build(settings: Any) -> Any:
    if not settings.OPERATIONS_SERVICE_URL:
        return NullMobileRequests()
    return HttpMobileRequests(
        url=settings.OPERATIONS_SERVICE_URL, path=settings.OPERATIONS_MOBILE_REQUESTS_PATH,
        hours_path=settings.OPERATIONS_MOBILE_VISIT_HOURS_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN, timeout=settings.PEER_TIMEOUT_SECONDS)
