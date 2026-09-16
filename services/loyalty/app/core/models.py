"""What a balance is — a ledger, not a number.

THE CENTRAL DECISION: A BALANCE IS NEVER A STORED INTEGER THAT GETS INCREMENTED. Every point is a
deferred financial obligation (spec §9.1) — the shop promised something it has not yet paid. So the
owner must be able to answer two questions at any moment, and an integer answers neither: "where
did these 240 points come from?" and "who spent them?"

A counter cannot be audited. A counter that drifts cannot even be noticed, because there is nothing
to compare it against. A ledger compared against its own sum makes drift a detectable fact rather
than a suspicion, and that is the whole reason for the shape.

WE STILL MATERIALISE THE TOTAL, and that is not a contradiction. The field screen reads the balance
on every customer lookup inside a five-second journey; summing a ledger of six hundred rows per
lookup is a query we would regret within a month. So `Balance` carries the running total AND the
ledger stays the truth: a property test proves they agree, and a repair path exists for when they
do not (which is trap-shaped — see §9.11 in the playbook).

NOTHING IS EVER EDITED OR DELETED. A correction is a new entry with reason `adjust`. A ledger you
can edit is not evidence, and the entire point of writing points down this way was evidence.

EXPIRY IS MEASURED FROM THE LAST MOVEMENT (spec §9.7), so `last_movement_at` is a FIELD on the
balance, not a query over the ledger. The daily expiry tick reads it for every balance in the
product; deriving it would turn a cheap sweep into a full scan of every entry ever written.

CROSS-BRANCH: the balance is keyed by TENANT, and in this product a chain's branches share one
tenant (spec §12.2) — so earning at one branch and redeeming at another needs no special case. It
is the absence of code that implements that rule, which is worth saying out loud, because a reader
looking for the cross-branch logic should stop looking.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

ENTRIES = "loyalty_entries"
BALANCES = "loyalty_balances"
REWARDS = "loyalty_rewards"
REDEMPTIONS = "loyalty_redemptions"
SETTINGS = "loyalty_settings"

# Why a balance moved. Four, and no more: every movement is a grant, a spend, a lapse, or a human
# correcting one of the three.
REASONS = ("earn", "redeem", "expire", "adjust")

# What a reward IS. The `service` type is the one with consequences beyond points: redeeming it
# records a real visit, which restarts the reminder cycle (spec §9.4).
REWARD_TYPES = ("service", "item", "discount")

# How an integrated establishment earns. A SWITCH, exactly two states — see `EarnConfig`.
EARN_MODES = ("services", "invoice")


def _now() -> int:
    return int(time.time())


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


@dataclass
class LedgerEntry:
    """One movement. Append-only, by construction: nothing in this service updates one."""

    tenant: str
    # The PSEUDONYM, never the phone. operations holds the raw identifier because it already had
    # it; every peer including this one gets subject_ref = HMAC(PII_SALT, tenant|subject).
    subject_ref: str
    delta: int                      # signed: + for earn/adjust-up, − for redeem/expire
    reason: str                     # one of REASONS
    id: str = field(default_factory=lambda: _id("led"))
    # WHAT CAUSED IT — a visit id, a redemption id, an invoice id, or the expiry run's day key.
    # This is what makes the entry idempotent: the event bus is at-most-once BY CONTRACT, so a
    # redelivered visit must not pay twice, and the source is how we know it is the same visit.
    source: str = ""
    # WHO DID IT. The account from the session (spec §3.5) — there is no PIN in this product any
    # more. Empty for machine movements (expiry, an event-driven earn) and that emptiness is
    # meaningful: it says no person chose this.
    actor: str = ""
    # For an earn, WHICH LEVEL of the settings tree produced the number (spec §9.2). Stored so the
    # owner can be answered when he asks "why 30?" — a number with no provenance is a number he
    # will not trust, and a loyalty programme the owner does not trust he switches off.
    rule_level: str = ""
    # WHERE it happened, when the caller knows it. Carried on the MOVEMENT as well as on the
    # redemption, because the ledger is the truth: a fact that lives only on the receipt is a fact
    # the truth does not have, and a branch report built from receipts would silently omit every
    # movement that has no receipt — every earn, and every expiry.
    branch_id: str = ""
    # The balance AFTER this entry. Redundant with the sum, and deliberately so: it is what makes
    # a drift locatable rather than merely detectable. Without it, a mismatch tells you the total
    # is wrong; with it, a scan tells you the exact entry where the two diverged.
    balance_after: int = 0
    note: str = ""                  # for `adjust` only — why a human moved it
    created_at: int = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "tenant": self.tenant, "subject_ref": self.subject_ref,
            "delta": self.delta, "reason": self.reason, "source": self.source,
            "actor": self.actor, "rule_level": self.rule_level,
            "branch_id": self.branch_id,
            "balance_after": self.balance_after, "note": self.note,
            "created_at": self.created_at,
        }


@dataclass
class Balance:
    """The materialised running total. The ledger is the truth; this is the read."""

    tenant: str
    subject_ref: str
    points: int = 0
    # Earn OR redeem — not expire. An expiry is not the customer moving, it is us moving, and
    # counting it would restart the clock we were about to run out (spec §9.7).
    last_movement_at: int = 0
    # Set when the expiry warning was sent, so it goes once per expiry cycle rather than daily.
    # Cleared by any real movement, because the customer came back and the cycle restarted.
    expiry_warned_at: int = 0
    created_at: int = field(default_factory=_now)

    @property
    def key(self) -> str:
        """The natural key. One balance per person per establishment (spec §8.1 isolation) — and
        one across that establishment's branches, since they share the tenant (spec §12.2)."""
        return f"{self.tenant}|{self.subject_ref}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "tenant": self.tenant, "subject_ref": self.subject_ref,
            "points": self.points, "last_movement_at": self.last_movement_at,
            "expiry_warned_at": self.expiry_warned_at, "created_at": self.created_at,
        }


@dataclass
class Reward:
    """A reward is NOT a service (spec §9.4).

    Shops reward with things that are not their services — a coffee, an air freshener, money off.
    Modelling rewards as catalogue rows would have forced every shop to invent fake services, and
    a catalogue full of things nobody can book is a catalogue that stops being accurate.
    """

    tenant: str
    name: str
    cost: int
    type: str                       # one of REWARD_TYPES
    id: str = field(default_factory=lambda: _id("rwd"))
    # For type `service` only: which catalogue service this reward IS. Redeeming it records a real
    # visit, so the reminder cycle restarts — the join everybody forgets, and the reason this
    # field exists rather than the type being cosmetic.
    service_id: str = ""
    # For type `discount`: the amount off, in halalas, so no float ever touches money.
    discount_halalas: int = 0
    active: bool = True             # retired, never deleted — see the redemption snapshot below
    created_at: int = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "tenant": self.tenant, "name": self.name, "cost": self.cost,
            "type": self.type, "service_id": self.service_id,
            "discount_halalas": self.discount_halalas, "active": self.active,
            "created_at": self.created_at,
        }


@dataclass
class Redemption:
    """A spend, with the reward's name and cost COPIED ONTO IT.

    Not a reference. A receipt that changes when the menu changes is not a receipt: if the shop
    renames "free wash" to "premium wash" or reprices it, every redemption in history would
    silently restate itself, and the customer's message would stop matching what he was told.
    """

    tenant: str
    subject_ref: str
    reward_id: str
    reward_name: str                # the snapshot, not a lookup
    reward_type: str
    cost: int
    id: str = field(default_factory=lambda: _id("rdm"))
    actor: str = ""                 # from the session (spec §3.5)
    # The caller's key, so a double-tap or a retry on a bad connection spends once. The field
    # screen WILL retry — it runs on a phone in a service lane — and idempotency here is not a
    # nicety, it is the difference between a receipt and a complaint.
    idem_key: str = ""
    channel: str = "field"          # field | panel | till — see spec §9.8
    # WHERE. A chain shares one balance across its branches (§12.2) — that is the design and it
    # stays — but the shop still needs to know which branch handed the reward over. Without it an
    # owner reading his own report can see WHO spent a customer's points and not WHERE, which is
    # exactly half of the question he asks. Optional: a till that does not send it records a
    # redemption with no branch rather than failing, the same rule visits already follow.
    branch_id: str = ""
    discount_halalas: int = 0
    approved_by: str = ""           # set when the reward was above the manager threshold
    # WHETHER THE OTHER HALF OF THE ACT HAPPENED (ز-9). A `service` reward is two things: points
    # spent, and a visit recorded so the reminder cycle restarts. The second ran in a try/except
    # that only wrote telemetry, and nothing ever replayed it — so a free wash was handed over, the
    # points were gone, no visit existed, and the customer was reminded to come in for the service
    # he had just received. Written on the receipt rather than inferred, because the repair needs
    # to find the halves without asking a peer about every redemption we ever made.
    visit_recorded: bool = False
    created_at: int = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "tenant": self.tenant, "subject_ref": self.subject_ref,
            "reward_id": self.reward_id, "reward_name": self.reward_name,
            "reward_type": self.reward_type, "cost": self.cost, "actor": self.actor,
            "idem_key": self.idem_key, "channel": self.channel,
            "branch_id": self.branch_id,
            "discount_halalas": self.discount_halalas, "approved_by": self.approved_by,
            "visit_recorded": self.visit_recorded,
            "created_at": self.created_at,
        }


class LoyaltyError(Exception):
    """A refusal the caller should see the reason for. Never a 500."""


class Overdraft(LoyaltyError):
    """A redemption that would take the balance below zero.

    REFUSED, NEVER CLAMPED. Clamping to zero would hand out the reward and quietly under-charge
    for it, and the shop would discover the shape of that generosity at month end.
    """
