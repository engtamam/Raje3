"""The link in every message, and what it is allowed to reveal.

THE SECURITY MODEL HERE IS INVERTED FROM EVERY OTHER SURFACE ON THE PRODUCT, and getting that
backwards is the only way this page can go badly wrong.

Everywhere else we ask: who are you, and may you see this? Here we cannot ask at all. The link
arrives at the end of a WhatsApp message, the customer has no account and never will, and the
message is forwarded, screenshotted and pasted into group chats. So the question becomes: **what
does a stranger holding this link learn?** And the answer must be: nothing about whose it is.

THE REFERENCE IS `{tenant}.{subject_ref}` AND CARRIES NO TOKEN.

Not because a token would be hard — because it would be wrong. A one-time token dies on the first
open, and a customer who reopens yesterday's message finds a dead page and concludes we ignored
them. An expiring token has the same failure on a slower clock. The link has to work the day it
arrives and the month after, or it is not a link, it is a receipt.

WHAT PROTECTS IT. The subject_ref is already 128 bits of HMAC output under a salt only our services
hold. It cannot be reversed to a phone number, and the same person at two shops has two different
ones — so a leaked reference exposes one relationship with one shop, never a person across the
product. This is a capability URL: holding it IS the authorisation, exactly like a password-reset
link, and the same reasoning applies.

THE HONEST WORST CASE. Someone who receives a forwarded link can open the page and switch that
person's messages off. That is why the page shows no name, no phone, no address, and no 404 — the
damage of the worst case is FEWER messages, never a disclosure. A design whose failure mode is
"the customer gets less marketing" is a design we can defend.

AND WHY THE TENANT IS IN THE PATH. Not decoration: the subject_ref alone is not unique across
establishments, and resolving one without a tenant would mean scanning every shop's customers on an
UNAUTHENTICATED route. The tenant makes the lookup a single keyed read.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# A tenant slug as tenant-service mints them, and a subject_ref as operations publishes them.
# Anchored and bounded: this string comes off a URL, and a pattern without a ceiling is a pattern
# a long path can spend a worker's time on.
_TENANT = re.compile(r"^[a-z0-9][a-z0-9_-]{1,62}$")
_SUBJECT = re.compile(r"^sub_[a-f0-9]{16,64}$")


@dataclass(frozen=True)
class Reference:
    tenant: str
    subject_ref: str

    @property
    def valid(self) -> bool:
        return bool(self.tenant and self.subject_ref)

    def __str__(self) -> str:
        return f"{self.tenant}.{self.subject_ref}"


def parse(raw: str) -> Reference:
    """Split a reference from a URL. NEVER RAISES.

    An invalid reference returns an empty one and the caller renders the same page it renders for
    an unknown-but-valid reference. Distinguishing them in the response would be an oracle: a
    stranger with a forwarded link could learn whether a shop exists, and whether it has a customer
    with that reference, by watching which error came back.
    """
    raw = (raw or "").strip()
    # Split on the FIRST separator. A tenant slug cannot contain a dot and a subject_ref cannot
    # either, so a string with two is malformed rather than ambiguous — but partitioning on the
    # first keeps that decision in one place rather than depending on which side is longer.
    tenant, sep, subject = raw.partition(".")
    if not sep:
        return Reference("", "")
    tenant = tenant.lower()
    subject = subject.lower()
    if not _TENANT.match(tenant) or not _SUBJECT.match(subject):
        return Reference("", "")
    return Reference(tenant, subject)


def build(tenant: str, subject_ref: str) -> str:
    """The reference to put in a message.

    Here so that the one place that builds it and the one place that parses it are the same
    module. A separator chosen independently on two sides is trap 4.x in waiting: every button in
    every message 404s, and the templates are already approved by Meta with the broken link baked
    in.
    """
    return f"{tenant}.{subject_ref}"
