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

    # THE REFUSAL MOVED, ON PURPOSE (ط-4). It used to live inline in this one route, which is
    # exactly why `/offer` and `/offers` — reading the same collection — had no check at all. It
    # now sits in `_branch_scope`, which all three call, so this follows it there rather than
    # asserting on the shape the defect happened to have.
    src = inspect.getsource(O._branch_scope) + inspect.getsource(O.send_log)
    # AGAINST THE SET, NOT ONE LITERAL. There are two answers that are not a branch — we could not
    # ask, and his shop stopped him — and the route must refuse on BOTH. Naming one sentinel here
    # would let a second be added that falls through to «no restriction», which is the whole
    # defect: every one of these starts as a state nobody compared against.
    assert "in DENIED" in src
    assert "تعذّر التحقق" in src, "and it says so in words the owner can act on"


def test_denied_holds_every_answer_that_is_not_a_branch():
    """The guard on the guard: whatever DENIED contains, none of it may be readable as a branch."""
    from app.adapters.branch_scope import DENIED, REVOKED, UNREADABLE

    assert DENIED == {UNREADABLE, REVOKED}
    assert "" not in DENIED, "the empty scope is «the whole shop» and must never be refused"


# ── one customer's messages, when one customer is asked about ─────────────────────────────────


def test_the_log_narrows_to_one_customer_when_asked():
    """THE LEAK. «رسائله» on the customer page has always sent `subject_ref`, and this route never
    declared it — so FastAPI dropped it in silence and answered with the WHOLE SHOP'S send log.
    The screen then printed that under one man's name.

    The owner reads other customers' messages believing they are this one's, and answers «لماذا لم
    تصلني رسالة؟» from a history that belongs to somebody else. Nothing failed: 200, a full list,
    a fast screen. The only way to see it was to hold both sides at once — which is what the gate
    `ci/check_screens_send_declared_fields.py` now does on every build.
    """
    import inspect

    from app.api.v1 import owner as O

    sig = inspect.signature(O.send_log)
    assert "subject_ref" in sig.parameters, (
        "the screen sends it; a route that does not declare it answers about everybody")

    src = inspect.getsource(O.send_log)
    assert 'where = {**(where or {}), "subject_ref": subject_ref}' in src, (
        "declaring the parameter and not filtering on it is the same answer with extra typing")


def test_the_whole_shop_is_still_readable_without_it():
    """AND THE OTHER DIRECTION. «رسائلي» reads the shop's whole log, and a filter applied when
    nobody asked for one would empty the screen this service exists to provide."""
    import inspect

    from app.api.v1 import owner as O

    src = inspect.getsource(O.send_log)
    assert "if subject_ref:" in src, "the filter must be conditional on having been asked for"
