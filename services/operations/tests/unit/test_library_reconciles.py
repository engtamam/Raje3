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
