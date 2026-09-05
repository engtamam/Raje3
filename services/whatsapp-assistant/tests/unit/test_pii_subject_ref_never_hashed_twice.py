"""subject_ref must fold a ref of a ref back to itself — found by
ci/check_a_pseudonym_is_never_hashed_twice.py, no test anywhere had ever exercised this.

WHY IT MATTERS (د-2): an erasure fans out by the pseudonym, since that is the one identifier
every peer service holds. Hashing an already-pseudonymised value AGAIN produces the ref of a
ref, matching no row anywhere — the scan finds nothing, answers `already_absent` with 200, and
the request closes COMPLETED while every message stays exactly where it was.
"""
from __future__ import annotations

import pytest

from app.core.pii import is_subject_ref, subject_ref

SALT = "s" * 32


def test_a_real_subject_produces_a_real_pseudonym():
    ref = subject_ref(SALT, "t1", "+966500000000")
    assert is_subject_ref(ref)


def test_the_same_subject_and_tenant_always_produces_the_same_pseudonym():
    a = subject_ref(SALT, "t1", "+966500000000")
    b = subject_ref(SALT, "t1", "+966500000000")
    assert a == b


def test_a_different_tenant_produces_a_different_pseudonym_for_the_same_subject():
    a = subject_ref(SALT, "t1", "+966500000000")
    b = subject_ref(SALT, "t2", "+966500000000")
    assert a != b


def test_an_already_pseudonymised_ref_is_returned_unchanged_not_hashed_again():
    ref = subject_ref(SALT, "t1", "+966500000000")
    assert subject_ref(SALT, "t1", ref) == ref
    # AND SALT/TENANT ARE IRRELEVANT ONCE THE INPUT IS ALREADY A REF — a caller passing a
    # different tenant or even a blank salt alongside an already-folded ref must still get the
    # SAME ref back, never a fresh hash of it: the whole point is idempotence on the value itself.
    assert subject_ref(SALT, "t2", ref) == ref


def test_an_empty_salt_is_refused_for_a_real_subject():
    with pytest.raises(ValueError):
        subject_ref("", "t1", "+966500000000")


def test_an_empty_subject_is_refused():
    with pytest.raises(ValueError):
        subject_ref(SALT, "t1", "")


def test_is_subject_ref_recognises_only_the_real_shape():
    real = subject_ref(SALT, "t1", "+966500000000")
    assert is_subject_ref(real) is True
    assert is_subject_ref("+966500000000") is False
    assert is_subject_ref("sub_tooshort") is False
    assert is_subject_ref("") is False
