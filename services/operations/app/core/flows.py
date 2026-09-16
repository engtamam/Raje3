"""Giving a shop its own copy of a clone-per-shop Flow — the same shape as `core/library.py`'s
publish.

WHY A FLOW AT ALL. A Flow-button template can be registered without ever having a live Flow behind
its button, and Meta then refuses to send it — so the Flow must exist on THIS SHOP'S OWN WABA
before its templates are registered, exactly as the template library must exist before it can be
drained.

ONE MASTER, CLONED PER SHOP. A Flow is WABA-scoped and every shop connects its own WABA, so a
platform-wide Flow cannot be referenced by every shop — each needs its own copy. Authoring the
same screen sixty-six times is not the answer: the master is authored ONCE (see each Flow's own
`deploy/seed/bootstrap-*-flow.sh`, which mints it under the platform's own WABA and stores the
resulting id), and every shop's copy is a Meta-side CLONE of that master, requested here with
`clone_flow_id`. Clones share the FLOW NAME — never the id — because a template's `flow_button`
references a Flow by name, and that name must resolve on every shop's own WABA to ITS OWN clone.

IDEMPOTENT BY NAME, on notification-service's side (`ensure_flow`) — a re-run (a shop reconnecting,
a retried background task) finds the shop's existing clone by name rather than making a second one.

RATING AND REPORT FLOWS BOTH REMOVED (2026-09-16) — the rating screen moved from a native Flow to
a hosted web page ([[task-service-procedure-checklists]] phase 2); the report Flow's own template
was deleted 2026-09-13 (owner's decision to drop the weekly-digest feature) but its clone-at-
connect call in `connect.py` was accidentally left behind — found and removed alongside this
cleanup rather than repeating that same incomplete-deletion mistake a second time. `provision()`/
`provision_shop_flow()` below stayed generic (built for the report Flow) and both booking_flow/
visit_flow already pass their own explicit `flow_name`/`categories`, so removing the two constants
these functions used to default to needed no signature change — every remaining caller was already
explicit.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

#: THE RESERVED TENANT PLATFORM-OWNED FLOWS/TEMPLATES ARE FILED UNDER — same spelling as
#: core/commission.py, core/partners.py, core/templates.py's own `PLATFORM` constant (each its
#: own local copy, not shared, matching this codebase's own convention); the same account
#: `AdminWhatsAppTemplates.tsx` registers `auth_otp` on. A Flow authored here is authored ONCE,
#: never cloned per shop.
PLATFORM = "_platform"

#: PHASE 5 — the WhatsApp booking Flow (structured screens), a THIRD Flow through the same
#: clone-at-connect pattern. Unlike rating/report (static, read-only screens authored once as a
#: fixed JSON file), the booking Flow is DYNAMIC (data_exchange, driven live by
#: services/whatsapp-assistant's FlowBookingBackend) — but it is still ONE definition shared by
#: every tenant on this deployment (WHATSAPP_BOOKING_DEFINITION, notification-service's own
#: config), so the SAME clone-per-shop provisioning shape applies unchanged: author the JSON once
#: (deploy/seed/bootstrap-booking-flow.sh, from notification-service's own generator endpoint,
#: not a static file), mint the master under the platform's own WABA, clone it per shop here.
BOOKING_FLOW_NAME = "booking_flow"
#: The one category Meta's fixed set has for exactly this purpose.
BOOKING_FLOW_CATEGORIES = ["APPOINTMENT_BOOKING"]

#: THE FIFTH FLOW, CLONE-PER-SHOP LIKE `booking_flow` above — visit-registration over WhatsApp, a
#: second channel alongside the console's own شاشة تسجيل الزيارة (this session's own approved
#: plan). Staff talking to THEIR OWN shop's number about THAT shop's own customers is exactly the
#: same shape as `booking_flow`'s own reasoning — never `_platform`, unlike subscription_renewal.
#: Also DYNAMIC and GENERATED (notification-service's own WHATSAPP_VISIT_DEFINITION, third
#: BookingEngine registration under name="visit") — same "ask the running service for the JSON,
#: never hand-author a file for a dynamic Flow" shape `deploy/seed/bootstrap-visit-flow.sh` copies
#: from `bootstrap-booking-flow.sh` verbatim.
VISIT_FLOW_NAME = "visit_flow"
#: Nothing in Meta's fixed set names "an employee logs an in-person visit" — OTHER is the honest
#: answer, same as report_flow's own category for the identical reason.
VISIT_FLOW_CATEGORIES = ["OTHER"]

#: A FOURTH FLOW — but NOT clone-per-shop like the three above (owner's decision, 2026-09-10). It
#: is PLATFORM-owned: sent from OUR OWN WhatsApp number to a shop owner about THEIR bill, the same
#: category as the `auth_otp` template (see `PLATFORM` above) — authored ONCE, on `PLATFORM`, via
#: `HttpFlows.author_master` below, an explicit admin action
#: (`api/v1/platform.py::seed_subscription_renewal_flow`), never at a shop's own connect time.
#: DYNAMIC (data_exchange, driven live by `renewal_provider.py` through platform v0.19.12's
#: LoyaltyEngine(name="subscription_renewal")), so it still needs a live `endpoint_uri` — fixed to
#: `.../webhooks/whatsapp/flow/_platform/subscription_renewal`, set once at authoring time, never
#: per shop. WHICH shop a given Flow session is about travels inside the Flow's own seed data
#: (`renewal_provider.py`'s `customer` field carries `"{tenant}:{invoice_id}"`), not the URL.
SUBSCRIPTION_RENEWAL_FLOW_NAME = "subscription_renewal"
#: Meta's fixed category set has none named for billing; SIGN_UP/SIGN_IN et al. all mean something
#: else. LEAD_GENERATION and OTHER are the two honest fits documented for "neither of the above" —
#: this is a payment collection, not a lead, so OTHER.
SUBSCRIPTION_RENEWAL_FLOW_CATEGORIES = ["OTHER"]
#: THE SCREENS THEMSELVES — SELECT ("جدّد الآن", the one option is the whole due invoice, priced)
#: -> CONFIRM ("تأكيد") -> the endpoint's `redeem` creates the real pay-link and terminates via
#: extension_message_response (reward_ref = pay_url); SUCCESS is the schema-mandated terminal
#: screen, shown only as a fallback (loyalty_flow.py's own SUCCESS reply almost never lets it
#: render). Embedded here, not a deploy/seed/*.json file: authoring now happens from a running
#: admin action (api/v1/platform.py), which cannot read a deploy-time-only asset — see
#: `author_master`'s own docstring below. Key names (`selection`, the screen ids, `reward_ref`/
#: `flow_token`) are loyalty_flow.py's own contract; renaming any of them here without renaming
#: them there breaks the redeem step silently. Schema verified against developers.facebook.com/
#: docs/whatsapp/flows/reference/{flowjson,components} (2026-09-08), same pass that verified
#: booking's own generator — version 7.3 / data_api_version 3.0, the same pinned pair.
SUBSCRIPTION_RENEWAL_FLOW_JSON: dict[str, Any] = {
    "version": "7.3",
    "data_api_version": "3.0",
    "routing_model": {"SELECT": ["CONFIRM"], "CONFIRM": ["SUCCESS"]},
    "screens": [
        {
            "id": "SELECT", "title": "تجديد الاشتراك",
            "data": {
                "title": {"type": "string", "__example__": "تجديد الاشتراك — 150.00 SAR"},
                "options": {"type": "array",
                           "__example__": [{"id": "t1:inv_1",
                                            "title": "تجديد الاشتراك — 150.00 SAR",
                                            "description": "تطبيق الحجوزات، تطبيق التذكيرات"}]},
                "error_message": {"type": "string", "__example__": "", "optional": True},
            },
            "layout": {"type": "SingleColumnLayout", "children": [
                {"type": "TextHeading", "text": "${data.title}"},
                {"type": "RadioButtonsGroup", "name": "selection", "label": "${data.title}",
                 "required": True, "data-source": "${data.options}"},
                {"type": "Footer", "label": "متابعة", "on-click-action": {
                    "name": "data_exchange", "payload": {"selection": "${form.selection}"}}},
            ]},
        },
        {
            "id": "CONFIRM", "title": "تأكيد التجديد",
            "data": {"title": {"type": "string", "__example__": "تأكيد التجديد"},
                    "error_message": {"type": "string", "__example__": "", "optional": True}},
            "layout": {"type": "SingleColumnLayout", "children": [
                {"type": "TextHeading", "text": "${data.title}"},
                {"type": "TextBody", "text": "بالتأكيد، بيصلك رابط الدفع مباشرة."},
                {"type": "Footer", "label": "تأكيد", "on-click-action": {
                    "name": "data_exchange", "payload": {"action": "confirm"}}},
            ]},
        },
        {
            "id": "SUCCESS", "title": "تم", "terminal": True, "success": True, "data": {},
            "layout": {"type": "SingleColumnLayout", "children": [
                {"type": "TextHeading", "text": "جاري تجهيز رابط الدفع — بيصلك برسالة الآن."},
                {"type": "Footer", "label": "تم",
                "on-click-action": {"name": "complete", "payload": {}}},
            ]},
        },
    ],
}


class NullFlows:
    """No notification-service peer configured. Says so, provisions nothing.

    Mirrors `NullLibrary` on purpose — a deployment with no notification-service has no WABA to put
    a Flow on, and reporting a plausible "provisioned" here would hide a missing configuration
    behind a number that never happened.
    """

    driver = "null"

    def __init__(self) -> None:
        self.provisioned: list[str] = []

    async def provision(self, tenant: str, *, clone_flow_id: str,
                       flow_name: str,
                       categories: list[str] | None = None,
                       endpoint_uri: str = "") -> dict[str, Any]:
        self.provisioned.append(tenant)
        return {"ok": False, "reason": "flow provisioning is not configured"}

    async def ensure_encryption(self, tenant: str, *, phone_number_id: str = "") -> dict[str, Any]:
        self.provisioned.append(tenant)
        return {"ok": False, "reason": "flow encryption provisioning is not configured"}

    async def author_master(self, *, name: str, categories: list[str], flow_json: dict[str, Any],
                            endpoint_uri: str = "") -> dict[str, Any]:
        self.provisioned.append(name)
        return {"ok": False, "reason": "flow provisioning is not configured"}


class HttpFlows:
    """notification-service's internal Flow-provisioning twin."""

    driver = "http"

    def __init__(self, *, notify_url: str, provision_path: str, token: str,
                 timeout: int = 8, encryption_ensure_path: str = "") -> None:
        base = notify_url.rstrip("/")
        self._provision = base + provision_path
        # OPTIONAL — a deployment that has not declared the path yet (an old values file, before
        # the Phase 5 wiring) simply cannot call ensure_encryption; `build_flows` below always
        # sets a real default, so this is only ever empty in a hand-built instance.
        self._encryption_ensure = base + encryption_ensure_path if encryption_ensure_path else ""
        self._token = token
        self._timeout = timeout

    def _post(self, body: dict[str, Any]) -> tuple[int, Any]:
        return self._post_to(self._provision, body)

    def _post_to(self, url: str, body: dict[str, Any]) -> tuple[int, Any]:
        if not url:
            return 503, {"detail": "no path configured for this call"}
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"X-Internal-Token": self._token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, {"detail": exc.read().decode()[:200]}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return 503, {"detail": str(exc)[:120]}

    async def provision(self, tenant: str, *, clone_flow_id: str,
                       flow_name: str,
                       categories: list[str],
                       endpoint_uri: str = "") -> dict[str, Any]:
        """Ensure THIS shop's WABA has a published clone of a master Flow, named `flow_name`.

        GENERIC, BUILT FOR MULTIPLE FLOWS SHARING THIS ONE CALL — `flow_name`/`categories` have no
        default any more (2026-09-16): they used to default to the rating Flow's own name/
        category, which silently made every OTHER caller's explicit values look optional when they
        never were. Both remaining callers (booking_flow, visit_flow) already pass their own.

        `endpoint_uri` (Phase 5) — OMITTED (never sent) unless a caller passes one. A static,
        read-only Flow never calls back to us at all, so it never needs this; the booking Flow
        (dynamic, data_exchange) DOES — Meta calls THIS URL to reach the shop's own clone, and it
        must resolve to that shop's own tenant on our side (see PUBLIC_BASE_URL's own docstring in
        config.py).

        NO MASTER, NO CALL. `clone_flow_id` is resolved by the caller (connect.py) from the stored
        setting the bootstrap script writes once — see its module docstring. Calling Meta with an
        empty clone id would either be refused there or, worse, misread as "author from scratch",
        which is not what an empty configuration means.
        """
        if not clone_flow_id:
            return {"ok": False, "reason": f"no master {flow_name.replace('_', ' ')} configured"}
        body: dict[str, Any] = {
            "tenant": tenant, "name": flow_name,
            "categories": categories,
            "clone_flow_id": clone_flow_id, "publish": True,
        }
        if endpoint_uri:
            body["endpoint_uri"] = endpoint_uri
        # OFF THE EVENT LOOP — see services/whatsapp-assistant/app/core/customer_lookup.py's own
        # comment on why: `_post` is a plain (non-async) method that calls urlopen synchronously.
        status, out = await asyncio.to_thread(self._post, body)
        if status >= 400:
            return {"ok": False, "reason": str(out.get("detail", ""))[:160]}
        return {"ok": True, **(out if isinstance(out, dict) else {})}

    async def ensure_encryption(self, tenant: str, *, phone_number_id: str = "") -> dict[str, Any]:
        """The booking Flow's OTHER connect-time step (Phase 5, base-services v0.18.55): ensure
        this shop has a sealed Flow-encryption key and a matching public key registered with Meta
        for its number — the twin of `provision` above, called alongside it, never instead of it.
        Idempotent on notification-service's own side (never regenerates an existing key, only
        re-registers the public half) — safe to call on every connect, not just the first."""
        body: dict[str, Any] = {"tenant": tenant}
        if phone_number_id:
            body["phone_number_id"] = phone_number_id
        status, out = await asyncio.to_thread(self._post_to, self._encryption_ensure, body)
        if status >= 400:
            return {"ok": False, "reason": str(out.get("detail", ""))[:160]}
        return {"ok": True, **(out if isinstance(out, dict) else {})}

    async def author_master(self, *, name: str, categories: list[str], flow_json: dict[str, Any],
                            endpoint_uri: str = "") -> dict[str, Any]:
        """Author a Flow DIRECTLY on `PLATFORM` (`tenant="_platform"`) from its own screens JSON —
        no `clone_flow_id`. This is the SAME "author from scratch" call each of the three
        clone-per-shop Flows' own bootstrap scripts used exactly once to mint their master, before
        every shop's own connect-time clone; the subscription-renewal Flow simply stops here and
        is never cloned — see this module's own docstring on `SUBSCRIPTION_RENEWAL_FLOW_JSON`."""
        body: dict[str, Any] = {
            "tenant": PLATFORM, "name": name, "categories": categories,
            "flow_json": json.dumps(flow_json), "publish": True,
        }
        if endpoint_uri:
            body["endpoint_uri"] = endpoint_uri
        status, out = await asyncio.to_thread(self._post, body)
        if status >= 400:
            return {"ok": False, "reason": str(out.get("detail", ""))[:160]}
        return {"ok": True, **(out if isinstance(out, dict) else {})}


def build_flows(settings: Any) -> Any:
    url = getattr(settings, "NOTIFICATION_SERVICE_URL", "") or ""
    path = getattr(settings, "WHATSAPP_FLOW_PROVISION_PATH", "") or ""
    if not url or not path:
        return NullFlows()
    return HttpFlows(
        notify_url=url, provision_path=path,
        token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8),
        encryption_ensure_path=getattr(settings, "WHATSAPP_FLOW_ENCRYPTION_ENSURE_PATH", "") or "")


async def provision_shop_flow(flows: Any, tenant: str, master_flow_id: str, *,
                              flow_name: str,
                              categories: list[str],
                              endpoint_uri: str = "") -> dict[str, Any]:
    """The one call connect.py's background task makes — mirrors `library.publish`'s free-function
    shape so the several background tasks read the same way at each call site. `flow_name`/
    `categories` are always the caller's own (no default, see `HttpFlows.provision`'s own note on
    why the rating Flow's former default was removed); `endpoint_uri` — see that same docstring —
    only a DYNAMIC Flow's call site (booking, visit) sets one."""
    return await flows.provision(tenant, clone_flow_id=master_flow_id, flow_name=flow_name,
                                 categories=categories, endpoint_uri=endpoint_uri)


async def provision_shop_flow_encryption(flows: Any, tenant: str, *,
                                         phone_number_id: str = "") -> dict[str, Any]:
    """The booking Flow's OTHER connect-time call — see `HttpFlows.ensure_encryption`'s own
    docstring. Same free-function shape as `provision_shop_flow` beside it, for the same reason
    (connect.py's background tasks read identically either way)."""
    return await flows.ensure_encryption(tenant, phone_number_id=phone_number_id)
