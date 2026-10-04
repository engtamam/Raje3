"""coworking — auditable actions: what this service must be able to PROVE it did.

See `services/affiliate-service/app/auditable_actions.py`'s own module doc for the full contract
(what each field means, why `critical` is a behaviour rather than a severity label, why the actor
is always a pseudonym). This file is the SEED for this service's own small domain.
"""
from __future__ import annotations

from typing import Any

AUDITABLE_ACTIONS: list[dict[str, Any]] = [
    {
        "action": "operator.secret_set",
        "source": "admin",
        "critical": True,
        "resource": "secret",
        "why": "a credential change is the action that most needs attribution: the previous value "
               "is gone the moment it happens, so an unrecorded rotation cannot be reconstructed, "
               "and an unattributable one is indistinguishable from an attacker's",
    },
    {
        "action": "operator.secret_cleared",
        "source": "admin",
        "critical": True,
        "resource": "secret",
        "why": "clearing a credential silently reverts the service to whatever the environment "
               "holds, which is a behaviour change nobody would otherwise see",
    },
    {
        "action": "operator.config_changed",
        "source": "admin",
        "critical": False,
        "resource": "config",
        "why": "policy changes explain later behaviour — that history is unavailable anywhere "
               "else. Not critical: this service's RUNTIME_POLICY is currently empty, but the "
               "route exists and stays declared for the day a knob is added",
    },
    {
        "action": "coworking.pause_changed",
        "source": "admin",
        "critical": False,
        "resource": "tenant",
        "why": "explains later why every new booking attempt started (or stopped) being refused "
               "for a shop, which a freelancer disputing a refusal would otherwise have no way to "
               "confirm was a deliberate owner decision — not critical: a delay in recording a "
               "pause toggle costs nothing an owner cannot immediately fix by toggling again",
    },
    {
        "action": "coworking.resource_image_set",
        "source": "admin",
        "critical": False,
        "resource": "resource",
        "why": "explains later when/who replaced a resource's public photo — not critical: a "
               "delay in recording it costs nothing a shop owner cannot immediately fix by "
               "re-uploading, same reasoning as coworking.pause_changed above",
    },
    {
        "action": "coworking.subject_erase_requested",
        "source": "internal",
        "critical": False,
        "resource": "subject",
        "why": "the fan-out's own request is useful context around the erasure result that "
               "follows; not critical on its own since the completion record below is what "
               "actually proves the erasure happened",
    },
    {
        "action": "coworking.subject_erased",
        "source": "internal",
        "critical": True,
        "resource": "subject",
        "why": "erasing a freelancer's identifying phone number platform-wide (the DSAR fan-out "
               "compliance-service triggers) is one of the most legally significant, irreversible "
               "actions this service ever performs — an unwitnessed erasure is indistinguishable "
               "from one nobody actually authorised",
    },
]
