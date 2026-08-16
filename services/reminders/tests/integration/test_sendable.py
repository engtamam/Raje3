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
    def __init__(self, tone):
        self.tone = tone
        self.name = "بنشر النور"
        # The send route refuses outright on an unusable shop — a message with a blank
        # establishment name is worse than a late one.
        self.usable = True


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


def test_a_campaign_send_carries_its_branch_to_the_number_and_the_ledger(client):
    """Two things ride on `branch_id`, and neither had it for a campaign.

    `tick._sending_identity` turns it into `tenant:branch` — the number the message leaves from —
    and the send log records it as the branch that messaged. A chain on a number per branch (§12.4)
    therefore sent every campaign from the CENTRAL number, and «من راسلنا ومن أيّ فرع» had no
    answer for a single campaign message.
    """
    seen: dict = {}

    class Tick:
        async def send_one(self, tenant, schedule, **kw):
            seen.update(schedule)
            return {"sent": True}

    c = client.app.state.container
    c.tick = Tick()
    c.identity = Identity("calm")
    c.library = Library()
    c.approved_templates = Approved({"of_calm"})

    r = client.post("/internal/reminders/send", headers=HEAD, json={
        "tenant": "t-1", "subject_ref": "sub_abcdefgh", "template_type": "mkt_offer",
        "class": "marketing", "owner_text": "خصم", "idempotency_key": "cmp:1:sub_abcdefgh",
        "branch_id": "br_jeddah"})

    assert r.status_code == 200, r.text
    assert seen.get("branch_id") == "br_jeddah", (
        "the schedule reached the tick without a branch — central number, empty ledger row")


def test_the_preview_withholds_whoever_the_send_would_withhold(client, monkeypatch):
    """«so the preview's number is the number that goes out» — the route's own promise, broken.

    `gate.evaluate` decides the holdout from `tenant` + `subject_ref` + the share, and all three
    default to values that fail OPEN. This endpoint passed none of them, so it answered «reachable»
    for the tenth of customers the engine deliberately withholds from — the control group that is
    our only evidence the messages do anything. The owner was shown 340 and the report said 306.
    """
    import asyncio

    from app.config import get_settings
    from app.core import holdout as H

    get_settings.cache_clear()
    monkeypatch.setenv("HOLDOUT_ENABLED", "true")
    monkeypatch.setenv("HOLDOUT_SHARE_PERCENT", "10")
    get_settings.cache_clear()

    c = client.app.state.container
    from app.core.consent import Consent
    tenant = "t-hold"

    # Someone who DID consent — so nothing but the holdout can refuse him.
    held = next(s for s in (f"sub_{n:08d}" for n in range(5000))
                if H.is_holdout(tenant, s, share=10))
    free = next(s for s in (f"sub_{n:08d}" for n in range(5000))
                if not H.is_holdout(tenant, s, share=10))
    from app.core.stores import EngagementStore

    now = 1_800_000_000
    for sub in (held, free):
        asyncio.run(Consent(c.datastore).record(tenant, sub, state="granted",
                                                source="customer_page"))
        # ENGAGED, so nothing but the holdout can refuse either of them. Without this both are on
        # the «minimal» tier and both are refused for the same unrelated reason — a test that would
        # have passed on the broken code and proved nothing.
        asyncio.run(EngagementStore(c.datastore).put(
            tenant, sub, {"score": 100.0, "scored_at": now}))

    def ask(sub):
        return client.post("/internal/reminders/eligibility", headers=HEAD,
                           json={"tenant": tenant, "subject_ref": sub,
                                 "class": "marketing"}).json()

    assert ask(free)["allowed"] is True, f"refused: {ask(free)}"
    assert ask(held)["allowed"] is False, (
        "the preview counted a held-out customer as reachable — the send withholds him, and the "
        "owner is left with an unexplained gap between the two numbers")

    get_settings.cache_clear()
