"""The global anonymous referral code — Phase 1 (app/core/referral_code.py)."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.referral_code import (
    BY_CODE, BY_PHONE, CodeMintFailed, _LETTERS, code_for_phone, phone_for_code,
)
from tests.contracts.util import run


@pytest.fixture
def store():
    return MemoryDataStore()


def test_a_phone_gets_a_real_five_character_code(store):
    code = run(code_for_phone(store, "0501234567"))
    assert len(code) == 5
    assert code[0] in _LETTERS, "the first character must always be a letter"


def test_the_same_phone_always_gets_the_same_code_back(store):
    first = run(code_for_phone(store, "0501234567"))
    second = run(code_for_phone(store, "0501234567"))
    assert first == second


def test_different_typed_shapes_of_the_same_phone_fold_to_one_code(store):
    """`0501234567`, `+966501234567` and `966501234567` are one human — the whole point of
    normalizing before ever touching the store."""
    a = run(code_for_phone(store, "0501234567"))
    b = run(code_for_phone(store, "+966501234567"))
    c = run(code_for_phone(store, "966501234567"))
    assert a == b == c


def test_two_different_phones_never_share_a_code(store):
    a = run(code_for_phone(store, "0501111111"))
    b = run(code_for_phone(store, "0502222222"))
    assert a != b


def test_an_empty_or_unparseable_phone_is_refused(store):
    with pytest.raises(CodeMintFailed):
        run(code_for_phone(store, ""))
    with pytest.raises(CodeMintFailed):
        run(code_for_phone(store, "not a phone"))


def test_the_reverse_lookup_finds_the_phone_a_code_belongs_to(store):
    code = run(code_for_phone(store, "0501234567"))
    assert run(phone_for_code(store, code)) == "+966501234567"


def test_reverse_lookup_of_an_unknown_code_returns_none_not_an_error(store):
    assert run(phone_for_code(store, "ZZZZZ")) is None


def test_reverse_lookup_is_case_insensitive_and_trims_whitespace(store):
    code = run(code_for_phone(store, "0501234567"))
    assert run(phone_for_code(store, f"  {code.lower()}  ")) == "+966501234567"


def test_only_the_by_phone_and_by_code_collections_are_ever_written(store):
    """No third collection, no stray field — the module's own promise ('the ONLY fact this module
    keeps') proven, not just claimed in a docstring."""
    run(code_for_phone(store, "0501234567"))
    assert set(store._data.keys()) == {BY_PHONE, BY_CODE}
    phone_row = list(store._data[BY_PHONE].values())[0]
    assert set(phone_row.keys()) - {"expires"} == {"phone", "code"}


def test_minting_is_atomic_under_real_concurrency_for_the_same_phone(store):
    """The exact race this module's own two-phase claim exists to close: many callers asking for
    the SAME new phone's code at once must all get back the identical code, never two different
    ones and never a crash."""
    async def _all():
        return await asyncio.gather(*(code_for_phone(store, "0507654321") for _ in range(20)))

    codes = run(_all())
    assert len(set(codes)) == 1, "concurrent requests for one phone minted more than one code"


def test_minting_is_atomic_under_real_concurrency_across_different_phones(store):
    async def _one(n: int) -> str:
        return await code_for_phone(store, f"05{n:08d}")

    async def _all():
        return await asyncio.gather(*(_one(n) for n in range(20)))

    codes = run(_all())
    assert len(set(codes)) == 20, "two different phones ended up sharing one code"


def test_length_escalates_once_the_short_space_is_exhausted(store, monkeypatch):
    """Forces every 5-character draw to collide, so minting must fall through to 6 characters —
    proven by actually exhausting the space (with a tiny monkeypatched alphabet), not by reading
    the constant and trusting the logic around it."""
    import itertools

    import app.core.referral_code as mod

    monkeypatch.setattr(mod, "_LETTERS", "AB")
    monkeypatch.setattr(mod, "_ALPHABET", "AB")
    monkeypatch.setattr(mod, "_LENGTH_ESCALATION_STREAK", 3)

    # Exhaust every possible 5-character code in this tiny 2-symbol alphabet (2^5 = 32 codes) by
    # claiming them all directly, bypassing the module's own generator.
    for i, letters in enumerate(itertools.product("AB", repeat=5)):
        code = "".join(letters)
        run(store.claim(BY_CODE, code, {"phone": f"filler{i}", "code": code},
                        ttl_seconds=mod._PERMANENT_TTL_SECONDS, now=1.0))

    code = run(code_for_phone(store, "0509999999"))
    assert len(code) == 6, "minting did not escalate to 6 characters once 5-character space was full"
