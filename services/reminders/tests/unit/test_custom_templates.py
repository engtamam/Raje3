"""His own texts: what we refuse before Meta does, and what we never take away."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.custom_templates import (APPROVED, CustomTemplateError, CustomTemplateStore,
                                       RETIRED, check, slugify, with_mandatory_tail)


def run(c):
    return asyncio.run(c)


@pytest.fixture
def store():
    return CustomTemplateStore(MemoryDataStore())


# ── what we refuse before Meta does ────────────────────────────────────────────────────────────
def test_a_blank_the_reason_cannot_fill_is_refused_at_writing_time():
    """THE FAILURE THIS EXISTS FOR. A visit confirmation knows the customer and the shop; a text
    asking for a fourth blank renders nothing and fails at send — once, for one shop, weeks after
    Meta approved it."""
    with pytest.raises(CustomTemplateError):
        check("أهلاً {{1}} في {{2}}، خصمك {{3}} برمز {{4}}", "visit_recorded",
              ["customer", "shop", "offer_value", "coupon"])


def test_the_blanks_the_reason_does_fill_are_accepted():
    # EVERY TEXT ENDS WITH THE ADDRESS IT OWES ITS READER, so every body here carries it. The
    # editor never asks him for it — `with_mandatory_tail` puts it there — but `check` is the layer
    # that refuses a body which lost it, so a fixture without it is a shape no draft can have.
    assert check("أهلاً {{1}}، حان وقت {{2}} لدى {{3}}. {{4}}", "service_due",
                 ["customer", "service", "shop", "invite"]) == [1, 2, 3, 4]
    # AND HE MAY LEAVE ONE OUT. WhatsApp already shows the sender, so a shop that does not want to
    # name itself writes two blanks — and the meanings travel with the positions, not the numbers.
    assert check("{{1}}، حان وقت {{2}}. {{3}}", "service_due",
                 ["customer", "service", "invite"]) == [1, 2, 3]


def test_a_numbering_gap_is_refused_because_meta_refuses_it_hours_later():
    with pytest.raises(CustomTemplateError):
        check("أهلاً {{1}} في {{3}}", "service_due", ["customer", "service"])


def test_a_link_is_refused():
    """A link inside a template Meta approved is a carrier for something nobody approved, and it
    goes out under the shop's name against our quality rating."""
    with pytest.raises(CustomTemplateError):
        check("زر موقعنا example.com يا {{1}}", "service_due", ["customer"])


def test_an_empty_text_is_refused():
    with pytest.raises(CustomTemplateError):
        check("   ", "service_due", [])


def test_a_reason_that_is_not_his_to_reword_refuses():
    with pytest.raises(CustomTemplateError):
        check("رمزك {{3}} يا {{1}} من {{2}}", "privacy_code", ["code", "customer", "shop"])


# ── the name, which he never invents and we never reuse ────────────────────────────────────────
def test_the_name_is_meta_legal_whatever_the_tenant_is_called():
    assert slugify("مغسلة النخيل") == "shop"
    assert slugify("Nakheel Wash-2") == "nakheel_wash_2"


def test_editing_an_approved_text_makes_a_new_name_and_leaves_the_old_one_sending(store):
    """Meta freezes a name at approval and editing it sends it back for review. Reusing it would
    take the shop off the air for a day over one word."""
    first = run(store.draft("t1", reason_id="service_due", body="حان وقت {{2}} يا {{1}}", fills=["customer", "service"]))
    run(store.mark("t1", first.name, status=APPROVED))

    second = run(store.draft("t1", reason_id="service_due",
                             body="{{1}}، صارت {{2}} تحتاج مراجعة", fills=["customer", "service"], replaces=first.name))
    assert second.name != first.name and second.version == 2
    # The approved one is untouched until the new one is approved in its turn.
    assert run(store.get("t1", first.name))["status"] == APPROVED


def test_approving_a_new_version_retires_the_old_one_and_never_deletes_it(store):
    first = run(store.draft("t1", reason_id="service_due", body="حان وقت {{2}} يا {{1}}", fills=["customer", "service"]))
    run(store.mark("t1", first.name, status=APPROVED))
    second = run(store.draft("t1", reason_id="service_due",
                             body="{{1}}، موعد {{2}} قرُب", fills=["customer", "service"], replaces=first.name))
    run(store.mark("t1", second.name, status=APPROVED))

    assert run(store.get("t1", first.name))["status"] == RETIRED
    assert run(store.get("t1", second.name))["status"] == APPROVED


def test_metas_refusal_is_carried_in_its_own_words(store):
    row = run(store.draft("t1", reason_id="service_due", body="حان وقت {{2}} يا {{1}}", fills=["customer", "service"]))
    run(store.mark("t1", row.name, status="rejected", reason="INVALID_FORMAT: sample missing"))
    assert "INVALID_FORMAT" in run(store.get("t1", row.name))["reason"]


def test_another_shops_template_is_not_readable_by_name(store):
    """The name is global at Meta and guessable by shape."""
    row = run(store.draft("t1", reason_id="service_due", body="حان وقت {{2}} يا {{1}}", fills=["customer", "service"]))
    assert run(store.get("t2", row.name)) is None


def test_a_meaning_the_reason_does_not_know_is_refused():
    """«رمز القسيمة» inside a visit confirmation is a blank nobody can fill."""
    with pytest.raises(CustomTemplateError):
        check("{{1}}، رمزك {{2}}", "visit_recorded", ["customer", "coupon"])


def test_a_meaning_per_blank_is_required():
    with pytest.raises(CustomTemplateError):
        check("{{1}} و{{2}}", "service_due", ["customer"])


def test_a_second_write_without_naming_the_old_one_destroys_the_approved_text(store):
    """THE PATH THE SCREEN ACTUALLY TAKES, and the two tests above do not take it.

    Both of them pass `replaces=`, so both prove the versioning works — for a caller that names the
    text it is replacing. `TextEditor.tsx` sends `{reason_id, body, fills}` and nothing else. On
    that path `version` stays 1, the name is rebuilt as `{tenant}_{reason_id}_1`, and `put` writes
    over the row already sitting under it.

    So an owner who edits his own approved message DESTROYS it: the text Meta approved is gone from
    the store, replaced by an unapproved draft carrying the name Meta approved. Nothing refuses,
    nothing warns, and the screen says saved.
    """
    first = run(store.draft("t1", reason_id="service_due",
                            body="حان وقت {{2}} يا {{1}}", fills=["customer", "service"]))
    run(store.mark("t1", first.name, status=APPROVED))

    # No `replaces` — exactly what the editor sends.
    second = run(store.draft("t1", reason_id="service_due",
                             body="{{1}}، صارت {{2}} تحتاج مراجعة", fills=["customer", "service"]))

    assert second.name != first.name, (
        "a second write reused the approved name and overwrote the approved row: "
        "the shop's approved text is gone and an unapproved draft now carries its Meta name")
    assert run(store.get("t1", first.name))["status"] == APPROVED


# ── the address he cannot forget, because forgetting is not an option he has ───────────────────
def test_a_marketing_text_that_never_mentioned_a_stop_link_gets_one(store):
    """Tamam's decision: he writes it, Meta approves it under HIS name, the fine lands on HIM.

    So the stop link is not a field he can leave empty. He is never asked for it — the server puts
    it at the end — and PDPL §8.3 is satisfied by a text whose author never thought about PDPL.
    """
    row = run(store.draft("t1", reason_id="gone_missing", cls="marketing",
                          body="اشتقنا لك يا {{1}}! عرض خاص في {{2}}",
                          fills=["customer", "shop"]))
    assert row.fills == ["customer", "shop", "stop_link"]
    assert row.body.rstrip().endswith("{{3}}"), row.body
    assert row.variables == [1, 2, 3]


def test_a_service_text_gets_the_invitation_rather_than_the_stop_link(store):
    """The two are not interchangeable, and the difference is what the message is FOR.

    A utility text that carried a stop link would be offering to stop something the customer never
    started — and it would leave the shop with no door to consent at all, so no campaign it ever
    runs can be lawful. Which one is owed follows from the class alone (`reasons.mandatory_tail`).
    """
    row = run(store.draft("t1", reason_id="service_due",
                          body="{{1}}، حان وقت {{2}}", fills=["customer", "service"]))
    assert row.fills == ["customer", "service", "invite"]


def test_a_text_that_already_ends_with_it_is_not_given_a_second_one(store):
    """Re-saving a draft must not accumulate a link per visit to the editor — the owner would end
    up submitting a text with four identical addresses and Meta would refuse the lot."""
    once = run(store.draft("t1", reason_id="service_due",
                           body="{{1}} {{2}}", fills=["customer", "invite"]))
    assert once.fills == ["customer", "invite"]
    assert once.body == "{{1}} {{2}}", "an untouched body must come back untouched"


def test_a_body_that_lost_its_address_is_refused_rather_than_sent():
    """`with_mandatory_tail` puts it there; this is the layer that notices when something took it
    away again — a migration, a support script, or a hand-edited row."""
    with pytest.raises(CustomTemplateError) as exc:
        check("{{1}}، حان وقت {{2}}", "service_due", ["customer", "service"])
    # AND THE REFUSAL SAYS WHOSE RULE IT IS. «إلزامي» with no reason reads as our bureaucracy, and
    # an owner who thinks a rule is ours argues with it instead of working with it.
    assert "الباب الوحيد لموافقة العميل" in str(exc.value)

    with pytest.raises(CustomTemplateError) as marketing:
        check("عرض {{1}}", "gone_missing", ["customer"], "marketing")
    assert "حماية البيانات" in str(marketing.value)


def test_an_address_in_the_middle_of_the_message_is_refused():
    """Two calls to action competing for one tap, and a link mid-sentence reads as a broken line on
    a phone. `with_mandatory_tail` deliberately does NOT move it — quietly relocating text a shop
    wrote is an edit we never asked permission for, so he is told where it belongs instead."""
    with pytest.raises(CustomTemplateError) as exc:
        check("{{1}} تفضل {{2}} ثم زر {{3}}", "service_due", ["customer", "invite", "service"])
    assert "آخر" in str(exc.value)

    body, fills = with_mandatory_tail("{{1}} تفضل {{2}} ثم زر {{3}}",
                                      ["customer", "invite", "service"], "service")
    assert fills == ["customer", "invite", "service"], "it must not be silently moved or doubled"
