"""The message library must match the file on every boot — not on the first one only.

WHAT HAPPENED, AND IT WAS TOTAL. The seeder returned early whenever the table was non-empty, so
whatever landed on the first boot was the library for ever. On the cluster that was 78 rows written
in one second from an older image, EVERY ONE `active: False`. An inactive template is not offered,
so «رسائلي» answered «تعذّر عرض نصّ هذه الرسالة» for every message in the product, and the send
path had nothing to choose either. No error, no log, and no redeploy could repair it.

The tests below are about the three things a reconcile must do and the one it must never do.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.core.templates import PLATFORM, TemplateLibrary


def run(c):
    return asyncio.run(c)


class Store:
    def __init__(self, rows=None):
        self.rows = dict(rows or {})

    async def get(self, coll, key):
        return self.rows.get(key)

    async def put(self, coll, key, row):
        self.rows[key] = row
        return row

    async def find(self, coll, where, **kw):
        out = [r for r in self.rows.values()
               if all(r.get(k) == v for k, v in where.items())]
        return sorted(out, key=lambda r: r.get("name", "")), None


def seed_file(tmp_path, names, *, active=True):
    body = {"templates": [
        {"name": n, "type": n.rsplit("_", 1)[0], "class": "service", "category": "UTILITY",
         "label": n, "tone": "brief", "body": "مرحباً {{1}}، من {{2}}.", "active": active,
         "model": "both"}
        for n in names]}
    p = tmp_path / "templates.seed.json"
    p.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_it_repairs_a_library_that_is_already_there(tmp_path):
    """THE DEFECT ITSELF. A row sitting inactive must be corrected by the next boot."""
    store = Store({f"{PLATFORM}|svc_visit_confirmation_brief": {
        "id": "svc_visit_confirmation_brief", "tenant": PLATFORM,
        "name": "svc_visit_confirmation_brief", "type": "svc_visit_confirmation",
        "active": False, "body": "قديم", "class": "service", "category": "UTILITY"}})
    lib = TemplateLibrary(store)

    n = run(lib.seed_from_file(seed_file(tmp_path, ["svc_visit_confirmation_brief"])))

    assert n == 1, "a non-empty library must still be reconciled"
    row = store.rows[f"{PLATFORM}|svc_visit_confirmation_brief"]
    assert row["active"] is True
    assert row["body"] != "قديم", "the wording must follow the file too"


def test_a_template_the_file_no_longer_names_is_retired_not_deleted(tmp_path):
    """An establishment may hold that name with Meta. Deleting our row leaves both pointing at
    something we cannot explain."""
    store = Store({f"{PLATFORM}|mkt_old_brief": {
        "id": "mkt_old_brief", "tenant": PLATFORM, "name": "mkt_old_brief", "type": "mkt_old",
        "active": True, "body": "نص", "class": "marketing", "category": "MARKETING"}})
    lib = TemplateLibrary(store)

    run(lib.seed_from_file(seed_file(tmp_path, ["svc_visit_confirmation_brief"])))

    assert f"{PLATFORM}|mkt_old_brief" in store.rows, "retired, never deleted"
    assert store.rows[f"{PLATFORM}|mkt_old_brief"]["active"] is False


def test_it_leaves_a_shops_own_templates_alone(tmp_path):
    """A shop's custom texts live under its own tenant and are never in our file. Reconciling the
    PLATFORM library must not touch one — that would retire a text Meta approved for him."""
    his = {"id": "cst_eid", "tenant": "tnt_1", "name": "cst_eid", "type": "cst",
           "active": True, "body": "كل عام وأنتم بخير", "class": "marketing",
           "category": "MARKETING"}
    store = Store({"tnt_1|cst_eid": his})
    lib = TemplateLibrary(store)

    run(lib.seed_from_file(seed_file(tmp_path, ["svc_visit_confirmation_brief"])))

    assert store.rows["tnt_1|cst_eid"]["active"] is True


def test_an_empty_path_does_nothing(tmp_path):
    """A deployment with no seed file configured must not wipe a library it cannot see."""
    store = Store({f"{PLATFORM}|svc_a_brief": {
        "id": "svc_a_brief", "tenant": PLATFORM, "name": "svc_a_brief", "type": "svc_a",
        "active": True, "body": "نص", "class": "service", "category": "UTILITY"}})
    lib = TemplateLibrary(store)

    assert run(lib.seed_from_file("")) == 0
    assert store.rows[f"{PLATFORM}|svc_a_brief"]["active"] is True


# ── the fields register() forwards must survive the seed -> row -> list() round trip ────────────
# BUG FIXED HERE (2026-09-13, found while wiring the photo+button variant): `upsert()`'s row dict
# never carried `flow_button`/`carousel` at all, so every template the seed declared one for
# registered with Meta MISSING that component — silently, because `library.py::register()` skips
# a falsy `{}` without complaint. `media_header`/`flat_button`/`shape` are the new photo+button
# variant's own fields and must not repeat the same defect.
def _upsert(tmp_path, extra):
    store = Store()
    lib = TemplateLibrary(store)
    row = {"name": "mkt_x_brief", "type": "mkt_x", "class": "marketing", "category": "MARKETING",
          "label": "x", "tone": "brief", "body": "هلا {{1}}", "model": "both"}
    row.update(extra)
    run(lib.upsert(row))
    return store.rows[f"{PLATFORM}|mkt_x_brief"]


def test_upsert_forwards_flow_button(tmp_path):
    got = _upsert(tmp_path, {"flow_button": {"flow_name": "booking_flow"}})
    assert got["flow_button"] == {"flow_name": "booking_flow"}


def test_upsert_with_no_flow_button_stores_an_empty_dict_not_a_missing_key(tmp_path):
    got = _upsert(tmp_path, {})
    assert got["flow_button"] == {}


def test_upsert_forwards_carousel(tmp_path):
    carousel = {"cards": [{"header_format": "IMAGE", "header_example_handle": ""}]}
    got = _upsert(tmp_path, {"carousel": carousel})
    assert got["carousel"] == carousel


def test_upsert_with_no_carousel_stores_an_empty_dict(tmp_path):
    got = _upsert(tmp_path, {})
    assert got["carousel"] == {}


def test_upsert_defaults_shape_to_plain(tmp_path):
    got = _upsert(tmp_path, {})
    assert got["shape"] == "plain"


def test_upsert_forwards_an_explicit_shape(tmp_path):
    got = _upsert(tmp_path, {"shape": "photo_button",
                            "media_header": {"format": "IMAGE", "example_handle": ""}})
    assert got["shape"] == "photo_button"


def test_upsert_refuses_an_unknown_shape(tmp_path):
    from app.core.templates import TemplateError
    with pytest.raises(TemplateError):
        _upsert(tmp_path, {"shape": "carousel_of_one"})


def test_upsert_refuses_a_photo_button_shape_with_no_media_header(tmp_path):
    """Meta refuses a HEADER component with no example to review — catching this here is a row
    that fails one seed reconcile, not a name burned three days later against a 400."""
    from app.core.templates import TemplateError
    with pytest.raises(TemplateError):
        _upsert(tmp_path, {"shape": "photo_button"})


def test_upsert_forwards_media_header(tmp_path):
    got = _upsert(tmp_path, {"media_header": {"format": "IMAGE", "example_handle": ""}})
    assert got["media_header"] == {"format": "IMAGE", "example_handle": ""}


def test_upsert_with_no_media_header_stores_an_empty_dict(tmp_path):
    got = _upsert(tmp_path, {})
    assert got["media_header"] == {}


def test_upsert_forwards_flat_button(tmp_path):
    got = _upsert(tmp_path, {"flat_button": {"type": "QUICK_REPLY", "text": "احجز الآن"}})
    assert got["flat_button"] == {"type": "QUICK_REPLY", "text": "احجز الآن"}


def test_upsert_with_no_flat_button_stores_an_empty_dict(tmp_path):
    got = _upsert(tmp_path, {})
    assert got["flat_button"] == {}


def test_upsert_forwards_all_five_new_fields_together(tmp_path):
    got = _upsert(tmp_path, {
        "flow_button": {"flow_name": "booking_flow"},
        "shape": "photo_button",
        "media_header": {"format": "IMAGE", "example_handle": "hnd_1"},
        "flat_button": {"type": "QUICK_REPLY", "text": "اطلب الآن"},
    })
    assert got["flow_button"] == {"flow_name": "booking_flow"}
    assert got["shape"] == "photo_button"
    assert got["media_header"]["example_handle"] == "hnd_1"
    assert got["flat_button"]["text"] == "اطلب الآن"


def test_a_reconciled_library_read_back_via_list_still_carries_the_photo_button_fields(tmp_path):
    body = {"templates": [
        {"name": "mkt_x_brief_photo_button", "type": "mkt_x", "class": "marketing",
         "category": "MARKETING", "label": "x", "tone": "brief", "body": "هلا {{1}}",
         "model": "both", "shape": "photo_button",
         "media_header": {"format": "IMAGE", "example_handle": ""},
         "flat_button": {"type": "QUICK_REPLY", "text": "احجز الآن"}},
    ]}
    p = tmp_path / "templates.seed.json"
    p.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    store = Store()
    lib = TemplateLibrary(store)
    run(lib.seed_from_file(str(p)))
    rows = run(lib.list())
    assert rows[0]["shape"] == "photo_button"
    assert rows[0]["media_header"]["format"] == "IMAGE"
    assert rows[0]["flat_button"]["text"] == "احجز الآن"


def test_a_reconciled_library_read_back_via_list_still_carries_flow_button(tmp_path):
    """The end-to-end path `publish()` actually walks: seed file -> seed_from_file -> list() ->
    register(). A regression here is invisible to a unit test that constructs `register()`'s
    input dict by hand, which is exactly how the original defect went unnoticed."""
    body = {"templates": [
        {"name": "mkt_x_brief", "type": "mkt_x", "class": "marketing", "category": "MARKETING",
         "label": "x", "tone": "brief", "body": "هلا {{1}}", "model": "both",
         "flow_button": {"flow_name": "booking_flow"}},
    ]}
    p = tmp_path / "templates.seed.json"
    p.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    store = Store()
    lib = TemplateLibrary(store)
    run(lib.seed_from_file(str(p)))
    rows = run(lib.list())
    assert rows[0]["flow_button"] == {"flow_name": "booking_flow"}


# ── every submitted template carries an example per placeholder (ح-2) ──────────────────────────


def test_every_curated_template_can_be_submitted_with_examples():
    """META REFUSES A TEMPLATE WHOSE PLACEHOLDER HAS NO EXAMPLE, and not one of the 66 rows carried
    any: `register` read `template.get("examples") or []` and sent an empty list every time. So
    every submission was refused, the shop showed «connected» in green, and every send sat «under
    review» for ever. The real values lived in `deploy/seed/templates.json` — read only by the
    manual script, never by the live path."""
    import json
    import pathlib

    from app.core.library import examples_for

    seed = json.loads((pathlib.Path(__file__).resolve().parents[2] / "data" /
                       "templates.seed.json").read_text(encoding="utf-8"))
    rows = seed["templates"]
    assert rows, "the library is empty"
    for row in rows:
        got = examples_for(row)
        assert len(got) == len(row.get("variables") or []), row["name"]
        assert all(v.strip() for v in got), row["name"]


def test_a_placeholder_with_no_example_refuses_instead_of_submitting_a_short_list():
    """A submission Meta will refuse is not a submission. Failing here names the template while
    somebody can still fix it."""
    import pytest as _pytest

    from app.core.library import MissingExample, examples_for

    with _pytest.raises(MissingExample):
        examples_for({"name": "svc_made_up", "variables": [1, 99]})


# ── retired templates must not be pushed to Meta (ح-3) ──────────────────────────────────────────


def test_list_defaults_to_active_only():
    """`list()` with no argument is what the two publish paths call — the hourly Meta sync
    (`c.templates.list()` in internal.py) and `connect.py`'s per-tenant push. Handing them a
    retired row burns Meta's 100/hour cap on text nobody chose any more and shows a human reviewer
    wording we pulled last month."""
    store = Store({
        f"{PLATFORM}|svc_live_brief": {"id": "svc_live_brief", "tenant": PLATFORM,
                                        "name": "svc_live_brief", "active": True,
                                        "class": "service", "category": "UTILITY"},
        f"{PLATFORM}|svc_dead_brief": {"id": "svc_dead_brief", "tenant": PLATFORM,
                                        "name": "svc_dead_brief", "active": False,
                                        "class": "service", "category": "UTILITY"},
    })
    lib = TemplateLibrary(store)

    names = {t["name"] for t in run(lib.list())}
    assert names == {"svc_live_brief"}, "a retired template must not reach the default listing"

    all_names = {t["name"] for t in run(lib.list(active_only=False))}
    assert all_names == {"svc_live_brief", "svc_dead_brief"}, \
        "the platform console must still be able to see what it retired"
