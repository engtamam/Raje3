"""What a customer asked his shop for, from his own page — recorded where the shop will see it.

WHY THIS EXISTS RATHER THAN A DIRECT ERASURE. Under the PDPL the establishment is the controller
and we are its processor: the right is exercised AGAINST the shop, and the shop answers. A page
that erased a customer's history the moment he tapped a button would be us acting on the
controller's behalf without its knowledge — and it would hand anyone who obtained a page link a
delete button for somebody else's record.

SO THE PAGE RECORDS THE ASK AND THE OWNER ACTS. He already has the control (see
core/erase_customer.py); what he did not have was any way to know the request existed. A right the
customer can only exercise by phoning the workshop is a right that depends on the workshop
answering the phone.

AND THE ASK ITSELF IS EVIDENCE. It carries the moment it was made, which is when the thirty-day
clock in the regulation starts, and it survives the erasure it asks for — the record that a request
was received and honoured is exactly what must remain when the personal data does not. It holds a
pseudonym and a type; it never holds a name, a number, or a reason typed by anybody.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

PRIVACY_REQUESTS = "privacy_requests"

# The two a customer can ask for from his own page. Correction is deliberately absent: it is a
# conversation at the counter — the operator fixes a name in a second — and a queue for it would be
# slower than the thing it replaces. Access and erasure are the two that need a record.
TYPES = ("export", "erase")

OPEN = "open"
DONE = "done"


@dataclass
class PrivacyRequest:
    """One customer's request, as his shop sees it."""

    id: str
    tenant: str
    subject_ref: str
    type: str
    at: int = field(default_factory=lambda: int(time.time()))
    status: str = OPEN
    # WHO CLOSED IT AND WHEN — because "we answered him" is the claim the establishment has to be
    # able to make, and an unattributed close is not an answer.
    closed_at: int = 0
    closed_by: str = ""

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "subject_ref": self.subject_ref, "type": self.type,
                "at": self.at, "status": self.status,
                "closed_at": self.closed_at, "closed_by": self.closed_by}


def key(tenant: str, request_id: str) -> str:
    return f"{tenant}|{request_id}"


def natural_key(tenant: str, subject_ref: str, kind: str) -> str:
    """One OPEN request per person per kind.

    A customer who taps twice — or who is asked to confirm and taps again — has made one request,
    not two. Two rows would show his shop a queue that overstates what is owed, and a shop that
    sees five requests where there is one starts ignoring the list.
    """
    return f"{tenant}|{subject_ref}|{kind}"
