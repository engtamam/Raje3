"""RhythmProvider port — a customer's own learned per-service rhythm (reminders' adaptive engine,
core/adaptive.py there), read here to feed the two personalization tools (core/tools.py:
list_due_services, list_lapsed_services): a decision-making INPUT, never a sentence spoken to the
customer — see core/conversation.py's `personalization` persona section for the rule this exists
to serve, and its own sanitizer backstop for what happens if the model tries anyway.

SAME SHAPE AS `ports/catalog_provider.py` and `ports/booking_provider.py`, DELIBERATELY: a
`@runtime_checkable Protocol` carrying `driver: str`, a frozen dataclass for the one value object
it returns, and a driver string in config picking one adapter in `app/container.py`'s own explicit
if/elif — never a generic registry, matching both ports' own precedent exactly.

`is_learned` TRAVELS WITH EACH ROW (reminders' own `/reminders/rhythm-for-subject` already computes
it) — a caller two services away from the adaptive engine's warmup logic must never be the one
deciding whether an estimate is real or a defaulted guess wearing learning's hat.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RhythmEntry:
    service_id: str
    interval_days: float
    last_visit_at: int
    observations: int
    is_learned: bool


@runtime_checkable
class RhythmProvider(Protocol):
    driver: str

    async def for_subject(self, *, tenant: str, subject_ref: str) -> list[RhythmEntry]: ...
