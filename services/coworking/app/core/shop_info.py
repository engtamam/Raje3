"""What the freelancer's public portal shows about the SHOP itself — name, logo, accent colour,
and whether it is paused right now — never the platform's own identity (spec: the portal is the
shop's own door, not ours).

WHY A PEER CALL. Branding lives in tenant-service (`branding.logo_url`/`branding.accent`), the same
field `services/operations/app/core/tenant_branding.py` already reads for printed documents — same
`INTERNAL_SERVICE_TOKEN`/`TENANT_SERVICE_URL` plumbing, GET only, no second source of truth.

NO PNG DECODE, UNLIKE OPERATIONS' OWN VERSION — that module re-encodes the logo because python-docx
cannot read WebP. A browser has no such limit, so `logo_url` is handed to `<img src>` exactly as
tenant-service stored it.

DEGRADES SILENTLY, NEVER RAISES — same posture as every other peer-branding read in this fleet
(`tenant_branding.py`'s own module doc). A portal with no reachable tenant-service still shows a
plain header and a working booking flow; it just cannot show a logo.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from starlette.concurrency import run_in_threadpool


@dataclass
class ShopInfo:
    name: str = ""
    logo_url: str = ""
    accent: str = ""


async def fetch_shop_info(settings: Any, tenant: str) -> ShopInfo:
    base = (getattr(settings, "TENANT_SERVICE_URL", "") or "").rstrip("/")
    if not base or not tenant:
        return ShopInfo()
    try:
        return await run_in_threadpool(_fetch_sync, settings, base, tenant)
    except Exception:                                                          # noqa: BLE001
        return ShopInfo()


def _fetch_sync(settings: Any, base: str, tenant: str) -> ShopInfo:
    url = f"{base}/internal/tenants/{urllib.parse.quote(tenant, safe='')}"
    headers = {"X-Internal-Token": getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or ""}
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(
            req, timeout=getattr(settings, "SIGNUP_TIMEOUT_SECONDS", 10)) as resp:  # nosec B310 - config-only host
            out = json.loads(resp.read() or b"{}")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return ShopInfo()
    branding = out.get("branding") or {}
    return ShopInfo(
        name=str(out.get("name") or "").strip(),
        logo_url=str(branding.get("logo_url") or "").strip(),
        accent=str(branding.get("accent") or "").strip(),
    )
