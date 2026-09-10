"""The reminders engine's own real capabilities — and the CANONICAL text for every "shared
feature" another app's catalog re-shows on its own card.

WHY THIS FILE IS THE AUTHORITY FOR SHARED ENTRIES. `reminders` is a shared capability bundled
into whichever app records a customer event (`feature.visit`/`feature.bookings` — see
`api/subscribed.py`'s own OR), never a product of its own — so the sentence describing it must be
written ONCE, here, where the real code (`core/adaptive.py`, `core/engagement.py`) actually lives.
`services/bookings/app/core/features.py` and `services/operations/app/core/apps.py` each keep
their own literal copy of `SHARED_FEATURES` entries — services do not import each other's code,
so a byte-for-byte Python import across the boundary is not available — but `ci/
check_shared_features_match.py` parses every copy with `ast.literal_eval` (no import, no service
boot needed) and fails the build the moment any of them drifts by so much as a character from
what is written HERE. That is what turns "three copies that happen to agree today" into one
feature that CANNOT read differently on two cards — enforced, not hoped for.

`SHARED_FEATURES` HOLDS ONLY FEATURES THIS SERVICE'S CODE ACTUALLY GRANTS ACROSS APP BOUNDARIES —
not everything reminders does internally, and not a general "features" list for a product this
service does not sell on its own (see this session's own 2026-09-11 decision: messaging is a
FEATURE bundled into an event-recording app, never a purchasable product of its own — there is no
"رسائلي app" card for this file to describe itself).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SharedFeature:
    id: str
    title: str
    detail: str
    icon: str
    tone: str
    # EVERY APP ID THIS FEATURE IS GRANTED THROUGH — kept here as the one list a consumer's own
    # `shared_with` (that app's id removed from this list) must be a subset of.
    granted_by: tuple[str, ...]


SHARED_FEATURES: tuple[SharedFeature, ...] = (
    SharedFeature(
        id="reminders.learns_each_customer",
        title="يرجّع لك عميلك بلا ما تتعب",
        detail="يعرف امتى كل عميل يرجع عادة، ويذكّره بوقته — حجز إضافي بلا أي مجهود منك",
        icon="bell",
        tone="rose",
        granted_by=("visit", "bookings"),
        # `core/adaptive.py::observe` — an exponentially weighted moving average LEARNED per
        # customer per service (never a per-shop average), clamped to sane bounds and discarding
        # anomalous gaps (a customer who travelled once should not have their whole rhythm
        # stretched). `core/engagement.py` decides, from the SAME learned relationship, whether
        # this customer is still worth a marketing nudge at all — service/personal messages are
        # never gated by it, only the optional ones are.
    ),
)


def by_id(feature_id: str) -> SharedFeature | None:
    return next((f for f in SHARED_FEATURES if f.id == feature_id), None)
