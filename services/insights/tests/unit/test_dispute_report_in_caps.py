"""insights-r2-008 (QA audit, 2026-09-12): DisputeReportIn.scenario lacked the max_length its
sibling fields (phone, file_format) both carry, letting an unbounded string reach the scenario
lookup in the dispute-report endpoint."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.v1.insights import DisputeReportIn


def test_scenario_rejects_an_oversized_value():
    with pytest.raises(ValidationError):
        DisputeReportIn(phone="0500000000", scenario="s" * 65, file_format="docx")


def test_scenario_accepts_a_real_value():
    DisputeReportIn(phone="0500000000", scenario="contract_breach", file_format="docx")
