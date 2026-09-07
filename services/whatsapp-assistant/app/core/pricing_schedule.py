"""A pricing change is never instant — a fair-warning delay by design.

Every other `platform.config` knob (app/runtime_policy.py: ASSISTANT_MODEL_NAME/
SOFT_DECLINE_THRESHOLD/MAX_CAROUSEL_CARDS) applies the moment an operator sets it — that is
correct for those, because none of them changes what a shop is BILLED. A pricing key
(PRICING_STRATEGY/PRICING_USAGE_HALALAS_PER_1K_TOKENS/...) is different: a shop that woke up to a
higher rate with no notice has a real grievance, not a UX inconvenience. So a pricing change is
SCHEDULED, not applied — written here with an `effective_at` in the future, and only actually
handed to `RuntimeConfig.set()` once a tick (api/internal.py::tick(), the same cron-driven sweep
every other periodic job in this service already runs on) finds it due. The gap between scheduling
and taking effect is exactly the window the console's own calculator screen gives an operator to
notify shops before the number changes under them.

ONE PENDING CHANGE PER KEY, PLATFORM-WIDE (tenant=""). Pricing is never per-tenant (see
app/api/v1/operator.py's own note: every LLM/pricing knob here is platform-wide) — scheduling a
second change for the same key before the first lands REPLACES it outright, the same "last write
wins" contract RuntimeConfig.set() already has for an instant override. There is deliberately no
queue of several pending changes stacked on one key; an operator who changes their mind schedules
again.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PRICING_PENDING = "wa_pricing_pending"


@dataclass(frozen=True)
class PendingPriceChange:
    key: str
    value: Any
    effective_at: int
    scheduled_by: str
    scheduled_at: int


def _doc_id(key: str) -> str:
    # PLATFORM-WIDE, SO NO TENANT IN THE KEY — see module docstring. A bare key name is
    # collision-free here because only pricing keys are ever scheduled through this module (the
    # caller, not this one, is what limits which keys reach it — see operator.py).
    return key


async def schedule(store: Any, *, key: str, value: Any, effective_at: int, actor: str,
                   now: int) -> PendingPriceChange:
    """Replace whatever was pending for this key with a new scheduled change."""
    row = {"key": key, "value": value, "effective_at": effective_at,
          "scheduled_by": actor, "scheduled_at": now}
    await store.put(PRICING_PENDING, _doc_id(key), row)
    return PendingPriceChange(**row)


async def cancel(store: Any, *, key: str) -> bool:
    """Drop a pending change before it lands — the operator changed their mind, or made a mistake.
    Returns whether a row actually existed to cancel (a caller telling an operator "cancelled"
    for a key that was never pending would be lying to them)."""
    return bool(await store.delete(PRICING_PENDING, _doc_id(key)))


async def pending(store: Any) -> list[PendingPriceChange]:
    """Every scheduled-but-not-yet-applied change, whatever `now` currently is — what the
    calculator screen shows as "قادم". `scan_all`, not `find({})` — this port's `find()` requires
    a non-empty `where` (a real membership filter); reading every row of a small, capped
    collection is exactly what `scan_all` exists for (see its own port docstring)."""
    rows = await store.scan_all(PRICING_PENDING, limit=len(_PRICING_KEYS) + 1)
    return [PendingPriceChange(key=r["key"], value=r["value"], effective_at=r["effective_at"],
                               scheduled_by=r.get("scheduled_by", ""),
                               scheduled_at=r.get("scheduled_at", 0)) for r in rows]


# THE ONLY KEYS THIS MODULE EVER SCHEDULES — a closed list, not "whatever RUNTIME_POLICY allows",
# so a future runtime-policy addition that is NOT a pricing number (a behavioural knob like
# SOFT_DECLINE_THRESHOLD) can never accidentally be scheduled through this delayed path instead of
# applying instantly the way an operator setting it would expect.
_PRICING_KEYS = frozenset({
    "PRICING_STRATEGY", "PRICING_TIER_BASE_HALALAS", "PRICING_TIER_INCLUDED_CONVERSATIONS",
    "PRICING_TIER_OVERAGE_HALALAS_PER_CONVERSATION", "PRICING_ADDON_FLAT_HALALAS",
    "PRICING_USAGE_HALALAS_PER_1K_TOKENS", "PRICING_USAGE_HALALAS_PER_CONVERSATION",
})


def is_a_pricing_key(key: str) -> bool:
    return key in _PRICING_KEYS


async def apply_due(store: Any, runtime_config: Any, *, now: int) -> list[str]:
    """Called once per tick (api/internal.py::tick()), never per-tenant — pricing is platform-wide.

    A due change is hard-applied via the SAME `RuntimeConfig.set()` an instant override would use
    (tenant="", actor_ref="system:pricing_schedule" — this is the platform's own clock acting, not
    a person, and the audit trail should say so plainly rather than attribute it to whoever
    originally scheduled it days earlier). Returns the keys actually applied this tick, for the
    tick's own response body to report — the same "what did this pass actually do" shape every
    other counter in that response already has.
    """
    applied: list[str] = []
    for change in await pending(store):
        if change.effective_at > now:
            continue
        await runtime_config.set(tenant="", key=change.key, value=change.value,
                                 actor_ref="system:pricing_schedule")
        await store.delete(PRICING_PENDING, _doc_id(change.key))
        applied.append(change.key)
    return applied
