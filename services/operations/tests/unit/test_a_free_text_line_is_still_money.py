"""ح-6 — the customer paid 480 riyals and was rewarded for 100.

`resolve()` walks an invoice's lines and does two separate things with each: map it onto the
shop's catalogue, and add its money to `total_minor`. The addition lived INSIDE the two branches
that found or created a catalogue row — so a line the till sent without a product id was dropped
from the money as well as from the catalogue.

    غسيل            100.00     <- has a product id, counted
    خدمة إضافية     380.00     <- free text, NOT counted

Total recorded: 100.00. Points earned: 100 instead of 480. And free-text lines are not an edge
case — they are most of what a workshop writes, because the thing that broke is never in the
catalogue.

Nothing failed anywhere. The catalogue mapping and the money are different questions, and only
the first one had any business caring whether the line was recognised.
"""
from __future__ import annotations

import asyncio

from app.core.invoices import Line, resolve


class _Store:
    """The shop's catalogue, with one known service."""

    def __init__(self, services: list | None = None):
        self.services = services or []
        self.saved: list = []

    async def list(self, tenant: str, active_only: bool = False):
        return list(self.services)

    async def save(self, svc):
        self.saved.append(svc)
        return svc

    async def save_new(self, **kw):
        svc = type("S", (), kw)()
        svc.external_id = kw.get("external_id", "")
        svc.name = kw.get("name", "")
        svc.id = kw.get("id", "")
        self.services.append(svc)
        return svc


def _known(sid: str, ext: str, name: str):
    s = type("S", (), {})()
    s.id, s.external_id, s.name = sid, ext, name
    return s


def run(c):
    return asyncio.run(c)


def _resolve(lines, services=None, auto_create=True):
    n = [0]

    def new_id(prefix):
        n[0] += 1
        return f"{prefix}_{n[0]}"

    return run(resolve(lines, tenant="shop", service_store=_Store(services),
                       new_id=new_id, now=1_780_000_000, auto_create=auto_create))


def test_a_free_text_line_counts_toward_the_invoice_total():
    """THE DEFECT. 100.00 recognised + 380.00 free text is an invoice of 480.00."""
    res = _resolve([
        Line(product_id="p1", name="غسيل", quantity=1, amount_minor=10_000),
        Line(product_id="", name="خدمة إضافية", quantity=1, amount_minor=38_000),
    ], services=[_known("srv_1", "p1", "غسيل")])

    assert res.total_minor == 48_000, "the free-text line's money was dropped"
    assert res.free_text == ["خدمة إضافية"], "and it is still reported as unmapped"
    assert res.service_ids == ["srv_1"], "and it still creates no catalogue row"


def test_an_invoice_that_is_all_free_text_is_not_an_invoice_of_zero():
    """A workshop billing one repair it has never billed before. The commonest shape there is."""
    res = _resolve([Line(product_id="", name="إصلاح ناقل الحركة", quantity=1,
                         amount_minor=250_000)])
    assert res.total_minor == 250_000


def test_the_money_is_counted_even_when_we_are_told_not_to_create_services():
    """`auto_create=False` is a decision about the CATALOGUE. It was silently one about money too."""
    res = _resolve([
        Line(product_id="p9", name="خدمة جديدة", quantity=1, amount_minor=7_500),
    ], services=[], auto_create=False)

    assert res.total_minor == 7_500
    assert res.service_ids == [], "and no service was created, which is what the flag asked for"


def test_a_recognised_line_is_counted_exactly_once():
    """Moving the addition to the top of the loop must not double it for mapped lines."""
    res = _resolve([Line(product_id="p1", name="غسيل", quantity=1, amount_minor=10_000)],
                   services=[_known("srv_1", "p1", "غسيل")])
    assert res.total_minor == 10_000


def test_a_negative_line_does_not_become_a_positive_charge():
    """A discount row must not inflate the total. Whether it should REDUCE it is a till-contract
    question, and deciding that silently here would be the same class of mistake."""
    res = _resolve([
        Line(product_id="p1", name="غسيل", quantity=1, amount_minor=10_000),
        Line(product_id="", name="خصم", quantity=1, amount_minor=-3_000),
    ], services=[_known("srv_1", "p1", "غسيل")])
    assert res.total_minor == 10_000
