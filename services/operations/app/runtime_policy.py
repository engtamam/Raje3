"""The settings an operator may change at runtime, for this service.

DECLARING A KEY HERE IS A PROMISE THAT SOMETHING READS IT through RuntimeConfig at the point of
use. That promise is the entire point: offering every settable field to the panel instead fails in
the most convincing way available — the panel accepts the change, the audit log records it with an
actor and a timestamp, and behaviour does not move, because nothing consults the override. The
operator ends up holding a receipt for a change that never happened.

The generated service starts with none, deliberately. Add a key here in the same change that wires
the read, never before: unavailable is honest, inert is not.
"""
from __future__ import annotations

RUNTIME_POLICY: frozenset[str] = frozenset({
    # How long an establishment keeps a customer whose last visit has passed. ITS decision, not
    # ours — it is the controller of that data — and core/retention.py reads it here per tenant on
    # every sweep. Our configured value is the ceiling and the default: a shop may shorten it and
    # may not extend it past what we hold.
    "RETENTION_CUSTOMER_YEARS",
    # `MASTER_RATING_FLOW_ID`/`MASTER_REPORT_FLOW_ID` BOTH REMOVED (2026-09-16) — see
    # core/flows.py's own module docstring: the rating screen moved off native Flow entirely, and
    # the report Flow's config was orphaned by an earlier, incomplete feature deletion.
    #
    # THE SAME PATTERN, THE REMAINING FLOWS — WhatsApp booking (Phase 5), minted once by
    # deploy/seed/bootstrap-booking-flow.sh, read per shop by connect.py. MISSING HERE UNTIL NOW —
    # a real bug, not a new one: the bootstrap script's own write (PUT /api/v1/operator/config)
    # was refused by `settable()` on every run, silently leaving MASTER_BOOKING_FLOW_ID unset no
    # matter how many times the script "succeeded" (its own idempotency check reads the SAME
    # refused key, so it never even noticed) — found while wiring the fourth Flow below and
    # fixed in the same change rather than left for whoever hits it next.
    "MASTER_BOOKING_FLOW_ID",
    # THE SAME PATTERN, A FIFTH FLOW — visit-registration over WhatsApp, minted once by
    # deploy/seed/bootstrap-visit-flow.sh, read per shop by connect.py. Added here FROM THE START
    # this time — see MASTER_BOOKING_FLOW_ID's own comment on the bug this exact omission caused
    # once already.
    "MASTER_VISIT_FLOW_ID",
    # THE SAME PATTERN, A FOURTH FLOW — subscription renewal, minted once by an explicit admin
    # action (api/v1/platform.py::seed_subscription_renewal_flow) rather than at a shop's own
    # connect time (never cloned per shop — see core/flows.py's own module comments). Read back
    # by that same route on every call, purely as an idempotency check ("already seeded, skip").
    "MASTER_SUBSCRIPTION_RENEWAL_FLOW_ID",
})
