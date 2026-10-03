"""What a person may SEE is a set; where he WORKS is one place.

Until this cycle they were the same field. `branch_scope` answered with `op.branch_id` — his
station — so an owner had exactly two settings for anybody: «this one branch» or, by leaving the
field blank, the whole chain. «مشرف يعمل في الملز ويتابع أربعة» could not be said at all, and the
way people said it anyway was to leave the field empty, which handed a supervisor every branch's
revenue.

The failure that would follow a half-fix is silent, which is why these are written as they are: an
equality test satisfies every single-branch case above and then shows a man ONE of his four with no
error anywhere. So the answer is a set and the readers ask membership.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.api.scope import REVOKED, branch_scope, visible
from app.core.models import Operator


def run(coro):
    return asyncio.run(coro)


class _Store:
    """Just enough of the datastore for OperatorStore.list to answer."""

    def __init__(self, rows):
        self._rows = rows

    async def find(self, collection, filt=None, **kw):
        tenant = (filt or {}).get("tenant")
        return [r for r in self._rows if r.get("tenant") == tenant], None


def _op(**over) -> dict:
    row = Operator(id="op1", tenant="t1", name="سالم", person_id="p1", branch_id="br_malaz")
    for k, v in over.items():
        setattr(row, k, v)
    return {"id": row.id, "tenant": row.tenant, "name": row.name, "person_id": row.person_id,
            "branch_id": row.branch_id, "active": row.active, "role": row.role,
            "created": row.created,
            "visible_branch_ids": row.visible_branch_ids, "visible_all": row.visible_all}


def _scope(row):
    return run(branch_scope(_Store([row]), SimpleNamespace(subject="p1", tenant="t1")))


def test_where_he_works_is_what_he_sees_when_nobody_widened_him():
    """The default, and the answer for almost every employee in the product."""
    assert _scope(_op()) == "br_malaz"


def test_a_supervisor_granted_two_branches_is_answered_with_both():
    """The case that could not be expressed before. His STATION is still Malaz — his visits are
    counted there — and what he may READ is the two he was given."""
    scope = _scope(_op(visible_branch_ids=["br_malaz", "br_olaya"]))

    assert scope == frozenset({"br_malaz", "br_olaya"})
    assert "br_jeddah" not in scope, "a branch he was never granted"


def test_the_whole_establishment_is_said_out_loud_not_left_blank():
    """An emptiness that means «no limit» is how a dismissed employee once got widened to the whole
    chain. «Everything» is now a field somebody set on purpose."""
    assert _scope(_op(visible_all=True)) == ""


def test_a_stopped_employee_is_revoked_however_wide_he_was():
    """Dismissal must never WIDEN. The flag outranks every grant on the row."""
    assert _scope(_op(active=False, visible_branch_ids=["br_malaz", "br_olaya"])) is REVOKED
    assert _scope(_op(active=False, visible_all=True)) is REVOKED


def test_rows_are_kept_by_membership_so_two_branches_means_two():
    """`visible()` is what every listing route filters through, and an `==` inside it would drop
    one of the two branches while every screen still looked healthy."""
    rows = [{"branch_id": "br_malaz"}, {"branch_id": "br_olaya"}, {"branch_id": "br_jeddah"},
            {"branch_id": ""}]

    kept = visible(rows, frozenset({"br_malaz", "br_olaya"}))

    assert [r["branch_id"] for r in kept] == ["br_malaz", "br_olaya", ""], (
        "both of his branches, plus the unassigned row that belongs to nobody"
    )


@pytest.mark.parametrize("scope,expected", [
    ("br_malaz", ["br_malaz", ""]),
    ("", ["br_malaz", "br_olaya", "br_jeddah", ""]),
])
def test_the_single_branch_and_unscoped_answers_are_unchanged(scope, expected):
    """The widening must not have moved the two cases that already worked."""
    rows = [{"branch_id": "br_malaz"}, {"branch_id": "br_olaya"}, {"branch_id": "br_jeddah"},
            {"branch_id": ""}]

    assert [r["branch_id"] for r in visible(rows, scope)] == expected


def test_revoked_keeps_nothing_even_though_it_is_falsy():
    """`None` is falsy, so a single `if not scope` would hand a dismissed employee everything."""
    assert visible([{"branch_id": "br_malaz"}], REVOKED) == []
