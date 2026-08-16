"""Marketing consent — three states, and a record written to be produced as evidence.

WHY THIS FILE EXISTS AT ALL. `Preferences` records REFUSALS: a dict of the classes somebody has
stopped, where absence means allowed. That is right for the sending gate — a customer who has never
spoken has not objected, and a shop that cannot send a visit confirmation to a new customer has no
product — and it makes "agreed" and "was never asked" the same fact.

Two things break on that, and the second is not ours to be relaxed about:

  the owner's dashboard promises "340 customers agreed to receive your offers" (spec §8.5) as the
  truest upgrade motivator in the product. Computed from refusals, that number is every customer he
  has — worse than showing nothing, because it sells an upgrade on a premise the first campaign
  disproves.

  and PDPL requires PRIOR consent for direct marketing. "Did not refuse" is not consent, in any
  reading, and a record that cannot tell the two apart cannot be produced when somebody asks.

────────────────────────────────────────────────────────────────────────────────────────────────
THE THREE STATES

    granted       they were asked and said yes
    withdrawn     they were asked, said yes, and later said no
    never_asked   we have nothing from them

`never_asked` is a state and not a null. It is the honest answer to "may we market to this person?"
and the answer is no — but it is a different no from `withdrawn`, and the difference decides
whether asking again is reasonable or is harassment.

────────────────────────────────────────────────────────────────────────────────────────────────
APPEND-ONLY, BECAUSE THE HISTORY IS THE EVIDENCE

Every transition is a new row. Nothing is ever updated and nothing is ever deleted, so the current
state is the newest row rather than a field somebody can set.

A record you can edit proves nothing: if the row can be changed, then "granted" in the database is
only a claim about today. What answers a regulator is the sequence — asked here, agreed then,
withdrew later — and each entry carrying the moment, the SOURCE, and the exact sentence they were
shown.

THE SENTENCE IS STORED WITH ITS VERSION, and that is the part most implementations miss. Consent is
to a specific statement about who is sending, what they will send and how to stop. Rewrite that
statement and every prior consent becomes consent to something the person never read — so the
version is captured at the moment of granting and never back-filled.

────────────────────────────────────────────────────────────────────────────────────────────────
WITHDRAWAL IS AS EASY AS GRANTING, and that is a requirement rather than a courtesy. It is already
one tap at `/p/{ref}/stop`, and that tap must write a withdrawal ROW rather than only flipping the
send gate — otherwise the gate stops the message and the evidence still says they agreed.

AND MARKETING ALONE NEEDS THIS. Service, personal, awareness and warning messages keep the existing
rule, because they are not direct marketing and stopping a shop from confirming a visit to a new
customer would be a product with no purpose. Only `marketing` requires an explicit grant.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

CONSENT = "marketing_consent"

GRANTED, WITHDRAWN, NEVER_ASKED = "granted", "withdrawn", "never_asked"

# One page of the append-only log, for the reads that must see all of it. The same 500 as
# core/backup.py, which pages the same store for the same reason.
_PAGE = 500

# Where the decision was made. Recorded because "how did you obtain this consent?" is the first
# question anybody asks about it, and an answer reconstructed later is not an answer.
SOURCES = (
    "customer_page",    # they ticked the box on their own page — the only one they drove themselves
    "field_screen",     # the operator asked and recorded it in front of them
    "import",           # migrated from the shop's own prior records; the weakest, and marked so
    "support",          # they told us, and we wrote it down
)

# The statement's version. It changes whenever the WORDING changes, so a consent granted under v1
# is never silently re-read as consent to v2. Bumping it is a deliberate act with a migration
# conversation attached, not a typo fix.
STATEMENT_VERSION = "v1"

STATEMENT = (
    "أوافق على استقبال عروض {shop} على واتساب. "
    "أربع رسائل شهرياً على الأكثر، ويمكنني الإيقاف بضغطة في أي وقت."
)


def _now() -> int:
    return int(time.time())


class ConsentError(Exception):
    """A record this module refuses to write. Never a 500."""


@dataclass
class ConsentRecord:
    """One transition. Append-only — nothing here is ever updated."""

    tenant: str
    subject_ref: str
    state: str                      # GRANTED or WITHDRAWN; NEVER_ASKED is the absence of any row
    source: str
    id: str = field(default_factory=lambda: f"cns_{uuid.uuid4().hex}")
    # WHAT THEY SAW, stored rather than referenced. A pointer to a statement we can edit is a
    # pointer to something that may no longer be what they read.
    statement: str = ""
    statement_version: str = STATEMENT_VERSION
    # Who recorded it, when the source is a person rather than the customer themselves. Empty for
    # `customer_page`, and that emptiness is meaningful: nobody stood between them and the box.
    actor: str = ""
    at: int = field(default_factory=_now)
    # WHAT ORDERS THE HISTORY, and it is not `at`.
    #
    # `at` is seconds, because that is what a person reads. Two records can share a second — a
    # grant and a withdrawal one tap apart do it easily — and then the sequence has NO DEFINED
    # ORDER. In a record we would hand to a regulator, "which came last" is the entire question,
    # and a tie broken by a random id answers it differently on different reads.
    #
    # Found by a test that granted, withdrew and granted again through the routes: the count came
    # back wrong, and only sometimes.
    seq: int = field(default_factory=time.time_ns)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "subject_ref": self.subject_ref,
                "state": self.state, "source": self.source, "statement": self.statement,
                "statement_version": self.statement_version, "actor": self.actor,
                "at": self.at, "seq": self.seq, "created": self.at}


def statement_for(shop: str) -> str:
    """The sentence shown beside the box, with the shop's own name in it.

    THE SHOP IS NAMED, NEVER US. Consent is given to an establishment to send its own offers —
    "I agree to receive offers" with no subject is consent to nobody, and it is exactly the
    ambiguity that makes a bought marketing list look lawful on paper.
    """
    return STATEMENT.format(shop=shop or "المنشأة")


class Consent:
    """Reads and appends. There is deliberately no update and no delete."""

    def __init__(self, store: Any) -> None:
        self._s = store

    async def history(self, tenant: str, subject_ref: str, *, limit: int = 50) -> list[dict]:
        rows, _ = await self._s.find(CONSENT, {"tenant": tenant, "subject_ref": subject_ref},
                                     limit=limit, sort=("seq", "desc"))
        return list(rows or [])

    async def state(self, tenant: str, subject_ref: str) -> str:
        """The newest row's state, or `never_asked` when there is none.

        Derived rather than stored. A stored current-state field is a second truth that can
        disagree with the history, and the history is the one we would have to defend.
        """
        rows = await self.history(tenant, subject_ref, limit=1)
        return rows[0]["state"] if rows else NEVER_ASKED

    async def allows_marketing(self, tenant: str, subject_ref: str) -> bool:
        return await self.state(tenant, subject_ref) == GRANTED

    async def record(self, tenant: str, subject_ref: str, *, state: str, source: str,
                     shop: str = "", actor: str = "", now: int | None = None) -> ConsentRecord:
        """Append one transition.

        REFUSES A SOURCE IT DOES NOT KNOW rather than storing it. "Where did this consent come
        from?" answered with a string somebody typed once is not an answer, and an unrecognised
        source is how a consent of unknown provenance enters the record.
        """
        if state not in (GRANTED, WITHDRAWN):
            raise ConsentError(f"a consent record is granted or withdrawn, not {state!r}")
        if source not in SOURCES:
            raise ConsentError(f"unknown consent source {source!r} — one of {SOURCES}")
        if not tenant or not subject_ref:
            raise ConsentError("tenant and subject are both required")

        rec = ConsentRecord(
            tenant=tenant, subject_ref=subject_ref, state=state, source=source,
            # ONLY A GRANT CARRIES THE STATEMENT. A withdrawal is not agreement to anything, and
            # attaching the sentence to it would put the words of a consent on the record of its
            # refusal.
            statement=statement_for(shop) if state == GRANTED else "",
            actor=actor)
        if now is not None:
            rec.at = now
            # A caller-supplied time orders too, so a test that writes a sequence with explicit
            # timestamps gets the sequence it asked for rather than the order it happened to run in.
            rec.seq = now * 1_000_000_000
        await self._s.put(CONSENT, rec.id, rec.to_dict())
        return rec

    async def count_granted(self, tenant: str) -> int:
        """How many people currently allow this shop's offers (spec §8.5).

        A COUNT, NEVER A LIST. The number is what an owner is shown, and a route that returned who
        consented would be a customer export under a different name.

        Counted from the newest row per person rather than by counting grants: somebody who granted
        and later withdrew has two rows and must not be counted, and somebody who granted twice is
        one person.

        AND IT READS EVERY PAGE, WHICH IS NOT OPTIONAL HERE. This log is append-only — every grant
        and every withdrawal is a row — so the row count is not the people count and grows without
        limit for a shop that has been running a year. A single `find` returned the OLDEST page
        (`seq asc`) and stopped, and «newest row per person» computed over the oldest page is not
        a truncated answer, it is a WRONG one: a customer who withdrew last month still counts as
        consenting, and the number goes UP as the shop loses people. It is shown to an owner and a
        decision to upgrade is made on it.

        Paged rather than bounded by a big `limit`, following core/backup.py: a bound large enough
        to be safe is a bound nobody can defend the day it is reached, and it would be reached
        silently.
        """
        latest: dict[str, str] = {}
        cursor: str | None = None
        while True:
            rows, cursor = await self._s.find(CONSENT, {"tenant": tenant}, limit=_PAGE,
                                              after=cursor, sort=("seq", "asc"))
            for r in rows or []:
                latest[r["subject_ref"]] = r["state"]
            if not cursor:
                break
        return sum(1 for s in latest.values() if s == GRANTED)
