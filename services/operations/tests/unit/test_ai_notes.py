"""What the owner told the WhatsApp AI assistant about his own shop.

WHY THIS IS NOT `sanitise_owner_text`. That function rejects newlines and phone numbers because it
fills a WhatsApp TEMPLATE VARIABLE a customer reads verbatim; this field is paragraphs of real
instructions for an AI, so multi-line prose is exactly what it must accept — while still refusing
control characters and an oversized payload, and redacting anything that looks like a personal
identifier before it is ever stored.
"""
from __future__ import annotations

import asyncio

import pytest

from app.core import ai_notes as AN


def run(coro):
    return asyncio.run(coro)


class _Store:
    def __init__(self, rows=None):
        self.rows = dict(rows or {})

    async def get(self, collection, key):
        return self.rows.get((collection, key))

    async def put(self, collection, key, row):
        self.rows[(collection, key)] = row


class _Unreadable(_Store):
    async def get(self, collection, key):
        raise RuntimeError("the datastore is down")


# ── sanitise() ────────────────────────────────────────────────────────────────
def test_ordinary_multiline_prose_is_accepted_unchanged():
    text = "نفتح من السبت للخميس.\nما نقبل الدفع نقداً.\nالأسعار تشمل الضريبة."
    out = AN.sanitise(text)
    assert out.text == text
    assert out.hits == ()


def test_clearing_to_empty_is_a_valid_answer_not_an_error():
    """Unlike a template variable, an owner emptying this field means "nothing to add", not a
    refusal — see the module's own docstring."""
    out = AN.sanitise("")
    assert out.text == ""
    assert out.hits == ()


def test_control_characters_are_refused():
    with pytest.raises(AN.AiNotesError):
        AN.sanitise("نص فيه حرف تحكّم \x07 مخفي")


def test_text_longer_than_the_cap_is_refused_not_silently_truncated():
    with pytest.raises(AN.AiNotesError):
        AN.sanitise("أ" * (AN.MAX_AI_NOTES + 1))


def test_a_phone_number_is_redacted_and_reported():
    out = AN.sanitise("اتصل بنا على 0501234567 لو احتجت")
    assert "0501234567" not in out.text
    assert "phone" in out.hits


def test_an_iban_is_redacted_and_reported():
    out = AN.sanitise("رقم الحساب SA0380000000608010167519 للتحويل")
    assert "SA0380000000608010167519" not in out.text
    assert "iban" in out.hits


# ── AiNotesStore ──────────────────────────────────────────────────────────────
def test_a_shop_that_never_wrote_anything_reads_back_empty():
    assert run(AN.AiNotesStore(_Store()).get("t1")) == ""


def test_writing_then_reading_round_trips():
    store = _Store()
    run(AN.AiNotesStore(store).set("t1", "نفتح من السبت للخميس"))
    assert run(AN.AiNotesStore(store).get("t1")) == "نفتح من السبت للخميس"


def test_one_shops_notes_are_not_another_shops():
    store = _Store()
    run(AN.AiNotesStore(store).set("t1", "ملاحظات المحل الأول"))
    assert run(AN.AiNotesStore(store).get("t2")) == ""


def test_an_unreadable_row_reads_back_empty_rather_than_failing_the_screen():
    assert run(AN.AiNotesStore(_Unreadable()).get("t1")) == ""


def test_a_missing_tenant_reads_back_empty():
    assert run(AN.AiNotesStore(_Store()).get("")) == ""
