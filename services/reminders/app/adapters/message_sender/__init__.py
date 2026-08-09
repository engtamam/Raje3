"""Sending a message — the two-step the design forced, and why it is right anyway.

WHAT WE FOUND WHEN THE TWO SIDES MET. This service holds a `subject_ref` and no phone number, on
purpose. `notification-service` takes a `recipient` — a real destination. Neither side was wrong;
they simply had never been called in sequence, and the gap only appears when you write the caller.

That is the seam defect this codebase keeps finding: two components each correct alone, disagreeing
where they meet, and no test on either side can see it.

THE FIX, AND THE ONE IT IS NOT. We did NOT store the number here — that would undo the whole reason
this service holds a pseudonym. We did not give notification-service our salt and our customer
table either; that is a larger blast radius, not a smaller one. Instead operations gained
`/internal/operations/recipient`: one subject per call, no listing, nothing logged. The number
exists in that response and in this process's memory for the length of one send, and rests nowhere
new.

TWO CALLS PER MESSAGE IS A REAL COST, AND IT IS THE RIGHT TRADE. It buys a database that leaks
nobody, logs that leak nobody, and a backup that leaks nobody. The resolver is also the natural
place to discover that a customer was erased — a blanked phone comes back empty and the send is
abandoned rather than attempted with a pseudonym as the destination.

FOUR THINGS NOTIFICATION-SERVICE WILL NOT FORGIVE, learned from its request model:

  `variables` is a DICT keyed by number      — a list is silently dropped and every variable
                                               renders empty.
  `tenant` must be sent                      — without it every consent-gated send resolves against
                                               an empty tenant, finds no record, and permanently
                                               denies. Its own model documents this as a past
                                               outage.
  `template_key`, not `template_name`.
  `idempotency_key` is honoured              — which is what makes a retry after a timeout safe.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class NullSender:
    """Sends nothing and records what it would have sent.

    Correct for tests and a local run; refused in production by the boot guard in config.py, where
    it would mean a service that schedules perfectly and never messages anybody — the quietest
    possible outage.
    """
    driver = "null"

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, *, tenant: str, subject_ref: str, template_name: str,
                   variables: list[str], cls: str, idempotency_key: str) -> None:
        self.sent.append({"tenant": tenant, "subject_ref": subject_ref,
                          "template_name": template_name, "variables": variables,
                          "cls": cls, "idempotency_key": idempotency_key})


class HttpSender:
    """The real one: resolve the recipient from operations, then hand it to notification-service.

    stdlib urllib, matching every other internal client on the platform — no extra runtime
    dependency and a leaner image.
    """
    driver = "http"

    def __init__(self, *, notify_url: str, notify_path: str, operations_url: str,
                 recipient_path: str, token: str, channel: str = "whatsapp",
                 timeout: int = 8) -> None:
        self._notify = notify_url.rstrip("/") + notify_path
        self._resolve = operations_url.rstrip("/") + recipient_path
        self._token = token
        self._channel = channel
        self._timeout = timeout

    async def send(self, *, tenant: str, subject_ref: str, template_name: str,
                   variables: list[str], cls: str, idempotency_key: str) -> None:
        recipient = self._recipient(tenant, subject_ref)
        if not recipient:
            # NOT AN ERROR, and not a retry. The subject was erased, or never existed. Raising
            # would put this schedule into the retry loop forever, and every tick would ask
            # operations about a customer who asked to be forgotten.
            raise Unsendable(f"no recipient for {subject_ref} — erased or unknown")

        body = json.dumps({
            "recipient": recipient,
            "channel": self._channel,
            "template_key": template_name,
            # WITHOUT THIS, every consent-gated send resolves against an empty tenant and denies
            # permanently. Documented as a past outage in the peer's own request model.
            "tenant": tenant,
            # A DICT KEYED BY NUMBER. A list is dropped silently and renders every variable empty.
            "variables": {str(i + 1): v for i, v in enumerate(variables)},
            "idempotency_key": idempotency_key,
            "event": f"reminders.{cls}",
        }).encode()
        req = urllib.request.Request(
            self._notify, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
            if not 200 <= resp.status < 300:
                raise SendFailed(f"notification-service returned {resp.status}")
            result = json.loads(resp.read() or b"{}")

        # THE HTTP STATUS IS NOT THE DELIVERY STATUS, and reading only the first was a silent
        # defect for as long as this file existed.
        #
        # `/internal/notify` answers 200 and returns the delivery RECORD — including
        # `status: "failed"` with a reason. Its most common reason in this product is the one that
        # cannot be avoided: a WhatsApp template Meta has not approved yet (spec §6.6.1), because
        # the library is submitted per establishment and approval takes minutes to a day. So a
        # reminder for a shop that connected this morning came back 200, was written to the ledger
        # as `sent`, and the schedule was closed — a message that never went, recorded as one that
        # did, with the customer never reminded and nothing anywhere to find.
        #
        # Raising SendFailed instead puts the schedule back to `pending` with a short delay (see
        # tick._fail), so it goes out by itself once the template clears. Nothing is lost and
        # nobody has to notice.
        status = str(result.get("status") or "")
        if status and status not in _DELIVERED:
            # THE CEILING FIRST, because it is the one refusal that must not be retried in an hour
            # and must not pollute the peer-failure counts.
            code = str(result.get("error_code") or result.get("code") or "")
            if code in CEILING_CODES:
                raise CeilingReached(code, f"{code}: {result.get('error') or 'ceiling reached'}")
            raise SendFailed(f"{status}: {result.get('error') or 'no reason given'}")

    def _recipient(self, tenant: str, subject_ref: str) -> str:
        body = json.dumps({"tenant": tenant, "subject_ref": subject_ref}).encode()
        req = urllib.request.Request(
            self._resolve, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # nosec B310
                data = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            raise SendFailed(f"recipient lookup returned {exc.code}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise SendFailed(f"recipient lookup unreachable: {exc}") from exc
        return str(data.get("recipient") or "")


# What counts as "it went". `queued` is included deliberately: the peer has taken responsibility
# and will drain it, so treating it as a failure would send twice.
_DELIVERED = frozenset({"sent", "queued"})


# THE CODES META RETURNS WHEN THE SHOP HAS SENT ENOUGH FOR NOW, from its Cloud API error
# reference. Numbers, never message text: the text is translated, reworded and localised, and a
# branch that matches on a phrase stops matching without anything failing.
#
# They are NOT all the same thing, and the difference is the shop's to know:
#   130429  the API's own throughput ceiling — ours to back off from
#   80007   the WhatsApp Business Account hit its rate limit
#   131048  sending blocked because earlier messages were flagged as spam — a quality problem,
#           not a volume one, and the only one here that needs a human
#   131056  too many messages to the SAME recipient in a short time
#   131064  the account reached its messaging limit
#   131049  blocked to maintain healthy engagement — the per-user marketing limit
#
# All six mean "not now", which is why one exception carries them; the code travels with it so the
# operator panel can tell an overdue shop apart from a suspected one.
CEILING_CODES = frozenset({"130429", "80007", "131048", "131056", "131064", "131049"})


class CeilingReached(Exception):
    """WhatsApp will not take another message from this shop right now.

    NEITHER TRANSIENT NOR PERMANENT, which is why it is its own class. Retrying in an hour walks
    into the same closed door; giving up loses a message that would go tomorrow. What happens next
    depends on the TEMPLATE — a visit confirmation is worthless tomorrow, an offer is not — and
    that decision is data, not code (spec §8.4.3).

    IT MUST NOT BE COUNTED AS A PEER FAILURE. The reason counts are how an operator sees a real
    notification-service outage; burying a daily, expected, self-resolving condition in them
    destroys the signal they exist to carry.
    """

    def __init__(self, code: str = "", detail: str = "") -> None:
        super().__init__(detail or code or "ceiling reached")
        self.code = code


class SendFailed(Exception):
    """A transient failure. The tick reschedules and tries again."""


class Unsendable(Exception):
    """A permanent one: there is nobody to send to. Retrying would ask operations about an erased
    customer on every tick, forever."""


def build_sender(settings) -> Any:
    driver = (getattr(settings, "SENDER_DRIVER", "") or "null").lower()
    if driver == "null":
        return NullSender()
    return HttpSender(
        notify_url=settings.NOTIFICATION_SERVICE_URL,
        notify_path=settings.NOTIFICATION_SEND_PATH,
        operations_url=settings.OPERATIONS_SERVICE_URL,
        recipient_path=settings.OPERATIONS_RECIPIENT_PATH,
        token=settings.INTERNAL_SERVICE_TOKEN,
        channel=settings.MESSAGE_CHANNEL,
        timeout=settings.PEER_TIMEOUT_SECONDS)
