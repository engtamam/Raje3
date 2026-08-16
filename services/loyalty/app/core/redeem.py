"""Spending points — one path for the field, the panel and the till.

THE OPERATOR SPENDS, NOT THE MANAGER (spec §9.5). A manager signing off every redemption is a
bottleneck in a busy shop, and the outcome is not a controlled programme but an unused one. The
control is a trail rather than a gate, in three parts:

  1. every redemption is attributed to the account that performed it (spec §3.5 — from the session;
     there is no PIN in this product),
  2. the customer gets an instant receipt (`notify.py`) — which is the real audit, because the only
     person who reliably notices a balance being spent is the person whose balance it was,
  3. a reward above a threshold the OWNER sets needs a manager. The threshold is his, and an owner
     who leaves it wide open has made a choice rather than been failed by a default.

THE SAME FUNCTION SERVES ALL THREE CHANNELS. The till's redemption (spec §9.8) and the panel
fallback for tills that cannot be modified must produce IDENTICAL ledger entries — same shape, same
attribution, same customer message. A fallback that records differently is a reporting bug waiting
for month end, and it would be discovered by an owner reconciling two numbers that should match.

MESSAGE AFTER COMMIT, ALWAYS. The receipt is sent by the caller AFTER this returns, never inside.
A message announcing a redemption that then failed to commit is worse than no message: the customer
has a receipt for points he still has, and the next thing he does is ask why his balance is wrong.
"""
from __future__ import annotations

from typing import Any

from app.core.ledger import Ledger
from app.core.models import (REDEMPTIONS, LoyaltyError, Overdraft, Redemption, Reward)
from app.core.rewards import Rewards
from app.core.spend_lock import SpendLock


class Redeemer:
    def __init__(self, store: Any, ledger: Ledger, rewards: Rewards, cache: Any = None) -> None:
        self.store = store
        self.ledger = ledger
        self.rewards = rewards
        # ONE SPENDER AT A TIME. See core/spend_lock.py: the balance read and the ledger write are
        # not atomic against each other, and this product opens two redemption doors on purpose.
        self.cache = cache

    async def _existing(self, tenant: str, idem_key: str) -> Redemption | None:
        if not idem_key:
            return None
        rows, _ = await self.store.find(REDEMPTIONS, {"tenant": tenant, "idem_key": idem_key},
                                        limit=1)
        if not rows:
            return None
        return _row_to_redemption(rows[0])

    async def redeem(self, tenant: str, subject_ref: str, reward_id: str, *,
                     actor: str = "", idem_key: str = "", channel: str = "field",
                     approved_by: str = "", manager_threshold: int = 0,
                     branch_id: str = "", source: str = "") -> tuple[Redemption, bool]:
        """Spend points. Returns (redemption, is_new).

        `is_new` is False when the idempotency key had already been used — and the caller must NOT
        send a second receipt in that case. A field phone on a bad connection retries; the customer
        must not receive two messages for one reward.
        """
        prior = await self._existing(tenant, idem_key)
        if prior is not None:
            return prior, False

        # HELD FROM THE BALANCE READ TO THE LEDGER WRITE, and released whatever happens.
        #
        # Everything below reads a balance and then spends against what it read. Two callers in
        # that window — the till at one branch and the phone at another, which the product
        # deliberately allows — both see the same points and both hand a reward over. The customer
        # paid for one. `SpendBusy` is raised as a refusal a cashier can read and retry.
        async with SpendLock(self.cache, tenant, subject_ref):
            return await self._redeem_locked(
                tenant, subject_ref, reward_id, actor=actor, idem_key=idem_key, channel=channel,
                approved_by=approved_by, manager_threshold=manager_threshold,
                branch_id=branch_id, source=source)

    async def _redeem_locked(self, tenant: str, subject_ref: str, reward_id: str, *,
                             actor: str, idem_key: str, channel: str, approved_by: str,
                             manager_threshold: int, branch_id: str,
                             source: str) -> tuple[Redemption, bool]:
        # RE-CHECKED INSIDE THE LOCK. The caller that lost the race above may have been waiting on
        # the winner's own idempotency key — and outside the lock this read was the stale one.
        prior = await self._existing(tenant, idem_key)
        if prior is not None:
            return prior, False

        reward: Reward = await self.rewards.get(tenant, reward_id)
        if not reward.active:
            raise LoyaltyError("هذه المكافأة متوقفة")

        bal = await self.ledger.balance(tenant, subject_ref)
        if bal.points < reward.cost:
            # Refused, never clamped. Handing out the reward and under-charging for it is a
            # generosity the shop discovers at month end, having never approved it.
            raise Overdraft(
                f"الرصيد {bal.points} نقطة، والمكافأة {reward.cost} — لا يكفي")

        if manager_threshold and reward.cost >= manager_threshold:
            if not approved_by:
                raise LoyaltyError(
                    f"هذه المكافأة تحتاج اعتماد المدير (الحد {manager_threshold} نقطة)")
            # A SECOND PERSON, NOT A SECOND FIELD.
            #
            # The check was «is this string non-empty», and the string is typed by the person doing
            # the redeeming. So the control read as «type any name to continue» — a manager
            # approval that the operator grants himself, on exactly the redemptions expensive
            # enough to have been worth a threshold.
            #
            # Requiring a DIFFERENT identity is the smallest thing that makes it a control rather
            # than a label. It does not yet prove the approver is a manager — that needs the staff
            # list from operations, and it is written down as the next step — but it does mean the
            # person spending the points is not also the person allowing it.
            if approved_by.strip().casefold() == (actor or "").strip().casefold():
                raise LoyaltyError(
                    "اعتماد المدير لا يكون من الشخص نفسه — أدخل اسم من اعتمدها.")

        rec = Redemption(
            tenant=tenant, subject_ref=subject_ref, reward_id=reward.id,
            # THE SNAPSHOT, not a reference. A receipt that restates itself when the menu changes
            # is not a receipt (see models.Redemption).
            reward_name=reward.name, reward_type=reward.type, cost=reward.cost,
            actor=actor, idem_key=idem_key, channel=channel, branch_id=branch_id,
            discount_halalas=reward.discount_halalas, approved_by=approved_by)

        # The ledger movement is what makes it real; the redemption row is the receipt. The
        # movement is posted FIRST so a crash between the two leaves points deducted with no
        # receipt — recoverable by reading the ledger — rather than a receipt for points still in
        # the account, which reads to the customer as us taking his reward back.
        entry = await self.ledger.post(
            tenant=tenant, subject_ref=subject_ref, delta=-reward.cost, reason="redeem",
            source=source or rec.id, actor=actor, branch_id=branch_id)
        if entry is None:
            # The same source already produced a redeem movement. Not an error — a retry that
            # arrived without its idempotency key, which is exactly what a NAT'd mobile does.
            raise LoyaltyError("تم استبدال هذه العملية مسبقاً")

        await self.store.put(REDEMPTIONS, rec.id, rec.to_dict())
        return rec, True

    async def history(self, tenant: str, subject_ref: str = "", limit: int = 50) -> list[dict]:
        where: dict[str, Any] = {"tenant": tenant}
        if subject_ref:
            where["subject_ref"] = subject_ref
        rows, _ = await self.store.find(REDEMPTIONS, where, limit=limit,
                                        sort=("created_at", "desc"))
        return list(rows or [])


def _row_to_redemption(row: dict) -> Redemption:
    r = Redemption(tenant=row["tenant"], subject_ref=row["subject_ref"],
                   reward_id=row["reward_id"], reward_name=row["reward_name"],
                   reward_type=row["reward_type"], cost=int(row["cost"]),
                   actor=row.get("actor") or "", idem_key=row.get("idem_key") or "",
                   channel=row.get("channel") or "field",
                   branch_id=row.get("branch_id") or "",
                   discount_halalas=int(row.get("discount_halalas") or 0),
                   approved_by=row.get("approved_by") or "")
    r.id = row["id"]
    r.created_at = int(row.get("created_at") or 0)
    return r
