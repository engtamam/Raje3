"""The service records whoever the field screen offers it — and the screen may not be stricter.

THE TWIN OF `apps/console/src/phone-agreement.test.ts`, READING THE SAME FILE. `VisitIn` asks for
three characters and the till asks for none at all, while the screen demanded a Saudi mobile: a
Gulf visitor or a company landline left the save button dark with no message, though the same
customer could be recorded through the till. `fixtures/phones.json` is the one list.

WHAT THIS ASSERTS IS THE ROUTE'S OWN MODEL, not a copy of its rule. If somebody tightens `VisitIn`
one day, this goes red naming the customer that stops being recordable — which is the question the
screen and the service kept answering differently.
"""
from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from app.api.v1.field import VisitIn
from app.core.operations import _normalise_phone

ROOT = pathlib.Path(__file__).resolve().parents[4]
CORPUS = json.loads((ROOT / "fixtures" / "phones.json").read_text(encoding="utf-8"))


def _records(phone: str) -> bool:
    try:
        VisitIn(phone=phone, service_ids=["s1"])
    except ValidationError:
        return False
    return True


def test_there_is_a_corpus_to_agree_on():
    """SILENCE IS NOT AGREEMENT — an empty list would pass every case below."""
    assert len(CORPUS["cases"]) > 4


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda c: c["note"][:40])
def test_the_route_records_whoever_the_screen_offers(case):
    assert _records(case["phone"]) is case["accepted"], case["note"]


@pytest.mark.parametrize("case", [c for c in CORPUS["cases"] if c["accepted"]],
                         ids=lambda c: c["note"][:40])
def test_an_unusual_number_is_stored_as_typed_rather_than_dropped(case):
    """THE OTHER HALF OF THE PROMISE. Recording him is worth nothing if the number is then thrown
    away: `_normalise_phone` folds and canonicalises a Saudi mobile and keeps everything else as
    the digits it was given."""
    assert _normalise_phone(case["phone"]) != ""
