"""A customer asks his shop for his data — the route that could not run.

WHAT WAS BROKEN, AND HOW COMPLETELY. The route called `_svc(request)`, a name that exists nowhere
in the module. Python resolves a name when the line runs, so the import succeeded, the app booted,
and the whole suite stayed green — while every privacy request a customer made through his own page
returned 500 and was never written down.

THAT ROW IS THE CLOCK. PDPL gives the establishment thirty days, counted from when the request was
made, and this record is what proves when that was. Without it we cannot say a request arrived, let
alone that it was answered in time — so the failure was not «a feature was down», it was «the one
piece of evidence the regulation asks for was never created».

These tests exercise the ROUTE, not the store. A store test would have passed throughout.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/operations/privacy-request"


def _post(client, **over):
    body = {"tenant": "tnt_pr", "subject_ref": "sub_pr_00001", "type": "export"}
    body.update(over)
    return client.post(PATH, json=body, headers=INTERNAL)


def test_a_request_is_recorded_and_answers_with_its_own_id(client):
    """THE DEFECT ITSELF: this returned 500 for every customer, for as long as the route existed."""
    r = _post(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["id"], "a request with no id cannot be answered or closed later"
    assert body["at"] > 0, "the hour it arrived IS the thirty-day clock"


def test_the_row_is_readable_afterwards_by_the_owner(client):
    """A request that is recorded and then invisible is the same failure wearing a 200."""
    import asyncio

    from app.core.stores import PrivacyRequestStore

    created = _post(client, tenant="tnt_pr_open", subject_ref="sub_pr_00002").json()
    store = PrivacyRequestStore(client.app.state.container.datastore)
    rows = asyncio.run(store.list_open("tnt_pr_open"))

    assert [r.id for r in rows] == [created["id"]]


def test_an_unknown_type_is_refused_before_anything_is_written(client):
    r = _post(client, type="whatever")
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "type must be one of" in r.json()["reason"]


def test_the_arrival_is_audited(client, monkeypatch):
    """«When did he ask» is answered from the audit trail when the row itself is later erased —
    the request survives the erasure it asks for, and so must the record that it arrived."""
    seen: list[tuple[str, str]] = []

    async def record(action, **kw):
        seen.append((action, kw.get("tenant", "")))

    monkeypatch.setattr(client.app.state.auditor, "record", record)
    assert _post(client, tenant="tnt_pr_audit", subject_ref="sub_pr_00003").status_code == 200
    assert ("privacy.requested", "tnt_pr_audit") in seen


def test_the_route_names_no_helper_that_does_not_exist(client):
    """A regression guard aimed at the exact shape, not at the symptom.

    ci/check_undefined_names.py now fails the build on any unresolvable name anywhere in the repo —
    this test is the local half of that, so the route cannot quietly reacquire a caller to nothing.
    """
    import inspect

    from app.api import internal as I

    code = [line for line in inspect.getsource(I.privacy_request).splitlines()
            if not line.lstrip().startswith("#")]
    body = chr(10).join(code)
    assert "_svc(" not in body, "the route reaches for a helper that does not exist"
