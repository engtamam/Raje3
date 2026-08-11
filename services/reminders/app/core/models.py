"""What this service holds, and the two decisions that shaped it.

NO PHONE NUMBERS HERE, AND NO NAMES. `operations` stores the number because the field screen is
unusable without it and the establishment already had it. This service never needs it: it decides
WHETHER and WHEN to send, and `notification-service` resolves the destination at send time. So a
customer is a `subject_ref` — the HMAC pseudonym operations publishes — and a leak of this
database leaks nobody.

That is not defence in depth for its own sake. This service holds something operations does not:
a prediction of when each person will next need a service, per person, across every shop they use.
Attached to a phone number that is a marketing list; attached to a pseudonym it is arithmetic.

THREE RECORDS, AND THE THIRD IS THE ONE PEOPLE FORGET:

  Schedule    what we intend to send, and when.
  RuleState   what we have learned about a customer's rhythm for one service.
  SendLog     what actually went out — and what did not, with the reason.

Every cap in spec 8.4.2 is counted against the SendLog. A cap with no ledger is a wish: "four
marketing messages a month" is unenforceable unless something durable remembers the previous three,
and remembers them across a restart, a redeploy, and two replicas. The suppression rows matter as
much as the sends — a message that was not sent and cannot be explained is indistinguishable from
a broken service, and that is the support ticket nobody can close.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

# The five regulatory classes (spec 8.4.1). Held here as well as in operations' template library
# because the GATE reasons about them and must not need a peer call to know what it is holding.
CLASSES = ("service", "personal", "awareness", "warning", "marketing")

# What a schedule is FOR. Not the same axis as the class: a reminder and a follow-up are both
# service-class messages, and they behave differently — a visit cancels the follow-up and advances
# the reminder.
KINDS = ("reminder", "follow_up", "review_request", "campaign")

# Where a schedule is in its life. `suppressed` is a terminal state and NOT a failure: the gate
# refused it for a reason we recorded, and retrying tomorrow would re-refuse it for the same reason.
STATES = ("pending", "sent", "cancelled", "suppressed", "failed")


def _now() -> int:
    return int(time.time())


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass
class Schedule:
    """One intended message.

    KEYED BY (tenant, customer, service, kind) FOR A REASON. A second visit for the same service
    must MOVE the pending reminder, not add one — spec 5.8's merge-before-count rule applies to the
    schedule, not only to the send. Two rows here would become two messages that the daily cap then
    turns into one message and one mystery suppression.
    """
    tenant: str
    subject_ref: str
    service_id: str
    kind: str
    due_at: int
    id: str = field(default_factory=lambda: _id("sch"))
    # The class the message will carry. Decided when the schedule is created, not at send time,
    # because the class decides which cap applies and an owner asking "why was this suppressed?"
    # needs the answer to be stable.
    cls: str = "service"
    # Which template to render. Held rather than derived, so a template renamed in the console does
    # not silently repoint a schedule that was created under the old name.
    template_type: str = ""
    # Extra services merged into this one message. A visit with three services produces ONE
    # reminder naming three, and this is where the other two live (spec 5.8).
    also_services: list[str] = field(default_factory=list)
    state: str = "pending"
    # Why it is not pending any more. Empty while pending; on `suppressed` it carries the gate's
    # reason verbatim, which is the whole point of the gate returning one.
    reason: str = ""
    # The visit that caused it. Lets a later visit find and cancel this row, and lets an owner
    # trace a message back to the thing that produced it.
    visit_id: str = ""
    branch_id: str = ""
    created: int = field(default_factory=_now)
    updated: int = field(default_factory=_now)

    @property
    def key(self) -> str:
        """The natural key. Distinct from `id`: the id is stable for tracing, this is what a
        second visit collides with so it updates instead of duplicating."""
        return f"{self.tenant}|{self.subject_ref}|{self.service_id}|{self.kind}"


@dataclass
class RuleState:
    """What we have learned about ONE customer's rhythm for ONE service (spec 5.2).

    Per customer, not per shop, and that is the product: "the customer who returns every two months
    is reminded every two months". A per-service average would be the same number for everybody,
    which is the thing this replaces.

    `interval_days` starts at the sector default and moves toward the observed gap smoothly. It
    never jumps: one late return by a customer who travelled must not stretch the estimate for the
    rest of their life, which is what the anomaly filter in core/adaptive.py exists to prevent.
    """
    tenant: str
    subject_ref: str
    service_id: str
    interval_days: float
    id: str = field(default_factory=lambda: _id("rul"))
    # How many observations shaped it. Below two the estimate is still the default wearing a
    # different hat, and the API says so rather than presenting a guess as learning.
    observations: int = 0
    last_visit_at: int = 0
    # Observations discarded as anomalies, kept as a COUNT rather than dropped silently. A customer
    # whose every visit is an anomaly is not an anomaly — it is a default that is wrong for them,
    # and only this counter can ever reveal that.
    anomalies: int = 0
    updated: int = field(default_factory=_now)

    @property
    def key(self) -> str:
        return f"{self.tenant}|{self.subject_ref}|{self.service_id}"


@dataclass
class SendLog:
    """What went out, or what did not and why. The ledger every cap is counted against.

    APPEND-ONLY. A cap that is enforced by reading rows must never be quietly relieved by deleting
    them — retention trims this by age, on a schedule, and never by count.
    """
    tenant: str
    subject_ref: str
    cls: str
    at: int
    id: str = field(default_factory=lambda: _id("snd"))
    schedule_id: str = ""
    template_name: str = ""
    # "sent" or "suppressed". Suppressions are rows here on purpose: they are the answer to the
    # only question support ever gets about this service.
    outcome: str = "sent"
    reason: str = ""
    # The key we handed notification-service. Held so a retry after a timeout reuses it rather than
    # sending twice — the failure mode where the customer pays for our uncertainty.
    idempotency_key: str = ""
    # Delivery facts as they come back (spec 8.4.2 section 3): read receipts and button taps feed
    # the engagement score. Absent is not zero — it means we have not heard, which is different
    # from ignored, and the score treats it that way.
    read_at: int = 0
    clicked_at: int = 0
    # WHAT THE OFFER SAID, AND UNTIL WHEN — recorded only on a message that carried one (§5.6.2).
    #
    # An offer the operator cannot see becomes a discount argued over at the counter: the customer
    # is holding a message from this shop and the man in front of him knows nothing about it, and
    # both are embarrassed. So the field screen shows it — and its source is THE MESSAGE THAT WENT
    # OUT, never a field somebody retypes. What was not sent is not shown, and what was sent is
    # shown in its own words.
    #
    # AN EXPIRED OFFER IS NOT AN OFFER. The expiry travels with the text precisely so the screen
    # can drop it without asking anybody: a screen showing an offer that has run out is worse than
    # a screen showing nothing, because it contradicts the operator out loud.
    offer_text: str = ""
    offer_expires_at: int = 0
    # WHICH SERVICES IT COVERS. Empty means the whole shop — a real answer, not a missing one, and
    # the screens say so in words rather than showing a gap. The sentence persuades and cannot be
    # enforced; this is the part a screen can act on.
    offer_services: list[str] = field(default_factory=list)


@dataclass
class Preferences:
    """The customer's own switches — five, one per class (spec 8.4.2 section 5).

    ALLOW BY DEFAULT, REFUSE ABSOLUTELY. Deny-by-default is right for permissions and wrong here:
    a customer who has never spoken has not objected, and a shop that cannot send a visit
    confirmation to a new customer has no product. But an explicit stop outranks every priority,
    every cap exemption, and every class — including personal.
    """
    tenant: str
    subject_ref: str
    id: str = field(default_factory=lambda: _id("prf"))
    # class -> allowed. Absent means allowed; only an explicit False is a stop. Storing the
    # positive case too would make "never asked" and "said yes" indistinguishable in the log we
    # would have to defend.
    stopped: dict[str, bool] = field(default_factory=dict)
    updated: int = field(default_factory=_now)

    def allows(self, cls: str) -> bool:
        return not self.stopped.get(cls, False)

    @property
    def key(self) -> str:
        return f"{self.tenant}|{self.subject_ref}"


@dataclass
class Engagement:
    """One number per customer: are they still alive with us? (spec 8.4.2 section 3)

    Stored as a score plus the moment it was computed, and decayed on READ rather than by a sweep.
    A nightly job that halves every score is a job that can fail, skip, or run twice — and each of
    those is silently wrong in a different direction. Decaying on read cannot drift, because the
    arithmetic is a pure function of elapsed time.
    """
    tenant: str
    subject_ref: str
    id: str = field(default_factory=lambda: _id("eng"))
    score: float = 0.0
    scored_at: int = field(default_factory=_now)
    updated: int = field(default_factory=_now)

    @property
    def key(self) -> str:
        return f"{self.tenant}|{self.subject_ref}"


def as_row(obj: Any) -> dict[str, Any]:
    """Dataclass to datastore row. The store keys on `key`; `id` rides along for tracing."""
    from dataclasses import asdict
    return asdict(obj)
