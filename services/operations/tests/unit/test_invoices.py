"""Invoice lines to services — where product_id decides and text never does."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import invoices as I
from app.core.models import Service
from app.core.stores import ServiceStore, new_id

NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


@pytest.fixture
def store():
    return ServiceStore(MemoryDataStore())


def resolve(store, lines, **kw):
    return run(I.resolve(I.parse_lines(lines), tenant="t1", service_store=store,
                         new_id=new_id, now=NOW, **kw))


# ── normalisation: the type change nobody announces ────────────────────────────────────────────
def test_an_id_sent_as_a_number_and_as_a_string_is_one_product():
    """A partner changes a serialiser and the owner sees the duplicate long before anyone finds
    the type change."""
    assert I.normalise_id(4471) == I.normalise_id("4471") == "4471"
    assert I.normalise_id(4471.0) == "4471"


def test_a_boolean_is_never_a_product_id():
    assert I.normalise_id(True) == "" and I.normalise_id(False) == ""


def test_whitespace_in_a_name_is_collapsed_and_nothing_else_is_touched():
    """Quietly rewriting this text produces a catalogue the owner does not recognise as theirs."""
    assert I.normalise_name("  قص   شعر  ") == "قص شعر"


# ── the boundary ───────────────────────────────────────────────────────────────────────────────
def test_a_line_with_an_id_becomes_a_real_service(store):
    res = resolve(store, [{"product_id": "P1", "name": "قص شعر"}])
    assert len(res.created_services) == 1 and len(res.service_ids) == 1
    svc = run(store.by_external_id("t1", "P1"))
    assert svc.name == "قص شعر"


def test_a_line_without_an_id_creates_nothing(store):
    """'Extra cheese' is not something anyone should be reminded about."""
    res = resolve(store, [{"name": "إضافة جبنة"}])
    assert res.created_services == [] and res.service_ids == []
    assert res.free_text == ["إضافة جبنة"]


def test_a_shared_free_item_id_is_treated_as_no_id(store):
    """Taking it at face value creates one bogus service that then accumulates every free item a
    cashier ever types."""
    res = resolve(store, [{"product_id": "0", "name": "خدمة إضافية"},
                          {"product_id": "custom", "name": "شيء آخر"}])
    assert res.created_services == [] and len(res.free_text) == 2


def test_an_auto_created_service_has_no_cycle(store):
    """A default of 90 days on a coffee is a reminder that reads as nonsense. The adaptive engine
    learns the real rhythm; until then the service simply schedules nothing."""
    resolve(store, [{"product_id": "P9", "name": "قهوة"}])
    assert run(store.by_external_id("t1", "P9")).cycle_days == 0


# ── the three field failures ───────────────────────────────────────────────────────────────────
def test_a_renamed_product_updates_and_never_forks(store):
    """Forking would double the catalogue every time a shop tidies its wording."""
    resolve(store, [{"product_id": "P1", "name": "قص شعر"}])
    res = resolve(store, [{"product_id": "P1", "name": "قص شعر والفلتر"}])
    assert res.created_services == [] and len(res.renamed_services) == 1
    assert len(run(store.list("t1", active_only=False))) == 1
    assert run(store.by_external_id("t1", "P1")).name == "قص شعر والفلتر"


def test_a_shop_that_went_manual_first_adopts_its_tills_id(store):
    """It has the service typed by hand months ago. A second row would split the visit history."""
    run(store.save(Service(id=new_id("srv"), tenant="t1", name="قص شعر",
                           cycle_days=90, created=NOW)))
    res = resolve(store, [{"product_id": "P1", "name": "قص شعر"}])
    assert res.created_services == []
    assert len(run(store.list("t1", active_only=False))) == 1
    adopted = run(store.by_external_id("t1", "P1"))
    # AND IT KEEPS THE CYCLE THE OWNER SET. Adopting must not reset what a person decided.
    assert adopted.cycle_days == 90


def test_the_same_product_twice_in_one_invoice_resolves_once_per_line(store):
    res = resolve(store, [{"product_id": "P1", "name": "غسيل"},
                          {"product_id": "P1", "name": "غسيل"}])
    assert len(res.created_services) == 1 and len(res.service_ids) == 2


# ── never fail the invoice ─────────────────────────────────────────────────────────────────────
def test_a_malformed_line_becomes_free_text_rather_than_an_error(store):
    """The till has already taken the customer's money. The visit must be recorded."""
    lines = I.parse_lines(["not a dict", {"product_id": None, "name": "شيء"}, {}, None])
    assert len(lines) == 1 and not lines[0].is_defined


def test_auto_create_off_sends_everything_to_free_text(store):
    res = resolve(store, [{"product_id": "P1", "name": "قص شعر"}], auto_create=False)
    assert res.created_services == [] and res.free_text == ["قص شعر"]


def test_one_tenants_catalogue_is_never_touched_by_another(store):
    """The catalogue is a per-tenant COPY, which is what makes auto-creation safe at all."""
    resolve(store, [{"product_id": "P1", "name": "قص شعر"}])
    run(I.resolve(I.parse_lines([{"product_id": "P1", "name": "شيء مختلف"}]),
                  tenant="t2", service_store=store, new_id=new_id, now=NOW))
    assert run(store.by_external_id("t1", "P1")).name == "قص شعر"
    assert len(run(store.list("t2", active_only=False))) == 1


# ── the integrated establishment ───────────────────────────────────────────────────────────────
#
# THE SEEDING TESTS THAT LIVED HERE ARE GONE WITH THE THING THEY TESTED. A shop's catalogue used to
# be copied from the trade its owner picked at signup — a whole trade for a manual shop, the
# catch-all alone for an integrated one. Nothing is seeded now: every shop starts empty and writes
# what it sells, so «how many rows does a new shop get» has one answer for everybody, which is
# none. What survives above is the part that still decides something: how a till's invoice line
# finds, adopts or creates a service.
