from __future__ import annotations

from app.core.phone import canonical_phone


def test_local_leading_zero():
    assert canonical_phone("0501234567") == "+966501234567"


def test_already_international_plus():
    assert canonical_phone("+966501234567") == "+966501234567"


def test_bare_country_code_no_plus():
    assert canonical_phone("966501234567") == "+966501234567"


def test_leading_00():
    assert canonical_phone("00966501234567") == "+966501234567"


def test_empty_folds_to_empty():
    assert canonical_phone("") == ""
    assert canonical_phone(None) == ""  # type: ignore[arg-type]


def test_garbage_folds_to_empty():
    assert canonical_phone("not a phone") == ""


def test_custom_default_cc():
    assert canonical_phone("0501234567", default_cc="20") == "+20501234567"
