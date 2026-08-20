"""§١٣'s consent-scoped ticket reads — the properties worth a test:

  * no configured URL is reported, not crashed on
  * a 409 (no active grant) is the honest common case, not an error
  * a per-ticket read failure is skipped, never aborts the whole average
  * averages are computed only over tickets that actually carry that KPI
"""
from __future__ import annotations

import pytest

from app.core.tickets import TicketReader


class FakeTicketHttp:
    """Answers by exact URL match — same idiom as test_commission.py's FakeBillingHttp."""

    def __init__(self, answers: dict[str, tuple[int, dict]]) -> None:
        self.answers = answers
        self.calls: list[str] = []

    def call(self, url, *, method, body=None, internal=False):
        self.calls.append(url)
        for prefix, answer in self.answers.items():
            if url.startswith(prefix):
                return answer
        return 500, {}


@pytest.mark.anyio
async def test_no_url_configured_is_reported_not_raised():
    reader = TicketReader(http=FakeTicketHttp({}), ticket_service_url="")
    out = await reader.support_kpis(tenant="t-1", grantee="aff-1")
    assert out == {"available": False, "reason": "ticket_service_not_configured"}


@pytest.mark.anyio
async def test_no_active_grant_is_the_honest_common_case():
    http = FakeTicketHttp({"http://tickets:8000/internal/tickets?": (409, {})})
    reader = TicketReader(http=http, ticket_service_url="http://tickets:8000")
    out = await reader.support_kpis(tenant="t-1", grantee="aff-1")
    assert out == {"available": False, "reason": "no_active_grant"}


@pytest.mark.anyio
async def test_an_unreachable_ticket_service_reports_the_status():
    http = FakeTicketHttp({"http://tickets:8000/internal/tickets?": (503, {})})
    reader = TicketReader(http=http, ticket_service_url="http://tickets:8000")
    out = await reader.support_kpis(tenant="t-1", grantee="aff-1")
    assert out == {"available": False, "reason": "unreachable:503"}


@pytest.mark.anyio
async def test_averages_only_over_tickets_that_carry_that_kpi():
    http = FakeTicketHttp({
        "http://tickets:8000/internal/tickets?": (200, {"tickets": [{"id": "tk-1"}, {"id": "tk-2"}]}),
        "http://tickets:8000/internal/tickets/tk-1": (200, {"kpis": {
            "first_response_seconds": 100.0, "resolution_seconds": 500.0, "escalated": False}}),
        "http://tickets:8000/internal/tickets/tk-2": (200, {"kpis": {
            "first_response_seconds": None, "resolution_seconds": None, "escalated": True}}),
    })
    reader = TicketReader(http=http, ticket_service_url="http://tickets:8000")
    out = await reader.support_kpis(tenant="t-1", grantee="aff-1")
    assert out["available"] is True
    assert out["ticket_count"] == 2
    assert out["avg_first_response_seconds"] == 100.0     # only tk-1 had a value
    assert out["avg_resolution_seconds"] == 500.0
    assert out["escalation_rate"] == 0.5                   # 1 of 2 escalated


@pytest.mark.anyio
async def test_one_tickets_own_read_failure_is_skipped_not_fatal():
    http = FakeTicketHttp({
        "http://tickets:8000/internal/tickets?": (200, {"tickets": [{"id": "tk-1"}, {"id": "tk-2"}]}),
        "http://tickets:8000/internal/tickets/tk-1": (500, {}),
        "http://tickets:8000/internal/tickets/tk-2": (200, {"kpis": {
            "first_response_seconds": 42.0, "resolution_seconds": None, "escalated": False}}),
    })
    reader = TicketReader(http=http, ticket_service_url="http://tickets:8000")
    out = await reader.support_kpis(tenant="t-1", grantee="aff-1")
    assert out["available"] is True
    assert out["ticket_count"] == 2                        # still counts BOTH in the list
    assert out["avg_first_response_seconds"] == 42.0        # but only tk-2 fed the average


@pytest.mark.anyio
async def test_no_tickets_at_all_reports_a_clean_zero_state():
    http = FakeTicketHttp({"http://tickets:8000/internal/tickets?": (200, {"tickets": []})})
    reader = TicketReader(http=http, ticket_service_url="http://tickets:8000")
    out = await reader.support_kpis(tenant="t-1", grantee="aff-1")
    assert out == {"available": True, "ticket_count": 0, "avg_first_response_seconds": None,
                   "avg_resolution_seconds": None, "escalation_rate": 0.0}
