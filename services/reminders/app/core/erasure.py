"""reminders — erasing a data subject.

THIS SERVICE HOLDS NO IDENTIFIERS, AND THE ERASURE IS STILL REAL. Every row here is keyed by
`subject_ref`, the pseudonym operations publishes. There is no phone number to blank and no name to
clear — which makes it tempting to answer 200 and do nothing, and that would be exactly wrong.

What this service holds about a person is a PREDICTION: when they will next need each service, how
engaged they are, and the record of every message we sent them. Attached to a pseudonym it
identifies nobody — but it is still their data, it is still processed on their behalf, and once
they ask us to stop, a schedule that survives the erasure will send them a message. **That is the
failure mode: not a leak, a message to someone who asked us to go away.**

SO ROWS ARE DELETED HERE, NOT BLANKED — the opposite of operations, and for a reason:

  Schedules   DELETED. A blanked schedule still has a due date. The tick would find it, fail to
              resolve a destination, and log an error every day forever. And if the resolution
              ever succeeded through some other path, it would send.

  Rules       DELETED. The learned interval is a statement about one person's habits. It has no
              value without them and no defence for keeping it.

  Engagement  DELETED. Same.

  Prefs       DELETED LAST, AND ONLY AFTER THE SCHEDULES. Order matters: if prefs went first and
              the erasure then failed halfway, we would be left with schedules and no record of
              what the customer had switched off — the one state where a partial erasure makes us
              send MORE than before it started.

  SendLog     RETAINED, WITH ITS IDENTIFIERS ALREADY ABSENT, under `communications_record`.

The send log is the only judgement call here, so it is argued rather than asserted. It records that
a message of a given class went to a given pseudonym at a given time. We keep it because it is the
evidence for two obligations that outlive the relationship: proving to a regulator that we honoured
the sending caps, and proving to an establishment that a message it is being blamed for was or was
not sent. Deleting it would leave us unable to defend the customer's own complaint.

But it is trimmed by AGE regardless — retention is a schedule, not a promise — and it holds no
identifier at any point in its life.
"""
from __future__ import annotations

from typing import Any

from app.core.consent import CONSENT
from app.core.stores import ENGAGEMENT, PREFS, RULES, SCHEDULES, SEND_LOG


class RemindersErasure:
    """The privacy-erase contract for this service.

    IDEMPOTENT. A DSAR retries, and a fan-out that gets a 500 on the second call reports a failed
    erasure for data that is already gone — which is investigated as a leak and is not one.
    """

    def __init__(self, *, store, max_scan: int = 5000) -> None:
        self._s = store
        self._max = max_scan

    async def erase(self, tenant: str, subject: str) -> dict[str, Any]:
        """Erase everything this service holds about one subject.

        `subject` is already the subject_ref: unlike operations, this service never sees the raw
        identifier, so there is nothing to hash. Accepting a raw value here would mean accepting
        something we should not be able to receive.
        """
        if not tenant or not subject:
            return {"service": "reminders", "erased": [], "retained": [],
                    "already_absent": True, "truncated": False,
                    "note": "tenant and subject are both required; nothing was scanned"}

        erased: list[str] = []
        truncated = False

        # ORDER IS DELIBERATE — schedules first. A half-finished erasure must never leave a
        # sendable schedule behind, and every step after this one is safe to interrupt.
        # CONSENT GOES WITH THEM, and the argument for keeping it does not survive.
        #
        # "It is our evidence that we were allowed to market to them" is true, and it is evidence
        # about a person who has asked to be forgotten — kept to defend sends that will never
        # happen again, because after this there are none. The send log stays and carries the
        # pseudonym and the timestamp, which is what answers "was a cap honoured"; the consent row
        # is the person's own decision, and it leaves with them.
        #
        # ERASING IT IS ALSO THE SAFER STATE: with no record the gate reads `never_asked` and
        # refuses marketing (core/gate.py). A grant that outlived the person who gave it would be
        # a permission nobody can withdraw.
        for collection in (SCHEDULES, RULES, ENGAGEMENT, PREFS, CONSENT):
            n, hit_ceiling = await self._delete_where(collection, tenant, subject)
            truncated = truncated or hit_ceiling
            if n:
                erased.append(f"{collection}:{n}")

        return {
            "service": "reminders",
            "category": "messaging_schedule",
            "subject_ref": subject,
            "erased": erased,
            "retained": [{
                "what": "send log entries, pseudonymous",
                "basis": "communications_record",
                "why": "the evidence that the regulatory sending caps were honoured, and the "
                       "answer when an establishment is blamed for a message. It carries a "
                       "pseudonym and a timestamp, never an identifier, and is trimmed by age on "
                       "a schedule regardless of any request.",
            }],
            "already_absent": not erased,
            "truncated": truncated,
        }

    async def _delete_where(self, collection: str, tenant: str, subject: str) -> tuple[int, bool]:
        """Delete every row in one collection for one subject.

        BOUNDED. A DSAR is rare and an unbounded read is an outage waiting for the one tenant large
        enough to trigger it — so this pages with a ceiling and REPORTS hitting it rather than
        silently erasing part of a person and answering success.
        """
        deleted = 0
        after: str | None = None
        scanned = 0
        while True:
            rows, after = await self._s.find(
                collection, {"tenant": tenant, "subject_ref": subject},
                limit=200, after=after, sort=("id", "asc"))
            if not rows:
                return deleted, False
            for row in rows:
                key = _key_for(collection, row)
                if key:
                    await self._s.delete(collection, key)
                    deleted += 1
            scanned += len(rows)
            if scanned >= self._max:
                # Truncated is surfaced in the ack, not swallowed. A partial erasure reported as
                # complete is the false ack this whole contract exists to prevent.
                return deleted, True
            if not after:
                return deleted, False


def _key_for(collection: str, row: dict[str, Any]) -> str:
    """The datastore key for a row, rebuilt from its own fields.

    Rebuilt rather than read: the natural keys here are composite (see core/stores.py) and a `key`
    field on the row would be a second source of truth that drifts from the first.
    """
    t, s = row.get("tenant", ""), row.get("subject_ref", "")
    if collection == SCHEDULES:
        return f"{t}|{s}|{row.get('service_id', '')}|{row.get('kind', '')}"
    if collection == RULES:
        return f"{t}|{s}|{row.get('service_id', '')}"
    if collection in (PREFS, ENGAGEMENT):
        return f"{t}|{s}"
    if collection == SEND_LOG:
        return f"{t}|{row.get('id', '')}"
    return ""
