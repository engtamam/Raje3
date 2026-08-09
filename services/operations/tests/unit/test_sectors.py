"""Sectors are content our operators edit at runtime — these tests hold that promise.

The failure each one prevents is a product failure rather than a crash: an empty grid on an owner's
first day, an edit that vanishes overnight, a salon asked for a plate number.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.sectors import PLATFORM, SectorCatalogue, SectorError
from app.core.stores import ServiceStore

T = "tnt_alpha"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def cat():
    store = MemoryDataStore()
    return SectorCatalogue(store), store


SEED = {
    "sectors": [
        {"key": "tyres", "name": "بنشر", "asset": "vehicle", "fields": ["plate"], "sort": 10,
         "services": [{"name": "تبديل إطارات", "cycle_days": 730, "sort": 10},
                      {"name": "تصليح بنشر", "cycle_days": 0, "sort": 20}]},
        {"key": "salon", "name": "صالون", "asset": "none", "fields": [], "sort": 20,
         "services": [{"name": "قص شعر", "cycle_days": 60, "sort": 10}]},
    ],
    "fields": {"plate": {"label": "رقم اللوحة", "type": "text", "required": False}},
}


def _seed_file(tmp_path):
    p = tmp_path / "sectors.seed.json"
    p.write_text(json.dumps(SEED, ensure_ascii=False), encoding="utf-8")
    return str(p)


# ── the seed ──────────────────────────────────────────────────────────────────────────────────
def test_a_fresh_install_is_not_a_blank_product(cat, tmp_path):
    c, _ = cat
    assert run(c.seed_from_file(_seed_file(tmp_path))) == 2
    assert {s["key"] for s in run(c.list())} == {"tyres", "salon"}


def test_the_seed_never_overwrites_an_operator_edit(cat, tmp_path):
    """The bug this prevents is the worst kind: the console appears to work, and the change is gone
    by morning. Applying the seed on every boot would do exactly that."""
    c, _ = cat
    path = _seed_file(tmp_path)
    run(c.seed_from_file(path))
    run(c.upsert({"key": "tyres", "name": "بنشر وإطارات — معدّل", "asset": "vehicle",
                  "fields": ["plate"], "services": []}))

    # A restart. The table is not empty, so the seed must do nothing at all.
    assert run(c.seed_from_file(path)) == 0
    assert run(c.get("tyres"))["name"] == "بنشر وإطارات — معدّل"


# ── runtime editing, which is the whole point ─────────────────────────────────────────────────
def test_a_new_sector_needs_no_deploy(cat):
    c, _ = cat
    run(c.upsert({"key": "vet", "name": "عيادة بيطرية", "asset": "none", "fields": [],
                  "services": [{"name": "تطعيم", "cycle_days": 365}]}))
    assert run(c.get("vet"))["name"] == "عيادة بيطرية"
    assert run(c.seed_tenant(tenant=T, sector_key="vet")) == 1


def test_a_reserved_key_is_refused(cat):
    """`_platform` owns the platform-wide rows. A sector allowed to take an underscore key could
    collide with it and make the whole table unreadable."""
    c, _ = cat
    with pytest.raises(SectorError):
        run(c.upsert({"key": "_platform", "name": "x"}))


def test_a_sector_is_deactivated_not_deleted(cat):
    """Establishments already point at it. Deleting leaves them referring to something that no
    longer exists — discovered months later by whoever tries to read it."""
    c, _ = cat
    run(c.upsert({"key": "tyres", "name": "بنشر", "asset": "vehicle", "services": []}))
    assert run(c.deactivate("tyres")) is True
    assert run(c.get("tyres"))["active"] is False
    # And it can no longer seed a new tenant, which is the point of switching it off.
    with pytest.raises(SectorError):
        run(c.seed_tenant(tenant=T, sector_key="tyres"))


# ── seeding a tenant ──────────────────────────────────────────────────────────────────────────
def test_a_new_establishment_gets_a_full_catalogue(cat, tmp_path):
    """An owner who signs up and meets a blank grid closes the tab. This is that, prevented."""
    c, store = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    assert run(c.seed_tenant(tenant=T, sector_key="tyres")) == 2
    names = {s.name for s in run(ServiceStore(store).list(T))}
    assert names == {"تبديل إطارات", "تصليح بنشر"}


def test_seeding_twice_does_not_duplicate_the_catalogue(cat, tmp_path):
    """A retried provisioning step must not produce a list with every service twice — a mess the
    owner cleans by hand, on their first day."""
    c, store = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    run(c.seed_tenant(tenant=T, sector_key="tyres"))
    assert run(c.seed_tenant(tenant=T, sector_key="tyres")) == 0
    assert len(run(ServiceStore(store).list(T))) == 2


def test_an_unknown_sector_names_the_valid_ones(cat, tmp_path):
    """A caller that sent a typo fixes it from the response, without reading our source."""
    c, _ = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    with pytest.raises(SectorError) as exc:
        run(c.seed_tenant(tenant=T, sector_key="tyre"))       # missing the 's'
    assert "tyres" in str(exc.value)


def test_a_zero_cycle_service_is_seeded_as_zero(cat, tmp_path):
    """0 means NO natural cycle — a puncture repair. Defaulting it would schedule a reminder for a
    puncture and teach a customer that our messages are noise."""
    c, store = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    run(c.seed_tenant(tenant=T, sector_key="tyres"))
    by_name = {s.name: s for s in run(ServiceStore(store).list(T))}
    assert by_name["تصليح بنشر"].cycle_days == 0
    assert by_name["تبديل إطارات"].cycle_days == 730


# ── the field that must not appear in the wrong shop ───────────────────────────────────────────
def test_the_plate_belongs_to_vehicle_sectors_only(cat, tmp_path):
    """A women's salon asked for a plate number is a screen built for somebody else — and that one
    detail tells an owner this product was not made for them."""
    c, _ = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    assert [f["name"] for f in run(c.fields_for("tyres"))] == ["plate"]
    assert run(c.fields_for("salon")) == []
    assert run(c.tracks_vehicle("tyres")) is True
    assert run(c.tracks_vehicle("salon")) is False


def test_a_field_is_described_once_and_referenced_by_name(cat, tmp_path):
    """The screen never carries its own copy of what a field means. A second copy is a second thing
    to keep in step, and it will not be kept in step."""
    c, _ = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    spec = run(c.fields_for("tyres"))[0]
    assert spec["label"] == "رقم اللوحة" and spec["type"] == "text"


# ── platform scoping ──────────────────────────────────────────────────────────────────────────
def test_sectors_are_platform_scoped_not_tenant_scoped(cat, tmp_path):
    """One sector table for the whole product. A tyre shop must not be able to rename "بنشر" for
    every other tyre shop on the platform."""
    c, store = cat
    run(c.seed_from_file(_seed_file(tmp_path)))
    rows, _ = run(store.find("sectors", {"tenant": PLATFORM}, limit=10))
    assert len(rows) == 2
    # And nothing lands under a real tenant's id.
    rows, _ = run(store.find("sectors", {"tenant": T}, limit=10))
    assert rows == []


# ── the catch-all: never lose a visit because a service is not in the list ────────────────────
def test_every_sector_ships_a_catch_all(cat, tmp_path):
    """Without it the operator cannot save, and a lost visit loses the CUSTOMER from the product
    entirely — no reminder, no points, no metric, permanently."""
    c, store = cat
    SEED["sectors"][0]["services"].append({"name": "خدمة أخرى", "cycle_days": 0, "sort": 999,
                                           "catchall": True})
    p = tmp_path / "s.json"
    p.write_text(json.dumps(SEED, ensure_ascii=False), encoding="utf-8")
    run(c.seed_from_file(str(p)))
    run(c.seed_tenant(tenant=T, sector_key="tyres"))
    catch = run(ServiceStore(store).catchall(T))
    assert catch is not None and catch.name == "خدمة أخرى"
    # Cycle 0 necessarily: we do not know what was done, so we cannot say when it is due again.
    assert catch.cycle_days == 0


# ── the template library: the same pattern, and the line that keeps a class honest ─────────────
from app.core.templates import TemplateError, TemplateLibrary


def _lib(store):
    return TemplateLibrary(store)


def _tpl(**over):
    t = {"name": "svc_x_brief", "type": "svc_x", "tone": "brief", "class": "service",
         "category": "UTILITY", "body": "أهلاً {{1}}، من {{2}}.", "label": "x"}
    t.update(over)
    return t


def test_a_template_edit_needs_no_rebuild(cat):
    """The point of the whole exercise: the library lives in the datastore, not in an image."""
    _, store = cat
    lib = _lib(store)
    run(lib.upsert(_tpl()))
    run(lib.upsert(_tpl(body="أهلاً {{1}}، رسالة معدّلة من {{2}}.")))
    assert "معدّلة" in run(lib.get("svc_x_brief"))["body"]


def test_a_gap_in_the_variable_numbering_is_refused(cat):
    """Meta refuses it at submission and blames the wording, days later. Two of our own templates
    had exactly this — caught by counting, not by reading."""
    _, store = cat
    with pytest.raises(TemplateError) as exc:
        run(_lib(store).upsert(_tpl(body="من {{2}} إلى {{3}}.")))
    assert "gap" in str(exc.value)


def test_an_awareness_template_carrying_an_offer_is_refused(cat):
    """This is the line that makes the five-class taxonomy honest (spec §8.4.1). The moment an
    awareness template can contain a discount, we have built the loophole ourselves."""
    _, store = cat
    with pytest.raises(TemplateError) as exc:
        run(_lib(store).upsert(_tpl(name="awr_y_brief", **{"class": "awareness"},
                                    body="{{1}}، افحص إطاراتك — وعندنا خصم من {{2}}.")))
    assert "promotional" in str(exc.value)


def test_an_awareness_template_without_an_offer_is_fine(cat):
    _, store = cat
    row = run(_lib(store).upsert(_tpl(name="awr_y_brief", **{"class": "awareness"},
                                      body="{{1}}، الحرارة ترفع ضغط الإطارات. من {{2}}.")))
    assert row["class"] == "awareness" and row["category"] == "UTILITY"


def test_one_tone_selects_the_whole_set(cat):
    """The owner picks a tone once, not sixty-nine times — that is a form, not a feature."""
    _, store = cat
    lib = _lib(store)
    run(lib.upsert(_tpl(name="svc_a_warm", tone="warm")))
    run(lib.upsert(_tpl(name="svc_b_warm", tone="warm")))
    run(lib.upsert(_tpl(name="svc_a_brief", tone="brief")))
    assert len(run(lib.for_tone("warm"))) == 2


def test_a_template_is_deactivated_not_deleted(cat):
    """Establishments carry the name in their registry and Meta holds an approved copy under it."""
    _, store = cat
    lib = _lib(store)
    run(lib.upsert(_tpl()))
    assert run(lib.deactivate("svc_x_brief")) is True
    assert run(lib.get("svc_x_brief"))["active"] is False


def test_a_template_may_ask_the_owner_for_one_field_at_most(cat):
    """Two blank pages is a form, and an owner who abandons a form sends nothing at all."""
    _, store = cat
    with pytest.raises(TemplateError) as exc:
        run(_lib(store).upsert(_tpl(**{"class": "marketing"}, category="MARKETING",
                                    body="أهلاً {{1}}، من {{2}}: {{3}} — {{4}}.",
                                    fills=["system", "system", "owner", "owner"])))
    assert "One at most" in str(exc.value)


def test_the_declared_fills_must_cover_every_variable(cat):
    """A short fills list means the console asks for the wrong field and the message goes out
    with somebody else's value in it."""
    _, store = cat
    with pytest.raises(TemplateError):
        run(_lib(store).upsert(_tpl(body="{{1}} من {{2}} — {{3}}",
                                    fills=["system", "system"])))


# ── the reminder model: which kind of business a template is for (spec 16.6.5) ─────────────────
def test_every_template_ships_switched_off(cat):
    """Sixty-six switches on day one is not a choice, it is an abandonment. The sector's set is
    enabled for the owner at signup."""
    _, store = cat
    row = run(_lib(store).upsert(_tpl(active=False)))
    assert row["active"] is False


def test_a_cafe_is_offered_loyalty_templates_and_not_cycle_ones(cat):
    """Nobody is reminded that their coffee is due."""
    _, store = cat
    lib = _lib(store)
    run(lib.upsert(_tpl(name="svc_service_reminder_brief", type="svc_service_reminder",
                        model="cycle")))
    run(lib.upsert(_tpl(name="mkt_winback_brief", type="mkt_winback", model="loyalty",
                        **{"class": "marketing"}, category="MARKETING")))
    run(lib.upsert(_tpl(name="svc_receipt_brief", type="svc_receipt", model="both")))
    got = {t["name"] for t in run(lib.for_model("loyalty"))}
    assert got == {"mkt_winback_brief", "svc_receipt_brief"}


def test_a_workshop_gets_the_cycle_set_plus_the_shared_one(cat):
    _, store = cat
    lib = _lib(store)
    run(lib.upsert(_tpl(name="svc_service_reminder_brief", type="svc_service_reminder",
                        model="cycle")))
    run(lib.upsert(_tpl(name="svc_receipt_brief", type="svc_receipt", model="both")))
    assert len(run(lib.for_model("cycle"))) == 2


def test_an_unknown_model_is_refused(cat):
    _, store = cat
    with pytest.raises(TemplateError, match="model must be"):
        run(_lib(store).upsert(_tpl(model="seasonal")))


def test_the_default_model_is_both_so_an_old_template_is_never_hidden(cat):
    """A template written before this field existed must not silently disappear from every
    console."""
    _, store = cat
    row = run(_lib(store).upsert(_tpl()))
    assert row["model"] == "both"
