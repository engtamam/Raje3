"""«ساعدوني» — the queue behind the button.

WHY THE BUTTON EXISTS. We took ourselves out from between the owner and Meta on purpose («هو يقرر
ونحط ميزة ساعدوني»). The cost is that a refusal arrives in English, from a reviewer he cannot
reach, about a policy he has never read — and what follows is always the same: he edits a word,
resubmits, is refused again, and after the third time he stops using the feature.
"""
from __future__ import annotations

import asyncio

import pytest

from app.core.help_requests import ANSWERED, HelpRequestError, HelpRequestStore, OPEN


class _Store:
    """The datastore's two calls this uses, and nothing else."""

    def __init__(self):
        self.rows: dict[str, dict] = {}

    async def put(self, collection, key, row):
        self.rows[f"{collection}/{key}"] = dict(row)

    async def get(self, collection, key):
        return self.rows.get(f"{collection}/{key}")

    async def list(self, collection):
        return [r for k, r in self.rows.items() if k.startswith(f"{collection}/")]


def run(c):
    return asyncio.run(c)


def store():
    return HelpRequestStore(_Store())


ASK = {"name": "salon_visit_confirmation_1", "reason_id": "visit_confirmation",
       "body": "أهلاً {{1}}", "refusal": "Template contains a URL shortener"}


def test_asking_keeps_meta_s_words_and_his_text_exactly():
    """WHOEVER ANSWERS HAS TO SEE WHAT THE REVIEWER ACTUALLY SAID. Our paraphrase of a rejection
    is how support ends up solving a problem we invented."""
    s = store()
    row = run(s.ask("t1", **ASK))
    assert row["refusal"] == "Template contains a URL shortener"
    assert row["body"] == "أهلاً {{1}}"
    assert row["status"] == OPEN


def test_pressing_twice_does_not_open_two_tickets():
    """HE PRESSES AGAIN BECAUSE NOTHING VISIBLE HAPPENED — the most human thing on this screen.
    A queue that grows a row each time punishes him for our silence."""
    s = store()
    run(s.ask("t1", **ASK))
    run(s.ask("t1", **ASK))
    assert len(run(s.list("t1"))) == 1


def test_a_second_press_keeps_his_newer_note():
    """The second attempt usually carries the better explanation — «أبغى أقول إن الخصم للفرع
    الجديد فقط» — and losing it would waste the one thing he bothered to type."""
    s = store()
    run(s.ask("t1", **ASK, note="أول"))
    row = run(s.ask("t1", **ASK, note="الخصم للفرع الجديد فقط"))
    assert row["note"] == "الخصم للفرع الجديد فقط"


def test_the_body_stays_frozen_even_when_he_keeps_editing():
    """He edits the draft while he waits. Answering a question about a text that has since changed
    is how support ends up arguing with a customer about what he typed."""
    s = store()
    run(s.ask("t1", **ASK))
    row = run(s.ask("t1", **{**ASK, "body": "نصّ مختلف تماماً"}))
    assert row["body"] == "أهلاً {{1}}"


def test_one_shop_never_sees_another_s_requests():
    s = store()
    run(s.ask("t1", **ASK))
    run(s.ask("t2", **{**ASK, "name": "other_1"}))
    assert [r["tenant"] for r in run(s.list("t1"))] == ["t1"]


def test_the_platform_queue_shows_every_shop_and_the_open_ones_first():
    """An empty tenant means EVERYBODY, and it is only reachable from a `platform.*` route."""
    s = store()
    run(s.ask("t1", **ASK))
    run(s.ask("t2", **{**ASK, "name": "other_1"}))
    assert len(run(s.list())) == 2
    assert len(run(s.list(status=OPEN))) == 2


def test_answering_closes_it_and_keeps_what_was_said():
    """KEPT, NOT DELETED. The next shop refused for the same Meta rule is answered from this row,
    and a queue that empties itself teaches us nothing about which rule keeps catching people."""
    s = store()
    run(s.ask("t1", **ASK))
    row = run(s.answer("t1", ASK["name"], answer="احذف الرابط المختصر واكتب العنوان كاملاً"))
    assert row["status"] == ANSWERED
    assert "الرابط" in row["answer"]
    assert run(s.list("t1", status=OPEN)) == []


def test_answering_a_request_that_does_not_exist_says_so():
    with pytest.raises(HelpRequestError):
        run(store().answer("t1", "nope", answer="x"))


def test_a_new_refusal_after_an_answer_opens_a_fresh_request():
    """The old one is closed and kept; this is a different problem on the same text, and folding
    it into the answered row would hide that we failed to solve it the first time."""
    s = store()
    run(s.ask("t1", **ASK))
    run(s.answer("t1", ASK["name"], answer="جرّب كذا"))
    row = run(s.ask("t1", **{**ASK, "refusal": "Now it says something else"}))
    assert row["status"] == OPEN
    assert row["refusal"] == "Now it says something else"
