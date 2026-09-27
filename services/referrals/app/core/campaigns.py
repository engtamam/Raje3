"""Campaign management (spec §2/§3/§4) — the shop's own referral-program configuration.

CONFIG ONLY, PHASE 2 — see this module's own `models.py` docstring for why nothing here is ever
applied at a till yet.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from app.core.models import (
    CAMPAIGNS, CAP_SCOPE_CAMPAIGN, CAP_SCOPES, MODE_X_TIMES, MODES, USAGE_CAP_PERIODS, Campaign,
)
from app.core.rewards import RewardError, validate_new_customer_reward, validate_reward


class CampaignError(Exception):
    """A refusal a caller should show verbatim — never a stack trace."""


class CampaignService:
    def __init__(self, store: Any) -> None:
        self._store = store

    async def create(
        self, tenant: str, *, mode: str, reward_type: str, reward_params: dict[str, Any],
        new_customer_reward_type: str, new_customer_reward_params: dict[str, Any],
        x_times_limit: int = 0, min_spend_minor: int = 0,
        usage_cap_period: str = "", usage_cap_limit: int = 0,
        cap_scope: str = CAP_SCOPE_CAMPAIGN,
    ) -> Campaign:
        if mode not in MODES:
            raise CampaignError(f"نمط إحالة غير معروف: {mode}")
        if mode == MODE_X_TIMES and int(x_times_limit) < 1:
            raise CampaignError("وضع الإحالة المحدودة يحتاج عدد زيارات لا يقل عن 1")
        if int(min_spend_minor) < 0:
            raise CampaignError("الحد الأدنى للفاتورة لا يمكن أن يكون سالباً")
        usage_cap_period, usage_cap_limit = self._validate_usage_cap(usage_cap_period, usage_cap_limit)
        cap_scope = (cap_scope or CAP_SCOPE_CAMPAIGN).strip().lower()
        if cap_scope not in CAP_SCOPES:
            raise CampaignError(f"نطاق سقف الاستخدام غير معروف: {cap_scope}")

        # MANDATORY, UNCONDITIONALLY — spec §4c's own "قاعدة الطرفين": a campaign with no honest
        # win-win reward for the new customer must never reach the store at all.
        try:
            normalized_reward = validate_reward(reward_type, reward_params)
            normalized_new_customer = validate_new_customer_reward(
                new_customer_reward_type, new_customer_reward_params)
        except RewardError as exc:
            raise CampaignError(str(exc)) from exc

        campaign = Campaign(
            id=str(uuid.uuid4()), tenant=tenant, created_at=int(time.time()),
            mode=mode, x_times_limit=int(x_times_limit) if mode == MODE_X_TIMES else 0,
            min_spend_minor=int(min_spend_minor),
            usage_cap_period=usage_cap_period, usage_cap_limit=usage_cap_limit,
            reward_type=reward_type, reward_params=normalized_reward,
            new_customer_reward_type=new_customer_reward_type,
            new_customer_reward_params=normalized_new_customer,
            active=True, created_ns=time.time_ns(), cap_scope=cap_scope,
        )
        await self._store.put(CAMPAIGNS, campaign.id, campaign.to_dict())
        return campaign

    @staticmethod
    def _validate_usage_cap(period: str, limit: int) -> tuple[str, int]:
        period = (period or "").strip().lower()
        limit = int(limit or 0)
        if not period and not limit:
            return "", 0
        if period not in USAGE_CAP_PERIODS:
            raise CampaignError(f"دورة السقف غير معروفة: {period or '(فارغة)'}")
        if limit < 1:
            raise CampaignError("سقف الاستخدام يحتاج رقماً لا يقل عن 1")
        return period, limit

    async def get(self, tenant: str, campaign_id: str) -> Campaign | None:
        row = await self._store.get(CAMPAIGNS, campaign_id)
        if row is None or row.get("tenant") != tenant:
            # NO CROSS-TENANT EXISTENCE LEAK — same posture every tenant-scoped read in this
            # fleet takes (see services/coworking/app/core/resources.py's own identical note).
            return None
        return Campaign.from_dict(row)

    async def list(self, tenant: str, *, active_only: bool = False) -> list[Campaign]:
        rows, _ = await self._store.find(CAMPAIGNS, {"tenant": tenant}, limit=1000,
                                         sort=("created_at", "desc"))
        campaigns = [Campaign.from_dict(r) for r in rows]
        if active_only:
            campaigns = [c for c in campaigns if c.active]
        return campaigns

    async def get_active_for_tenant(self, tenant: str) -> Campaign | None:
        """The one campaign a till-side redemption checks against. MOST-RECENTLY-CREATED active
        campaign, deliberately — a shop that paused an old campaign and started a new one is
        never caught by a stale first match. A shop running two active campaigns at once (not
        refused anywhere in this phase) still gets a single, deterministic answer rather than an
        arbitrary one.

        PICKED BY `created_ns` (nanoseconds), NOT BY `list()`'s OWN ORDER — `created_at` has only
        whole-second resolution, so two campaigns created in the same wall-clock second would
        otherwise tie-break on the datastore's own incidental secondary sort (descending UUID
        string in MemoryDataStore, which is not insertion order at all). `created_ns` is set once
        at creation and never touched again, so `max()` over it is deterministic regardless of
        what order the store itself returns rows in."""
        campaigns = await self.list(tenant, active_only=True)
        if not campaigns:
            return None
        return max(campaigns, key=lambda c: c.created_ns)

    async def set_active(self, tenant: str, campaign_id: str, *, active: bool) -> Campaign:
        """The ONLY mutable field — see this module's own `models.py` docstring for why every
        other term is fixed for the campaign's whole life."""
        campaign = await self.get(tenant, campaign_id)
        if campaign is None:
            raise CampaignError("الحملة غير موجودة")
        updated = Campaign(
            id=campaign.id, tenant=campaign.tenant, created_at=campaign.created_at,
            mode=campaign.mode, x_times_limit=campaign.x_times_limit,
            min_spend_minor=campaign.min_spend_minor,
            usage_cap_period=campaign.usage_cap_period, usage_cap_limit=campaign.usage_cap_limit,
            reward_type=campaign.reward_type, reward_params=campaign.reward_params,
            new_customer_reward_type=campaign.new_customer_reward_type,
            new_customer_reward_params=campaign.new_customer_reward_params,
            active=bool(active), created_ns=campaign.created_ns, cap_scope=campaign.cap_scope,
        )
        await self._store.put(CAMPAIGNS, campaign.id, updated.to_dict())
        return updated
