"""The four tests the definition of done requires, plus the phone normalisation they rest on.

Not coverage for its own sake. Each maps to a failure that has actually happened on this platform
or would end the product on its first day in a workshop:

  1. cross-tenant refusal, on READ and on WRITE
  2. the idempotent path, called twice
  3. the deny-by-default path, asserted refused
  4. the failure mode, asserting a LEGIBLE error rather than merely a non-200
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.operations import OperationError, Operations, _normalise_phone
from app.core.stores import CustomerStore, VisitStore

SALT = "s" * 32
A = "tnt_alpha"
B = "tnt_beta"


def run(coro):
    # asyncio.run, not get_event_loop: the latter was removed in 3.14, and a test helper that
    # depends on a deprecated global is a test suite with an expiry date.
    return asyncio.run(coro)


@pytest.fixture()
def ops():
    store = MemoryDataStore()
    return Operations(store=store, pii_salt=SALT), store


# ── 1. cross-tenant isolation, read AND write ─────────────────────────────────────────────────
def test_a_tenant_cannot_read_another_tenants_customer(ops):
    svc, store = ops
    run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"]))

    # Read-only proof is HALF a proof, so both halves are here. First: B cannot see A's customer.
    assert run(svc.customer_by_phone(B, "0501234567")) is None
    assert run(svc.recent_customers(B)) == []
    assert len(run(svc.recent_customers(A))) == 1


def test_a_tenant_cannot_write_into_another_tenants_row(ops):
    """The half that is usually missing, and the one where damage is permanent.

    B records the SAME phone number. That must produce B's own separate customer, not an update to
    A's row — otherwise one workshop's entry silently rewrites another's record of the same person.
    """
    svc, store = ops
    run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"], name="A's name"))
    run(svc.record_visit(tenant=B, phone="0501234567", service_ids=["srv_9"], name="B's name"))

    a = run(svc.customer_by_phone(A, "0501234567"))
    b = run(svc.customer_by_phone(B, "0501234567"))
    assert a.id != b.id
    assert a.name == "A's name"          # untouched by B's write
    assert b.name == "B's name"
    # The pseudonyms differ too: the same person at two establishments must not be correlatable
    # across them by comparing refs.
    assert a.subject_ref != b.subject_ref


def test_a_customer_id_from_another_tenant_is_not_readable(ops):
    svc, _ = ops
    res = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"]))
    # Holding a valid id is not enough. This is what makes the 404 in the route honest rather than
    # a handler that forgot its filter.
    assert run(svc.customer_record(B, res.customer.id)) is None
    assert run(svc.customer_record(A, res.customer.id)) is not None


# ── 2. the idempotent path, called twice ──────────────────────────────────────────────────────
def test_a_double_tap_records_one_visit(ops):
    svc, store = ops
    key = "entry-abc-123"
    first = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"],
                                 idempotency_key=key))
    second = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"],
                                  idempotency_key=key))

    assert first.duplicate is False
    assert second.duplicate is True
    assert first.visit.id == second.visit.id
    # And exactly one customer: the guard runs BEFORE customer creation, which is what stops a
    # double tap from also producing a second customer record.
    assert len(run(svc.recent_customers(A))) == 1
    assert run(svc.customer_by_phone(A, "0501234567")).visit_count == 1


def test_two_genuine_visits_are_two_visits(ops):
    """The other side of the same coin, and the reason the key is client-generated.

    The same customer really does come back. Without a per-entry key from the screen, a
    server-side guard would have to guess whether two identical requests are a double tap or a
    returning customer — and in a tyre shop it is routinely the latter.
    """
    svc, _ = ops
    run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"], idempotency_key="e1"))
    run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"], idempotency_key="e2"))
    assert run(svc.customer_by_phone(A, "0501234567")).visit_count == 2


# ── 3. deny by default ────────────────────────────────────────────────────────────────────────
def test_a_visit_without_a_tenant_is_refused(ops):
    svc, _ = ops
    with pytest.raises(OperationError):
        run(svc.record_visit(tenant="", phone="0501234567", service_ids=["srv_1"]))


def test_a_visit_without_a_service_is_refused(ops):
    """A visit with no service is a tap on the save button by mistake. Recording it would put a
    meaningless row into the data every reminder and metric is derived from."""
    svc, _ = ops
    with pytest.raises(OperationError):
        run(svc.record_visit(tenant=A, phone="0501234567", service_ids=[]))


# ── 4. the failure mode, with a LEGIBLE error ─────────────────────────────────────────────────
def test_a_missing_phone_says_what_to_do(ops):
    svc, _ = ops
    with pytest.raises(OperationError) as exc:
        run(svc.record_visit(tenant=A, phone="", service_ids=["srv_1"]))
    # The message reaches an operator's screen. "a phone number is required" is actionable;
    # "ValidationError" is not, and an unactionable error trains people to ignore errors.
    assert "phone" in str(exc.value).lower()


def test_a_seam_failure_does_not_lose_the_visit(ops):
    """The visit is durable before any seam runs, so a broken search must not surface as a failed
    save. The operator's work is safe; the index catches up."""
    from app.core.seams import Seams

    class Exploding:
        driver = "boom"

        async def index(self, **kw):
            raise RuntimeError("search is down")

    svc, store = ops
    res = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"]))
    seams = Seams(search=Exploding(), events=None, telemetry=None)
    run(seams.after_visit(res))                      # must not raise
    assert run(svc.customer_by_phone(A, "0501234567")) is not None


# ── the normalisation everything above rests on ───────────────────────────────────────────────
@pytest.mark.parametrize("typed", ["0501234567", "501234567", "+966501234567", "966501234567",
                                   "00966501234567", "05 01 23 45 67"])
def test_every_way_a_saudi_number_is_typed_is_one_customer(typed):
    """Six spellings of one number. Stored differently they become six customers with one visit
    each instead of one customer with six — and the entire product is recognising the customer
    who came back."""
    assert _normalise_phone(typed) == "966501234567"


def test_an_unusual_number_is_kept_rather_than_refused():
    """A landline, a foreign number, a genuine oddity. Refusing it would block a real visit to
    enforce a format nobody promised."""
    assert _normalise_phone("0112345678") == "112345678"
    assert _normalise_phone("") == ""


# ── two clocks: the device's and ours ─────────────────────────────────────────────────────────
# These exist because an integration replays visits after an outage, and a cashier's clock is not
# something we can trust. `occurred_at` is what reminders schedule from, so every one of these is a
# wrong reminder prevented.
import time as _time


def test_a_visit_recorded_here_has_both_clocks_agreeing(ops):
    svc, _ = ops
    res = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"]))
    assert res.visit.occurred_at == res.visit.created


def test_a_replayed_visit_keeps_the_time_it_happened(ops):
    """A batch drained two days late describes a customer who was here two days ago. Stamping it
    with the receive time would push their whole reminder schedule two days out."""
    svc, _ = ops
    two_days_ago = int(_time.time()) - 2 * 24 * 3600
    res = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"],
                               idempotency_key="e1", occurred_at=two_days_ago))
    assert res.visit.occurred_at == two_days_ago
    assert res.visit.created > res.visit.occurred_at        # ours is when we received it


def test_a_device_clock_in_the_future_is_clamped(ops):
    """A future timestamp is always wrong: we received it, so it has happened. Trusting one would
    schedule a reminder from a date that has not arrived."""
    svc, _ = ops
    res = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"],
                               occurred_at=int(_time.time()) + 90 * 24 * 3600))
    assert res.visit.occurred_at <= res.visit.created


def test_a_dead_battery_clock_is_clamped(ops):
    """A tablet that lost its battery comes back at the epoch. Left alone it would mark every
    customer permanently absent and fire a win-back at somebody who was here this morning."""
    svc, _ = ops
    res = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"], occurred_at=1))
    assert res.visit.occurred_at == res.visit.created


def test_a_late_replay_cannot_drag_last_visit_backwards(ops):
    """An old visit arriving after a newer one must not rewind the customer's last-visit date —
    that would schedule a reminder that has already passed and mark a returning customer absent."""
    svc, _ = ops
    now = int(_time.time())
    run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"], idempotency_key="new",
                         occurred_at=now - 3600))
    run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"], idempotency_key="old",
                         occurred_at=now - 5 * 24 * 3600))
    c = run(svc.customer_by_phone(A, "0501234567"))
    assert c.last_visit == now - 3600
    assert c.visit_count == 2          # both are real visits; only the DATE refuses to go back


# ── unknown services from a till: absorbed, never refused ─────────────────────────────────────
from app.core.models import Service as _Service
from app.core.stores import ServiceStore as _SS, new_id as _nid


def _with_catalogue(store):
    run(_SS(store).save(_Service(id="srv_oil", tenant=A, name="تغيير زيت", cycle_days=120)))
    run(_SS(store).save(_Service(id="srv_other", tenant=A, name="خدمة أخرى", catchall=True)))


def test_a_till_sending_an_unknown_service_keeps_the_visit(ops):
    """The alternative loses the visit — and a lost visit loses the customer from the product.
    Losing the service NAME is the small cost; losing the visit costs the premise."""
    svc, store = ops
    _with_catalogue(store)
    res = run(svc.record_visit(tenant=A, phone="0501234567",
                               service_ids=["srv_oil", "pos_sku_9931"],
                               idempotency_key="k1", allow_unknown_services=True))
    assert res.visit.id
    assert "srv_other" in res.visit.service_ids          # folded into the catch-all
    assert "srv_oil" in res.visit.service_ids            # the known one survives
    assert res.unknown_services == ["pos_sku_9931"]      # and it is REPORTED, not swallowed
    assert "pos_sku_9931" in res.visit.custom_service    # the label is preserved


def test_the_field_screen_still_fails_loudly_on_an_unknown_service(ops):
    """On our own screen the operator picks from the grid, so an unknown id is a bug — absorbing
    it there would hide a broken client instead of surfacing it."""
    svc, store = ops
    _with_catalogue(store)
    res = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["not_a_service"],
                               idempotency_key="k2"))
    # No absorption without the flag: the id is recorded as sent, and nothing is silently rewritten.
    assert res.unknown_services == []
    assert res.visit.service_ids == ["not_a_service"]


def test_a_tenant_without_a_catch_all_gets_a_clean_refusal(ops):
    """Named and actionable, rather than a crash or a silently dropped service."""
    svc, store = ops
    run(_SS(store).save(_Service(id="srv_oil", tenant=A, name="تغيير زيت")))
    with pytest.raises(OperationError) as exc:
        run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["unknown"],
                             idempotency_key="k3", allow_unknown_services=True))
    assert "أخرى" in str(exc.value)


# ── the offer, spent on the visit (§5.6.2) ────────────────────────────────────────────────────
def test_an_offer_is_recorded_on_the_visit_and_only_once(ops):
    """«عرضٌ واحد لكل زيارة» — enforced HERE, because here is where the visit is.

    The mark used to be written into the send log, and §5.6.2 says why that cannot be: the log is
    append-only and every cap in 5.8 is counted against it. So reminders judges which offer
    applies and this service records that it was applied.

    A SECOND TAP RETURNS THE FIRST ANSWER and asks nobody anything. A double tap at a counter is
    one intention, never two discounts on one invoice.
    """
    svc, store = ops
    asked = []

    async def chooser(*, tenant, subject_ref, service_ids):
        asked.append(subject_ref)
        return {"ref": "s1", "text": "غسلة مجانية"}

    svc.with_offer_chooser(chooser)
    v = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"],
                             idempotency_key="key-1"))

    first = run(svc.apply_offer(tenant=A, visit_id=v.visit.id, subject_ref="sub_a"))
    again = run(svc.apply_offer(tenant=A, visit_id=v.visit.id, subject_ref="sub_a"))

    assert first["ref"] == "s1" and first["text"] == "غسلة مجانية"
    assert again == first
    # AND THE SECOND TAP NEVER ASKED. Asking again could return a DIFFERENT offer and quietly spend
    # a second one on the same invoice.
    assert asked == ["sub_a"]

    # It is on the visit, which is what both screens read.
    stored = run(VisitStore(store).get(A, v.visit.id))
    assert stored.offer_ref == "s1" and stored.offer_used_at > 0


def test_the_offer_can_be_applied_by_the_key_the_screen_actually_holds(ops):
    """«تسجيل زيارة» queues offline: it has its own idempotency key and never learns our id."""
    svc, _ = ops
    svc.with_offer_chooser(lambda **kw: _answer({"ref": "s9", "text": "خصم"}))
    run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"],
                         idempotency_key="key-9"))

    assert run(svc.apply_offer(tenant=A, visit_id="key-9", subject_ref="sub_a"))["ref"] == "s9"


def test_no_chooser_refuses_rather_than_guesses(ops):
    """A discount is money. A missing peer must never be the reason one is granted."""
    svc, _ = ops
    v = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["srv_1"]))

    with pytest.raises(OperationError):
        run(svc.apply_offer(tenant=A, visit_id=v.visit.id, subject_ref="sub_a"))


async def _answer(value):
    return value


def test_a_customer_is_findable_by_every_plate_he_holds():
    """IN A TYRE SHOP THE CUSTOMER IS THE CAR, and search knew nothing about cars.

    Only `phone` and `name` were indexed, so an operator reading a plate off a bumper as it rolled
    in found nothing at all — on the screen used a hundred times a day, in the sector this product
    was built for first.

    AND BOTH CARS, NOT THE ONE IN FRONT OF US. «ممكن عندي سيارتين برقمي»: indexing only this
    visit's plate leaves the other car unfindable until the day it happens to come in.
    """
    class Spy:
        def __init__(self):
            self.docs = []

        async def index(self, **kw):
            self.docs.append(kw)

    store = MemoryDataStore()
    svc = Operations(store=store, pii_salt=SALT)
    spy = Spy()
    seams = __import__("app.core.seams", fromlist=["Seams"]).Seams(search=spy)

    run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["s"], plate="ABC 1234"))
    r = run(svc.record_visit(tenant=A, phone="0501234567", service_ids=["s"], plate="XYZ 7788"))
    run(seams.after_visit(r))

    indexed = spy.docs[-1]["fields"]["plate"]
    assert "ABC 1234" in indexed and "XYZ 7788" in indexed
