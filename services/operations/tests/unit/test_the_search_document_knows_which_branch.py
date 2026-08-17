"""ط-3 · the keypad walks around every branch guard, because the index has no branch.

`field.py` builds a careful scope for `recent` and for `resolve`: a manager assigned to Jeddah
reads Jeddah's customers and no one else's, and the file says so twice. The keypad calls NEITHER.
It types four digits into search-service's prefix suggestion, and search-service — vendored, and
not ours to change — has no notion of a branch at all.

So a supervisor in Jeddah typing `0501` was answered with Riyadh's customers by name, number and
plate. Not by a route anybody forgot to guard: by the one route that was never ours to guard.

THE FIRST THING THE FIX NEEDS IS A FIELD TO FILTER ON, and the document did not have one. Nothing
downstream — not a filter passed to `POST /search`, not a scoped route of our own — can narrow a
result set by a field that was never written. That is what this test pins.

AND BOTH WRITERS, WHICH IS THE HALF THAT IS EASY TO MISS. The visit path writes the document as it
happens; the backfill rewrites it for customers who came before a field existed. A branch written
only by new visits would make every customer from before today invisible to a scoped reader — the
same leak inverted, and a shop that looks like it lost its customer list.
"""
from __future__ import annotations

import asyncio


class _Search:
    def __init__(self) -> None:
        self.docs: list[dict] = []

    async def index(self, *, index: str, doc_id: str, tenant: str, fields: dict) -> None:
        self.docs.append({"index": index, "id": doc_id, "tenant": tenant, "fields": fields})


def _seams(search):
    from app.core.seams import Seams

    return Seams(search=search)


def test_the_visit_path_stamps_the_branch_on_the_search_document() -> None:
    from app.core.models import Customer

    search = _Search()
    s = _seams(search)

    class _Result:
        pass

    res = _Result()
    res.customer = Customer(id="c1", tenant="t1", phone="966501234567", subject_ref="r1", name="محمد")
    res.customer.last_branch_id = "jeddah"
    res.plates = ["ا ب ج 1234"]

    asyncio.run(s._index_customer(res))

    assert search.docs, "the visit path indexed nothing at all"
    fields = search.docs[0]["fields"]
    assert "branch_id" in fields, (
        "the customer's search document carries no branch — so no reader can narrow a prefix "
        "suggestion to the branch asking, and the keypad answers Jeddah with Riyadh's customers")
    assert fields["branch_id"] == "jeddah"


def test_a_customer_with_no_branch_is_indexed_with_an_empty_one_not_a_missing_one() -> None:
    """Empty is «visible to everyone» — the rule `SCOPE.visible` already applies everywhere else.

    MISSING IS DIFFERENT AND WOULD BE WORSE. A filter cannot tell «this customer belongs to no
    branch» from «this document predates the field», so a key that is sometimes absent hides
    exactly the customers a till recorded — which is most of them in a busy shop.
    """
    from app.core.models import Customer

    search = _Search()
    s = _seams(search)

    class _Result:
        pass

    res = _Result()
    res.customer = Customer(id="c2", tenant="t1", phone="966505555555", subject_ref="r2", name="")
    res.plates = []

    asyncio.run(s._index_customer(res))
    assert search.docs[0]["fields"]["branch_id"] == ""


def test_the_backfill_carries_the_branch_too() -> None:
    """The older half of a shop must answer the same question as the newer half.

    `index_customer_row` is deliberately the ONE place the document is composed, and both callers
    reach it — but only a caller that PASSES the branch puts one in. The backfill reads it off the
    stored row (`last_branch_id`), which is where the visit path put it.
    """
    search = _Search()
    s = _seams(search)

    asyncio.run(s.index_customer_row(
        tenant="t1", customer_id="c3", phone="966509999999", name="سارة",
        plates=[], branch_id="riyadh"))

    assert search.docs[0]["fields"]["branch_id"] == "riyadh"
