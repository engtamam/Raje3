"""«أي قالب يرسله هذا المحل فعلاً» — the answer campaigns used to guess.

Its template peer took a tenant and threw it away: one process-wide copy of the platform library,
answered from the first row of the matching type. Three per-shop facts were missing — the tone,
Meta's per-account approval, and the owner's own re-written text — from a call whose docstring
promised all three. The preview showed one wording and the customer received another, and a goal
card read «متاح» for a shop whose whole library was still under review.
"""
from __future__ import annotations

from tests.conftest import INTERNAL_TOKEN

HEAD = {"X-Internal-Token": INTERNAL_TOKEN}

LIBRARY = [
    {"name": "wb_calm", "type": "mkt_winback", "tone": "calm", "active": True},
    {"name": "wb_warm", "type": "mkt_winback", "tone": "warm", "active": True},
    {"name": "of_calm", "type": "mkt_offer", "tone": "calm", "active": True},
]


class Library:
    async def all(self):
        return list(LIBRARY)


class Shop:
    def __init__(self, tone): self.tone = tone; self.name = "بنشر النور"


class Identity:
    def __init__(self, tone): self._tone = tone
    async def get(self, tenant): return Shop(self._tone)


class Approved:
    def __init__(self, names): self._names = names
    async def names(self, tenant): return set(self._names)


def _wire(client, *, tone, approved):
    c = client.app.state.container
    c.library = Library()
    c.identity = Identity(tone)
    c.approved_templates = Approved(approved)
    return c


def test_the_shop_s_own_tone_is_what_it_gets(client):
    _wire(client, tone="warm", approved={"wb_calm", "wb_warm", "of_calm"})
    body = client.get("/internal/reminders/sendable?tenant=t-1", headers=HEAD).json()
    assert body["templates"]["mkt_winback"]["name"] == "wb_warm"
    assert set(body["types"]) == {"mkt_winback", "mkt_offer"}


def test_a_template_meta_has_not_approved_for_THIS_shop_is_not_offered(client):
    """The failure the owner could do nothing about.

    A goal card that reads «متاح» while the shop's library is under review invites a launch whose
    every recipient fails at the delivery layer — one wasted phone resolution each, and a run
    report full of a refusal he cannot act on.
    """
    _wire(client, tone="calm", approved={"wb_calm"})
    body = client.get("/internal/reminders/sendable?tenant=t-1", headers=HEAD).json()

    assert body["types"] == ["mkt_winback"], "an unapproved type was offered as available"
    # AND THE REASON IS CARRIED, because «قيد المراجعة» resolves itself in an hour and «لا يوجد
    # قالب» is ours to fix. One sentence for both sends him to support for neither.
    assert "mkt_offer" in body["blocked"]
    assert "مراجعة" in body["blocked"]["mkt_offer"]


def test_nothing_approved_is_an_empty_answer_not_a_full_one(client):
    _wire(client, tone="calm", approved=set())
    body = client.get("/internal/reminders/sendable?tenant=t-1", headers=HEAD).json()
    assert body["templates"] == {} and body["count"] == 0
    assert set(body["blocked"]) == {"mkt_winback", "mkt_offer"}


def test_it_is_internal_only(client):
    assert client.get("/internal/reminders/sendable?tenant=t-1").status_code == 401
