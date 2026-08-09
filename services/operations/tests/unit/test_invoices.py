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
    assert I.normalise_name("  غيار   الزيت  ") == "غيار الزيت"


# ── the boundary ───────────────────────────────────────────────────────────────────────────────
def test_a_line_with_an_id_becomes_a_real_service(store):
    res = resolve(store, [{"product_id": "P1", "name": "غيار الزيت"}])
    assert len(res.created_services) == 1 and len(res.service_ids) == 1
    svc = run(store.by_external_id("t1", "P1"))
    assert svc.name == "غيار الزيت"


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
    resolve(store, [{"product_id": "P1", "name": "غيار زيت"}])
    res = resolve(store, [{"product_id": "P1", "name": "غيار الزيت والفلتر"}])
    assert res.created_services == [] and len(res.renamed_services) == 1
    assert len(run(store.list("t1", active_only=False))) == 1
    assert run(store.by_external_id("t1", "P1")).name == "غيار الزيت والفلتر"


def test_a_shop_that_went_manual_first_adopts_its_tills_id(store):
    """It has the service typed by hand months ago. A second row would split the visit history."""
    run(store.save(Service(id=new_id("srv"), tenant="t1", name="غيار الزيت",
                           cycle_days=90, created=NOW)))
    res = resolve(store, [{"product_id": "P1", "name": "غيار الزيت"}])
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
    res = resolve(store, [{"product_id": "P1", "name": "غيار الزيت"}], auto_create=False)
    assert res.created_services == [] and res.free_text == ["غيار الزيت"]


def test_one_tenants_catalogue_is_never_touched_by_another(store):
    """The catalogue is a per-tenant COPY, which is what makes auto-creation safe at all."""
    resolve(store, [{"product_id": "P1", "name": "غيار الزيت"}])
    run(I.resolve(I.parse_lines([{"product_id": "P1", "name": "شيء مختلف"}]),
                  tenant="t2", service_store=store, new_id=new_id, now=NOW))
    assert run(store.by_external_id("t1", "P1")).name == "غيار الزيت"
    assert len(run(store.list("t2", active_only=False))) == 1


# ── the integrated establishment ───────────────────────────────────────────────────────────────
from app.core.sectors import SectorCatalogue


def _cat(st):
    return SectorCatalogue(st)


SECTOR = {"key": "tyres", "name": "بنشري", "asset": "vehicle", "sort": 1,
          "services": [{"name": "تبديل إطار", "cycle_days": 0, "sort": 1},
                       {"name": "غيار زيت", "cycle_days": 90, "sort": 2},
                       {"name": "خدمة أخرى", "cycle_days": 0, "sort": 99, "catchall": True}]}


def test_a_manual_shop_gets_the_whole_sector_catalogue():
    st = MemoryDataStore()
    run(_cat(st).upsert(SECTOR))
    n = run(_cat(st).seed_tenant(tenant="manual", sector_key="tyres"))
    assert n == 3


def test_an_integrated_shop_gets_only_the_catch_all():
    """Seeding names its invoices never mention leaves an owner staring at services they cannot
    tell apart from the real ones."""
    st = MemoryDataStore()
    run(_cat(st).upsert(SECTOR))
    n = run(_cat(st).seed_tenant(tenant="wired", sector_key="tyres", integrated=True))
    assert n == 1
    services = run(ServiceStore(st).list("wired", active_only=False))
    assert len(services) == 1 and services[0].catchall is True


def test_the_catch_all_is_never_skipped_even_when_integrated():
    """A line with no product id has to land somewhere; without it the first free item fails the
    whole invoice."""
    st = MemoryDataStore()
    run(_cat(st).upsert(SECTOR))
    run(_cat(st).seed_tenant(tenant="wired", sector_key="tyres", integrated=True))
    assert run(ServiceStore(st).catchall("wired")) is not None


def test_the_catalogue_is_a_copy_so_one_shop_never_edits_anothers():
    """Without the copy, one tyre shop renaming a service renames it for every tyre shop."""
    st = MemoryDataStore()
    run(_cat(st).upsert(SECTOR))
    store = ServiceStore(st)
    for t in ("shopA", "shopB"):
        run(_cat(st).seed_tenant(tenant=t, sector_key="tyres"))
    svc = [s for s in run(store.list("shopA", active_only=False)) if s.name == "غيار زيت"][0]
    svc.name = "تغيير الزيت"
    run(store.save(svc))
    assert any(s.name == "غيار زيت" for s in run(store.list("shopB", active_only=False)))


def test_a_sector_saved_without_a_catch_all_gets_one():
    """Found on the cluster: the live tyres sector had seventeen services and not one flagged
    catchall — dropped by a console edit months after seeding. The symptom is not an error; it is
    an operator who cannot save a visit, and a lost visit is a lost customer for ever."""
    st = MemoryDataStore()
    cat = _cat(st)
    run(cat.upsert({"key": "barber", "name": "حلاق",
                    "services": [{"name": "قص", "cycle_days": 30}]}))
    services = run(cat.get("barber"))["services"]
    assert any(x.get("catchall") for x in services)
    assert len(services) == 2


def test_an_existing_catch_all_is_not_duplicated():
    st = MemoryDataStore()
    cat = _cat(st)
    run(cat.upsert(SECTOR))
    run(cat.upsert(SECTOR))
    assert sum(1 for x in run(cat.get("tyres"))["services"] if x.get("catchall")) == 1


def test_an_empty_sector_is_left_empty():
    """A sector with no services at all is a draft somebody is still writing — adding a lone
    catch-all to it would put a service in a list the operator has not started."""
    st = MemoryDataStore()
    cat = _cat(st)
    run(cat.upsert({"key": "draft", "name": "مسودة", "services": []}))
    assert run(cat.get("draft"))["services"] == []
