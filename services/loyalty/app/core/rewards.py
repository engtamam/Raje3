"""The rewards catalogue, and the name that reaches a WhatsApp message.

A REWARD IS NOT A SERVICE (spec §9.4). Shops reward with things that are not their services — a
coffee, an air freshener, money off the bill. Modelling rewards as catalogue rows would have forced
every shop to invent services nobody can book, and a service catalogue containing "free air
freshener" stops being the thing the field screen shows.

THE NAME LIMIT IS ENFORCED AT SAVE, WITH THE REASON NAMED. The reward's name goes into a template
variable in a message the customer receives, and this product refuses owner text rather than
escaping it. So the check happens when the owner presses save — in the panel, where he can see what
is wrong and fix it — not at send time, where the failure is a message that silently did not go.

AND IT IS CHECKED ON THE SERVER, not only in the field. That is not distrust of our own console:
the till reaches this API directly (spec §9.8), so the console is not the only path in. A rule
enforced in one of two entrances is not enforced.

RETIRED, NEVER DELETED. A reward that has been redeemed is referenced by history, and its name and
cost are snapshotted onto every redemption (see `models.Redemption`) precisely so that renaming or
repricing it does not silently restate what a customer was told last year.
"""
from __future__ import annotations

import re
from typing import Any

from app.adapters.datastore.drain import drain
from app.core.models import (REWARDS, REWARD_TYPES, LoyaltyError, Reward)

# What a reward's name may contain. Arabic, Latin, digits, spaces and the handful of separators a
# shop actually types. Everything else — newlines, template braces, control characters, the
# direction-override marks that make a string render as something other than what it says — is
# refused, because this string ends up inside a message we send under the shop's own name.
NAME_OK = re.compile(r"^[\w؀-ۿ0-9 ,.\-/()&+%]+$", re.UNICODE)

# Meta renders a template variable inline; a long name turns the sentence into a wall. This is a
# product limit, not a platform one, and it is stated here so it has one home.
NAME_MAX = 40
NAME_MIN = 2


def validate_name(name: str) -> str:
    """The one place a reward name is judged. Returns the cleaned name or raises with the reason.

    The message names the ACTUAL limit rather than saying "invalid", because an owner told his
    input is invalid without being told the rule tries again, fails again, and calls support.
    """
    n = (name or "").strip()
    if len(n) < NAME_MIN:
        raise LoyaltyError("اسم المكافأة قصير جداً")
    if len(n) > NAME_MAX:
        raise LoyaltyError(f"اسم المكافأة أطول من {NAME_MAX} حرفاً — اختصره ليظهر في رسالة العميل")
    if "\n" in name or "\r" in name:
        raise LoyaltyError("اسم المكافأة سطر واحد")
    if not NAME_OK.match(n):
        raise LoyaltyError("اسم المكافأة يحتوي رموزاً لا تصلح في رسالة واتساب")
    return n


class Rewards:
    def __init__(self, store: Any) -> None:
        self.store = store

    async def create(self, tenant: str, *, name: str, cost: int, type: str,
                     service_id: str = "", discount_halalas: int = 0) -> Reward:
        clean = validate_name(name)
        if type not in REWARD_TYPES:
            raise LoyaltyError("نوع المكافأة: من الكتالوج أو هدية أو خصم")
        if cost <= 0:
            raise LoyaltyError("تكلفة المكافأة بالنقاط يجب أن تكون أكبر من صفر")
        if type == "service" and not service_id:
            # Without it, "free wash" is a name and nothing more: the visit is never recorded and
            # the reminder cycle never restarts, which is the whole reason this type is separate.
            raise LoyaltyError("مكافأة من نوع خدمة يجب أن تُربط بخدمة من الكتالوج")
        if type == "discount" and discount_halalas <= 0:
            raise LoyaltyError("مكافأة الخصم يجب أن تحمل مبلغاً")
        r = Reward(tenant=tenant, name=clean, cost=int(cost), type=type,
                   service_id=service_id, discount_halalas=int(discount_halalas))
        await self.store.put(REWARDS, r.id, r.to_dict())
        return r

    async def update(self, tenant: str, reward_id: str, **kw: Any) -> Reward:
        row = await self.store.get(REWARDS, reward_id)
        if not row or row.get("tenant") != tenant:
            # 404 rather than 403 for a reward of another establishment: telling a caller that an
            # id exists but is not theirs is telling them something about another tenant.
            raise LoyaltyError("المكافأة غير موجودة")
        if "name" in kw:
            row["name"] = validate_name(kw["name"])
        if "cost" in kw:
            if int(kw["cost"]) <= 0:
                raise LoyaltyError("تكلفة المكافأة بالنقاط يجب أن تكون أكبر من صفر")
            row["cost"] = int(kw["cost"])
        if "active" in kw:
            row["active"] = bool(kw["active"])
        if "discount_halalas" in kw:
            row["discount_halalas"] = int(kw["discount_halalas"])
        # READ-MODIFY-WRITE, NO LOCK — and that is fine here. The two doors that move points
        # (`redeem`, `earn`, the expiry sweep) hold `SpendLock` because they touch a customer's
        # BALANCE, where a lost update means a shop gives away or loses real points nobody can
        # explain. This edits the CATALOGUE ROW instead: an owner (or the till, per the module
        # docstring) tuning a reward's name/cost/active flag from the console — a low-frequency,
        # effectively single-writer path with no financial consequence if a rare double-edit drops
        # one field back to its old value; the owner sees the stale field on the very next screen
        # and re-saves. Serialising catalogue edits behind a lock would be cost for a race that,
        # even realised, costs nothing.
        await self.store.put(REWARDS, reward_id, row)
        return _row_to_reward(row)

    async def get(self, tenant: str, reward_id: str) -> Reward:
        row = await self.store.get(REWARDS, reward_id)
        if not row or row.get("tenant") != tenant:
            raise LoyaltyError("المكافأة غير موجودة")
        return _row_to_reward(row)

    async def list(self, tenant: str, *, active_only: bool = True) -> list[Reward]:
        """EVERY reward this tenant has ever created — fixed 2026-09-12, a real gap a QA audit
        found. A single `limit=500` page with the cursor discarded meant a shop with more than 500
        rewards ever made (including retired ones — `active_only` filters in Python, AFTER the
        fetch) silently lost some from this list, `affordable()`'s list, and `/loyalty/rewards`,
        with nothing anywhere saying so. `drain()` is the same paging primitive `report.py`/
        `Ledger.reconcile` already use for this exact class of bug."""
        rows = await drain(self.store, REWARDS, {"tenant": tenant}, sort=("created_at", "asc"))
        out = [_row_to_reward(r) for r in rows]
        if active_only:
            out = [r for r in out if r.active]
        return sorted(out, key=lambda r: r.cost)

    async def affordable(self, tenant: str, points: int, *,
                         catalogue: list[Reward] | None = None) -> list[Reward]:
        """What this balance can actually buy — and ONLY that (spec §9.5).

        Not the full menu with the unaffordable greyed out. Showing a customer standing at the
        counter a reward he cannot have is a worse moment than his not knowing it exists, and the
        operator holding the phone is the one who has to manage it.

        `catalogue` lets a caller that already fetched `list(tenant)` (e.g. to also show every
        reward's cost) pass it in rather than pay for the same read twice — the default still
        fetches, so every other caller is unaffected.
        """
        rows = catalogue if catalogue is not None else await self.list(tenant)
        return [r for r in rows if r.cost <= points]


def _row_to_reward(row: dict) -> Reward:
    r = Reward(tenant=row["tenant"], name=row["name"], cost=int(row["cost"]),
               type=row["type"], service_id=row.get("service_id") or "",
               discount_halalas=int(row.get("discount_halalas") or 0),
               active=bool(row.get("active", True)))
    r.id = row["id"]
    r.created_at = int(row.get("created_at") or 0)
    return r
