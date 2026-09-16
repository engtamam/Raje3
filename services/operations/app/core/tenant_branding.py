"""A shop's own logo and accent colour, for the documents this service prints and hands to a
customer — «تقرير أداء الموظفين» and the procedure checklist alike. The owner's own instruction
(2026-09-16): a shop already saves both on «حسابي», so use them everywhere a document leaves the
building, never a second time render our own platform's identity instead of the shop's.

WHY THIS IS A PEER CALL. Branding lives in tenant-service (`branding.logo_url`/`branding.accent`,
`AccountPanes.tsx`'s own `BrandCard`), not here — the same registry `set_shop_name` above already
proxies a WRITE to. This is the read half, same `Http`/`TENANT_SERVICE_URL` plumbing, GET instead
of PATCH.

WHY PILLOW. `AccountPanes.tsx`'s own `shrink()` saves the logo as a WebP data URL (falling back to
JPEG only when a browser's canvas cannot encode WebP) — and python-docx's own `docx.image` package
has readers for PNG/JPEG/GIF/BMP/TIFF only, no WebP at all. Handing it a WebP file raises
`UnrecognizedImageError` outright, so the logo is decoded and re-encoded as PNG here before either
render module ever sees it.

DEGRADES SILENTLY, NEVER RAISES. A shop with no logo, no configured tenant-service URL, an
unreachable peer, or a corrupt stored image all fall back to the SAME thing: no picture, text-only
header — precedent set by `staff_performance_render.py`'s own `logo_path=None` branch. Printing a
report should never fail because branding could not be fetched.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any

from starlette.concurrency import run_in_threadpool

_DATA_URL = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,(?P<b64>.+)$")


@dataclass
class Branding:
    logo_png: bytes | None = None
    accent: str = ""


async def fetch_branding(settings: Any, tenant: str) -> Branding:
    base = (getattr(settings, "TENANT_SERVICE_URL", "") or "").rstrip("/")
    if not base or not tenant:
        return Branding()
    try:
        from app.core.signup import Http

        http = Http(timeout=getattr(settings, "SIGNUP_TIMEOUT_SECONDS", 10),
                   internal_token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "")
        code, out = await run_in_threadpool(
            http.call, f"{base}/internal/tenants/{tenant}", method="GET", internal=True)
        if code != 200:
            return Branding()
        branding = out.get("branding") or {}
        accent = str(branding.get("accent") or "").strip()
        logo_url = str(branding.get("logo_url") or "").strip()
        logo_png = _decode_to_png(logo_url) if logo_url else None
        return Branding(logo_png=logo_png, accent=accent)
    except Exception:                                                          # noqa: BLE001
        # A branding fetch is a NICE-TO-HAVE on top of a document that must still print — the
        # exact reasoning `staff_performance_render.py`'s own logo_path already carries.
        return Branding()


def _decode_to_png(data_url: str) -> bytes | None:
    m = _DATA_URL.match(data_url)
    if not m:
        return None
    try:
        raw = base64.b64decode(m.group("b64"), validate=False)
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(raw)) as img:
            out = BytesIO()
            img.convert("RGBA").save(out, format="PNG")
            return out.getvalue()
    except Exception:                                                          # noqa: BLE001
        return None
