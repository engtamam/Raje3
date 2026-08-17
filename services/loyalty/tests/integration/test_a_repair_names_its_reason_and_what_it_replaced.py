"""§8.3 promises three things about a repaired balance. One of them was kept.

    «باسم من أصلحه، ومعه ما كان قبله، وبسببٍ مكتوب. ومن غير سببٍ لا يُنفَّذ.»

The actor was recorded. The reason had no field to arrive in — `ReconcileIn` did not carry one —
and the previous value was never written down, so the audit entry said «somebody reconciled a
balance» and nothing more: not which customer, not what the number had been.

AND THE OMISSION WAS EXACTLY BACKWARDS. `POST /loyalty/adjust` — the owner moving one balance in
his own shop, the lowest-risk repair in the product — has required a `note` since it was written,
with a comment saying an adjustment without a reason is unexplainable the moment anybody asks.
These two routes let support rewrite the total of any ledger in any establishment. They asked for
nothing at all.
"""
from __future__ import annotations

TENANT = "t_repair"
SUBJECT = "ref_repaircust01"


def _url_body(**over):
    body = {"tenant": TENANT, "subject_ref": SUBJECT, "reason": "تذكرة دعم #4412"}
    body.update(over)
    return body


def test_the_internal_repair_refuses_without_a_reason(client):
    """«ومن غير سببٍ لا يُنفَّذ» — 422 from the model, before anything is recomputed."""
    from tests.integration.test_loyalty_api import INTERNAL

    body = _url_body()
    body.pop("reason")
    r = client.post("/internal/loyalty/reconcile", json=body, headers=INTERNAL)
    assert r.status_code == 422, r.text


def test_the_internal_repair_runs_when_a_reason_is_given(client):
    from tests.integration.test_loyalty_api import INTERNAL

    r = client.post("/internal/loyalty/reconcile", json=_url_body(), headers=INTERNAL)
    assert r.status_code == 200, r.text
    # `was`, `ledger` and `drift` are what the second audit entry carries — the promise that the
    # number this replaced is on the record.
    assert set(r.json()) >= {"ledger", "was", "drift", "repaired"}


def test_a_blank_reason_is_not_a_reason(client):
    """A three-character floor, so «.» does not satisfy a rule written about accountability."""
    from tests.integration.test_loyalty_api import INTERNAL

    r = client.post("/internal/loyalty/reconcile", json=_url_body(reason=" "),
                    headers=INTERNAL)
    assert r.status_code == 422, r.text
