"""Per-tenant app-visibility overrides — a plan hidden from everyone (`listed: false`,
deploy/seed/plans.json's own convention) can still be shown, and self-subscribed to, by one named
tenant a platform operator picks. Reached from the platform's own already-open «العملاء» screen
(`CustomerDetail.tsx`) — no phone-lookup door of its own, because the tenant is already known by
the time an operator is looking at that shop's own settings.

GENERIC BY DESIGN, NOT ONE APP HARDCODED — keyed by (tenant, feature_key), so showing a DIFFERENT
unlisted app to a different tenant later needs no new code at all, only a new row through the same
two routes.

SECURITY — THE WHOLE REASON THIS IS SAFE ENOUGH TO GATE ON `platform.operations` RATHER THAN AN
OWNER-ONLY CAPABILITY: this flag ONLY EVER affects what a shop's OWN store screen shows it. It
never subscribes anyone to anything, never calls billing-service, never touches an existing
subscription, and never moves money. A shop still clicks «اشترك» itself, through the exact same
paid/free subscribe path every other app already goes through — billing-service's own validation
(is this plan real, active, priced correctly) runs exactly as it always does. A wrong or malicious
row here can, at worst, make an app tile visible to a shop that should not see it; it can never
make anyone a subscriber on its own.

THE READ SIDE NEVER TAKES A TENANT FROM THE CALLER — `visible_keys_for_tenant` is only ever called
with the tenant resolved from the CALLING SHOP'S OWN TOKEN (see `api/v1/subscription.py`'s own
`_tenant(principal)`), never a client-supplied value, which is what makes IDOR (shop A asking "is
X visible for shop B") structurally impossible rather than merely checked for. The ADMIN routes
(`api/v1/platform.py`) are the only place a tenant is ever taken as a parameter, and those are
gated on `platform.operations` — a real platform-staff capability, never issued to a shop token.

`feature_key` IS VALIDATED AGAINST A SHAPE, NOT A FIXED LIST — `feature.[a-z_]+`, the same
convention every real key in `deploy/seed/plans.json` already follows. Enough to catch a typo or a
garbage value without hardcoding which apps this mechanism may ever apply to.
"""
from __future__ import annotations

import re
from typing import Any

APP_VISIBILITY_OVERRIDES = "app_visibility_overrides"
_FEATURE_KEY = re.compile(r"^feature\.[a-z_]+$")


class AppVisibilityError(Exception):
    """A refusal a caller should show verbatim — never a stack trace."""


def _row_key(tenant: str, feature_key: str) -> str:
    return f"{tenant}:{feature_key}"


class AppVisibilityOverrides:
    def __init__(self, store: Any) -> None:
        self._store = store

    async def visible_keys_for_tenant(self, tenant: str) -> list[str]:
        """Every feature key ONE tenant is individually shown, on top of whatever is already
        globally listed. Called ONLY with the caller's OWN tenant — see this module's own
        docstring for why that is what makes this safe against IDOR by construction."""
        if not tenant:
            return []
        rows, _ = await self._store.find(
            APP_VISIBILITY_OVERRIDES, {"tenant": tenant, "visible": True}, limit=200)
        return sorted({str(r["feature_key"]) for r in rows if r.get("feature_key")})

    async def list_for_tenant(self, tenant: str) -> list[dict]:
        """Every override row for one tenant, visible or revoked — the admin panel's own read, so
        a customer file's settings can show what has already been toggled either way, not only
        what is currently on."""
        if not tenant:
            return []
        rows, _ = await self._store.find(APP_VISIBILITY_OVERRIDES, {"tenant": tenant}, limit=200)
        return [{"feature_key": r.get("feature_key", ""), "visible": bool(r.get("visible"))}
                for r in rows]

    async def set_visible(self, tenant: str, feature_key: str, visible: bool) -> dict:
        """The ONLY write in this module. `tenant`/`feature_key` are both operator-supplied here
        (never a shop's own input) — validated for shape, not existence: a row for a tenant id or
        feature key that turns out to be wrong is inert (nothing to show, nothing to find), never
        a security exposure, so this does not spend a peer call proving either one is real."""
        tenant = (tenant or "").strip()
        if not tenant:
            raise AppVisibilityError("لا يوجد محل محدَّد")
        feature_key = (feature_key or "").strip()
        if not _FEATURE_KEY.match(feature_key):
            raise AppVisibilityError("مفتاح تطبيق غير صالح")
        row = {"tenant": tenant, "feature_key": feature_key, "visible": bool(visible)}
        await self._store.put(APP_VISIBILITY_OVERRIDES, _row_key(tenant, feature_key), row)
        return row
