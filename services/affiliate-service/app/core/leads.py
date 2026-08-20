# =============================================================================
# affiliate-service — §٦ Lead Sourcing: Google Places API key management (BYOK per manager)
# -----------------------------------------------------------------------------
# Tamam, 2026-08-20 (recommended, approved): a manager brings HIS OWN Google Places API key, not
# necessarily the company's. Reuses SecretStore (app/core/secret_store.py) — the exact write-
# only, KEK-sealed mechanism already built for operator-managed credentials — keyed by the
# manager's OWN affiliate id as the "tenant". That is not a hack: SecretStore.get()'s own
# contract is "a caller with no per-tenant override inherits the platform-wide one before falling
# back to env", which is EXACTLY the fallback chain this needs, for free: the manager's own key →
# a platform-wide default an admin may set (tenant="") → the deploy-time env default → refused.
#
# WHY BYOK. A grid search over a whole city can burn thousands of Places API calls. One shared key
# across every manager means one manager's aggressive search can exhaust the whole platform's
# monthly quota/budget for everybody else — BYOK puts the cost and the quota on the manager
# actually running the search, the same "who owns this cost" boundary a marketer's own payout
# method already draws (core/payouts.py).
# =============================================================================
from __future__ import annotations

from app.core.secret_store import SecretInfo, SecretStore

_KEY_NAME = "leads_places_api_key"


class LeadSourcingKeys:
    def __init__(self, *, secret_store: SecretStore, fallback_api_key: str = "") -> None:
        self._secrets = secret_store
        self._fallback = fallback_api_key

    async def set_key(self, affiliate_id: str, *, value: str, actor_ref: str = "") -> SecretInfo:
        return await self._secrets.set(
            tenant=affiliate_id, name=_KEY_NAME, value=value, actor_ref=actor_ref)

    async def clear_key(self, affiliate_id: str) -> bool:
        return await self._secrets.clear(tenant=affiliate_id, name=_KEY_NAME)

    async def info(self, affiliate_id: str) -> SecretInfo | None:
        """What the manager himself may see about his own key — a hint, never the value. Only
        his OWN row: a platform-wide default set at tenant="" is not "his key" and must not be
        reported as one, even though `resolve()` below would fall back to using it for him."""
        return await self._secrets.info(tenant=affiliate_id, name=_KEY_NAME)

    async def resolve(self, affiliate_id: str) -> str:
        """The PLAINTEXT key an actual search job should call Google with — IN-PROCESS USE ONLY
        (SecretStore's own write-only contract), never returned from any HTTP route. Manager's
        own key, then the platform-wide default, then the deploy-time env default, in that
        order — see the module docstring."""
        return await self._secrets.get(tenant=affiliate_id, name=_KEY_NAME, fallback=self._fallback)
