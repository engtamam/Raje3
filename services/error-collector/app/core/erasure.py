"""Erasing a data subject from the signal store — and why this service is in the fan-out at all.

THE QUESTION THIS FILE HAD TO ANSWER FIRST, BECAUSE IT WAS GENUINELY OPEN.

A signal is an error report. Its `context` blob is written by whatever emitted it, so it CAN carry
personal data by accident — a URL with a phone number in the query string, a stack trace whose
local variable held a customer name, a log line a service printed under pressure. It is not KEYED
by a subject: nothing here is filed under a person, and no query in this service starts from one.
And every row of it dies on its own after ten days.

So the honest case for LEAVING IT OUT of compliance's PRIVACY_TARGETS was real, and it is the case
`services/secrets-admin` makes for itself in its own `app/api/internal.py`: it serves no erase
route at all, on the grounds that a service holding no data subject would be acking an erasure it
did not perform — "a 'yes' that means nothing, which is worse than an absence."

THAT ARGUMENT DOES NOT SURVIVE HERE, AND THE DIFFERENCE IS THE `context` BLOB. secrets-admin holds
five provider credentials and three annotations each; it is structurally incapable of holding a
person. This service accepts a free-form JSON blob from every pod on the cluster and from every
browser the console runs in. "Probably nothing personal" is not the same claim as "nothing
personal", and PDPL Article 18 is not answered by a probability.

THE SHAPE THAT WON, WHICH IS whatsapp-assistant's, NOT secrets-admin's. That service's inbound
message log is the closest thing in this codebase to what a signal store is: an ephemeral,
bounded, auto-purging record whose content is written by somebody else. It is on the erasure
fan-out (`whatsapp-assistant=...` in PRIVACY_TARGETS, `whatsapp-assistant:conversations` in
TENANT_DATA_MAP) AND it has its own age-based purge, and it treats those as two answers to two
different questions — `app/core/erasure.py` there says so in its own first paragraph: the
scheduled purge answers "this is old enough to no longer be useful"; the erasure answers "this
person asked", and must not wait for the first to agree. Ten days is not an answer to somebody
standing in front of us today.

So: this service IS in PRIVACY_TARGETS and IS in TENANT_DATA_MAP, and the ten-day purge is a
SECOND control rather than a substitute for the first.

WHAT AN ERASURE CAN ACTUALLY REACH, STATED PLAINLY SO THE ACK IS NOT A LIE:

  Attributed signals   DELETED. A browser report is posted by an authenticated person, so the row
                       carries the reporter's own tenant and subject_ref off their token. These are
                       findable by subject and they go, immediately.

  Unattributed signals NOT REACHABLE BY SUBJECT, and this is REPORTED rather than glossed. A pod's
                       log line has no subject; there is no key to look it up by and no honest way
                       to decide whether a name inside a stack trace is this person's. The control
                       on those is the ten-day purge, and the ack says exactly that, with a basis,
                       rather than counting them as erased or pretending they do not exist.

The second bullet is the reason `already_absent` is computed from what was SCANNED and not
defaulted to True. A DSAR that finds no attributed rows here has genuinely looked.
"""
from __future__ import annotations

from typing import Any

from app.core.pii import subject_ref
from app.core.signals import SignalStore


class TemplateErasure:
    # Both appear in the DSAR's target list and must match the data-map row registered for this
    # service (`error-collector:signals` in operations' TENANT_DATA_MAP). A mismatch means the
    # DSAR waits for an ack that never arrives — and waits without erroring.
    service = "error-collector"
    category = "signals"

    def __init__(self, *, store, pii_salt: str, max_scan: int = 100_000,
                 retention_days: int = 10) -> None:
        self._signals = SignalStore(store, retention_days=retention_days)
        self._salt = pii_salt
        self._max = max_scan
        self._retention_days = retention_days

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        """Erase every signal attributable to one person.

        `subject` is folded through `subject_ref` exactly as every other service folds it — and the
        fold is IDEMPOTENT, so a caller handing back a pseudonym it already holds gets the same
        pseudonym rather than the ref of a ref, which would match no row and close this request
        `already_absent` over data that was never touched (see app/core/pii.py).
        """
        if not tenant or not subject:
            return {"service": self.service, "category": self.category, "subject_ref": "",
                    "erased": [], "retained": [], "already_absent": True, "truncated": False,
                    "note": "tenant and subject are both required; nothing was scanned"}

        ref = subject_ref(self._salt, tenant, subject)
        deleted, truncated = await self._signals.purge_for_subject(
            tenant, ref, max_scan=self._max)

        return {
            "service": self.service,
            "category": self.category,
            "subject_ref": ref,          # the pseudonym — never the raw subject echoed back
            "erased": [f"signals:{deleted}"] if deleted else [],
            "retained": [{
                "what": "unattributed signals (server logs and anonymous browser errors)",
                "basis": "no_identifier_to_match",
                "why": "a pod's log line carries no data subject, so there is no key to find this "
                       "person's rows by and no honest way to decide whether a name inside a stack "
                       "trace is theirs. Deleting on a guess would erase other people's incidents; "
                       "claiming them as erased would be a false ack. Every one of these rows is "
                       f"deleted unconditionally by age within {self._retention_days} days of "
                       "arriving, by the scheduled reap — which is a control on this residue, not "
                       "a substitute for the deletion above.",
            }],
            # LOOKED, and this is what was there. Never a default.
            "already_absent": deleted == 0,
            "truncated": truncated,
        }
