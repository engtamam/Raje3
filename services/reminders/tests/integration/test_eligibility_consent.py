"""«Can this customer be sent a marketing message?» — the question that always answered «no».

THE DEFECT. `gate.evaluate` defaults `marketing_consent` to "never_asked", and its own rule is that
a marketing message requires "granted". The eligibility route never passed the argument, so the
default applied to every call: every customer was ineligible for marketing, the campaign audience
resolved to zero, and the preview told the owner his campaign would reach nobody.

WHY NO TEST CAUGHT IT. The gate's own tests pass consent explicitly and are correct. The send path
(core/tick.py) reads consent and is correct. The defect lived in ONE call site — the route the
campaign audience actually asks — and a call site is exactly what a unit test of the callee cannot
see.

AND WHY IT MATTERED IN BOTH DIRECTIONS. The same argument that was missing is the one that keeps a
withdrawn customer out of a campaign. A fix that simply passed "granted" would have turned a feature
that reached nobody into one that reached people who had said no — the more expensive failure, and
under the PDPL not merely a bug.
"""
from __future__ import annotations

import asyncio

INTERNAL = {"X-Internal-Token": "t" * 40}
PATH = "/internal/reminders/eligibility"


def _record(client, tenant: str, subject: str, state: str) -> None:
    from app.core.consent import Consent

    store = Consent(client.app.state.container.datastore)
    asyncio.run(store.record(tenant, subject, state=state, source="customer_page", actor=""))


def _engaged(client, tenant: str, subject: str) -> None:
    """A recently-engaged customer. The engagement tier is a SEPARATE rule from consent, and a
    dormant customer is refused for a reason of its own — so a test about consent must not be
    silently answering a question about engagement. The score is set well above
    ENGAGEMENT_FULL_THRESHOLD (5.0) so this fixture cannot become the thing under test."""
    import time

    from app.core.stores import EngagementStore

    asyncio.run(EngagementStore(client.app.state.container.datastore).put(
        tenant, subject, {"score": 10.0, "scored_at": int(time.time())}))


def _ask(client, tenant: str, subject: str, cls: str = "marketing"):
    return client.post(PATH, json={"tenant": tenant, "subject_ref": subject, "class": cls},
                       headers=INTERNAL).json()


def test_a_customer_who_agreed_is_eligible(client):
    """THE DEFECT ITSELF — this answered «no» for every shop, so every campaign reached zero."""
    _record(client, "tnt_el_yes", "sub_el_00001", "granted")
    _engaged(client, "tnt_el_yes", "sub_el_00001")

    got = _ask(client, "tnt_el_yes", "sub_el_00001")

    # ASSERTED ON THE REASON, NOT ON `allowed`, and deliberately. Marketing outside the send window
    # is DROPPED rather than deferred (gate.py), so a test that demanded True here would pass or
    # fail depending on the hour the suite happened to run — and a test that is sometimes right is
    # a test nobody trusts. What this file is about is that consent no longer refuses him.
    assert "لم يوافق" not in got.get("reason", "")
    assert got["tier"] == "full"


def test_a_customer_who_never_agreed_is_not(client):
    """The half that was accidentally correct, and must stay correct on purpose."""
    got = _ask(client, "tnt_el_no", "sub_el_00002")

    assert got["allowed"] is False
    assert got["reason"], "a refusal with no reason cannot be shown or acted on"


def test_a_customer_who_withdrew_is_not(client):
    """Consent is three states, not two: withdrawing must be as effective as never agreeing."""
    _record(client, "tnt_el_out", "sub_el_00003", "granted")
    _record(client, "tnt_el_out", "sub_el_00003", "withdrawn")

    assert _ask(client, "tnt_el_out", "sub_el_00003")["allowed"] is False


def test_a_service_reminder_needs_no_consent(client):
    """UTILITY passes on the contract the customer's own visit created (§8.4). If this ever starts
    demanding consent, every reminder in the product stops."""
    _engaged(client, "tnt_el_svc", "sub_el_00004")
    got = _ask(client, "tnt_el_svc", "sub_el_00004", cls="service")

    assert got["allowed"] is True, got.get("reason")


def test_the_route_reads_consent_rather_than_assuming_it(client):
    """A guard on the wiring, because the behaviour above can be satisfied by hardcoding
    «granted» — which would send to people who said no."""
    import inspect

    from app.api import internal as I

    src = inspect.getsource(I)
    idx = src.find("async def eligibility")
    assert idx > 0
    body = src[idx:idx + 3000]
    assert "Consent(" in body, "consent must be READ here"
    assert "marketing_consent=consent" in body, "and passed as read, not as a constant"
