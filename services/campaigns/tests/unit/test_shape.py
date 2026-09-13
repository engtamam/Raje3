"""What shape a campaign message takes — the booking Flow, or today's plain text.

WHY THE «NO» CASE IS TESTED HARDER THAN THE «YES» CASE. This file adds a field to a path that
already sends real messages to real customers under a shop's own name. The yes case is a new
feature and its worst failure is that it does not work; the no case is EVERY EXISTING SHOP, and its
worst failure is a wire body that changed under them. So the no case asserts absence — the keys are
not there at all — rather than merely asserting they are empty.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import shape
from app.core.audience import Audience, Candidate
from app.core.dispatch import Dispatcher

NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


class Licence:
    """billing's answer, as this service sees it. `answer=False` is a shop that never bought the
    appointment book AND a billing we could not reach — both are «no» and both must behave the
    same, which is what fails-closed means here."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[str] = []

    async def allowed(self, tenant: str) -> bool:
        self.asked.append(tenant)
        return self.answer


class Sender:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send(self, **kw):
        self.calls.append(kw)
        return {"sent": True}


def resolver(*subjects):
    async def _r(campaign, *, already_reached, now):
        return Audience(candidates=[Candidate(subject_ref=s) for s in subjects
                                    if s not in already_reached])
    return _r


def campaign(template_type: str = "mkt_winback") -> dict:
    return {"tenant": "t1", "id": "cmp_1", "template_type": template_type,
            "cls": "marketing", "owner_text": "خصم 20%"}


def fire(template_type="mkt_winback", *, licence=None, subjects=("sub_a",), service_ids=(),
        assistant_licence=None, ai_toggle=None):
    s = Sender()
    d = Dispatcher(store=MemoryDataStore(), sender=s, audience_resolver=resolver(*subjects),
                   bookings_licence=licence, assistant_licence=assistant_licence,
                   ai_toggle=ai_toggle)
    c = campaign(template_type)
    if service_ids:
        c["scope_service_ids"] = list(service_ids)
    run(d.fire(c, now=NOW))
    return s


class Toggle:
    """operations' own ai_toggle.py, as this service sees it."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[str] = []

    async def enabled(self, tenant: str) -> bool:
        self.asked.append(tenant)
        return self.answer


# ── (a) a shop that owns the appointment book ─────────────────────────────────────────────────
def test_a_bookings_shop_gets_a_flow_token_and_the_flows_own_seed():
    s = fire(licence=Licence(True))

    assert len(s.calls) == 1
    call = s.calls[0]
    assert call["flow_token"] == call["idempotency_key"], (
        "the send's own key IS the token — stable across a retry, unique per recipient, and it "
        "needs no store to mint (the weekly report's Flow reuses its key the same way)")
    assert call["flow_action_data"] == {"customer": ""}, (
        "the Flow's seed key is DECLARED here and filled with the resolved phone number inside "
        "reminders' sender — this service holds a pseudonym and must never hold a number")


@pytest.mark.parametrize("template_type", sorted(shape.BOOKING_TYPES))
def test_all_three_texts_that_end_in_come_back_open_the_book(template_type):
    assert fire(template_type, licence=Licence(True)).calls[0]["flow_token"]


def test_a_marketing_text_that_asks_for_nothing_opens_nothing():
    """`mkt_announcement` tells him something; there is nothing to book against it, and putting a
    calendar under «عندنا جديد» is a screen that asks a question the message did not."""
    assert fire("mkt_announcement", licence=Licence(True)).calls[0]["flow_token"] == ""


def test_the_entitlement_is_asked_once_for_the_whole_pass_not_once_per_recipient():
    """A thousand-recipient run must not become a thousand billing calls: the answer is a property
    of the shop and the text, and neither changes between two candidates of one pass."""
    lic = Licence(True)
    fire(licence=lic, subjects=("sub_a", "sub_b", "sub_c"))
    assert lic.asked == ["t1"]


# ── (b) every shop that does not own it — today's send, unchanged ─────────────────────────────
def test_a_shop_without_the_appointment_book_sends_exactly_what_it_sent_before():
    call = fire(licence=Licence(False)).calls[0]
    assert call["flow_token"] == "" and call["flow_action_data"] == {}


def test_a_deployment_with_no_licence_wired_sends_exactly_what_it_sent_before():
    """None is not «yes». A driver that was never configured must not hand every shop on the
    cluster a booking screen it has not bought."""
    call = fire(licence=None).calls[0]
    assert call["flow_token"] == "" and call["flow_action_data"] == {}


def test_a_billing_outage_costs_the_button_and_never_the_message():
    """Every licence in this fleet answers False rather than raising when billing is unreachable,
    so an outage resolves to PLAIN — the message still goes out."""
    s = fire(licence=Licence(False))
    assert len(s.calls) == 1 and s.calls[0]["flow_token"] == ""


# ── the wire body itself: an empty token never reaches reminders ──────────────────────────────
def test_the_peer_client_omits_the_flow_keys_entirely_on_an_ordinary_send():
    """ASSERTED ON THE BODY, not on the parameter. `""` passed to a peer and `""` SENT to a peer
    are different things: the second is a field with no meaning on every message this product has
    ever sent, forever."""
    from app.adapters import peers

    seen: dict = {}

    async def _fake_post(url, body, token, timeout):
        seen.update(body)
        return {"sent": True}

    real = peers._post
    peers._post = _fake_post
    try:
        sender = peers.HttpSender(url="http://reminders.invalid", path="/internal/reminders/send",
                                  token="t" * 40)
        run(sender.send(tenant="t1", subject_ref="sub_a", template_type="mkt_winback",
                        cls="marketing", owner_text="خصم", idempotency_key="cmp:c1:sub_a"))
        assert "flow_token" not in seen and "flow_action_data" not in seen

        seen.clear()
        run(sender.send(tenant="t1", subject_ref="sub_a", template_type="mkt_winback",
                        cls="marketing", owner_text="خصم", idempotency_key="cmp:c1:sub_a",
                        flow_token="cmp:c1:sub_a", flow_action_data={"customer": ""}))
        assert seen["flow_token"] == "cmp:c1:sub_a"
        assert seen["flow_action_data"] == {"customer": ""}
    finally:
        peers._post = real


def test_the_peer_client_carries_the_reward_fields_on_every_send():
    """Unlike `flow_token`/`button_item_id`, these two are ALWAYS on the wire — "discount"/0 is a
    real, meaningful default (today's whole behaviour), not an absent field to omit."""
    from app.adapters import peers

    seen: dict = {}

    async def _fake_post(url, body, token, timeout):
        seen.update(body)
        return {"sent": True}

    real = peers._post
    peers._post = _fake_post
    try:
        sender = peers.HttpSender(url="http://reminders.invalid", path="/internal/reminders/send",
                                  token="t" * 40)
        run(sender.send(tenant="t1", subject_ref="sub_a", template_type="mkt_personal_occasion",
                        cls="marketing", owner_text="", idempotency_key="cmp:c1:sub_a"))
        assert seen["reward_type"] == "discount" and seen["reward_points"] == 0

        seen.clear()
        run(sender.send(tenant="t1", subject_ref="sub_a", template_type="mkt_personal_occasion",
                        cls="marketing", owner_text="", idempotency_key="cmp:c1:sub_a",
                        reward_type="points", reward_points=50))
        assert seen["reward_type"] == "points" and seen["reward_points"] == 50
    finally:
        peers._post = real


# ── the resolver itself, without a dispatcher around it ───────────────────────────────────────
def test_for_send_with_no_key_answers_plain_rather_than_minting_an_empty_token():
    assert shape.for_send(opens_booking=True, idempotency_key="") is shape.PLAIN


def test_plain_is_empty_on_both_fields_and_says_so_about_itself():
    assert shape.PLAIN.flow_token == "" and shape.PLAIN.flow_action_data == {}
    assert shape.PLAIN.opens_booking is False


# ── the Flow's own service pre-seed (2026-09-13) ──────────────────────────────────────────────
def test_for_send_seeds_the_single_scoped_service_into_the_flow():
    result = shape.for_send(opens_booking=True, idempotency_key="k1", card_count=1,
                            item_id="svc_1", kind="service")
    assert result.flow_action_data == {shape.CUSTOMER_SEED: "", shape.SERVICE_SEED: "svc_1"}


def test_for_send_leaves_the_service_unseeded_with_more_than_one_scoped():
    result = shape.for_send(opens_booking=True, idempotency_key="k1", card_count=2, item_id="",
                            kind="service")
    assert result.flow_action_data == {shape.CUSTOMER_SEED: ""}


def test_for_send_leaves_the_service_unseeded_for_a_package_offer():
    """A package_offer's own `item_id` is a package id — meaningless to the booking Flow's
    "service" dimension."""
    result = shape.for_send(opens_booking=True, idempotency_key="k1", card_count=1,
                            item_id="pkg_1", kind="package")
    assert result.flow_action_data == {shape.CUSTOMER_SEED: ""}


def test_for_send_leaves_the_service_unseeded_with_none_scoped_at_all():
    result = shape.for_send(opens_booking=True, idempotency_key="k1")
    assert result.flow_action_data == {shape.CUSTOMER_SEED: ""}


# ── (c) the coupon code, dropped — this service's own half of it ──────────────────────────────
def test_the_owner_is_never_asked_to_fill_a_code_blank_again():
    """`MANUAL_BLANKS` is what the goal cards turn into questions on the campaign screen. A `code`
    left here would draw a field for a value nothing consumes — and the send would then refuse,
    because no template declares that blank any more."""
    from app.core.goals import MANUAL_BLANKS

    assert "code" not in MANUAL_BLANKS


def test_the_peer_client_can_no_longer_carry_a_coupon_code():
    """A parameter that still exists is a parameter somebody still passes, and reminders would
    accept it, store it on the schedule and drop it in silence."""
    import inspect

    from app.adapters.peers import HttpSender

    assert "coupon_code" not in inspect.signature(HttpSender.send).parameters


# ── `_card_button_allowed` (2026-09-13) — a button only where something would answer it ────────
def test_a_shop_with_neither_bookings_nor_the_assistant_gets_no_button():
    s = fire("mkt_offer", licence=Licence(False), service_ids=("svc_1",),
            assistant_licence=Licence(False))
    assert s.calls[0]["button_item_id"] == ""


def test_bookings_alone_is_not_enough_for_the_button():
    s = fire("mkt_offer", licence=Licence(True), service_ids=("svc_1",),
            assistant_licence=Licence(False))
    assert s.calls[0]["button_item_id"] == ""


def test_the_assistant_alone_is_not_enough_for_the_button():
    s = fire("mkt_announcement", licence=Licence(False), service_ids=("svc_1",),
            assistant_licence=Licence(True), ai_toggle=Toggle(True))
    assert s.calls[0]["button_item_id"] == ""


def test_bought_the_assistant_but_switched_it_off_still_gets_no_button():
    s = fire("mkt_announcement", licence=Licence(True), service_ids=("svc_1",),
            assistant_licence=Licence(True), ai_toggle=Toggle(False))
    assert s.calls[0]["button_item_id"] == ""


def test_bookings_and_a_live_assistant_together_get_the_button():
    s = fire("mkt_announcement", licence=Licence(True), service_ids=("svc_1",),
            assistant_licence=Licence(True), ai_toggle=Toggle(True))
    assert s.calls[0]["button_item_id"] == "svc_1"


def test_no_ai_toggle_wired_defaults_to_on_once_both_licences_answer_yes():
    """A deployment that has not wired the toggle peer at all (operations unreachable/unconfigured)
    resolves to today's behaviour for a shop that owns both apps — never a silent button removal
    for a switch nobody could have touched yet."""
    s = fire("mkt_announcement", licence=Licence(True), service_ids=("svc_1",),
            assistant_licence=Licence(True), ai_toggle=None)
    assert s.calls[0]["button_item_id"] == "svc_1"


def test_neither_licence_wired_at_all_defaults_to_no_button():
    """Same "unwired resolves to the safe answer" rule `bookings_licence=None` already takes for
    `opens_booking_for` — a button this service cannot verify is safe must not be offered."""
    s = fire("mkt_announcement", licence=None, service_ids=("svc_1",), assistant_licence=None)
    assert s.calls[0]["button_item_id"] == ""


def test_the_button_decision_is_asked_once_per_pass_not_once_per_recipient():
    s = fire("mkt_announcement", licence=Licence(True), service_ids=("svc_1",),
            assistant_licence=Licence(True), ai_toggle=Toggle(True), subjects=("a", "b", "c"))
    assert len(s.calls) == 3
    assert all(c["button_item_id"] == "svc_1" for c in s.calls)


def test_the_peer_client_omits_the_button_keys_entirely_on_an_ordinary_send():
    from app.adapters import peers

    seen: dict = {}

    async def _fake_post(url, body, token, timeout):
        seen.update(body)
        return {"sent": True}

    real = peers._post
    peers._post = _fake_post
    try:
        sender = peers.HttpSender(url="http://reminders.invalid", path="/internal/reminders/send",
                                  token="t" * 40)
        run(sender.send(tenant="t1", subject_ref="sub_a", template_type="mkt_offer",
                        cls="marketing", owner_text="خصم", idempotency_key="cmp:c1:sub_a"))
        assert "button_item_id" not in seen and "button_kind" not in seen

        seen.clear()
        run(sender.send(tenant="t1", subject_ref="sub_a", template_type="mkt_announcement",
                        cls="marketing", owner_text="", idempotency_key="cmp:c1:sub_a",
                        button_item_id="svc_1", button_kind="package"))
        assert seen["button_item_id"] == "svc_1"
        assert seen["button_kind"] == "package"
    finally:
        peers._post = real


# ── the single-item quick-reply button on the three NON-booking types (2026-09-13) ─────────────
def test_a_single_item_on_a_non_booking_type_gets_the_unified_button():
    s = fire("mkt_announcement", licence=Licence(True), service_ids=("svc_1",),
            assistant_licence=Licence(True), ai_toggle=Toggle(True))
    call = s.calls[0]
    assert call["button_item_id"] == "svc_1"
    assert call["button_kind"] == "service"
    assert call["flow_token"] == ""


def test_the_same_case_reaches_mkt_loyalty_activation_too():
    s = fire("mkt_loyalty_activation", licence=Licence(True), service_ids=("pkg_1",),
            assistant_licence=Licence(True), ai_toggle=Toggle(True))
    call = s.calls[0]
    assert call["button_item_id"] == "pkg_1"


def test_a_single_item_with_no_button_capability_gets_no_button():
    """A shop without bookings+assistant+AI-on gets the exact same message it always has — no
    button, never a broken promise."""
    s = fire("mkt_announcement", licence=None, service_ids=("svc_1",))
    call = s.calls[0]
    assert call["button_item_id"] == ""


def test_zero_items_on_a_non_booking_type_still_gets_no_button():
    """Card-button capability alone is not enough — there must be exactly one item attached."""
    s = fire("mkt_announcement", licence=Licence(True), service_ids=(),
            assistant_licence=Licence(True), ai_toggle=Toggle(True))
    call = s.calls[0]
    assert call["button_item_id"] == ""


def test_a_booking_type_with_bookings_owned_keeps_opening_the_flow_not_the_button():
    """The owner's own instruction: Flow stays the richer, preferred experience for the three
    "come back" types — the quick-reply button is for the OTHER three, never a replacement here."""
    s = fire("mkt_offer", licence=Licence(True), service_ids=("svc_1",),
            assistant_licence=Licence(True), ai_toggle=Toggle(True))
    call = s.calls[0]
    assert call["flow_token"] != ""
    assert call["button_item_id"] == ""


def test_for_send_directly_returns_the_button_shape():
    result = shape.for_send(opens_booking=False, idempotency_key="k1",
                            template_type="mkt_announcement", card_count=1,
                            item_id="svc_9", kind="package", card_button_allowed=True)
    assert result.button_item_id == "svc_9" and result.button_kind == "package"
    assert result.flow_token == ""


def test_for_send_refuses_the_button_without_card_button_allowed():
    result = shape.for_send(opens_booking=False, idempotency_key="k1",
                            template_type="mkt_announcement", card_count=1,
                            item_id="svc_9", card_button_allowed=False)
    assert result.button_item_id == ""
