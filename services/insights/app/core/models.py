"""What this service stores — and the far longer list of what it deliberately does not.

IT STORES ONLY WHAT IT COMPUTED. Visits belong to `operations`, balances to `loyalty`, runs to
`campaigns`. This service reads them, derives numbers, and keeps the numbers. It never keeps a copy
of the rows.

That is not tidiness. A second copy of a peer's data disagrees with the original the first time
anything is corrected — a visit amended, a customer erased, a service renamed — and the owner then
has two screens showing two truths with nothing to say which is right. The rule holds even where
copying would be faster.

WHY A SNAPSHOT AT ALL, THEN. The dashboard shows eleven indicators the moment it opens, and asking
every peer for raw rows on every open is a request that gets slower every month a shop stays with
us — the one performance curve that punishes loyalty. So a daily tick computes, and the panel reads
what was computed. The snapshot holds VALUES and COVERAGE, never rows.

AND STALENESS IS PART OF THE VALUE, not a caveat hidden under it. An owner comparing our number to
his till at 2pm must be able to see that ours was computed at 3am. A number without its as-of time
is a number he will stop trusting the first afternoon they disagree.

THE ONE THING HERE THAT IS A PERSON'S DATA is the per-customer service sequence the association
engine needs (`CustomerSequence`) — the set of services one pseudonym has taken across visits. It
is derived, but it is derived FROM one person and describes only them, so erasure has real work to
do. Keyed by `subject_ref` and never by a phone: this service has no business holding a number, and
the pseudonym is enough to group a person's own visits together, which is all the engine asks.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

SNAPSHOTS = "insight_snapshots"
SEQUENCES = "insight_sequences"
PAIRS = "insight_pairs"
SUBSCRIPTIONS = "insight_digest_subs"

def _now() -> int:
    return int(time.time())


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class VisitPage(list):
    """The visits, and whether the cap cut any off.

    A LIST, ON PURPOSE. Every caller wants the rows, most of them do not need to know about the
    cap, and a driver written before this existed still returns a plain list — `getattr(rows,
    "truncated", False)` reads correctly against both. The alternative was a tuple return, which
    would have broken every peers driver silently at the one boundary where silence caused ي-1.
    """

    truncated: bool = False


@dataclass
class Coverage:
    """How much of the data could answer this question (spec §10.6.3).

    Two numbers, never a percentage alone: the panel needs the RAW counts to render the
    "غير محدَّد" row, and the ranking rule needs them to decide whether the unknown bucket could
    overturn a superlative. A stored percentage would force both to be re-derived from it.
    """
    total: int = 0
    known: int = 0

    @property
    def unknown(self) -> int:
        return max(0, self.total - self.known)

    @property
    def ratio(self) -> float:
        return (self.known / self.total) if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"total": self.total, "known": self.known, "unknown": self.unknown,
                "ratio": round(self.ratio, 3)}


@dataclass
class Snapshot:
    """One tenant's computed dashboard, as of one moment."""

    tenant: str
    # indicator name -> its value, whatever shape that indicator has (a number, a list, a map).
    # Deliberately untyped: the alternative was a column per indicator and a migration per new one,
    # and this product does not do migrations.
    values: dict[str, Any] = field(default_factory=dict)
    # indicator name -> Coverage.to_dict(). Absent means the indicator needs no optional field, so
    # its coverage is total by construction and rendering a ratio next to it would be noise.
    coverage: dict[str, Any] = field(default_factory=dict)
    # WHICH BRANCH this snapshot is for. Empty is the whole establishment — the default view, and
    # the only one a single-branch shop ever sees (spec §10.6.4).
    branch_id: str = ""
    # AS OF. Shown on the screen, always. See the module docstring.
    computed_at: int = field(default_factory=_now)
    # How many visits went into it — the honest denominator behind every number above, and what
    # the learning state counts against.
    visits: int = 0
    # WAS THAT ALL OF THEM? The visit feed is read with a cap, and a shop past it is computed from
    # a window rather than its whole history. Every number here is then true of the window and not
    # of the shop, and the difference is invisible on the screen unless it travels with them.
    # False is the ordinary case — nearly every shop fits — and it must never be assumed.
    partial: bool = False

    @property
    def key(self) -> str:
        return f"{self.tenant}|{self.branch_id or '_all'}"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.key, "key": self.key, "tenant": self.tenant,
                "branch_id": self.branch_id, "values": self.values,
                "coverage": self.coverage, "computed_at": self.computed_at,
                "visits": self.visits, "partial": self.partial,
                "created_at": self.computed_at}


@dataclass
class CustomerSequence:
    """Every service one pseudonym has taken, across all their visits.

    THE ENGINE'S SECOND AXIS IS BUILT ON THIS (spec §10.6.2). Counting pairs here rather than
    within a receipt is what makes the group basket harmless: a family's single receipt cannot make
    two services look related if the same person never takes both across a year of visits.

    IT COUNTS VISITS PER SERVICE, and "ever" is not enough — that was a real hole, found by a test.

    A set of everything a person has ever taken keeps a ONE-OFF GROUP VISIT for ever: the payer who
    brought his family once has the kids' meal in his set permanently, and the pair then looks
    confirmed on the customer axis exactly when it should not be. So the axis is built from what a
    person takes REPEATEDLY, and a service seen in a single visit does not vouch for a relationship.

    The remaining case is stated rather than hidden: somebody who ALWAYS comes with his family has
    a family-shaped history, and no arithmetic separates that from his own taste. It is acceptable
    because the offer goes to him and he decides — the unit we measure is the unit we act on.
    """

    tenant: str
    subject_ref: str
    services: list[str] = field(default_factory=list)
    # service id -> in how many DISTINCT visits it appeared. This is what axis two reads.
    counts: dict[str, int] = field(default_factory=dict)
    visits: int = 0
    last_visit_at: int = 0
    updated_at: int = field(default_factory=_now)

    @property
    def key(self) -> str:
        return f"{self.tenant}|{self.subject_ref}"

    def repeated(self, minimum: int = 2) -> list[str]:
        """What this person takes AS A HABIT — the input to the customer axis.

        A service that appeared in one visit says nothing about whether they choose it: it may
        have been the table's order, or a one-off. Two is the smallest number that distinguishes
        a choice from an occurrence.
        """
        return sorted(s for s, n in self.counts.items() if n >= minimum)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.key, "key": self.key, "tenant": self.tenant,
                "subject_ref": self.subject_ref, "services": sorted(set(self.services)),
                "counts": dict(self.counts),
                "visits": self.visits, "last_visit_at": self.last_visit_at,
                "updated_at": self.updated_at, "created_at": self.updated_at}


@dataclass
class Pair:
    """One pair of services, judged on BOTH axes (spec §10.6.2).

    The verdict is stored rather than recomputed on read, because the panel, the bundles page and
    the operator's prompt all ask the same question and must get the same answer. Two callers
    re-deriving a threshold is two callers who will disagree the day one of them is edited.
    """

    tenant: str
    a: str
    b: str
    lift_basket: float = 0.0
    lift_customer: float = 0.0
    # How many customers the relationship covers. A strong relationship between two rare services
    # is not an opportunity, and the bundles page refuses to suggest one without this number.
    customers: int = 0
    # real | group | temporal | none — see core/associations.py for what each means and why the
    # second is the whole reason there are two lifts rather than one.
    verdict: str = "none"
    id: str = field(default_factory=lambda: _id("pair"))
    computed_at: int = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "tenant": self.tenant, "a": self.a, "b": self.b,
                "lift_basket": round(self.lift_basket, 3),
                "lift_customer": round(self.lift_customer, 3),
                "customers": self.customers, "verdict": self.verdict,
                "computed_at": self.computed_at, "created_at": self.computed_at}


class InsightsError(Exception):
    """A refusal the caller should see the reason for. Never a 500."""
