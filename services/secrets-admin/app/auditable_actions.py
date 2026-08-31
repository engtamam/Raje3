"""secrets-admin — auditable actions: what this service must be able to PROVE it did.

ONE ACTION, AND IT IS CRITICAL. That is the whole list, and both facts deserve their reason.

ONE, because this service does exactly one thing that changes the world: it replaces a provider
credential and rolls the Deployment that reads it. The list route reads metadata an operator is
entitled to see, on every page load — recording it would bury the writes under routine reads, and
an investigation looking for "who changed the Meta app secret in March" would be searching a log
that is mostly page views.

CRITICAL, because this is the textbook case for it. `critical: True` means the action is REFUSED
(503) when it cannot be recorded, trading availability for evidence — and the test is whether an
unprovable action is worse than a refused one. A credential change that nobody can attribute is
indistinguishable from an attacker's: the symptom of a compromised platform-owner account and the
symptom of a legitimate key rotation are the same patch to the same object. If we cannot say who
did it, we cannot tell those apart afterwards, ever. Being unable to rotate a key for the minutes
the audit log is down is a far cheaper failure.

THE VALUE NEVER ENTERS THE RECORD, not even its last four characters. `resource` names the Secret
object and the key inside it; `metadata` names the namespace and the Deployment. The audit log is
an append-only hash chain, readable by everyone holding the audit capability and erasable by
nobody — four characters of a live credential written there is a permanent disclosure to a wider
audience than the one person who typed them.

THE ACTOR IS THE TOKEN'S SUBJECT. Not a name, not an email, not a value from the body: a pseudonym
the identity service can resolve and later orphan, which is what keeps the chain both useful and
compatible with an erasure.
"""
from __future__ import annotations

from typing import Any

AUDITABLE_ACTIONS: list[dict[str, Any]] = [
    {
        "action": "platform.secret_changed",
        "source": "admin",
        "critical": True,
        "resource": "provider_secret",
        "why": "replacing a provider credential is a change to how every WhatsApp message on the "
               "product is sent, and it restarts a live service; an unattributable one is "
               "indistinguishable from an attacker rotating a key to their own account, and the "
               "first question after any provider incident is who changed this and when",
    },
]
