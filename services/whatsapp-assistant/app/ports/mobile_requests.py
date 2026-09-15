"""Port to operations' mobile/on-the-go service-requests doors (services/operations/app/api/
internal.py): `create` — the ONE write this service ever makes for the whole feature, only after
the LLM proposed it (core/tools.py::validate_and_render's `request_mobile_visit`), the shop's own
catalogue re-validated which service ids are real, and the customer then actually shared a location
(core/conversation.py::handle_location) — never before all three; and `hours`, a read, so the model
can tell the customer the shop's REAL working hours before ever asking for a time
(core/tools.py::check_mobile_visit_hours)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class MobileRequestFailed(Exception):
    """The peer call itself failed, OR operations refused the request (bad input, or a time
    outside the shop's own real working hours) — same posture as core/booking_assignment.py's own
    peer-error class: the caller (handle_location) turns this into one honest apology, never a
    silent drop."""


@dataclass(frozen=True)
class CreatedMobileRequest:
    request_id: str


class NullMobileRequests:
    driver = "null"

    async def create(self, *, tenant: str, phone: str, customer_name: str,
                     service_ids: list[str], requested_time: int,
                     lat: float, lng: float) -> CreatedMobileRequest:
        raise MobileRequestFailed("mobile requests are not configured on this deployment")

    async def hours(self, tenant: str) -> dict[str, Any] | None:
        return None
