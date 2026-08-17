"""ط-4 — the guard was on the route somebody was thinking about branches while writing.

`GET /reminders/log` resolves the caller's branch scope before it reads the send log. Its two
neighbours read the SAME collection and did not:

    GET /reminders/offer    what this customer is holding now
    GET /reminders/offers   every offer this customer has ever been sent

Both take a `subject_ref` and nothing else. So a marketing supervisor confined to Jeddah needed one
pseudonym — which the customer page hands out — to read the text of every message Riyadh sent that
customer, the code the customer is holding, and what it is worth. Exactly the data the route beside
them refuses him.

Nothing failed: 200, a full list, a fast screen. The two routes were written while thinking about
offers, and branches were somebody else's paragraph.
"""
from __future__ import annotations

import asyncio

from app.adapters.branch_scope import UNREADABLE
from app.api.v1.owner import _branch_scope, _in_scope, customer_offers

TENANT = "shop"
SUBJECT = "sub_abcdefgh"


def run(c):
    return asyncio.run(c)


class _Scope:
    def __init__(self, answer: str):
        self.answer = answer

    async def scope(self, tenant: str, subject: str) -> str:
        return self.answer


class _Store:
    """Two branches sent this customer an offer each."""

    def __init__(self, rows):
        self.rows = rows

    async def find(self, collection, where, **kw):
        # THE REAL SHAPE: `SendLogStore.since` page-walks through `_find`, which calls this and
        # filters. A fake that answered a method the store does not use would prove nothing.
        rows = [r for r in self.rows
                if all(str(r.get(k, "")) == str(v) for k, v in (where or {}).items())]
        return rows, ""

    async def get(self, *a, **kw):
        return None


class _Container:
    def __init__(self, rows, scope_answer=""):
        self.datastore = _Store(rows)
        self.branch_scope = _Scope(scope_answer)


class _Request:
    def __init__(self, container):
        self.app = type("A", (), {"state": type("S", (), {"container": container})()})()


class _Principal:
    tenant = TENANT
    subject = "person_jeddah"
    tenant_id = TENANT


def _rows():
    return [
        {"tenant": TENANT, "subject_ref": SUBJECT, "branch_id": "br_jeddah", "outcome": "sent", "at": 1_780_000_100,
         "offer_text": "خصم جدة", "offer_code": "JED1", "offer_expires_at": 9_999_999_999},
        {"tenant": TENANT, "subject_ref": SUBJECT, "branch_id": "br_riyadh", "outcome": "sent", "at": 1_780_000_200,
         "offer_text": "خصم الرياض", "offer_code": "RUH1", "offer_expires_at": 9_999_999_999},
    ]


def _offers(scope_answer):
    c = _Container(_rows(), scope_answer)
    return run(customer_offers(_Request(c), subject_ref=SUBJECT, include_expired=True,
                               principal=_Principal()))


def test_a_jeddah_supervisor_does_not_read_riyadhs_offer():
    """THE DEFECT. One pseudonym, and another branch's offer code and value came back."""
    out = _offers("br_jeddah")

    codes = [o["code"] for o in out["offers"]]
    assert codes == ["JED1"], "Riyadh's offer reached a supervisor scoped to Jeddah"


def test_the_owner_still_sees_every_branch():
    """He is unscoped by design, as is everybody in a shop that assigns nobody to a branch — most
    shops. A fix that locked them out would be the same defect facing the other way."""
    codes = sorted(o["code"] for o in _offers("")["offers"])
    assert codes == ["JED1", "RUH1"]


def test_a_scope_we_could_not_read_shows_nothing_and_says_so():
    """«We could not check» is not «no limit». Refusing costs him a screen for a minute; guessing
    shows him somebody else's customer history."""
    out = _offers(UNREADABLE)

    assert out["offers"] == []
    assert out.get("unavailable"), "and the screen is told why, rather than showing an empty list"


def test_the_resolver_is_the_one_the_guarded_route_uses():
    """Two ways of asking the same question drift, and the one nobody looks at drifts first."""
    c = _Container([], "br_jeddah")
    assert run(_branch_scope(c, _Principal())) == frozenset({"br_jeddah"})
    assert run(_branch_scope(type("C", (), {})(), _Principal())) == frozenset(), (
        "no resolver wired = no narrowing")


def test_a_row_with_no_branch_belongs_to_nobody_in_particular():
    """Rows written before branches existed carry "". A scoped caller must not inherit them."""
    assert _in_scope({"branch_id": ""}, frozenset({"br_jeddah"})) is False
    assert _in_scope({"branch_id": ""}, frozenset()) is True
    assert _in_scope({"branch_id": "br_jeddah"}, frozenset({"br_jeddah"})) is True


def test_a_man_who_watches_two_branches_reads_both_and_not_the_third():
    """The case the old shape could not express, and the reason for this cycle.

    Where a man WORKS is one place; what he may SEE is a list. While they were one field, an owner
    could say «Malaz» or «everything» and nothing in between — so a supervisor over two branches was
    either given one of them or handed the whole chain. An equality test would still pass every
    test above and silently show him ONE branch, which is why the answer is a set and this asks
    membership.
    """
    both = frozenset({"br_jeddah", "br_malaz"})

    assert _in_scope({"branch_id": "br_jeddah"}, both) is True
    assert _in_scope({"branch_id": "br_malaz"}, both) is True
    assert _in_scope({"branch_id": "br_riyadh"}, both) is False
    assert _in_scope({"branch_id": ""}, both) is False
