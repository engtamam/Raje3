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

# A MEDIA-HEADER TEMPLATE NEEDS A PHOTO OR IT ISN'T ONE — Meta requires an image or video header
# on `send_media`'s single-item template, and there is no text-only variant of that template
# shape. A covered service/package with no uploaded photo used to mean the send was refused
# outright. This is that gap closed: a plain neutral placeholder (400x300, solid light grey, no
# text, no logo — nothing that could be wrong for a shop) stands in for the missing photo so the
# message still goes out.
#
# CARRIES ITS OWN HISTORY: this placeholder used to stand in for a missing CARD photo too, in the
# multi-card carousel send this service no longer has (`send_carousel`, deleted 2026-09-13 — the
# carousel mechanism was retired in full). `_fetch_service_image`/`_upload_media_id` below are the
# same two functions that carousel path shared with this one; only the caller that needed two-or-
# more of them at once is gone.
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
                   sending_identity: str = "", url_button_param: str = "",
                   button_item_id: str = "", button_kind: str = "service",
                   branch_id: str = "") -> None:
        self.sent.append({"tenant": tenant,
                          # RECORDED BY THE FAKE TOO, so a test that targets a branch can assert
                          # which number it would have gone out from.
                          "sending_identity": sending_identity or tenant,
                          "subject_ref": subject_ref,
                          "template_name": template_name, "variables": variables,
                          "cls": cls, "idempotency_key": idempotency_key,
                          "url_button_param": url_button_param,
                          "button_item_id": button_item_id, "button_kind": button_kind,
                          "branch_id": branch_id})
        # THE FAKE RETURNS A HANDLE TOO, derived from the key so it is stable across a retry —
        # exactly as the peer's own delivery id is. A fake that returned "" would let the receipt
        # reconciler's tests pass against a shape the real sender never produces.
        return f"dlv_{idempotency_key}" if idempotency_key else ""

    async def send_media(self, *, tenant: str, subject_ref: str, template_name: str,
                         variables: list[str], cls: str, idempotency_key: str,
                         header_item_id: str, header_kind: str = "service",
                         sending_identity: str = "", button_item_id: str = "",
                         button_kind: str = "service", branch_id: str = "") -> str:
        self.sent.append({"tenant": tenant, "sending_identity": sending_identity or tenant,
                          "subject_ref": subject_ref, "type": "media",
                          "template_name": template_name, "variables": variables,
                          "cls": cls, "idempotency_key": idempotency_key,
                          "header_item_id": header_item_id, "header_kind": header_kind,
                          "button_item_id": button_item_id, "button_kind": button_kind,
                          "branch_id": branch_id})
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
                 interactive_notify_path: str = "",
                 media_upload_id_path: str = "",
                 catalogue_image_path: str = "",
                 whatsapp_assistant_url: str = "", carousel_shown_path: str = "") -> None:
        self._ceiling = frozenset(ceiling_codes)
        self._notify = notify_url.rstrip("/") + notify_path
        # OPTIONAL, and empty when omitted — a deployment that has not set
        # NOTIFICATION_INTERACTIVE_SEND_PATH yet simply cannot reach `send_flow` (it raises
        # SendFailed rather than posting to an empty URL), same as every other not-yet-wired knob
        # on this platform fails closed rather than guessing at a path.
        self._notify_interactive = (notify_url.rstrip("/") + interactive_notify_path
                                    if interactive_notify_path else "")
        # OPTIONAL, same posture: a deployment that has not set both yet cannot reach
        # `send_media` at all (it raises `SendFailed` for a media id that never came back rather
        # than guessing). Once configured, a covered service/package gets its own photo header —
        # or `_PLACEHOLDER_CARD_IMAGE` when operations has none uploaded for it.
        self._media_upload = notify_url.rstrip("/") + media_upload_id_path if media_upload_id_path else ""
        # `operations_url` — the SAME peer `_resolve` below already calls, just a different route.
        self._catalogue_image = (operations_url.rstrip("/") + catalogue_image_path
                                 if catalogue_image_path else "")
        self._resolve = operations_url.rstrip("/") + recipient_path
        self._token = token
        self._channel = channel
        self._timeout = timeout
        # THE BUTTON-TAP REGISTRATION DOOR (2026-09-13) — see `_register_carousel_shown`'s own
        # docstring for why the name still says "carousel" (whatsapp-assistant's tap handler and
        # payload prefix are the shared "carousel:{kind}:{id}" shape, not this deleted mechanism).
        # Optional exactly like `media_upload_id_path` above.
        self._carousel_shown = (whatsapp_assistant_url.rstrip("/") + carousel_shown_path
                                if whatsapp_assistant_url and carousel_shown_path else "")

    async def send(self, *, tenant: str, subject_ref: str, template_name: str,
                   variables: list[str], cls: str, idempotency_key: str,
                   sending_identity: str = "", url_button_param: str = "",
                   button_item_id: str = "", button_kind: str = "service",
                   branch_id: str = "") -> None:
        """`url_button_param` — the rating app's own URL-button-in-a-template send
        ([[task-service-procedure-checklists]] phase 2, base-services v0.24.4): when the approved
        template carries a dynamic URL button, this fills its one `{{1}}` suffix; empty otherwise,
        and notification-service ignores it for an ordinary template. THIS REPLACES the old
        `flow_token`/`flow_action_data` pair (the rating screen's own Flow-button send, removed the
        same day the screen moved off native Flow entirely to a hosted web page) — that pair had
        exactly one caller in this whole service and it is this same rating send, so there is no
        second caller left to keep them for.

        `button_item_id`/`button_kind` — THE UNIFIED REAL-BOOKING BUTTON (2026-09-13), a
        `"carousel:{kind}:{id}"` quick-reply payload — the prefix predates this send path, from
        the multi-card carousel send this service used to also offer (deleted 2026-09-13); the
        prefix and its handler on whatsapp-assistant's side outlived that deletion because this
        button mechanism was built to share both. Empty for every send that carries no such
        button — a plain reminder/confirmation must not grow a `button_payload` key with no
        meaning, forever. When set, this call also registers the id with whatsapp-assistant's own
        conversation engine (`_register_carousel_shown`) so a tap on it is honoured."""
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
        # THE RATING APP'S OWN URL-BUTTON PARAMETER — only when this call actually carries one.
        # An ordinary template send (every message today except rating_request) must not grow a
        # `url_button_param` key at all: notification-service ignores it harmlessly either way,
        # but sending "" for every plain confirmation is a wire field with no meaning, forever.
        if url_button_param:
            payload["url_button_param"] = url_button_param
        # THE UNIFIED BOOKING BUTTON. Declared only when used, same discipline as flow_token above.
        if button_item_id:
            payload["button_payload"] = f"carousel:{button_kind}:{button_item_id}"
        body = json.dumps(payload).encode()
        # Built in adapters/internal_http.py, the one place this service attaches the token.
        # OFF THE EVENT LOOP — fixed 2026-09-12, a real gap a QA audit found: the recipient lookup
        # just above was already offloaded, but this call (the actual send — the single most
        # frequent I/O this engine performs) still ran `urllib.request.urlopen` directly on the
        # loop, freezing the whole pod for up to `PEER_TIMEOUT_SECONDS` on every message, exactly
        # the pattern `quota.py` already wraps correctly elsewhere in this codebase.
        status, raw = await asyncio.to_thread(
            internal_http.send,
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

        # THE BUTTON'S OWN "SHOWN TO THIS CUSTOMER" STAMP (`_register_carousel_shown`) — a plain
        # send's button is honoured by whatsapp-assistant's tap handler only once this is on
        # record. Only after a real delivery, never for a send that raised above.
        if button_item_id:
            # OFF THE EVENT LOOP — `_register_carousel_shown` is plain blocking urllib, same as
            # every other peer call in this class; `send()` itself is async and must not block on it.
            await asyncio.to_thread(self._register_carousel_shown, tenant=tenant,
                                    subject_ref=subject_ref, item_ids=[button_item_id],
                                    branch_id=branch_id)

        # AND THE PEER'S HANDLE COMES BACK, so the send log can be matched to a receipt later.
        #
        # Empty is a real answer: the console driver has no delivery row and a peer we did not
        # reach raised long before this line. An empty handle means «this send will never be
        # matched», which the reconciler must be able to tell apart from «not delivered yet».
        return str(result.get("delivery_id") or "")

    async def send_media(self, *, tenant: str, subject_ref: str, template_name: str,
                         variables: list[str], cls: str, idempotency_key: str,
                         header_item_id: str, header_kind: str = "service",
                         sending_identity: str = "", button_item_id: str = "",
                         button_kind: str = "service", branch_id: str = "") -> str:
        """A SINGLE item, shown with its own real photo as the template's header. Thin async
        wrapper: every call inside is stdlib urllib, so the whole fetch-photo → upload → send
        sequence runs as ONE unit off the event loop.
        """
        return await asyncio.to_thread(
            self._send_media_sync, tenant=tenant, subject_ref=subject_ref,
            template_name=template_name, variables=variables, cls=cls,
            idempotency_key=idempotency_key, header_item_id=header_item_id,
            header_kind=header_kind, sending_identity=sending_identity,
            button_item_id=button_item_id, button_kind=button_kind, branch_id=branch_id)

    def _send_media_sync(self, *, tenant: str, subject_ref: str, template_name: str,
                         variables: list[str], cls: str, idempotency_key: str,
                         header_item_id: str, header_kind: str, sending_identity: str,
                         button_item_id: str, button_kind: str, branch_id: str) -> str:
        """GET the photo from operations, POST it to notification-service for a media id, THEN POST
        the template send with `header_media_id` set. No photo uploaded for this item is not a
        reason to refuse the send: `_PLACEHOLDER_CARD_IMAGE` stands in.
        """
        recipient, name = self._recipient(tenant, subject_ref)
        if not recipient:
            raise Unsendable(f"no recipient for {subject_ref} — erased or unknown")

        fetched = self._fetch_service_image(tenant, header_kind, header_item_id)
        if fetched is not None:
            data, ctype = fetched
        else:
            data, ctype = _PLACEHOLDER_CARD_IMAGE, _PLACEHOLDER_CARD_CONTENT_TYPE
        media_id = self._upload_media_id(tenant=tenant, data=data, content_type=ctype)
        if not media_id:
            raise SendFailed(f"media upload failed for {header_kind}:{header_item_id}")

        variables = list(variables)
        if name and variables and variables[0] in ("", FALLBACK_NAME):
            variables[0] = name

        payload: dict[str, Any] = {
            "recipient": recipient, "channel": self._channel, "template_key": template_name,
            "tenant": tenant, "sending_identity": sending_identity or tenant,
            "variables": {str(i + 1): v for i, v in enumerate(variables)},
            "idempotency_key": idempotency_key, "event": f"reminders.{cls}",
            "biz_opaque_callback_data": idempotency_key,
            # THE SINGLE ITEM'S OWN PHOTO — see notification-service's own NotifyIn.header_media_id
            # (base-services-72, 2026-09-13). Always set here: this method exists precisely because
            # the send has a header, unlike `send()`'s own plain path.
            "header_media_id": media_id,
        }
        if button_item_id:
            payload["button_payload"] = f"carousel:{button_kind}:{button_item_id}"
        body = json.dumps(payload).encode()
        status, raw = internal_http.send(
            self._notify, timeout=self._timeout, method="POST", body=body,
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

        if button_item_id:
            self._register_carousel_shown(tenant=tenant, subject_ref=subject_ref,
                                          item_ids=[button_item_id], branch_id=branch_id)
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
        # OFF THE EVENT LOOP — same fix, same reasoning as send()'s own call above.
        status, raw = await asyncio.to_thread(
            internal_http.send,
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
        peer hiccup and a 404 all look the same from here: "no real photo for this item", which
        `send_media` answers with the placeholder rather than refusing the send."""
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

    def _register_carousel_shown(self, *, tenant: str, subject_ref: str, item_ids: list[str],
                                 branch_id: str) -> None:
        """Tells whatsapp-assistant's own conversation engine which items this send actually put
        in front of the customer (`POST /internal/carousel-shown`) — the one thing whatsapp-
        assistant's tap handler checks a `carousel:{kind}:{id}` payload against before honouring
        it, for a button sent by an engine that never ran through its own conversation flow.

        THE NAME OUTLIVED THE FEATURE IT WAS NAMED FOR: this registered a card the deleted
        multi-card carousel send had just shown (2026-09-13, `send_carousel`); it now registers
        the single item `send()`'s and `send_media()`'s own quick-reply button names, which
        already shared this exact route and payload shape before that deletion — nothing here
        changed, only the caller that no longer exists.

        BEST-EFFORT, ALWAYS. Not configured (`_carousel_shown` empty — the ordinary case for any
        deployment that has not wired `WHATSAPP_ASSISTANT_SERVICE_URL` yet) or a network failure
        both mean the button, once tapped, answers "لم يعد صالحًا" instead of a real proposal —
        worse than the button not existing, but never worse than today, and never a reason to
        fail a send that has already gone out.
        """
        if not self._carousel_shown:
            return
        body = {"tenant": tenant, "subject_ref": subject_ref, "item_ids": item_ids,
               "branch_id": branch_id}
        try:
            internal_http.post_json(self._carousel_shown, body, self._token, self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            pass

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
        interactive_notify_path=getattr(settings, "NOTIFICATION_INTERACTIVE_SEND_PATH", ""),
        media_upload_id_path=getattr(settings, "NOTIFICATION_MEDIA_UPLOAD_ID_PATH", ""),
        catalogue_image_path=getattr(settings, "OPERATIONS_CATALOGUE_IMAGE_PATH", ""),
        whatsapp_assistant_url=getattr(settings, "WHATSAPP_ASSISTANT_SERVICE_URL", ""),
        carousel_shown_path=getattr(settings, "WHATSAPP_ASSISTANT_CAROUSEL_SHOWN_PATH", ""))
