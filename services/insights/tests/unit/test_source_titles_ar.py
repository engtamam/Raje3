"""insights-r2-009 (QA audit, 2026-09-12): the dispute report's "acceptance" source rendered as
the raw English word inside an otherwise-Arabic legal document because _SOURCE_TITLES_AR had no
label for it, even though contract_breach/suspended_tos scenarios both cite it."""
from __future__ import annotations

from app.core.report_render import _SOURCE_TITLES_AR


def test_acceptance_has_an_arabic_label():
    assert "acceptance" in _SOURCE_TITLES_AR
    label = _SOURCE_TITLES_AR["acceptance"]
    assert label != "acceptance"
    assert any("؀" <= ch <= "ۿ" for ch in label)
