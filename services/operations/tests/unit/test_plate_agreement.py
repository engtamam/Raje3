"""The service must not accept a plate the screen turns away, nor the reverse.

THE TWIN OF `apps/console/src/plate-agreement.test.ts`, READING THE SAME FILE. These two decisions
were written separately and drifted apart in the expensive direction: this module accepted an
Arabic-lettered plate and the screen refused it, so the operator typed what is stamped on the car
and the save button stayed dark — no message, because a disabled button cannot explain itself.

`fixtures/plates.json` is the one list. Whichever side changes, the other side's suite goes red
naming the same plate, which is the whole point: a disagreement between a screen and a service is
invisible to both of their own test suites.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from app.core.plate import is_plausible

ROOT = pathlib.Path(__file__).resolve().parents[4]
CORPUS = json.loads((ROOT / "fixtures" / "plates.json").read_text(encoding="utf-8"))


def test_there_is_a_corpus_to_agree_on():
    """SILENCE IS NOT AGREEMENT. An empty list would make every assertion below vacuously true."""
    assert len(CORPUS["cases"]) > 4


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda c: c["note"][:40])
def test_the_service_admits_exactly_who_the_screen_admits(case):
    assert is_plausible(case["plate"]) is case["accepted"], case["note"]
