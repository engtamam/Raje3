"""An append-only record of every real upsell moment: the assistant proposing a PACKAGE booking
(the one upsell-shaped act this service structurally tracks — see context_builder.py's own
`_eligible_upsell_packages` and tools.py's `list_packages` for the two ways a package reaches a
customer, both of which still resolve through `propose_booking(package_id=...)` before anything is
real), and what the customer actually did about it.

WHY A PACKAGE PROPOSAL SPECIFICALLY, NOT "ANY MENTION OF AN EXTRA". A model saying "you might also
like X" in free text is not a fact this codebase can safely log — it was never validated, never
button-confirmed, and core/conversation.py's own `_sanitize_reply` already treats unstructured
model claims as untrusted. `propose_booking(package_id=...)` is different: it is the ONE point a
package upsell becomes a real, button-gated proposal — re-validated against the real catalogue
(package still active/offerable — see `validate_and_render`'s own package branch), carrying a real
price the model did not invent. That is the honest, traceable "moment of offer" this ledger exists
to record — inventing a broader definition would mean logging things nobody actually confirmed or
declined.

ONE ROW PER PROPOSAL, UPDATED IN PLACE — keyed by the SAME `proposal_id` PendingProposal already
uses (core/tools.py), so "offer" and "outcome" are never two separately-correlated writes; the row
IS the proposal's own outcome, told honestly across its whole life:

  pending   -> written the instant `propose_booking(package_id=...)` renders a real button
              (validate_and_render, this module's `record_offer`).
  accepted  -> the customer tapped confirm and a real booking was made
              (execute_confirmed_proposal, `record_outcome(..., outcome="accepted")`).
  declined  -> the customer tapped the SAME proposal's own "إلغاء" button
              (conversation.py::handle_button_reply, `record_outcome(..., outcome="declined")`).

A proposal that simply expires unconfirmed (the customer never taps either button) stays "pending"
forever — never silently reclassified as "declined": silence is not a decline (see this session's
own `is_decline` heuristic in soft_decline.py, which exists BECAUSE silence and an explicit "لا"
are not the same signal). The aggregation report (upsell_report.py) counts "still pending" as its
own honest bucket, never folded into either outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

UPSELL_LEDGER = "wa_upsell_ledger"

OUTCOME_PENDING = "pending"
OUTCOME_ACCEPTED = "accepted"
OUTCOME_DECLINED = "declined"


@dataclass(frozen=True)
class UpsellRow:
    proposal_id: str
    tenant: str
    branch_id: str
    subject_ref: str
    package_id: str
    price_minor: int | None    # None = genuinely unknown, NEVER coerced to 0 — see module note
                                # on pricing_report.py's own honesty rule this mirrors.
    proposed_at: int
    outcome: str
    decided_at: int | None
    booking_id: str


async def record_offer(store: Any, *, proposal_id: str, tenant: str, branch_id: str,
                       subject_ref: str, package_id: str, price_minor: int | None,
                       now: int) -> None:
    """Written the instant a package proposal renders a real confirm/cancel button — BEFORE either
    is tapped, so a customer who never responds still leaves a real "pending" trace rather than no
    trace at all (the honest default `apply_due`/COST_LEDGER-style modules in this service already
    use for "recorded the moment a fact becomes true")."""
    await store.put(UPSELL_LEDGER, proposal_id, {
        "proposal_id": proposal_id, "tenant": tenant, "branch_id": branch_id,
        "subject_ref": subject_ref, "package_id": package_id, "price_minor": price_minor,
        "proposed_at": now, "outcome": OUTCOME_PENDING, "decided_at": None, "booking_id": ""})


async def record_outcome(store: Any, *, proposal_id: str, outcome: str, now: int,
                         booking_id: str = "") -> None:
    """Flips a still-pending row to its real outcome. A no-op (never raises, never overwrites) if
    no offer row exists for this proposal_id — every package proposal always has one (`record_offer`
    is called synchronously before the button is ever sent), but a caller here is never trusted to
    assume that; the row it would otherwise clobber might belong to an ordinary, non-package
    proposal that this ledger was never asked to track in the first place."""
    # This read-modify-write is NOT lock-guarded, and that is safe, not an oversight: both real
    # callers of this function (core/conversation.py's "cancel" branch for outcome="declined", and
    # core/tools.py's execute_confirmed_proposal for outcome="accepted") are reachable ONLY from
    # inside `handle_button_reply`, which wraps its entire body in `self._acquire_conv_lock(tenant,
    # subject_ref)` — so two button taps for the SAME proposal_id (same conversation) are already
    # fully serialised before either one gets here. The "accepted" path is additionally serialised a
    # second time, independently, by execute_confirmed_proposal's own per-proposal_id `_EXECUTE_LOCKS`
    # claim. There is no code path that reaches this function for the same proposal_id from two
    # genuinely concurrent, unlocked callers — a lock here would just duplicate protection that
    # already exists one layer up.
    row = await store.get(UPSELL_LEDGER, proposal_id)
    if row is None:
        return
    row["outcome"] = outcome
    row["decided_at"] = now
    if booking_id:
        row["booking_id"] = booking_id
    await store.put(UPSELL_LEDGER, proposal_id, row)
