"""core/tools.py's get_service_procedure — a service's REAL ordered steps back to the model, one
service at a time (never a firehose), for it to turn into a confident, natural reply per the
`procedure_selling` PromptSection (core/conversation.py). This tool itself returns plain facts
only, never pre-written sales copy — see its own docstring.
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import tools as T
from app.core.booking import BookingConfig, ConfigDrivenAvailabilityProvider
from app.core.points import NullPointsSummary

TENANT = "t1"
ALLOWED = frozenset({"get_service_procedure"})


class FakeServiceProcedure:
    def __init__(self, by_service: dict[str, dict]) -> None:
        self._by_service = by_service

    async def get(self, tenant, service_id):
        return self._by_service.get(service_id)


def _call(**kwargs):
    store = MemoryDataStore()
    cfg = BookingConfig(business_hours={}, default_duration_minutes=30, concurrency=1,
                       max_lead_days=7, slot_granularity_minutes=30, service_durations={})
    return T.validate_and_render(
        tenant=TENANT, subject_ref="sub1", conversation_id="conv1",
        tool="get_service_procedure", args=kwargs.pop("args", {}), allowed_tools=ALLOWED,
        store=store, booking_provider=ConfigDrivenAvailabilityProvider(store=store, cfg=cfg),
        points_summary=NullPointsSummary(), proposal_ttl_seconds=1800, **kwargs)


async def test_missing_service_id_is_rejected():
    with pytest.raises(T.ToolValidationError):
        await _call(args={}, service_procedure=FakeServiceProcedure({}))


async def test_no_peer_wired_says_so_plainly_not_an_error():
    result = await _call(args={"service_id": "svc1"}, service_procedure=None)
    assert result == "لا تتوفر تفاصيل الإجراء لهذه الخدمة حاليًا."


async def test_an_unknown_service_says_so_plainly():
    result = await _call(args={"service_id": "svc_ghost"},
                         service_procedure=FakeServiceProcedure({}))
    assert result == "لا تتوفر خطوات مفصّلة لهذه الخدمة حاليًا."


async def test_steps_come_back_in_order_with_names_and_numbering():
    procedure = {
        "service_id": "svc1", "service_name": "غسيل خارجي",
        "steps": [
            {"id": "s1", "text": "اغسل بالماء", "severity": "normal"},
            {"id": "s2", "text": "افحص الإطارات", "severity": "normal"},
            {"id": "s3", "text": "لمّع السيارة", "severity": "normal"},
        ],
    }
    result = await _call(args={"service_id": "svc1"},
                         service_procedure=FakeServiceProcedure({"svc1": procedure}))
    assert "غسيل خارجي" in result
    assert "1. اغسل بالماء" in result
    assert "2. افحص الإطارات" in result
    assert "3. لمّع السيارة" in result
    # order preserved exactly as returned by the peer
    assert result.index("اغسل بالماء") < result.index("افحص الإطارات") < result.index("لمّع السيارة")


async def test_critical_steps_are_flagged_normal_steps_are_not():
    procedure = {
        "service_id": "svc1", "service_name": "فحص شامل",
        "steps": [
            {"id": "s1", "text": "افحص الفرامل", "severity": "critical"},
            {"id": "s2", "text": "افحص المساحات", "severity": "normal"},
        ],
    }
    result = await _call(args={"service_id": "svc1"},
                         service_procedure=FakeServiceProcedure({"svc1": procedure}))
    assert "افحص الفرامل (أساسية)" in result
    assert "افحص المساحات (أساسية)" not in result
    assert "افحص المساحات" in result


async def test_a_retired_step_dropped_by_the_peer_is_simply_not_present():
    """The peer route (operations' /internal/operations/service-procedure) already drops retired
    steps before this tool ever sees the result — this test locks in that the tool trusts that
    filtering rather than re-listing anything not present."""
    procedure = {
        "service_id": "svc1", "service_name": "غسيل خارجي",
        "steps": [{"id": "s1", "text": "اغسل بالماء", "severity": "normal"}],
    }
    result = await _call(args={"service_id": "svc1"},
                         service_procedure=FakeServiceProcedure({"svc1": procedure}))
    assert "اغسل بالماء" in result
    assert result.count("\n") == 1   # header + exactly one step line
