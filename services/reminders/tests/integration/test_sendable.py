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
    {"name": "wb_masculine", "type": "mkt_winback", "tone": "masculine", "active": True},
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
    async def statuses(self, tenant): return {n: "approved" for n in self._names}


def _wire(client, *, tone, approved):
    c = client.app.state.container
    c.library = Library()
    c.identity = Identity(tone)
    c.approved_templates = Approved(approved)
    return c


def test_the_shop_s_own_tone_is_what_it_gets(client):
    _wire(client, tone="masculine", approved={"wb_calm", "wb_masculine", "of_calm"})
    body = client.get("/internal/reminders/sendable?tenant=t-1", headers=HEAD).json()
    assert body["templates"]["mkt_winback"]["name"] == "wb_masculine"
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


def test_statuses_carries_one_word_per_type_for_campaigns_own_goal_cards(client):
    """The badge campaigns' own goal cards show — a status per TYPE, not per registered name, so
    a type with one tone approved (`wb_masculine`) and the other never even registered (`wb_calm`
    absent from this fake's own approved set) still reads as usable overall — the same "best
    tone wins" reasoning `choose()` itself already applies to picking which one to send."""
    _wire(client, tone="masculine", approved={"wb_masculine"})
    body = client.get("/internal/reminders/sendable?tenant=t-1", headers=HEAD).json()
    assert body["statuses"]["mkt_winback"] == "approved"
    # `of_calm` (mkt_offer's only registered name here) is not in the approved set at all —
    # the fake's own `statuses()` never mentions it, so the type reads as never submitted.
    assert body["statuses"]["mkt_offer"] == "not_registered"


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


def test_a_campaign_send_is_isolated_per_tenant(client):
    """`tenant` is a plain body field on this internal-token route, never a verified claim (see
    any internal.py's own header note) — a call for one shop must carry ITS OWN tenant through to
    the send, never a value left over from a call made moments before for a different one."""
    seen_calls: list[dict] = []

    class Tick:
        async def send_one(self, tenant, schedule, **kw):
            seen_calls.append(schedule)
            return {"sent": True}

    c = client.app.state.container
    c.tick = Tick()
    c.identity = Identity("calm")
    c.library = Library()
    c.approved_templates = Approved({"of_calm"})

    client.post("/internal/reminders/send", headers=HEAD, json={
        "tenant": "tnt_send_iso_a", "subject_ref": "sub_abcdefgh", "template_type": "mkt_offer",
        "class": "marketing", "owner_text": "خصم", "idempotency_key": "cmp:a:sub_abcdefgh"})
    client.post("/internal/reminders/send", headers=HEAD, json={
        "tenant": "tnt_send_iso_b", "subject_ref": "sub_abcdefgh", "template_type": "mkt_offer",
        "class": "marketing", "owner_text": "خصم", "idempotency_key": "cmp:b:sub_abcdefgh"})

    assert [s["tenant"] for s in seen_calls] == ["tnt_send_iso_a", "tnt_send_iso_b"]


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

    # THE CLOCK IS PINNED, and this test taught us why the hard way: the route asks the gate
    # «right now», the gate refuses marketing inside quiet hours, and the suite therefore
    # passed all day and failed after ten at night. A test whose answer depends on when it is
    # run reports the codebase's health as a function of the hour.
    import time as _time

    from datetime import datetime
    from app.core.gate import RIYADH

    midday = int(datetime(2026, 6, 15, 12, tzinfo=RIYADH).timestamp())
    monkeypatch.setattr(_time, "time", lambda: float(midday))

    def ask(sub):
        return client.post("/internal/reminders/eligibility", headers=HEAD,
                           json={"tenant": tenant, "subject_ref": sub,
                                 "class": "marketing"}).json()

    assert ask(free)["allowed"] is True, f"refused: {ask(free)}"
    assert ask(held)["allowed"] is False, (
        "the preview counted a held-out customer as reachable — the send withholds him, and the "
        "owner is left with an unexplained gap between the two numbers")

    get_settings.cache_clear()


def test_an_offer_campaign_with_no_free_line_still_carries_an_entitlement(client):
    """أ-6 · THE WIRING, at the route.

    `offer_text` on the send log IS the entitlement — the till, `choose_offer` and the customer's
    page all skip a row whose text is blank — and this route used to take it from the owner's free
    line alone. The three offer templates declare no `owner` fill, so that line does not exist for
    the ordinary offer campaign: four hundred correct messages went out, and every one of them
    left nothing to honour.
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
        "class": "marketing", "owner_text": "", "idempotency_key": "cmp:2:sub_abcdefgh",
        "offer_expires_at": 2_000_000_000, "offer_value": "20%",
        "offer_services": ["svc_1"], "service_names": ["غسيل خارجي"]})

    assert r.status_code == 200, r.text
    assert seen["offer_text"] == "خصم 20% على غسيل خارجي"


def test_the_owners_line_still_wins_at_the_route(client):
    """It is what the customer read. A different sentence at the counter is how one offer becomes
    an argument about two."""
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
        "class": "marketing", "owner_text": "لك غسلة مجانية",
        "idempotency_key": "cmp:3:sub_abcdefgh", "offer_expires_at": 2_000_000_000,
        "offer_value": "20%"})

    assert r.status_code == 200, r.text
    assert seen["offer_text"] == "لك غسلة مجانية"


# ── the report Flow's own button (rating-app-feature.md phase 6b) ──────────────────────────────
def test_a_send_with_no_flow_fields_carries_none_through(client):
    """Every existing caller (campaigns never opens a Flow) must get byte-identical behaviour —
    an absent flow_token/flow_action_data on the request must arrive as empty on the schedule."""
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
        "class": "marketing", "owner_text": "خصم", "idempotency_key": "cmp:4:sub_abcdefgh"})

    assert r.status_code == 200, r.text
    assert seen.get("flow_token") == ""
    assert seen.get("flow_action_data") == {}


def test_a_report_sends_flow_token_and_flow_action_data_through_to_the_schedule(client):
    """The rating request is one caller that DOES open a Flow — its flow_token and the rating
    screen's data must reach `send_one`'s schedule dict unchanged."""
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
        "tenant": "t-1", "subject_ref": "sub_abcdefgh", "template_type": "svc_visit_confirmation_rating",
        "class": "service", "owner_text": "زيارتك في مغسلة النخيل",
        "idempotency_key": "reminders:rating:t-1:sub_abcdefgh:2900",
        "flow_token": "reminders:rating:t-1:sub_abcdefgh:2900",
        "flow_action_data": {"header_text": "زيارتك في مغسلة النخيل", "show_visits": True,
                             "visits_text": "120 (+15)"}})

    assert r.status_code == 200, r.text
    assert seen["flow_token"] == "reminders:rating:t-1:sub_abcdefgh:2900"
    assert seen["flow_action_data"]["show_visits"] is True
    assert seen["flow_action_data"]["visits_text"] == "120 (+15)"


def test_campaign_id_reaches_the_schedule_dict_the_send_log_stamps_from(client):
    """2026-09-14 (till-integration audit follow-up): the send log used to carry an offer's
    WORDS with no way to say which campaign produced them, so a shop applying an offer at the
    till could never learn "the win-back campaign worked". The route must forward `campaign_id`
    into the schedule dict `send_one` builds its log row from."""
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
        "class": "marketing", "owner_text": "", "idempotency_key": "cmp:9:sub_abcdefgh",
        "offer_expires_at": 2_000_000_000, "offer_value": "20%",
        "offer_services": ["svc_1"], "service_names": ["غسيل خارجي"],
        "campaign_id": "cmp_win_back_1"})

    assert r.status_code == 200, r.text
    assert seen["campaign_id"] == "cmp_win_back_1"
