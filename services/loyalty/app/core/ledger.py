"""The only place a balance ever moves.

ONE FUNCTION, AND EVERY PATH GOES THROUGH IT. Earning from a visit, earning from an invoice,
redeeming in the field, redeeming at a till, expiring on a tick, a manager correcting a mistake —
six callers, one `post()`. The alternative was six places that each remember to write the entry,
update the total, stamp the movement time and clear the warning flag, and the sixth would forget
one of the four. That is not a hypothetical: it is exactly how the same shape failed in the send
path before every send was routed through one gate.

WHAT `post()` GUARANTEES, in this order:
  1. the entry is refused if it would overdraw — refused, never clamped,
  2. the entry is refused if its (source, reason) was already posted — idempotency, not a retry
     policy: the event bus is at-most-once by contract and the field screen retries on its own,
  3. the ledger entry is written FIRST, carrying the resulting balance,
  4. the materialised total is updated to match.

Step 3 before step 4 is deliberate. If the process dies between them the ledger holds a movement
the total has not caught up with — which `reconcile()` finds and fixes, because the ledger is the
truth. The other order loses the entry entirely and leaves a total nobody can explain.
"""
from __future__ import annotations

from typing import Any

from app.adapters.datastore.drain import drain
from app.core.models import (BALANCES, ENTRIES, Balance, LedgerEntry, Overdraft, REASONS,
                             LoyaltyError)


class Ledger:
    def __init__(self, store: Any) -> None:
        self.store = store

    # ── reads ────────────────────────────────────────────────────────────────────────────────
    async def balance(self, tenant: str, subject_ref: str) -> Balance:
        """The materialised total, or a zero balance that is NOT persisted.

        A customer who has never earned anything must not create a row merely by being looked at:
        the field screen reads a balance on every single customer lookup, and persisting on read
        would fill the table with people who are not in the programme.
        """
        row = await self.store.get(BALANCES, f"{tenant}|{subject_ref}")
        if not row:
            return Balance(tenant=tenant, subject_ref=subject_ref)
        return Balance(tenant=row["tenant"], subject_ref=row["subject_ref"],
                       points=int(row.get("points") or 0),
                       last_movement_at=int(row.get("last_movement_at") or 0),
                       expiry_warned_at=int(row.get("expiry_warned_at") or 0),
                       created_at=int(row.get("created_at") or 0))

    async def history(self, tenant: str, subject_ref: str, limit: int = 50) -> list[dict]:
        rows, _ = await self.store.find(ENTRIES, {"tenant": tenant, "subject_ref": subject_ref},
                                        limit=limit, sort=("created_at", "desc"))
        return list(rows or [])

    async def already_posted(self, tenant: str, source: str, reason: str) -> bool:
        """Has this exact cause already moved this balance?

        Keyed on (tenant, source, reason) rather than source alone, because one visit legitimately
        produces an `earn` and — if the customer redeems in the same breath — a `redeem` whose
        source is the visit too. Same cause, different movements.
        """
        if not source:
            return False
        rows, _ = await self.store.find(ENTRIES, {"tenant": tenant, "source": source,
                                                  "reason": reason}, limit=1)
        return bool(rows)

    async def entry_for(self, tenant: str, source: str, reason: str) -> LedgerEntry | None:
        """The one entry a (source, reason) pair actually posted, if any — `already_posted`'s own
        query, returning the row instead of a bool. Written for `earn.py::reverse_earn`: reversing
        a visit's `earn` needs to know exactly how many points it granted, not merely that it did
        — reversing a GUESSED amount could over- or under-take a balance a human never actually
        held that much of."""
        if not source:
            return None
        rows, _ = await self.store.find(ENTRIES, {"tenant": tenant, "source": source,
                                                  "reason": reason}, limit=1)
        return LedgerEntry(**rows[0]) if rows else None

    # ── the write ────────────────────────────────────────────────────────────────────────────
    async def post(self, *, tenant: str, subject_ref: str, delta: int, reason: str,
                   source: str = "", actor: str = "", rule_level: str = "",
                   note: str = "", branch_id: str = "",
                   now: int | None = None, allow_negative: bool = False) -> LedgerEntry | None:
        """Move a balance. Returns the entry, or None if this cause was already posted.

        None rather than an exception for the idempotent case: a redelivered event is not an
        error, it is the bus behaving as documented, and callers that must treat it as one can
        check the return.

        `allow_negative` — OFF BY DEFAULT, AND EVERY EXISTING CALLER KEEPS REFUSING AN OVERDRAW
        UNCHANGED. Added 2026-09-16, the owner's own explicit call, for exactly one caller
        (`earn.py::reverse_earn`, TikTok's own CANCELLED-order reversal): a customer who already
        SPENT the points a since-cancelled order granted must not walk away having profited from
        an order that never actually happened — the balance goes negative (a real debt, collected
        against a future earn) rather than the take-back silently stopping at zero, which is
        exactly the gap that lets that trick work. This flag is never set by `redeem` or any
        human-facing spend path — those still refuse an overdraw exactly as before.
        """
        if reason not in REASONS:
            raise LoyaltyError(f"unknown reason {reason!r}")
        if delta == 0:
            # Not an error, but not a movement either. Writing it would put rows in the ledger
            # that say nothing happened, and stamp `last_movement_at` — restarting the expiry
            # clock for a customer who did nothing. That is the bug this branch exists to stop.
            return None
        if await self.already_posted(tenant, source, reason):
            return None

        bal = await self.balance(tenant, subject_ref)
        after = bal.points + delta
        if after < 0 and not allow_negative:
            raise Overdraft(
                f"balance is {bal.points}, this movement is {delta} — refused rather than clamped")

        ts = now if now is not None else None
        entry = LedgerEntry(tenant=tenant, subject_ref=subject_ref, delta=delta, reason=reason,
                            source=source, actor=actor, rule_level=rule_level, note=note,
                            branch_id=branch_id, balance_after=after)
        if ts is not None:
            entry.created_at = ts
        # THE ENTRY FIRST. See the module docstring: this order is recoverable and the other is not.
        await self.store.put(ENTRIES, entry.id, entry.to_dict())

        bal.points = after
        if reason in ("earn", "redeem"):
            # An expiry is US moving, not the customer, and counting it would restart the very
            # clock it just ran out (spec §9.7). An `adjust` is a correction of a past movement,
            # so it does not restart the clock either — otherwise a shop tidying its books would
            # silently extend every balance it touched.
            # MAX, never assignment. Events arrive out of order — a visit recorded offline and
            # drained days later carries its own timestamp — and letting a late one move the clock
            # BACKWARDS would expire a customer who had visited since. Found by a test where a
            # stale visit landed after an expiry had already run.
            bal.last_movement_at = max(bal.last_movement_at, entry.created_at)
            bal.expiry_warned_at = 0    # they moved; the warning belongs to a cycle that is over
        if not bal.created_at:
            bal.created_at = entry.created_at
        await self.store.put(BALANCES, bal.key, bal.to_dict())
        return entry

    # ── the repair ───────────────────────────────────────────────────────────────────────────
    async def reconcile(self, tenant: str, subject_ref: str) -> dict:
        """Recompute the total from the ledger, and report — or fix — a divergence.

        This exists because the materialised total CAN drift: a crash between the two writes in
        `post`, a restore that replayed one collection and not the other. Drift with no detector
        is the worst version of this bug, because the number stays plausible.
        """
        # DRAINED, AND THIS IS THE ONE THAT MATTERED MOST. It read at most a hundred thousand
        # entries, discarded the cursor, summed them — and then WROTE that sum over the balance as
        # the truth. The repair was the corruption: a subject past the limit would have its
        # balance silently replaced with the sum of part of its ledger, and the new number is
        # perfectly plausible. Refusing to read is now an error the caller sees; the balance is
        # never overwritten from a partial ledger.
        rows = await drain(self.store, ENTRIES, {"tenant": tenant, "subject_ref": subject_ref},
                           sort=("created_at", "asc"))
        truth = sum(int(r.get("delta") or 0) for r in (rows or []))
        bal = await self.balance(tenant, subject_ref)
        drift = bal.points - truth
        if drift:
            bal.points = truth
            await self.store.put(BALANCES, bal.key, bal.to_dict())
        return {"subject_ref": subject_ref, "ledger": truth, "was": bal.points + drift,
                "drift": drift, "repaired": bool(drift)}
