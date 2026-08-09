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
