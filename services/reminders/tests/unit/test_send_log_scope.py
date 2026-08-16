"""Whose messages may he read — on the one screen this service exists to provide.

THE HOLE. `GET /api/v1/reminders/log` narrows by branch, which is the whole reason its rows carry
one: an owner with three branches cannot answer «ما الذي خرج باسم فرع جدة؟» from one list of
everything. But it narrowed by whatever branch the CALLER TYPED. A manager assigned to Jeddah read
every message that went out in Riyadh's name by changing one query parameter — about the one thing
a shop is most sensitive about, which is what was said to its customers in its name.

AND THE FIX MUST NOT LOCK OUT THE OWNER. He is unscoped by design, as is everybody in a shop that
assigns nobody to a branch — most shops. A fix that refused them would be the same defect facing
the other way, and it would be discovered by every single customer rather than by one.
"""
from __future__ import annotations

import asyncio

from app.adapters.branch_scope import UNREADABLE, BranchScope


def run(c):
    return asyncio.run(c)


def test_an_unconfigured_deployment_does_not_refuse_every_read():
    """A deployment with no operations wired has no branches to isolate either. Refusing there
    would take the send log down for a shop that has one place."""
    scope = BranchScope(url="", path="/x", token="t")

    assert scope.configured is False
    assert run(scope.scope("t1", "person")) == ""


def test_an_unreachable_peer_is_unreadable_and_not_unscoped():
    """THE DISTINCTION THE WHOLE FILE EXISTS FOR. `""` means «this person sees everything» — the
    owner's answer. Returning it when we simply could not ask hands one manager another's messages
    during any hiccup at the peer."""
    scope = BranchScope(url="http://nowhere.invalid:1", path="/internal/operations/branch-scope",
                        token="t" * 40, timeout=1)

    assert run(scope.scope("t1", "person")) == UNREADABLE


def test_a_missing_subject_is_unscoped_not_unreadable():
    """A machine token with no person on it is not a branch manager, and answering «unreadable»
    would break every internal caller to protect nobody."""
    scope = BranchScope(url="http://operations:8000", path="/p", token="t")

    assert run(scope.scope("t1", "")) == ""


def test_the_route_applies_the_scope_and_ignores_the_parameter():
    """A guard on the wiring, because the behaviour can be satisfied by reading the scope and then
    filtering by the caller's parameter anyway — which is the bug with an extra HTTP call."""
    import inspect

    from app.api.v1 import owner as O

    src = inspect.getsource(O.send_log)
    assert "branch_scope" in src, "the scope must be READ"
    assert 'where = {**(where or {}), "branch_id": scope}' in src, (
        "and applied as read — his own branch, not the one the request carried")
    assert src.index("scope") < src.index("elif branch_id"), (
        "the caller's parameter may only be honoured for somebody who is unscoped")


def test_an_unreadable_scope_refuses_rather_than_showing_everything():
    import inspect

    from app.api.v1 import owner as O

    src = inspect.getsource(O.send_log)
    assert '"_unreadable"' in src
    assert "تعذّر التحقق" in src, "and it says so in words the owner can act on"
