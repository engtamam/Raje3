"""The preview offers the wording as WRITTEN as well as filled, and names the blanks.

READING THIS SHEET AS THE OWNER WOULD: «العميل يقرا الرساله ما يعرف وين الفراغات». The sheet showed one thing —
the example his customer receives — and from a filled sentence you cannot tell which words belong
to the shop forever and which change with every person. If he then wants to write his own wording,
he has no idea where the blanks go or what may fill them.

THE BLANKS ARE NAMED, NOT NUMBERED, AND THAT IS THE WHOLE POINT. `{{2}}` is a customer's name in
one wording and a service in the next — Meta numbers positions and names nothing. What carries the
meaning is `fills`, the list beside the body, so the screen shows «[اسم العميل]» from the same
vocabulary the editor puts on its chips: one word for a blank everywhere it is seen.

AND A BLANK WITH NO DECLARED MEANING STAYS A NUMBER. A wrong name over a blank is worse than a
bare one — he would write his text around a promise the template does not keep.
"""
from __future__ import annotations

from app.api.v1.owner import _with_named_blanks


def test_each_blank_is_shown_by_what_fills_it():
    row = {"body": "أهلاً {{1}}، تم تسجيل زيارتك لدى {{2}}. {{3}} 🎁",
           "fills": ["customer", "shop", "catalogue"]}
    shown = _with_named_blanks(row)
    assert "[اسم العميل]" in shown
    assert "[اسم محلّك]" in shown
    # THE WORDS AROUND THE BLANKS ARE UNTOUCHED — this is the wording, not a description of it.
    assert shown.startswith("أهلاً [اسم العميل]، تم تسجيل زيارتك لدى")
    assert "{{1}}" not in shown and "{{2}}" not in shown


def test_a_blank_nobody_declared_stays_a_number_rather_than_being_guessed():
    row = {"body": "أهلاً {{1}}، رصيدك {{2}}", "fills": ["customer"]}
    shown = _with_named_blanks(row)
    assert "[اسم العميل]" in shown
    # NOT «[الرصيد]», WHICH WE DO NOT KNOW. Naming it would be the screen inventing a meaning the
    # template never declared, and he would write around it.
    assert "{{2}}" in shown


def test_a_wording_with_no_blanks_comes_back_exactly_as_written():
    row = {"body": "شكراً لزيارتك", "fills": []}
    assert _with_named_blanks(row) == "شكراً لزيارتك"


def test_it_never_raises_on_a_row_that_is_missing_its_parts():
    # THE SHEET MUST NOT FALL OVER on a library row that predates `fills`. An exception here would
    # empty the whole list of wordings, which is the screen's entire content.
    assert _with_named_blanks({}) == ""
    assert _with_named_blanks({"body": "نصّ"}) == "نصّ"
