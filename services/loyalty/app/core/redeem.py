"""Spending points — one path for the field, the panel and the till.

THE OPERATOR SPENDS, NOT A MANAGER (spec §9.5). A manager signing off every redemption is a
bottleneck in a busy shop, and the outcome is not a controlled programme but an unused one. The
control is a trail rather than a gate, in two parts:

  1. every redemption is attributed to the account that performed it (spec §3.5 — from the session;
     there is no PIN in this product),
  2. the customer gets an instant receipt (`notify.py`) — which is the real audit, because the only
     person who reliably notices a balance being spent is the person whose balance it was.

THE SAME FUNCTION SERVES ALL THREE CHANNELS. The till's redemption (spec §9.8) and the panel
fallback for tills that cannot be modified must produce IDENTICAL ledger entries — same shape, same
attribution, same customer message. A fallback that records differently is a reporting bug waiting
for month end, and it would be discovered by an owner reconciling two numbers that should match.

MESSAGE AFTER COMMIT, ALWAYS. The receipt is sent by the caller AFTER this returns, never inside.
A message announcing a redemption that then failed to commit is worse than no message: the customer
has a receipt for points he still has, and the next thing he does is ask why his balance is wrong.
"""
from __future__ import annotations

import hashlib
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
                branch_id=branch_id, source=source)

    async def _redeem_locked(self, tenant: str, subject_ref: str, reward_id: str, *,
                             actor: str, idem_key: str, channel: str, branch_id: str,
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

        rec = Redemption(
            tenant=tenant, subject_ref=subject_ref, reward_id=reward.id,
            # THE SNAPSHOT, not a reference. A receipt that restates itself when the menu changes
            # is not a receipt (see models.Redemption).
            reward_name=reward.name, reward_type=reward.type, cost=reward.cost,
            actor=actor, idem_key=idem_key, channel=channel, branch_id=branch_id,
            discount_halalas=reward.discount_halalas)

        # The ledger movement is what makes it real; the redemption row is the receipt. The
        # movement is posted FIRST so a crash between the two leaves points deducted with no
        # receipt — recoverable by reading the ledger — rather than a receipt for points still in
        # the account, which reads to the customer as us taking his reward back.
        #
        # THE CAUSE IS DERIVED FROM THE IDEMPOTENCY KEY, NOT FROM A FRESH UUID.
        #
        # THE DOUBLE DEDUCTION THIS CLOSES. Retries were guarded by `_existing()`, which reads
        # REDEMPTIONS — the receipt, written LAST. A crash between the ledger post and that write
        # left points deducted with no receipt, so the retry found nothing, walked straight past
        # every check, and posted again. And the ledger could not catch it either: `source` was
        # `rec.id`, a NEW uuid on every attempt, so `already_posted` compared two different causes
        # and said no. The guard below was therefore DEAD CODE on the field path — it could only
        # fire for a caller that passed an explicit `source`, and the till is the only one that
        # does.
        #
        # `SpendLock` did not save it: fifteen seconds, and the retry that matters is the one after
        # a timeout, which arrives later than that by definition.
        #
        # Deriving the cause from `(tenant, idem_key)` makes the LEDGER the thing that deduplicates
        # — the store that holds the money, rather than the receipt written after it. Same key,
        # same cause, second post refused, whatever crashed in between.
        #
        # AND THE RECONCILER WAS CEMENTING IT. `/platform/reconcile` resets a balance to the sum of
        # the ledger, and the ledger held both deductions — so the one tool that exists to correct
        # drift was ratifying it as truth. That is worse than the defect: a wrong number somebody
        # audited.
        #
        # AND NO FALLBACK, BECAUSE A FALLBACK IS THE HOLE ITSELF. `or rec.id` would restore exactly
        # what this fixes for the one caller that sends neither — a deduction nothing can ever
        # deduplicate. Both callers (the field route and the till) send an idempotency key today,
        # so this refuses a case that does not occur; and the day somebody adds a third caller, the
        # refusal is a 400 at the door rather than a customer charged twice on a bad connection.
        cause = source or _cause(tenant, idem_key)
        if not cause:
            raise LoyaltyError(
                "لا يمكن تنفيذ الاستبدال بلا مفتاح تكرار — أعد المحاولة من الشاشة.")

        entry = await self.ledger.post(
            tenant=tenant, subject_ref=subject_ref, delta=-reward.cost, reason="redeem",
            source=cause, actor=actor, branch_id=branch_id)
        # THE RECEIPT IS WRITTEN EITHER WAY, and that is the whole recovery. `entry is None` now
        # means «the points already went out on an earlier attempt» — the case this fix creates —
        # and the customer is owed a record of a reward he was handed. Refusing here would leave
        # him permanently short with nothing to point at.
        #
        # `is_new` is what tells the caller not to send a second confirmation for one redemption.
        await self.store.put(REDEMPTIONS, rec.id, rec.to_dict())
        return rec, entry is not None

    async def history(self, tenant: str, subject_ref: str = "", limit: int = 50) -> list[dict]:
        where: dict[str, Any] = {"tenant": tenant}
        if subject_ref:
            where["subject_ref"] = subject_ref
        rows, _ = await self.store.find(REDEMPTIONS, where, limit=limit,
                                        sort=("created_at", "desc"))
        return list(rows or [])


def _cause(tenant: str, idem_key: str) -> str:
    """The ledger's idempotency key for a redemption, stable across retries.

    Hashed rather than concatenated so the value is a fixed length whatever the caller sends, and
    so a key that happens to contain the separator cannot be made to collide with another tenant's.
    Empty when there is no idempotency key — a caller that sends none is asking for a new movement
    every time, and pretending otherwise would silently merge two genuine redemptions.
    """
    if not idem_key:
        return ""
    return "rdm_" + hashlib.sha256(f"{tenant}|{idem_key}".encode("utf-8")).hexdigest()[:32]


def _row_to_redemption(row: dict) -> Redemption:
    r = Redemption(tenant=row["tenant"], subject_ref=row["subject_ref"],
                   reward_id=row["reward_id"], reward_name=row["reward_name"],
                   reward_type=row["reward_type"], cost=int(row["cost"]),
                   actor=row.get("actor") or "", idem_key=row.get("idem_key") or "",
                   channel=row.get("channel") or "field",
                   branch_id=row.get("branch_id") or "",
                   discount_halalas=int(row.get("discount_halalas") or 0),
                   # ABSENT MEANS NOT DONE (ز-9), which is the safe reading: rows written before
                   # this field existed get replayed once, and the far door is idempotent on
                   # `source=rec.id`, so a replay of a visit that did land is a no-op.
                   visit_recorded=bool(row.get("visit_recorded")))
    r.id = row["id"]
    r.created_at = int(row.get("created_at") or 0)
    return r
