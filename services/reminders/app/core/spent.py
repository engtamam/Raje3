"""Which offers a customer has already spent — asked of `operations`, because it is theirs to say.

WHY THIS FILE EXISTS AT ALL. Spec 5.6.2 splits the offer's life down the middle: `reminders`
issues it, and `operations` records that it was spent, «ويُسجَّل على الزيارة، لا على العرض». The
reason is not tidiness — the send log is append-only and every cap in 5.8 is counted against it, so
a used-flag written into that log breaks the ledger the limits are counted on. This code was
written the wrong way round first, and the spec is what caught it.

SO A FAILURE HERE HIDES AN OFFER, NEVER SHOWS A SPENT ONE. If operations cannot be reached we
cannot know what was spent — and the two wrong answers are not equal. Showing an offer the customer
already used puts a worker at a counter arguing with a customer holding a phone; hiding one for a
minute costs a customer an offer that is still there when the service returns. So an unreachable
peer subtracts nothing and the caller decides — see the callers, which treat an error as "unknown"
rather than as "none spent".
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class SpentUnknown(RuntimeError):
    """Operations could not be asked. NOT the same fact as "nothing was spent"."""


def spent_refs(*, operations_url: str, token: str, tenant: str, subject_ref: str,
               timeout: int = 5) -> set[str]:
    """Send-log row ids this customer has already applied to a visit.

    TIMES OUT FAST. This sits in front of a screen a worker is waiting on with a customer at the
    counter; five seconds is already longer than that moment can carry, and a long timeout here
    would turn one slow peer into a slow shop.
    """
    if not operations_url:
        raise SpentUnknown("no operations url configured")

    body = json.dumps({"tenant": tenant, "subject_ref": subject_ref}).encode()
    req = urllib.request.Request(
        operations_url.rstrip("/") + "/internal/operations/offers-spent",
        data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Internal-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:          # nosec B310
            if not 200 <= resp.status < 300:
                raise SpentUnknown(f"operations answered {resp.status}")
            payload = json.loads(resp.read() or b"{}")
    except SpentUnknown:
        raise
    except Exception as exc:                                                # noqa: BLE001
        raise SpentUnknown(str(exc)[:200]) from exc

    return {str(r) for r in (payload.get("refs") or []) if r}
