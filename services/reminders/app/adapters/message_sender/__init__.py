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

import asyncio
import base64
import json
import urllib.error
import urllib.parse
import urllib.request
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

# A CARD NEEDS A PHOTO OR IT ISN'T A CARD — Meta's media-card-carousel template requires an image
# or video header on every card (developers.facebook.com/documentation/business-messaging/
# whatsapp/templates/marketing-templates/media-card-carousel-templates: "Each card in the
# template has an image or video header asset"), there is no text-only card in this template
# type. A covered service with no uploaded photo used to mean its card was dropped — and the
# whole carousel with it, the day fewer than two services had one. This is that gap closed: a
# plain neutral placeholder (400x300, solid light grey, no text, no logo — nothing that could be
# wrong for a shop) stands in for the missing photo so the card, and the carousel, still send.
_PLACEHOLDER_CARD_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAZAAAAEsCAIAAABi1XKVAAAC90lEQVR42u3UMQ0AAAzDsPLn2WcohmOTJSPIkbQDcEIkAAwLwLAAwwIwLADDAgwLwLAADAswLADDAjAswLAADAvAsADDAjAsAMMCDAvAsAAMCzAsAMMCMCzAsAAMC8CwAMMCMCzAsFQADAvAsADDAjAsAMMCDAvAsAAMCzAsAMMCMCzAsAAMC8CwAMMCMCwAwwIMC8CwAAwLMCwAwwIwLMCwAAwLwLAAwwIwLMCwVAAMC8CwAMMCMCwAwwIMC8CwAAwLMCwAwwIwLMCwAAwLwLAAwwIwLADDAgwLwLAADAswLADDAjAswLAADAvAsADDAjAswLAADAvAsADDAjAsAMMCDAvAsAAMCzAsAMMCMCzAsAAMC8CwAMMCMCwAwwIMC8CwAAwLMCwAwwIwLMCwAAwLwLAAwwIwLMCwAAwLwLAAwwIwLADDAgwLwLAADAswLADDAjAswLAADAvAsADDAjAsAMMCDAvAsAAMCzAsAMMCMCzAsAAMC8CwAMMCMCzAsAAMC8CwAMMCMCwAwwIMC8CwAAwLMCwAwwIwLMCwAAwLwLAAwwIwLADDAgwLwLAADAswLADDAjAswLAADAvAsADDAjAsAMMCDAvAsAAMCzAsAMMCMCzAsAAMC8CwAMMCMCzAsAAMC8CwAMMCMCwAwwIMC8CwAAwLMCwAwwIwLMCwAAwLwLAAwwIwLMCwAAwLwLAAwwIwLADDAgwLwLAADAswLADDAjAswLAADAswLAkAwwIwLMCwAAwLwLAAwwIwLADDAgwLwLAADAswLADDAjAswLAADAvAsADDAjAsAMMCDAvAsAAMCzAsAMMCMCzAsAAMCzAsFQDDAjAswLAADAvAsADDAjAsAMMCDAvAsAAMC/hsAaYjYT7whqT1AAAAAElFTkSuQmCC"
)
_PLACEHOLDER_CARD_CONTENT_TYPE = "image/png"


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

    async def send_carousel(self, *, tenant: str, subject_ref: str, template_name: str,
                            variables: list[str], service_ids: list[str],
                            service_names: dict[str, str], idempotency_key: str,
                            sending_identity: str = "") -> str:
        self.sent.append({"tenant": tenant, "sending_identity": sending_identity or tenant,
                          "subject_ref": subject_ref, "type": "carousel",
                          "template_name": template_name, "variables": variables,
                          "service_ids": list(service_ids),
                          "service_names": dict(service_names),
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
                 interactive_notify_path: str = "",
                 carousel_send_path: str = "", media_upload_id_path: str = "",
                 catalogue_image_path: str = "") -> None:
        self._ceiling = frozenset(ceiling_codes)
        self._notify = notify_url.rstrip("/") + notify_path
        # OPTIONAL, and empty when omitted — a deployment that has not set
        # NOTIFICATION_INTERACTIVE_SEND_PATH yet simply cannot reach `send_flow` (it raises
        # SendFailed rather than posting to an empty URL), same as every other not-yet-wired knob
        # on this platform fails closed rather than guessing at a path.
        self._notify_interactive = (notify_url.rstrip("/") + interactive_notify_path
                                    if interactive_notify_path else "")
        # PHASE 2 (carousel, core/shape.py) — three more OPTIONAL routes, same posture: a
        # deployment that has not set all three yet cannot reach `send_carousel` at all (it raises
        # CarouselUnavailable immediately rather than guessing). Once configured, every covered
        # service gets a card — its own photo when operations has one, `_PLACEHOLDER_CARD_IMAGE`
        # when it doesn't — so the carousel's existence no longer depends on how many of this
        # shop's services happen to have a photo uploaded.
        self._carousel_send = notify_url.rstrip("/") + carousel_send_path if carousel_send_path else ""
        self._media_upload = notify_url.rstrip("/") + media_upload_id_path if media_upload_id_path else ""
        # `operations_url` — the SAME peer `_resolve` below already calls, just a different route.
        self._catalogue_image = (operations_url.rstrip("/") + catalogue_image_path
                                 if catalogue_image_path else "")
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
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        recipient, name = await asyncio.to_thread(self._recipient, tenant, subject_ref)
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
                action_data = dict(flow_action_data)
                # ── THE BOOKING FLOW'S SEED, FILLED HERE FOR THE SAME REASON THE NAME IS ────────
                # The booking Flow is keyed on the customer's own phone number — that is the
                # identity every op in whatsapp-assistant's FlowBookingBackend reads, and a Flow
                # opened without it cannot say who is asking. Neither campaigns nor this service
                # holds a phone number: the pseudonym is the whole point (see the module
                # docstring), and putting the number on a schedule row would put it in a render, a
                # log and a backup.
                #
                # It is already in scope right here, for the length of this one call, resolved a
                # few lines above beside the customer's name — so the caller DECLARES the key
                # empty and this fills the blank, exactly as the greeting above fills `variables[0]`
                # and by exactly the same rule: only over a blank, never over a value a caller
                # supplied. The weekly report's own Flow declares no such key and is untouched.
                if "customer" in action_data and not str(action_data["customer"] or ""):
                    action_data["customer"] = recipient
                payload["flow_action_data"] = action_data
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
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        recipient, _name = await asyncio.to_thread(self._recipient, tenant, subject_ref)
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

    def _fetch_service_image(self, tenant: str, kind: str, item_id: str) -> tuple[bytes, str] | None:
        """One service/package photo, or `None` on anything but a clean 2xx — a missing photo, a
        peer hiccup and a 404 all look the same from here: "no real photo for this card", which
        `send_carousel` now answers with the placeholder rather than dropping the card."""
        if not self._catalogue_image:
            return None
        url = self._catalogue_image.format(kind, item_id) + f"?tenant={urllib.parse.quote(tenant)}"
        req = internal_http.request(url, method="GET", token=self._token)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return None
                ctype = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
                return resp.read(), ctype
        except (urllib.error.URLError, OSError):
            return None

    def _upload_media_id(self, *, tenant: str, data: bytes, content_type: str) -> str:
        """A Meta media id for one photo — real or the placeholder, this call cannot tell the
        difference and does not need to — or `""` on any failure, the only case the caller still
        drops the card for."""
        if not self._media_upload:
            return ""
        body = {"tenant": tenant, "file_type": content_type, "file_name": "card.jpg",
                "data_base64": base64.b64encode(data).decode()}
        try:
            out = internal_http.post_json(self._media_upload, body, self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return ""
        return str(out.get("media_id") or "")

    async def send_carousel(self, *, tenant: str, subject_ref: str, template_name: str,
                            variables: list[str], service_ids: list[str],
                            service_names: dict[str, str], idempotency_key: str,
                            sending_identity: str = "") -> str:
        """Thin async wrapper — every call inside is stdlib urllib, plain synchronous methods, so
        the whole card-building-and-send sequence runs as ONE unit off the event loop. See
        core/customer_lookup.py::HttpCustomerLookup.resolve for the same offload idiom."""
        return await asyncio.to_thread(
            self._send_carousel_sync, tenant=tenant, subject_ref=subject_ref,
            template_name=template_name, variables=variables, service_ids=service_ids,
            service_names=service_names, idempotency_key=idempotency_key,
            sending_identity=sending_identity)

    def _send_carousel_sync(self, *, tenant: str, subject_ref: str, template_name: str,
                            variables: list[str], service_ids: list[str],
                            service_names: dict[str, str], idempotency_key: str,
                            sending_identity: str = "") -> str:
        """The carousel shape (core/shape.py Phase 2) — one card per covered service. GET the
        photo from operations, POST it to notification-service for a media id, THEN POST the
        assembled cards to `/internal/notify/whatsapp/carousel` — THE SAME TWO-STEP
        whatsapp-assistant's own CarouselSender performs for its catalog carousel
        (adapters/whatsapp_sender/carousel.py). A service with no uploaded photo still gets a
        card: `_PLACEHOLDER_CARD_IMAGE` stands in, uploaded for a real media id exactly like a
        real photo is, so a shop that never uploaded a single photo still gets a working carousel.

        RAISES CarouselUnavailable — never sends a broken carousel — when fewer than two cards
        survive. With the placeholder in play that now means only: no `service_ids` at all, or
        the media upload itself failing for enough of them. Meta's own carousel minimum is two
        cards, and `tick.send_one` treats this exactly as "no carousel template was found" and
        falls back to the flat message.
        """
        if not (self._carousel_send and self._media_upload and self._catalogue_image):
            raise CarouselUnavailable("carousel paths are not configured")
        recipient, _name = self._recipient(tenant, subject_ref)
        if not recipient:
            raise Unsendable(f"no recipient for {subject_ref} — erased or unknown")

        cards: list[dict[str, Any]] = []
        for sid in service_ids:
            fetched = self._fetch_service_image(tenant, "service", sid)
            if fetched is not None:
                data, ctype = fetched
            else:
                data, ctype = _PLACEHOLDER_CARD_IMAGE, _PLACEHOLDER_CARD_CONTENT_TYPE
            media_id = self._upload_media_id(tenant=tenant, data=data, content_type=ctype)
            if not media_id:
                continue
            cards.append({
                "media_id": media_id, "media_type": "image",
                # THE SERVICE'S OWN NAME, THEN THE SHARED VARIABLES (the offer's own value, in
                # today's only caller) — same order the seed's card body declares them in
                # (operations/data/templates.seed.json), one card per service, one offer per send.
                "body_params": [service_names.get(sid, sid), *variables],
                # INERT TODAY. A quick-reply payload notification-service will happily deliver and
                # nothing on this path reads back — whatsapp-assistant's own conversation handler
                # parses ITS carousel's "carousel:{kind}:{id}" payload; a campaign carousel reply
                # has no handler yet. Kept self-describing rather than blank so a future one is a
                # parser to add, not a payload shape to invent.
                "buttons": [{"sub_type": "quick_reply", "payload": f"mkt_carousel:service:{sid}"}],
            })
            if len(cards) >= 10:
                break
        if len(cards) < 2:
            raise CarouselUnavailable("fewer than two card media uploads succeeded")

        payload = {
            "recipient": recipient, "tenant": tenant, "template_name": template_name,
            # THE CAROUSEL ROW'S OWN TOP-LEVEL BODY IS STATIC (no variables) — same shape as
            # `wa_catalog_carousel`'s own seed row — so nothing here needs the customer's resolved
            # `name` this call already looked up; `variables` is per-card only (see `body_params`
            # above), never a top-level component.
            "language": "ar", "variables": [], "cards": cards,
            "user_id": subject_ref, "event": "campaigns.marketing",
            "sending_identity": sending_identity or tenant,
            "idempotency_key": idempotency_key, "biz_opaque_callback_data": idempotency_key,
        }
        body = json.dumps(payload).encode()
        status, raw = internal_http.send(
            self._carousel_send, timeout=self._timeout, method="POST", body=body,
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


class CarouselUnavailable(Exception):
    """The carousel shape (core/shape.py Phase 2) could not be built THIS time — not configured, no
    covered services at all, or fewer than two card media uploads succeeded (a missing photo no
    longer costs a card; only a failed upload does). NOT a send failure: `tick.send_one` catches
    it and falls back to the flat template it already chose, exactly as it would if no carousel
    template had been found in the library at all."""


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
        interactive_notify_path=getattr(settings, "NOTIFICATION_INTERACTIVE_SEND_PATH", ""),
        carousel_send_path=getattr(settings, "NOTIFICATION_CAROUSEL_SEND_PATH", ""),
        media_upload_id_path=getattr(settings, "NOTIFICATION_MEDIA_UPLOAD_ID_PATH", ""),
        catalogue_image_path=getattr(settings, "OPERATIONS_CATALOGUE_IMAGE_PATH", ""))
