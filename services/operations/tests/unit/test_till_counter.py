"""The counter, in the other direction — what a till may ask, and what it may hand over.

THE HOLE THESE COVER. The till could post sales and hear «accepted: 3». It could not learn a
customer's points, could not see what he was able to redeem, and could not hand a reward over —
while `loyalty` had served `/internal/loyalty/redeem`, complete with idempotency and receipt,
since the programme was written. The spec says redemption at an integrated till happens over the
API (§9.8); the API had no door, and nothing failed anywhere to say so.

WRITTEN AGAINST THE ROUTE FUNCTIONS, not through the HTTP stack: these assert the DECISIONS —
whose tenant is used, what is withheld, what a dead peer produces — and a TestClient would add a
token mint and a running datastore to prove the same three things.
"""
from __future__ import annotations

import asyncio
import types

import pytest

from app.api.v1 import till as till_routes


class _Principal:
    def __init__(self, tenant: str = "t_1") -> None:
        self.tenant = tenant
        self.subject = "svc_pos"
        self.raw: dict = {}


class _Customer:
    """The row as `Customer` really is (ب-5).

    It used to omit `visit_count`, and the route read `getattr(c, "visits", 0)` — a spelling the
    row has never had. The double was permissive enough to accept the wrong name and the default
    was silent enough to hide it, so the till told a shop that a fortnightly customer of two years
    had been in zero times. A stub that answers questions the real object cannot is a test that
    passes on behalf of code that fails.
    """

    def __init__(self, *, subject_ref: str = "sub_1", name: str = "أحمد",
                 visit_count: int = 0) -> None:
        self.id = "cus_1"
        self.phone = "966500000000"
        self.name = name
        self.subject_ref = subject_ref
        self.visit_count = visit_count


class _Ops:
    """Only what these routes reach for."""

    def __init__(self, customer=None) -> None:
        self._customer = customer
        self.asked_tenant = ""

    async def customer_by_phone(self, tenant, phone):
        self.asked_tenant = tenant
        return self._customer

    async def customer_by_plate(self, tenant, plate):
        self.asked_tenant = tenant
        return self._customer

    async def resolve_branch(self, tenant, branch_id):
        # The real one drops an id the shop does not have; here every id is taken at its word —
        # what these tests are about is the redemption, not the branch check.
        return branch_id


class _Desk:
    def __init__(self, *, balance=None, redeem=None, configured=True) -> None:
        self._balance = balance
        self._redeem = redeem
        self.configured = configured
        self.seen: dict = {}

    async def balance(self, *, tenant, subject_ref):
        self.seen = {"tenant": tenant, "subject_ref": subject_ref}
        return self._balance

    async def redeem(self, **kw):
        self.seen = kw
        return self._redeem


class _Auditor:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def record(self, action, **kw):
        self.calls.append((action, kw))


class _Store:
    """A minimal datastore, real enough for `TillHealth` to read back what it wrote (ك-2)."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

    async def get(self, collection, key):
        return self.rows.get((collection, key))

    async def put(self, collection, key, row):
        self.rows[(collection, key)] = row


class _Telemetry:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def event(self, name, **kw):
        self.events.append((name, kw))


def _request(ops, desk, *, api_licence=None):
    container = types.SimpleNamespace(operations=ops, loyalty_desk=desk, datastore=_Store(),
                                      telemetry=_Telemetry(), api_licence=api_licence)
    state = types.SimpleNamespace(container=container, auditor=_Auditor())
    return types.SimpleNamespace(app=types.SimpleNamespace(state=state), client=None)


def test_a_new_customer_is_not_an_error():
    """`found: false`, never a 404 — a first-time customer is the ordinary case at a till, and a
    vendor's HTTP layer treats a 404 as a fault to log and retry."""
    req = _request(_Ops(customer=None), _Desk())
    out = asyncio.run(till_routes.customer_at_the_counter(req, phone="0500000000",
                                                          principal=_Principal()))
    assert out == {"found": False}


def test_the_tenant_comes_off_the_token_on_the_read_too():
    """The whole security property of this route family, and it has to hold on every route in it —
    a read that took the tenant from a query string would let one shop's till look up another
    shop's customers by changing a word."""
    ops = _Ops(customer=_Customer())
    desk = _Desk(balance={"has_programme": True, "points": 30, "rewards": [],
                           "to_next_reward": 70})
    asyncio.run(till_routes.customer_at_the_counter(
        _request(ops, desk), phone="0500000000", principal=_Principal(tenant="t_9")))
    assert ops.asked_tenant == "t_9"
    assert desk.seen["tenant"] == "t_9"


def test_the_pseudonym_never_leaves():
    """It is our join key between services and a till has no use for it — it identifies its
    customer by the number it already holds. Handing it over would put a durable cross-service
    identifier in a third party's database for nothing."""
    desk = _Desk(balance={"has_programme": True, "points": 30,
                          "rewards": [{"id": "r1", "name": "غسلة", "cost": 20}],
                          "to_next_reward": 0})
    out = asyncio.run(till_routes.customer_at_the_counter(
        _request(_Ops(customer=_Customer()), desk), phone="0500000000", principal=_Principal()))
    assert "subject_ref" not in out
    assert out["points"] == 30
    # THE PROJECTION IS EXACT — the point of the assertion is that nothing ELSE crosses. Since
    # د-14أ each reward also carries whether a manager must sign for it, computed by loyalty from
    # the shop's threshold; it names no person and is exactly what the cashier's screen needs
    # before the tap.
    assert out["rewards"] == [{"id": "r1", "name": "غسلة", "cost": 20, "needs_approval": False}]


def test_an_unreachable_ledger_says_so_instead_of_reporting_zero():
    """A cashier told «0 points» for a customer holding three hundred hands him a grievance we
    manufactured. «تعذّرت القراءة» makes him wait a moment instead."""
    out = asyncio.run(till_routes.customer_at_the_counter(
        _request(_Ops(customer=_Customer()), _Desk(balance=None)),
        phone="0500000000", principal=_Principal()))
    assert out["points_unavailable"] is True
    assert "points" not in out


def test_a_shop_without_the_programme_is_shown_no_points_section_at_all():
    """§9.9: a shop that does not hold `feature.loyalty` has no points anywhere — not an empty
    box. An unconfigured desk is the same silence."""
    out = asyncio.run(till_routes.customer_at_the_counter(
        _request(_Ops(customer=_Customer()), _Desk(configured=False)),
        phone="0500000000", principal=_Principal()))
    assert "points" not in out and "points_unavailable" not in out
    assert out["found"] is True


def test_a_shop_with_the_desk_wired_and_no_rewards_is_shown_no_points_section_either():
    """`desk.configured` is one setting for the whole fleet — «do WE have a loyalty peer» — and it
    was the only question this route asked. It cannot answer «does THIS shop run a programme», so
    a wired deployment showed «0 نقطة» at the counter of every shop that runs none: a balance the
    cashier cannot spend, about a programme the shop never bought (هـ-1)."""
    out = asyncio.run(till_routes.customer_at_the_counter(
        _request(_Ops(customer=_Customer()),
                 _Desk(balance={"has_programme": False, "points": 0, "manager_threshold": 0,
                                "rewards": [], "to_next_reward": 0})),
        phone="0500000000", principal=_Principal()))
    assert "points" not in out and "points_unavailable" not in out


def test_a_balance_that_does_not_say_is_not_read_as_a_no():
    """Unknown is not zero and it is not «no programme» either. A peer that answered without the
    flag has told us nothing about this shop, and the cashier is told we could not check rather
    than being handed a silence he would read as «this customer has nothing»."""
    out = asyncio.run(till_routes.customer_at_the_counter(
        _request(_Ops(customer=_Customer()), _Desk(balance={"points": 30, "rewards": []})),
        phone="0500000000", principal=_Principal()))
    assert out["points_unavailable"] is True
    assert "points" not in out


def test_redemption_passes_the_tills_own_idempotency_key_through_untouched():
    """Only their system knows whether two calls are the same sale. A key minted here would be new
    on every retry — and a doubled redemption spends a customer's points twice."""
    desk = _Desk(redeem={"transaction_ref": "rdm_1", "remaining": 10})
    body = till_routes.TillRedeemIn(phone="0500000000", reward_id="r1",
                                    idempotency_key="POS-77", actor="ali", branch_id="b1")
    out = asyncio.run(till_routes.redeem_at_the_counter(
        _request(_Ops(customer=_Customer()), desk), body, principal=_Principal()))
    assert out["ok"] is True
    assert desk.seen["idempotency_key"] == "POS-77"
    assert desk.seen["actor"] == "ali" and desk.seen["branch_id"] == "b1"


def test_a_refusal_travels_back_in_the_words_the_ledger_used():
    """«رصيده لا يكفي» is a sentence the cashier reads to the customer; «409» is one he cannot."""
    desk = _Desk(redeem={"_status": 409, "_reason": "رصيده لا يكفي"})
    body = till_routes.TillRedeemIn(phone="0500000000", reward_id="r1", branch_id="brn-main", idempotency_key="k")
    out = asyncio.run(till_routes.redeem_at_the_counter(
        _request(_Ops(customer=_Customer()), desk), body, principal=_Principal()))
    assert out["ok"] is False and out["reason"] == "REFUSED"
    assert out["message"] == "رصيده لا يكفي"


def test_a_dead_peer_is_told_apart_from_a_refusal():
    """They are not the same event: one is retryable and one is final, and a till that cannot tell
    them apart either retries a legitimate refusal for ever or drops a recoverable failure."""
    desk = _Desk(redeem=None)
    body = till_routes.TillRedeemIn(phone="0500000000", reward_id="r1", branch_id="brn-main", idempotency_key="k")
    out = asyncio.run(till_routes.redeem_at_the_counter(
        _request(_Ops(customer=_Customer()), desk), body, principal=_Principal()))
    assert out["ok"] is False and out["reason"] == "UNAVAILABLE"


def test_redemption_is_audited_before_it_happens():
    """A customer's balance is being spent by a machine. A write-ahead the log could not take must
    not occur — the same rule the visit path already follows."""
    req = _request(_Ops(customer=_Customer()), _Desk(redeem={"transaction_ref": "x"}))
    body = till_routes.TillRedeemIn(phone="0500000000", reward_id="r1", branch_id="brn-main", idempotency_key="k")
    asyncio.run(till_routes.redeem_at_the_counter(req, body, principal=_Principal()))
    actions = [a for a, _ in req.app.state.auditor.calls]
    assert "loyalty.redeemed" in actions


def test_a_credential_bound_to_no_establishment_is_refused_on_both_routes():
    """A machine credential always belongs to exactly one shop; one that does not is not a till,
    and must never be widened into "all of them"."""
    nobody = _Principal(tenant="")
    read = asyncio.run(till_routes.customer_at_the_counter(
        _request(_Ops(), _Desk()), phone="05", principal=nobody))
    body = till_routes.TillRedeemIn(phone="05", reward_id="r", idempotency_key="k", branch_id="brn-main")
    write = asyncio.run(till_routes.redeem_at_the_counter(
        _request(_Ops(), _Desk()), body, principal=nobody))
    assert read["found"] is False
    assert write["ok"] is False


@pytest.mark.parametrize("field", ["reward_id", "idempotency_key"])
def test_the_two_fields_a_redemption_cannot_be_without(field):
    """Both are required rather than defaulted: a blank reward is a redemption of nothing, and a
    blank key is the doubling this route exists to prevent."""
    kw = {"phone": "0500000000", "reward_id": "r1", "idempotency_key": "k"}
    kw[field] = ""
    with pytest.raises(Exception):
        till_routes.TillRedeemIn(**kw)


# ── the key that told a retry from a second sale, and did not ─────────────────────────────────


def _visit(**kw):
    # THE BRANCH IS PART OF EVERY SALE NOW, so the shared builder carries one: a register that
    # does not name a place is refused at the door (§12.2), and a fixture
    # without it would be testing a request no till can send.
    base = {"phone": "0500000000", "occurred_at": 1_750_000_000, "branch_id": "brn-main"}
    base.update(kw)
    return till_routes.TillVisitIn(**base)


def test_their_own_key_wins_over_everything():
    """Only their system knows whether two calls are the same sale."""
    v = _visit(idempotency_key="POS-1", invoice_id="INV-9")
    assert till_routes._key_for("t_1", v) == "POS-1"


def test_the_invoice_number_is_namespaced_by_tenant():
    """A till whose invoice numbers restart at 1 each day must not collide with a key some other
    integration chose."""
    key = till_routes._key_for("t_1", _visit(invoice_id="1"))
    assert key.startswith("inv:t_1:") and key.endswith("1")


def test_the_content_fingerprint_is_namespaced_by_branch_too():
    """The last-resort fingerprint (no key, no invoice number at all) must not merge the same
    customer's identical-looking purchase at two different branches into one visit."""
    a = _visit(branch_id="brn-a")
    b = _visit(branch_id="brn-b")
    assert till_routes.content_key(tenant="t_1", visit=a) != till_routes.content_key(
        tenant="t_1", visit=b)


def test_the_invoice_number_is_namespaced_by_branch_too():
    """A supermarket with several branches, each with its own register restarting invoice
    numbers at 1, must not have branch B's invoice #1 silently swallowed as a duplicate of
    branch A's invoice #1 — the two are genuinely different sales."""
    key_a = till_routes._key_for("t_1", _visit(invoice_id="1", branch_id="brn-a"))
    key_b = till_routes._key_for("t_1", _visit(invoice_id="1", branch_id="brn-b"))
    assert key_a != key_b


def test_the_invoice_key_matches_the_internal_doors_own_derivation():
    """ك-8: the SAME invoice number through EITHER door must produce the SAME idempotency key, or
    a shop moving from the internal door to this one — or a till posting through both during a
    migration — records every invoice twice: doubled history, doubled reminders, doubled points."""
    from app.api.internal import BatchVisitIn

    till_key = till_routes._key_for("t_1", _visit(invoice_id="INV-42"))
    item = BatchVisitIn(tenant="t_1", branch_id="brn-main", invoice_id="INV-42")
    if item.invoice_id and not item.idempotency_key:
        item.idempotency_key = f"inv:{item.tenant}:{item.branch_id}:{item.invoice_id}"
    assert till_key == item.idempotency_key


def test_the_same_sale_sent_twice_produces_the_same_key():
    """THE DEFECT. The fallback was `till:{tenant}:{now}:{i}` — unique inside one request and NEW
    on the next, so a till that lost the reply and re-sent two seconds later recorded every visit
    a second time: doubled history, doubled reminders, doubled points."""
    a = till_routes._key_for("t_1", _visit(lines=[{"name": "غسيل", "amount_minor": 5000}]))
    b = till_routes._key_for("t_1", _visit(lines=[{"name": "غسيل", "amount_minor": 5000}]))
    assert a == b


def test_reordered_lines_are_the_same_sale():
    """A till is free to reorder the lines of one invoice between retries, and an unsorted
    fingerprint would make the reorder look like a different sale."""
    one = _visit(lines=[{"name": "غسيل", "amount_minor": 5000},
                        {"name": "تلميع", "amount_minor": 2000}])
    two = _visit(lines=[{"name": "تلميع", "amount_minor": 2000},
                        {"name": "غسيل", "amount_minor": 5000}])
    assert till_routes._key_for("t_1", one) == till_routes._key_for("t_1", two)


def test_a_different_sale_produces_a_different_key():
    """The other half: collapsing two real sales would lose one."""
    a = till_routes._key_for("t_1", _visit(occurred_at=1_750_000_000))
    b = till_routes._key_for("t_1", _visit(occurred_at=1_750_000_600))
    assert a != b


def test_one_shops_key_can_never_be_another_shops_key():
    """The tenant is inside the digest, not only in the prefix — two shops selling the same thing
    at the same second are two sales."""
    v = _visit()
    assert till_routes._key_for("t_1", v) != till_routes._key_for("t_2", v)


def test_a_sale_with_nothing_stable_on_it_is_refused_with_a_sentence():
    """A till that sends no key, no invoice number and no time of sale has given us no way to tell
    a retry from a second sale — and inventing one from OUR clock is what doubled a shop's
    history. The refusal names all three so their engineer reads instead of guessing."""
    body = till_routes.TillBatchIn(visits=[till_routes.TillVisitIn(phone="0500000000",
                                                              branch_id="brn-main")])
    request = _request(_Ops(), _Desk())
    out = asyncio.run(till_routes.record_from_till(request, body, principal=_Principal()))
    assert out["accepted"] == 0
    assert out["results"][0]["status"] == "rejected"
    for named in ("idempotency_key", "invoice_id", "occurred_at"):
        assert named in out["results"][0]["reason"]
    # ك-2: a wholly-refused batch is STILL a till heard from — the health row must not stay
    # absent, or a panel reads a shop refused every night for a month as "لم يبدأ أبداً".
    from app.core.till_health import TillHealth
    row = asyncio.run(TillHealth(request.app.state.container.datastore).get("t_1"))
    assert row is not None and row["rejected"] == 1 and row["accepted"] == 0


def test_a_shop_without_the_licence_is_refused_per_item_and_leaves_a_health_row():
    """ك-1 / ك-6: `feature.api` was checked once per BATCH with a bare `message` — the generated
    contract (gen_till_contract.py) promises the SDK one verdict PER ITEM, so an integration
    reading `results[i]` to decide what to retry saw an empty list on this refusal, treated the
    whole batch as accepted, and dropped every visit in it. And the shop is still a till heard
    from tonight — refused for a definite reason, not silent (ك-2)."""

    class _RefusingLicence:
        async def allowed(self, tenant):
            return False

    body = till_routes.TillBatchIn(visits=[
        till_routes.TillVisitIn(phone="0500000000", invoice_id="1", branch_id="brn-main"),
        till_routes.TillVisitIn(phone="0500000001", invoice_id="2", branch_id="brn-main")])
    request = _request(_Ops(), _Desk(), api_licence=_RefusingLicence())
    out = asyncio.run(till_routes.record_from_till(request, body, principal=_Principal()))

    assert out["accepted"] == 0
    assert out["total"] == 2
    assert len(out["results"]) == 2
    assert all(r["status"] == "rejected" for r in out["results"])
    assert {r["index"] for r in out["results"]} == {0, 1}

    from app.core.till_health import TillHealth
    row = asyncio.run(TillHealth(request.app.state.container.datastore).get("t_1"))
    assert row is not None and row["rejected"] == 2 and row["accepted"] == 0


def test_the_counter_shows_how_many_times_he_has_actually_been_here():
    """ب-5 · «زياراته: 0» about a man who comes every fortnight.

    The row counts visits in `visit_count`; the route asked for `visits`. `getattr` with a default
    cannot fail — that is what the third argument is for — so the wrong name and a real zero were
    the same answer, on the one screen a cashier uses to decide whether this is a regular.
    """
    ops = _Ops(customer=_Customer(visit_count=47))
    desk = _Desk(balance={"has_programme": True, "points": 30, "rewards": [],
                           "to_next_reward": 70})

    out = asyncio.run(till_routes.customer_at_the_counter(
        _request(ops, desk), phone="0500000000", principal=_Principal(tenant="t_9")))

    assert out["visits"] == 47
