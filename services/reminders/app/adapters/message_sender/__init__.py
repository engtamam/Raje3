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
from typing import Any

from app.adapters import internal_http

# The greeting a template falls back to when nobody knows the customer's name. Imported rather
# than repeated: two copies of this string is a message that greets one way here and another way
# in the renderer, and only one of them is the one Meta approved.
from app.core.rendering import FALLBACK_NAME


# A DEFAULT, NOT A CONSTANT. These are Meta's codes; they add and retire them, and a set of
# somebody else's identifiers frozen into our code is a branch that stops matching without
# anything failing. WHATSAPP_CEILING_CODES overrides it, and the day Meta publishes a new one it
# is a values-file edit rather than a release.
DEFAULT_CEILING_CODES = ("130429", "80007", "131048", "131056", "131064", "131049")


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
                   variables: list[str], cls: str, idempotency_key: str,
                   sending_identity: str = "", flow_token: str = "",
                   flow_action_data: dict[str, Any] | None = None) -> None:
        self.sent.append({"tenant": tenant,
                          # RECORDED BY THE FAKE TOO, so a test that targets a branch can assert
                          # which number it would have gone out from.
                          "sending_identity": sending_identity or tenant,
                          "subject_ref": subject_ref,
                          "template_name": template_name, "variables": variables,
                          "cls": cls, "idempotency_key": idempotency_key,
                          "flow_token": flow_token, "flow_action_data": dict(flow_action_data or {})})
        # THE FAKE RETURNS A HANDLE TOO, derived from the key so it is stable across a retry —
        # exactly as the peer's own delivery id is. A fake that returned "" would let the receipt
        # reconciler's tests pass against a shape the real sender never produces.
        return f"dlv_{idempotency_key}" if idempotency_key else ""

    async def send_flow(self, *, tenant: str, subject_ref: str, body: str, flow_token: str,
                        flow_id: str, flow_cta: str, flow_screen: str,
                        flow_data: dict[str, Any] | None = None, idempotency_key: str = "",
                        sending_identity: str = "") -> str:
        self.sent.append({"tenant": tenant, "sending_identity": sending_identity or tenant,
                          "subject_ref": subject_ref, "type": "flow", "body": body,
                          "flow_token": flow_token, "flow_id": flow_id, "flow_cta": flow_cta,
                          "flow_screen": flow_screen, "flow_data": dict(flow_data or {}),
                          "idempotency_key": idempotency_key})
        return f"dlv_{idempotency_key}" if idempotency_key else ""


class HttpSender:
    """The real one: resolve the recipient from operations, then hand it to notification-service.

    stdlib urllib, matching every other internal client on the platform — no extra runtime
    dependency and a leaner image.
    """
    driver = "http"

    def __init__(self, *, notify_url: str, notify_path: str, operations_url: str,
                 recipient_path: str, token: str, channel: str = "whatsapp",
                 timeout: int = 8, ceiling_codes: tuple[str, ...] = DEFAULT_CEILING_CODES,
                 interactive_notify_path: str = "") -> None:
        self._ceiling = frozenset(ceiling_codes)
        self._notify = notify_url.rstrip("/") + notify_path
        # OPTIONAL, and empty when omitted — a deployment that has not set
        # NOTIFICATION_INTERACTIVE_SEND_PATH yet simply cannot reach `send_flow` (it raises
        # SendFailed rather than posting to an empty URL), same as every other not-yet-wired knob
        # on this platform fails closed rather than guessing at a path.
        self._notify_interactive = (notify_url.rstrip("/") + interactive_notify_path
                                    if interactive_notify_path else "")
        self._resolve = operations_url.rstrip("/") + recipient_path
        self._token = token
        self._channel = channel
        self._timeout = timeout

    async def send(self, *, tenant: str, subject_ref: str, template_name: str,
                   variables: list[str], cls: str, idempotency_key: str,
                   sending_identity: str = "", flow_token: str = "",
                   flow_action_data: dict[str, Any] | None = None) -> None:
        """`flow_token`/`flow_action_data` — the rating app's own Flow-button-in-a-template send
        (notification-service v0.18.24): when the approved template carries a Flow button, these
        supply the per-send action; empty otherwise, and notification-service ignores them for an
        ordinary template. `flow_action_data` is omitted from the wire body entirely when empty —
        Meta rejects an empty data object, same rule build_flow's own docstring states."""
        recipient, name = self._recipient(tenant, subject_ref)
        if not recipient:
            # NOT AN ERROR, and not a retry. The subject was erased, or never existed. Raising
            # would put this schedule into the retry loop forever, and every tick would ask
            # operations about a customer who asked to be forgotten.
            raise Unsendable(f"no recipient for {subject_ref} — erased or unknown")

        # ── THE CUSTOMER'S NAME, AND THE ONLY PLACE IT MAY BE READ ───────────────────────────
        # Slot 1 is the customer's name in every one of our templates, and NOTHING was putting a
        # name in it: the tick passes `customer_names={}` and the campaign path passed `""`, so
        # every message this product has ever rendered said «عميلنا العزيز» — to customers whose
        # names we hold. The greeting is the first four words a customer reads, and it was the
        # same four words for everyone.
        #
        # AND IT IS FIXED HERE RATHER THAN IN THE TICK, deliberately. This service holds a
        # PSEUDONYM and no personal data (see the recipient route's own docstring): resolving a
        # name earlier would put it in a schedule row, a render, a log and a backup. The phone
        # number already lives for the length of this one call, and the name rides the same
        # response — no second read, and nothing new at rest.
        #
        # ONLY OVER THE FALLBACK. A caller that supplied a real name (the redemption path names
        # the person from the visit) keeps it; this fills the blank rather than overruling anyone.
        variables = list(variables)
        if name and variables and variables[0] in ("", FALLBACK_NAME):
            variables[0] = name

        payload: dict[str, Any] = {
            "recipient": recipient,
            "channel": self._channel,
            "template_key": template_name,
            # WITHOUT THIS, every consent-gated send resolves against an empty tenant and denies
            # permanently. Documented as a past outage in the peer's own request model.
            "tenant": tenant,
            # WHICH NUMBER THIS LEAVES FROM (spec 12.7.1). `tenant` for a shop that sends from one
            # number — which is every shop today — and `tenant:branch` for a chain that moved to a
            # number per branch. The peer treats it as an opaque key: it selects the credentials
            # sealed under it and never learns what a branch is.
            #
            # ABSENT MEANS THE ESTABLISHMENT, so a caller that has not been taught this yet keeps
            # behaving exactly as before rather than sending from nowhere.
            "sending_identity": sending_identity or tenant,
            # A DICT KEYED BY NUMBER. A list is dropped silently and renders every variable empty.
            "variables": {str(i + 1): v for i, v in enumerate(variables)},
            "idempotency_key": idempotency_key,
            "event": f"reminders.{cls}",
            # OUR OWN HANDLE, CARRIED THERE AND BACK. Meta echoes `biz_opaque_callback_data`
            # verbatim in the status webhook (≤512 chars), so a receipt can name the send it
            # belongs to without a join. The peer's `delivery_id` is the primary key we store; this
            # is the second one, and it is the one that survives — a receipt arriving for a message
            # whose delivery row we lost still says which of OUR sends it was about.
            "biz_opaque_callback_data": idempotency_key,
        }
        # THE RATING APP'S OWN ACTION — only when this call actually carries one. An ordinary
        # template send (every message today except rating_request) must not grow a flow_token
        # key at all: notification-service ignores it harmlessly either way, but sending "" for
        # every plain confirmation is a wire field with no meaning, forever. `flow_action_data` is
        # additionally never sent as an empty {} — Meta rejects an empty data object, same rule
        # build_flow's own docstring states for the interactive-Flow path.
        if flow_token:
            payload["flow_token"] = flow_token
            if flow_action_data:
                payload["flow_action_data"] = dict(flow_action_data)
        body = json.dumps(payload).encode()
        # Built in adapters/internal_http.py, the one place this service attaches the token.
        status, raw = internal_http.send(
            self._notify, timeout=self._timeout, method="POST", body=body,
            content_type=internal_http.JSON, token=self._token)
        if not 200 <= status < 300:
            raise SendFailed(f"notification-service returned {status}")
        result = json.loads(raw or b"{}")

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
            if code in self._ceiling:
                raise CeilingReached(code, f"{code}: {result.get('error') or 'ceiling reached'}")
            raise SendFailed(f"{status}: {result.get('error') or 'no reason given'}")

        # AND THE PEER'S HANDLE COMES BACK, so the send log can be matched to a receipt later.
        #
        # Empty is a real answer: the console driver has no delivery row and a peer we did not
        # reach raised long before this line. An empty handle means «this send will never be
        # matched», which the reconciler must be able to tell apart from «not delivered yet».
        return str(result.get("delivery_id") or "")

    async def send_flow(self, *, tenant: str, subject_ref: str, body: str, flow_token: str,
                        flow_id: str, flow_cta: str, flow_screen: str,
                        flow_data: dict[str, Any] | None = None, idempotency_key: str = "",
                        sending_identity: str = "") -> str:
        """NOT the rating app's message — that one goes out through `send()` above, as an ordinary
        approved template carrying a `flow_token` (the template's own registered `flow_button` is
        what actually opens the Flow; see operations/data/templates.seed.json). This is a SEPARATE
        mechanism: a Flow sent as a bare interactive message with no template behind it at all,
        posted to the same interactive route whatsapp-assistant already uses for buttons/lists,
        with `type: "flow"`.

        GENUINELY UNUSED TODAY — nothing in this service calls it outside its own tests, and
        nothing needs to for the rating feature, which is fully wired through `send()` instead.
        Kept to the same shape as `send()` — same recipient lookup, same erased-customer/ceiling/
        failure handling — in case a future feature needs a Flow with no template wrapping it (a
        one-off form, say), so that would be a call site, not a new sending path to build.
        """
        if not self._notify_interactive:
            raise SendFailed("NOTIFICATION_INTERACTIVE_SEND_PATH is not configured")
        recipient, _name = self._recipient(tenant, subject_ref)
        if not recipient:
            raise Unsendable(f"no recipient for {subject_ref} — erased or unknown")
        req_body = json.dumps({
            "recipient": recipient,
            "tenant": tenant,
            "type": "flow",
            "body": body,
            "flow_token": flow_token,
            "flow_id": flow_id,
            "flow_cta": flow_cta,
            "flow_screen": flow_screen,
            "flow_data": dict(flow_data or {}),
            "sending_identity": sending_identity or tenant,
            "idempotency_key": idempotency_key,
            "biz_opaque_callback_data": idempotency_key,
        }).encode()
        status, raw = internal_http.send(
            self._notify_interactive, timeout=self._timeout, method="POST", body=req_body,
            content_type=internal_http.JSON, token=self._token)
        if not 200 <= status < 300:
            raise SendFailed(f"notification-service returned {status}")
        result = json.loads(raw or b"{}")
        result_status = str(result.get("status") or "")
        if result_status and result_status not in _DELIVERED:
            code = str(result.get("error_code") or result.get("code") or "")
            if code in self._ceiling:
                raise CeilingReached(code, f"{code}: {result.get('error') or 'ceiling reached'}")
            raise SendFailed(f"{result_status}: {result.get('error') or 'no reason given'}")
        return str(result.get("delivery_id") or "")

    def _recipient(self, tenant: str, subject_ref: str) -> tuple[str, str]:
        body = json.dumps({"tenant": tenant, "subject_ref": subject_ref}).encode()
        try:
            data = json.loads(internal_http.read(
                self._resolve, self._timeout, method="POST", body=body,
                content_type=internal_http.JSON, token=self._token) or b"{}")
        except urllib.error.HTTPError as exc:
            raise SendFailed(f"recipient lookup returned {exc.code}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise SendFailed(f"recipient lookup unreachable: {exc}") from exc
        return str(data.get("recipient") or ""), str(data.get("name") or "")


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
        timeout=settings.PEER_TIMEOUT_SECONDS,
        ceiling_codes=settings.whatsapp_ceiling_codes,
        interactive_notify_path=getattr(settings, "NOTIFICATION_INTERACTIVE_SEND_PATH", ""))
