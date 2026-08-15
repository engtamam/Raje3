"""The code a customer reads out at the counter."""
from __future__ import annotations

from app.core.coupons import ALPHABET, code_for, looks_like_code, normalise
from app.core.rendering import _CODE


def test_the_same_send_always_produces_the_same_code():
    """A retry after a timeout must not hand him a second coupon — and a random code would need a
    write on the send path to be stable."""
    assert code_for("cmp:c1:r1:sub_a") == code_for("cmp:c1:r1:sub_a")


def test_two_customers_of_one_campaign_hold_different_codes():
    """Otherwise the code measures the campaign and not the person, and «who came back» — the only
    question worth asking — stays unanswerable."""
    assert code_for("cmp:c1:r1:sub_a") != code_for("cmp:c1:r1:sub_b")


def test_the_code_is_the_shape_the_renderer_accepts():
    """The send validates it (rendering._CODE). A code we generate and then refuse to send would
    be a message that fails after Meta approved the template."""
    assert _CODE.fullmatch(code_for("cmp:c1:r1:sub_a"))


def test_nothing_confusable_is_ever_printed():
    """It is read aloud by somebody not looking at the screen and typed by somebody who is."""
    for bad in "OIL01":
        assert bad not in ALPHABET


def test_a_send_with_no_key_carries_no_code():
    assert code_for("") == ""


def test_what_the_customer_says_is_recognised_however_he_says_it():
    code = code_for("cmp:c1:r1:sub_a")
    assert normalise(code.lower()) == code
    assert normalise(code.replace("-", "")) == code
    assert normalise(f" {code} ") == code


def test_free_text_at_a_till_is_refused_before_it_becomes_a_scan():
    assert looks_like_code("خصم") is False
    assert looks_like_code("RJ-") is False
    assert looks_like_code(code_for("cmp:c1:r1:sub_a")) is True
