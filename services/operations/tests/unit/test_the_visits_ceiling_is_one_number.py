"""The most rows one visits read may carry is ONE declared number, and the route enforces that one.

WHAT THIS IS WRITTEN AFTER, AND IT TOOK THE WHOLE DASHBOARD DOWN SILENTLY. This route's model said
`limit: int = Field(default=200, ge=1, le=1000)`. insights asked for `SNAPSHOT_VISIT_LIMIT: 5000` —
what ninety-day indicators need on a busy shop. Both numbers were defensible; nothing had ever put
them side by side.

So every snapshot computation was refused 422 BEFORE ANY WORK WAS DONE. Not slow, not partial:
never computed, for any establishment. The nightly sweep logged `{"computed": 0, "failed": [...]}`
and the owner's «حدّث الآن» answered 500.

The ceiling is config now, and `ci/check_paired_config.py` fails the build if the two services'
declarations ever differ again. This test holds the third side: that the ROUTE actually enforces
the declared number rather than a literal somebody typed beside it.
"""
from __future__ import annotations

from app.api.internal import VisitsSinceIn
from app.config import get_settings

import pytest
from pydantic import ValidationError


def test_the_route_accepts_exactly_what_the_declaration_allows():
    ceiling = get_settings().VISITS_PAGE_MAX
    # THE NUMBER INSIGHTS ACTUALLY SENDS. Before the fix this raised, and every snapshot with it.
    assert VisitsSinceIn(tenant="t", since=0, limit=ceiling, newest_first=True).limit == ceiling


def test_one_row_past_the_ceiling_is_still_refused():
    """The cap is raised, not removed — an unbounded read is the memory failure it guards against."""
    with pytest.raises(ValidationError):
        VisitsSinceIn(tenant="t", since=0, limit=get_settings().VISITS_PAGE_MAX + 1)


def test_the_ceiling_is_not_a_literal_in_the_route():
    """Read from config, so the two services can be checked against ONE declaration.

    A number typed into the model is a number the other side cannot be compared with — which is
    exactly how 1000 and 5000 lived beside each other for as long as they did.
    """
    import inspect

    from app.api import internal

    source = inspect.getsource(internal.VisitsSinceIn)
    assert "VISITS_PAGE_MAX" in source, source
