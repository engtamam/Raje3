"""His own texts: what we refuse before Meta does, and what we never take away."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.custom_templates import (APPROVED, CustomTemplateError, CustomTemplateStore,
                                       RETIRED, check, slugify)


def run(c):
    return asyncio.run(c)


@pytest.fixture
def store():
    return CustomTemplateStore(MemoryDataStore())


# ── what we refuse before Meta does ────────────────────────────────────────────────────────────
def test_a_blank_the_trigger_cannot_fill_is_refused_at_writing_time():
    """THE FAILURE THIS EXISTS FOR. A visit confirmation knows the customer and the shop; a text
    asking for a fourth blank renders nothing and fails at send — once, for one shop, weeks after
    Meta approved it."""
    with pytest.raises(CustomTemplateError):
        check("أهلاً {{1}} في {{2}}، خصمك {{3}} برمز {{4}}", "visit_recorded",
              ["customer", "shop", "offer_value", "coupon"])


def test_the_blanks_the_trigger_does_fill_are_accepted():
    assert check("أهلاً {{1}}، حان وقت {{2}} لدى {{3}}.", "service_due",
                 ["customer", "service", "shop"]) == [1, 2, 3]
    # AND HE MAY LEAVE ONE OUT. WhatsApp already shows the sender, so a shop that does not want to
    # name itself writes two blanks — and the meanings travel with the positions, not the numbers.
    assert check("{{1}}، حان وقت {{2}}.", "service_due", ["customer", "service"]) == [1, 2]


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


def test_a_trigger_that_is_not_his_to_reword_refuses():
    with pytest.raises(CustomTemplateError):
        check("رمزك {{3}} يا {{1}} من {{2}}", "privacy_code", ["code", "customer", "shop"])


# ── the name, which he never invents and we never reuse ────────────────────────────────────────
def test_the_name_is_meta_legal_whatever_the_tenant_is_called():
    assert slugify("مغسلة النخيل") == "shop"
    assert slugify("Nakheel Wash-2") == "nakheel_wash_2"


def test_editing_an_approved_text_makes_a_new_name_and_leaves_the_old_one_sending(store):
    """Meta freezes a name at approval and editing it sends it back for review. Reusing it would
    take the shop off the air for a day over one word."""
    first = run(store.draft("t1", trigger_id="service_due", body="حان وقت {{2}} يا {{1}}", fills=["customer", "service"]))
    run(store.mark("t1", first.name, status=APPROVED))

    second = run(store.draft("t1", trigger_id="service_due",
                             body="{{1}}، صارت {{2}} تحتاج مراجعة", fills=["customer", "service"], replaces=first.name))
    assert second.name != first.name and second.version == 2
    # The approved one is untouched until the new one is approved in its turn.
    assert run(store.get("t1", first.name))["status"] == APPROVED


def test_approving_a_new_version_retires_the_old_one_and_never_deletes_it(store):
    first = run(store.draft("t1", trigger_id="service_due", body="حان وقت {{2}} يا {{1}}", fills=["customer", "service"]))
    run(store.mark("t1", first.name, status=APPROVED))
    second = run(store.draft("t1", trigger_id="service_due",
                             body="{{1}}، موعد {{2}} قرُب", fills=["customer", "service"], replaces=first.name))
    run(store.mark("t1", second.name, status=APPROVED))

    assert run(store.get("t1", first.name))["status"] == RETIRED
    assert run(store.get("t1", second.name))["status"] == APPROVED


def test_metas_refusal_is_carried_in_its_own_words(store):
    row = run(store.draft("t1", trigger_id="service_due", body="حان وقت {{2}} يا {{1}}", fills=["customer", "service"]))
    run(store.mark("t1", row.name, status="rejected", reason="INVALID_FORMAT: sample missing"))
    assert "INVALID_FORMAT" in run(store.get("t1", row.name))["reason"]


def test_another_shops_template_is_not_readable_by_name(store):
    """The name is global at Meta and guessable by shape."""
    row = run(store.draft("t1", trigger_id="service_due", body="حان وقت {{2}} يا {{1}}", fills=["customer", "service"]))
    assert run(store.get("t2", row.name)) is None


def test_a_meaning_the_trigger_does_not_know_is_refused():
    """«رمز القسيمة» inside a visit confirmation is a blank nobody can fill."""
    with pytest.raises(CustomTemplateError):
        check("{{1}}، رمزك {{2}}", "visit_recorded", ["customer", "coupon"])


def test_a_meaning_per_blank_is_required():
    with pytest.raises(CustomTemplateError):
        check("{{1}} و{{2}}", "service_due", ["customer"])
