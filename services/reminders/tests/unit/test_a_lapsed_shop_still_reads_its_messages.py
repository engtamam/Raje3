"""A lapsed month stops the owner editing his messages and never stops his customer leaving.

THE SAME DECISION AS operations, ASKED IN THE SERVICE THAT SENDS. «القراءة تبقى والكتابة تقف» —
so when the subscription ends the owner can still open «رسائلي» and read every schedule, every
rule and every wording, and can change none of them until he renews.

AND ONE LINE THAT IS NOT OURS TO SUSPEND. `prefs.py` is the customer's own switch, reached from a
link at the end of a message he did not ask for. If a lapsed subscription refused it, a person
trying to stop our messages would be told, in effect, to go and ask the shop to pay its bill
first. That is the law's line, not a courtesy, and it is why the exemption is declared on the
route rather than remembered.
"""
from __future__ import annotations

import pytest

from app.core.base_licence import CANNOT_ASK, LAPSED, LicenceError, NullBaseLicence


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_a_live_month_lets_the_owner_edit():
    _run(NullBaseLicence(True).require_write("t1"))


def test_a_lapsed_month_refuses_and_an_outage_refuses_differently():
    with pytest.raises(LicenceError) as lapsed:
        _run(NullBaseLicence(False).require_write("t1"))
    with pytest.raises(LicenceError) as outage:
        _run(NullBaseLicence(None).require_write("t1"))
    assert lapsed.value.message == LAPSED and lapsed.value.reachable is True
    assert outage.value.message == CANNOT_ASK and outage.value.reachable is False


def test_editing_a_wording_asks_the_month_and_a_customer_opting_out_never_does():
    """READ OFF THE REAL ROUTERS. The two sides of the line, as the code states them."""
    from app.api.subscribed import no_subscription_needed, subscribed_write
    from app.api.v1.owner import router as owner
    from app.api.v1.prefs import router as prefs

    def _deps(router, path: str, method: str) -> set:
        for route in router.routes:
            if route.path == path and method in route.methods:
                return {d.call for d in route.dependant.dependencies}
        raise AssertionError(f"{method} {path} is not on the router any more")

    assert subscribed_write in _deps(owner, "/reminders/templates", "POST")
    # THE CUSTOMER'S SWITCH. Never gated, and the assertion is the strong one — not «it is not
    # required» but «it is declared exempt», so removing the declaration fails here too.
    assert no_subscription_needed in _deps(prefs, "/prefs/{ref}", "PUT")
    assert subscribed_write not in _deps(prefs, "/prefs/{ref}", "PUT")
