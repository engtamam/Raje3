"""The one message a redemption produces — and the rule that it is usually not its own.

The file did not exist before this: `Notifier` was covered only where other tests happened to
touch it, which is how a seam that sends a SECOND message to every customer survived unremarked.
"""
from __future__ import annotations

import pytest

from app.core.notify import Notifier


class _MergingSender:
    """Reminders, with a confirmation already waiting."""

    def __init__(self, merges: bool):
        self.merges = merges
        self.sent: list[dict] = []
        self.merged: list[dict] = []

    async def merge_redemption(self, **kw):
        self.merged.append(kw)
        return self.merges

    async def send(self, **kw):
        self.sent.append(kw)
        return {"sent": True}


@pytest.mark.asyncio
async def test_a_redemption_joins_the_confirmation_instead_of_sending_a_second_message():
    """THE OWNER'S RULE (§9.6): «ما نرسل رسايل كثير». A redemption at the counter happens inside
    the ten minutes the confirmation is deliberately waiting, so the two are one moment."""
    sender = _MergingSender(merges=True)
    out = await Notifier(sender).receipt(
        tenant="t1", subject_ref="sub_a", redemption_id="r1",
        reward_name="غسلة مجانية", cost=100, remaining=37)

    assert out["merged"] is True
    assert sender.sent == []          # nothing of its own went out
    assert sender.merged[0]["reward_name"] == "غسلة مجانية"


@pytest.mark.asyncio
async def test_with_nothing_to_join_it_still_tells_him_what_he_spent():
    """A redemption with no visit behind it — the owner correcting something, a portal redemption.
    Silence there is worse than a second message: he spent points and would hear nothing."""
    sender = _MergingSender(merges=False)
    await Notifier(sender).receipt(
        tenant="t1", subject_ref="sub_a", redemption_id="r1",
        reward_name="غسلة مجانية", cost=100, remaining=37)

    assert len(sender.sent) == 1
    assert "غسلة مجانية" in sender.sent[0]["owner_text"]
