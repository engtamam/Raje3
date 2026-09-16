"""GET /internal/reminders/rating/{ref} and POST .../submit — the hosted rating page's own two
calls ([[task-service-procedure-checklists]] phase 2). Portal's public `/r/{ref}` page is the
customer-facing half; these are the internal-token-holding half it calls server-to-server.
"""
from __future__ import annotations

import asyncio

from tests.conftest import INTERNAL_TOKEN

HEAD = {"X-Internal-Token": INTERNAL_TOKEN}


def run(c):
    return asyncio.run(c)


def _remember(client, *, ref: str, tenant: str, subject_ref: str, visit_id: str) -> None:
    from app.core.rating_request import RatingRequestStore

    store = RatingRequestStore(client.app.state.container.datastore)
    run(store.remember(flow_token=ref, tenant=tenant, subject_ref=subject_ref,
                       visit_id=visit_id, now=1_000))


class FakeWriter:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[dict] = []

    async def write(self, **kw):
        self.calls.append(kw)
        return self.ok


def test_an_unknown_ref_is_not_found(client):
    r = client.get("/internal/reminders/rating/rate:never_existed", headers=HEAD)
    assert r.status_code == 200, r.text
    assert r.json() == {"found": False}


def test_a_remembered_ref_resolves_to_its_tenant_and_visit(client):
    _remember(client, ref="rate:vis_page_1", tenant="t1", subject_ref="sub_a",
             visit_id="vis_page_1")
    r = client.get("/internal/reminders/rating/rate:vis_page_1", headers=HEAD)
    assert r.status_code == 200, r.text
    assert r.json() == {"found": True, "tenant": "t1", "visit_id": "vis_page_1"}


def test_the_anchor_read_does_not_consume_it(client):
    """A page LOAD must not spend the single-use anchor — a customer may look, then submit."""
    _remember(client, ref="rate:vis_page_2", tenant="t1", subject_ref="sub_a",
             visit_id="vis_page_2")
    client.get("/internal/reminders/rating/rate:vis_page_2", headers=HEAD)
    r = client.get("/internal/reminders/rating/rate:vis_page_2", headers=HEAD)
    assert r.json()["found"] is True


def test_submit_consumes_the_anchor_and_writes_the_rating(client):
    _remember(client, ref="rate:vis_page_3", tenant="t1", subject_ref="sub_a",
             visit_id="vis_page_3")
    writer = FakeWriter(ok=True)
    client.app.state.container.rating_writer = writer
    client.app.state.container.rating_points_for = None

    r = client.post("/internal/reminders/rating/rate:vis_page_3/submit", headers=HEAD,
                    json={"rating": 4, "feedback_text": "جيد",
                         "rating_issue_step_ids": ["step_a"]})
    assert r.status_code == 200, r.text
    assert r.json() == {"recorded": True, "visit_id": "vis_page_3"}
    assert writer.calls == [{"tenant": "t1", "visit_id": "vis_page_3", "rating": 4,
                            "feedback_text": "جيد", "subject_ref": "sub_a",
                            "rating_points": 0, "rating_issue_step_ids": ["step_a"]}]

    # THE ANCHOR IS GONE NOW — a second submit for the same ref finds nothing.
    again = client.post("/internal/reminders/rating/rate:vis_page_3/submit", headers=HEAD,
                        json={"rating": 5, "feedback_text": ""})
    assert again.json()["recorded"] is False


def test_submit_with_an_unknown_ref_reports_not_recorded_never_a_500(client):
    r = client.post("/internal/reminders/rating/rate:never_existed/submit", headers=HEAD,
                    json={"rating": 3, "feedback_text": ""})
    assert r.status_code == 200, r.text
    assert r.json()["recorded"] is False


def test_an_out_of_range_rating_is_refused_with_422(client):
    _remember(client, ref="rate:vis_page_4", tenant="t1", subject_ref="sub_a",
             visit_id="vis_page_4")
    r = client.post("/internal/reminders/rating/rate:vis_page_4/submit", headers=HEAD,
                    json={"rating": 6, "feedback_text": ""})
    assert r.status_code == 422
