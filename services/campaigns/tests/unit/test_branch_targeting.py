"""Targeting a campaign at one branch — and the two ways it can be wrong quietly.

THE FAILURE THIS GUARDS AGAINST IS NOT "IT DOES NOT FILTER". It is that it filters in the wrong
PLACE, or filters at preview and not at send. Either produces a number that is wrong, plausible,
and stable — which nobody catches, because nothing looks broken.
"""
from __future__ import annotations

import asyncio
import json

from app.adapters.peers import HttpAudience, NullAudience
from app.container import _AudienceFacade


def run(c):
    return asyncio.run(c)


def cust(ref, branch):
    return {"subject_ref": ref, "last_visit": 1, "visit_count": 3, "last_branch_id": branch}


def test_the_branch_narrows_the_audience_and_an_empty_branch_is_the_whole_shop():
    rows = [cust("a", "brn-jed"), cust("b", "brn-ruh"), cust("c", "brn-jed")]

    seen: dict = {}

    async def resolve(**kw):
        seen.update(kw)
        got = await kw["customers"]("t1")

        class R:
            count = len(got)
            candidates = got
            excluded = 0
        return R()

    facade = _AudienceFacade(NullAudience(rows), resolve, max_audience=5000)

    assert run(facade.resolve_for("t1", goal="announce", now=1, branch_id="brn-jed")).count == 2
    # AND NOT NARROWED BY DEFAULT. Every shop that never opened a second branch must keep
    # reaching everybody — a targeting feature that quietly targets is worse than none.
    assert run(facade.resolve_for("t1", goal="announce", now=1)).count == 3


def test_the_branch_is_sent_to_operations_rather_than_applied_on_this_side():
    """The whole reason the field is on the REQUEST.

    operations applies `limit` in the datastore. Narrowing here would mean filtering the 5000 most
    recent customers of the whole chain down to one branch — a Jeddah audience missing most of
    Jeddah, on a shop big enough for it to matter and never on one small enough to notice.
    """
    posted: list[dict] = []

    class FakeResponse:
        def __init__(self, payload):
            self._p = json.dumps(payload).encode()

        def read(self):
            return self._p

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import app.adapters.peers as peers

    def fake_urlopen(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
        return FakeResponse({"customers": [cust("a", "brn-jed")]})

    original = peers.urllib.request.urlopen
    peers.urllib.request.urlopen = fake_urlopen
    try:
        a = HttpAudience(operations_url="http://ops", customers_path="/internal/customers",
                         reminders_url="http://rem", eligibility_path="/internal/eligible",
                         token="tok")
        rows = run(a.customers("t1", branch_id="brn-jed"))
    finally:
        peers.urllib.request.urlopen = original

    assert rows and rows[0]["subject_ref"] == "a"
    assert posted[0]["branch_id"] == "brn-jed"
    # The cap is operations' to apply, after its own filter — not ours to apply after theirs.
    assert posted[0]["limit"] == 5000
