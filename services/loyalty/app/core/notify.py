"""What the customer is told, and the message we deliberately do not send.

THE REDEMPTION RECEIPT IS THE POINT OF THIS FILE (spec §9.6). Its purpose is not to inform — it is
to be un-forgeable. An operator redeeming a customer's balance for himself or a friend is caught
within seconds, because the only person who reliably notices a balance being spent is the person
whose balance it was. Without the message it surfaces months later, when someone asks about points
that vanished, and by then it is one person's word against another's and the trail is cold.

It is a PERSONAL message (spec §8.4.1): it arises from the customer's own action, so it reaches
those who stopped marketing, is exempt from the quiet hours, and is not counted against the message
cap. All three of those are properties the gate already knows about `per_account_notice` — we ask
and it decides. This file does not implement a single exemption, and that is the design.

EARNING GETS NO MESSAGE OF ITS OWN. It rides in the thank-you the reminders service already sends
after a service. Two messages for one visit is an annoyance we would be manufacturing ourselves,
and this product's entire discipline is about not doing that. So `earn_variables()` returns text
for somebody else's message rather than sending one.

AFTER THE COMMIT, ALWAYS. Every function here is called once the points have already moved. A
receipt for a redemption that then failed to commit is worse than no receipt: the customer holds
proof of a spend that did not happen, and his balance disagrees with it.
"""
from __future__ import annotations

from typing import Any

# The template types. Both already exist in the library (spec §8.4.1) — we are not inventing
# message classes here, we are naming the two this service uses.
RECEIPT = "per_account_notice"      # personal: the customer's own action
WARNING = "per_points_expiring"     # service: preventing a loss, not selling anything


def receipt_text(*, reward_name: str, cost: int, remaining: int) -> str:
    """The body of the redemption receipt.

    THREE FACTS AND NOTHING ELSE: what he got, what it cost, what is left. The third is what makes
    it auditable — a receipt without the remaining balance tells him a spend happened but not
    whether the arithmetic was right.

    Western digits throughout, like everywhere else in this product.
    """
    return f"تم استبدال {cost} نقطة مقابل {reward_name}. رصيدك المتبقي: {remaining} نقطة."


def warning_text(*, points: int, days: int) -> str:
    return f"رصيدك {points} نقطة سينتهي خلال {days} يوم. زُرنا لتستفيد منه."


def earn_variables(*, points: int, balance: int, to_next: int = 0) -> dict[str, Any]:
    """What the thank-you message says about points — NOT a message of its own.

    Returned as data for the sender of the after-service message to fold in. `to_next` is omitted
    when the shop has no reward the customer is short of, because "0 points to your next reward"
    is a sentence that means nothing to the person reading it.
    """
    out: dict[str, Any] = {"points_added": points, "balance": balance}
    if to_next > 0:
        out["to_next_reward"] = to_next
    return out


def to_next_reward(balance: int, costs: list[int]) -> int:
    """How far to the cheapest reward he cannot yet afford. Zero when he can afford everything, or
    when the shop has no rewards at all — both of which are "say nothing", not "say zero"."""
    ahead = sorted(c for c in costs if c > balance)
    return (ahead[0] - balance) if ahead else 0


class Notifier:
    """Sends through reminders' gate. Never around it."""

    def __init__(self, sender: Any) -> None:
        self.sender = sender

    async def receipt(self, *, tenant: str, subject_ref: str, redemption_id: str,
                      reward_name: str, cost: int, remaining: int) -> dict:
        return await self.sender.send(
            tenant=tenant, subject_ref=subject_ref, template_type=RECEIPT, cls="personal",
            owner_text=receipt_text(reward_name=reward_name, cost=cost, remaining=remaining),
            # The redemption's id: one receipt per redemption, however many times a retry asks.
            idempotency_key=f"loyalty:receipt:{redemption_id}")

    async def expiry_warning(self, *, tenant: str, subject_ref: str, points: int,
                             days: int, cycle_key: str) -> dict:
        return await self.sender.send(
            tenant=tenant, subject_ref=subject_ref, template_type=WARNING, cls="service",
            owner_text=warning_text(points=points, days=days),
            idempotency_key=f"loyalty:expiring:{cycle_key}")
