"""One establishment's answers about the rating app — whether it runs, how long after the visit it
asks, and what it pays for an answer.

A SEPARATE STORE FROM `reason_choices.py`, ON PURPOSE. `Choices` is documented as carrying exactly
two decisions per reason — on/off, and whose words — and nothing else; cramming a delay and a point
value into that row would be a third decision wearing the first two's shape. This is a small,
dedicated row instead, the same way `custom_templates.py` and `settings_tree.py` each own their one
concern rather than growing `reason_choices.py` a fourth time.

THIS STORE HAS NO OPINION ON WHETHER THE APP IS OWNED. Reading and writing these numbers before a
shop has bought the rating app is harmless — the same way a plan's price exists in the catalogue
before anyone subscribes to it. Whether the numbers here actually MOVE anything (whether a message
goes out, whether a point is credited) is decided at the point of consequence — the scheduling code
that reads this store — never here.

PRESENCE DECIDES, NOT TRUTH — same rule as `reason_choices.py` and `settings_tree.py`: a row that
has never been written answers with the product's own defaults, not with a stored zero that could
be confused for a deliberate "off".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_COLL = "rating_settings"

# THE DEFAULTS, NAMED HERE AND NOWHERE ELSE. `10` matches the platform's own pre-existing
# `VISIT_CONFIRM_DELAY_SECONDS` default (600 seconds) so a shop that never touches this setting
# sees no change in when its post-visit message arrives — only what it says, once the rating app is
# actually wired to read `enabled` (a later phase).
DEFAULT_ENABLED = True
DEFAULT_DELAY_MINUTES = 10
DEFAULT_POINTS = 0

# A DELAY OF ZERO IS NOT "IMMEDIATELY" — it is refused. A visit confirmed the same second it is
# recorded races the operator still standing at the counter, which is exactly the noise
# `VISIT_CONFIRM_DELAY_SECONDS` exists to prevent; a shop that genuinely wants "as fast as possible"
# still means "a minute or two", never zero.
MIN_DELAY_MINUTES = 1
# BOUNDED ABOVE TOO. A message that arrives after the customer has forgotten the visit answers
# nothing; a week is already generous for the slowest service this product has ever priced.
MAX_DELAY_MINUTES = 7 * 24 * 60
MAX_POINTS = 10_000


@dataclass
class RatingSettings:
    tenant: str
    enabled: bool = DEFAULT_ENABLED
    delay_minutes: int = DEFAULT_DELAY_MINUTES
    points: int = DEFAULT_POINTS

    def public(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "delay_minutes": self.delay_minutes,
                "points": self.points}


class RatingSettingsStore:
    def __init__(self, store: Any) -> None:
        self._s = store

    async def load(self, tenant: str) -> RatingSettings:
        row = await self._s.get(_COLL, tenant) or {}
        return RatingSettings(
            tenant=tenant,
            enabled=bool(row["enabled"]) if "enabled" in row else DEFAULT_ENABLED,
            delay_minutes=int(row["delay_minutes"]) if "delay_minutes" in row else DEFAULT_DELAY_MINUTES,
            points=int(row["points"]) if "points" in row else DEFAULT_POINTS)

    async def set(self, tenant: str, *, enabled: bool | None = None,
                  delay_minutes: int | None = None, points: int | None = None) -> RatingSettings:
        """Change what is named; leave the rest exactly as it was.

        `None` MEANS "LEAVE IT" — same rule `ReasonIn` uses for the reason toggles. A screen
        sending only the field the owner actually touched must not overwrite the other two with
        whatever it happened to have in memory a second earlier.
        """
        if delay_minutes is not None and not (MIN_DELAY_MINUTES <= delay_minutes <= MAX_DELAY_MINUTES):
            raise ValueError(
                f"مدة الإرسال يجب أن تكون بين {MIN_DELAY_MINUTES} و{MAX_DELAY_MINUTES} دقيقة.")
        if points is not None and not (0 <= points <= MAX_POINTS):
            raise ValueError(f"عدد النقاط يجب أن يكون بين 0 و{MAX_POINTS}.")

        current = await self.load(tenant)
        row = current.public()
        if enabled is not None:
            row["enabled"] = bool(enabled)
        if delay_minutes is not None:
            row["delay_minutes"] = int(delay_minutes)
        if points is not None:
            row["points"] = int(points)
        await self._s.put(_COLL, tenant, {**row, "tenant": tenant})
        return RatingSettings(tenant=tenant, **row)
