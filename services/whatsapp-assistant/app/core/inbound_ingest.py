"""One inbound message, dedup'd and dispatched — shared by BOTH ways this service learns of one.

TWO CALLERS, ONE PATH. app/main.py's `whatsapp.message` bus subscription (low-latency, at-most-
once, can silently miss a message) and app/api/internal.py's tick-driven catch-up sweep against
GET /internal/whatsapp/inbound (durable, replayable, higher latency) both end up here. Whichever
one sees a wamid FIRST processes it; the other sees `record_if_new` return False and stops — see
app/adapters/inbound_store/datastore_backed.py. This is what makes "delivered via both" safe: the
dedup keyed on Meta's wamid lives in ONE store, checked by ONE function, no matter which caller
reached it first.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.core.sending_identity import split as split_sending_identity
from app.ports.consent_gate import DENIED, UNKNOWN


@dataclass(frozen=True)
class GateContext:
    """Everything a pre-AI gate needs to decide "does this message even reach the conversation
    engine, or do I answer it myself and stop here" — deliberately the SAME small bundle every
    gate receives, so a new gate never needs a new parameter threaded through the caller."""
    container: Any
    logger: Any
    settings: Any
    auditor: Any
    tenant: str
    branch_id: str
    wamid: str
    from_number: str
    kind: str
    text: str
    reply_id: str


# `None` = pass through to the next gate; a dict = the FINAL return value of
# `ingest_inbound_message` itself — the gate has already sent (or deliberately withheld) whatever
# reply this message gets, and nothing downstream (customer_lookup, the conversation engine, the
# actual send dispatch) ever runs for it.
GateOutcome = dict[str, Any] | None
Gate = Callable[[GateContext], Awaitable[GateOutcome]]


# Fixed house copy — the explicit, first-contact service-processing consent ask (never bundled
# with, and never a stand-in for, marketing consent, which stays its own separate purpose with its
# own opt-in and an always-available unsubscribe — see this gate's own module docstring below).
_CONSENT_BODY = (
    "بالمتابعة، فإنك توافق على أن نقوم بمعالجة المعلومات اللازمة لإكمال خدمتك عبر واتساب — "
    "استلام رسائلك، والرد عليها، وتنفيذ ما تطلبه من خدماتنا. هذا لا يشمل أي رسائل تسويقية، والتي "
    "تتطلب موافقتك المنفصلة ويجب أن تتضمن دائمًا خيارًا لإلغاء الاشتراك.")
_CONSENT_CONTINUE_ID = "consent:agree"
_CONSENT_END_ID = "consent:end"


async def _gate_consent(ctx: GateContext) -> GateOutcome:
    """THE CONSENT GATE — first, explicit, service-only (never marketing) consent before this
    tenant's replies are ever sent to a given customer, and re-askable, never a permanent ban.

    TWO HALVES:

    1) A `consent:*` button reply is this customer's OWN live answer to the request THIS gate
       itself sent below — recorded via `consent_gate.record()` (2026-09-19, the subject's own
       live decision, distinct from compliance-service's admin-only `/consent/grant`). "متابعة"
       falls through to the ordinary path THIS SAME TURN (no need to make the customer repeat
       themselves); "إنهاء المحادثة" stops here, exactly like an on-record refusal always has.

    2) Otherwise: THE CONSENT CHECK, WITH THE RAW NUMBER, BEFORE IT IS EVER FOLDED INTO A
       PSEUDONYM. The port (app/ports/consent_gate.py) is explicit that a service holding only a
       subject_ref cannot use it without defeating the pseudonymisation — so this is the one
       honest place left to ask: the raw `from_number` is already in hand for this one call (same
       transient use customer_lookup makes a few lines down in `ingest_inbound_message`), never
       persisted, and gone the moment this function returns.

       compliance-service's own default-deny means "never asked before" and "an on-record refusal"
       are BOTH reported as DENIED (reason `no_consent_record` vs a real withdrawal reason) — this
       gate deliberately treats them identically: NEITHER is final. Every DENIED gets asked again,
       explicitly, right here, on the very next message; only a live "متابعة" tap ever lets this
       tenant past this gate. UNKNOWN keeps its OWN, separate, pre-existing meaning (compliance-
       service is genuinely unreachable) and its own CONSENT_POLICY_ON_UNKNOWN posture, untouched.
    """
    purpose = (ctx.settings.CONSENT_PURPOSE_ORDERING if ctx.kind == "order"
              else ctx.settings.CONSENT_PURPOSE)

    if ctx.reply_id in (_CONSENT_CONTINUE_ID, _CONSENT_END_ID):
        granted = ctx.reply_id == _CONSENT_CONTINUE_ID
        try:
            await ctx.container.consent_gate.record(
                tenant=ctx.tenant, subject=ctx.from_number, purpose=purpose,
                granted=granted)
        except Exception as exc:                                      # noqa: BLE001
            ctx.logger.warning("whatsapp_consent_record_failed", extra={
                "tenant": ctx.tenant, "wamid": ctx.wamid, "error": str(exc)[:200]})
        if granted:
            return None
        await ctx.container.inbound_store.mark_processed(ctx.tenant, ctx.wamid)
        try:
            await ctx.auditor.record(
                "whatsapp_assistant.consent_refused", actor="whatsapp-assistant",
                resource=f"wamid:{ctx.wamid}", tenant=ctx.tenant,
                metadata={"status": "denied", "reason": "customer_declined",
                         "purpose": purpose})
        except Exception:                                            # noqa: BLE001
            pass
        return {"processed": False, "reason": "consent_denied"}

    verdict = await ctx.container.consent_gate.check(
        tenant=ctx.tenant, subject=ctx.from_number, purpose=purpose)

    if verdict.status == UNKNOWN:
        if ctx.settings.CONSENT_POLICY_ON_UNKNOWN == "fail_open":
            return None
        await ctx.container.inbound_store.mark_processed(ctx.tenant, ctx.wamid)
        ctx.logger.info("whatsapp_consent_refused", extra={
            "tenant": ctx.tenant, "wamid": ctx.wamid, "status": verdict.status,
            "reason": verdict.reason})
        try:
            await ctx.auditor.record(
                "whatsapp_assistant.consent_refused", actor="whatsapp-assistant",
                resource=f"wamid:{ctx.wamid}", tenant=ctx.tenant,
                metadata={"status": verdict.status, "reason": verdict.reason,
                         "purpose": purpose})
        except Exception:                                            # noqa: BLE001
            pass
        return {"processed": False, "reason": f"consent_{verdict.status}"}

    if verdict.status == DENIED:
        await ctx.container.sender.send_interactive(
            tenant=ctx.tenant, to=ctx.from_number, body=_CONSENT_BODY,
            buttons=[{"id": _CONSENT_CONTINUE_ID, "title": "متابعة"},
                    {"id": _CONSENT_END_ID, "title": "إنهاء المحادثة"}],
            idempotency_key=f"{ctx.wamid}:consent_request")
        await ctx.container.inbound_store.mark_processed(ctx.tenant, ctx.wamid)
        try:
            await ctx.auditor.record(
                "whatsapp_assistant.consent_requested", actor="whatsapp-assistant",
                resource=f"wamid:{ctx.wamid}", tenant=ctx.tenant,
                metadata={"reason": verdict.reason, "purpose": purpose})
        except Exception:                                            # noqa: BLE001
            pass
        return {"processed": True, "reason": "consent_requested"}

    return None


# ── THE ONE REGISTRATION POINT — same plug-and-play contract as core/tools.py's `_TOOL_HANDLERS`
# and core/conversation.py's `_PROMPT_SECTIONS`. CHEAPEST/MOST-FUNDAMENTAL FIRST: a gate never
# needs to know what ran before it, only that if it returns `None`, whatever runs next gets exactly
# the same untouched `GateContext`. Adding a gate means writing one function with this same
# signature and adding it to this tuple, in the position its own cost/precedence calls for —
# nothing in `ingest_inbound_message` changes.
_GATES: tuple[Gate, ...] = (_gate_consent,)


async def outbound_allowed(container: Any, settings: Any, tenant: str, *,
                           subject_ref: str = "", branch_id: str = "") -> bool:
    """TWO limiters, see config.py's own note on `CONVERSATION_OUTBOUND_MAX_PER_10MIN` /
    `OUTBOUND_MAX_PER_NUMBER_PER_HOUR` for why they are separate. Shared by both send paths — this
    fast-path ingest and app/api/internal.py's tick — so the budget is the same no matter which one
    is sending.

    `subject_ref` is REQUIRED to get the tight per-conversation check at all — a caller with no
    conversation in hand (there is none today; kept optional rather than forcing every caller to
    thread a value it cannot have) only gets the coarser per-number backstop, same as before this
    split existed."""
    if subject_ref:
        conv_verdict = await container.rate_limiter.check(
            f"wa_outbound_conv:{tenant}:{subject_ref}",
            limit=settings.CONVERSATION_OUTBOUND_MAX_PER_10MIN, window_s=600)
        if not conv_verdict.allowed:
            return False

    verdict = await container.rate_limiter.check(
        f"wa_outbound_number:{tenant}:{branch_id}",
        limit=settings.OUTBOUND_MAX_PER_NUMBER_PER_HOUR, window_s=3600)
    return verdict.allowed


async def resolve_subject_ref(container: Any, settings: Any, tenant: str, from_number: str) -> str:
    """The SAME pseudonym-or-derive resolution every caller that only has a raw phone number
    needs — extracted 2026-09-19 so app/api/v1/connectors.py (a Meta Connector call, never a raw
    inbound message) can resolve the identical subject_ref an ordinary conversation turn would,
    without duplicating the derivation rule.

    UNKNOWN CUSTOMER is a normal case, not an error. Rather than invent a pseudonym (which would
    collide with a real one the day this number does become a customer), an unrecognised sender
    is keyed on a per-number-per-tenant hash derived the same way core/pii.py derives subject_ref
    — so it still holds a session, and a Connector call for it still resolves consistently."""
    lookup = await container.customer_lookup.resolve(tenant, from_number)
    subject_ref = str(lookup.get("subject_ref") or "")
    if subject_ref:
        return subject_ref
    from app.core.pii import subject_ref as derive_ref
    return derive_ref(settings.PII_SALT, tenant, from_number)


async def ingest_inbound_message(
    *, container: Any, logger: Any, settings: Any, auditor: Any,
    tenant: str, wamid: str, from_number: str, kind: str, text: str, reply_id: str,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    if not tenant or not wamid or not from_number:
        return {"processed": False, "reason": "missing_fields"}

    # SPLIT ONCE, HERE, BEFORE ANYTHING ELSE READS `tenant`. Both callers (app/main.py's bus
    # subscription, app/api/internal.py's catch-up poll) hand this function whatever
    # notification-service's WhatsAppNumberIndex bound the inbound phone_number_id to — for a
    # per_branch shop that is the COMPOSITE `tenant:branch_id` string operations-service's own
    # core/sending_identity.py mints, not a real tenant id. Reassigning `tenant` in place (rather
    # than threading a second `real_tenant` variable through every line below) means every
    # existing call — consent_gate, customer_lookup, the inbound_store dedup/retention keys, the
    # engine, the sender — is correct by construction with no other line touched: they were always
    # supposed to receive the real tenant, and for a central shop (branch_id == "") this is a
    # complete no-op, byte for byte.
    tenant, branch_id = split_sending_identity(tenant)
    if not tenant:
        return {"processed": False, "reason": "missing_fields"}

    is_new = await container.inbound_store.record_if_new(tenant, wamid, raw_payload)
    if not is_new:
        # ALREADY SEEN — a redelivery of the same wamid (bus firing twice, the catch-up sweep
        # revisiting a wamid the bus already delivered, or vice versa). This IS the dedup.
        return {"processed": False, "reason": "duplicate"}

    # THE LICENCE CHECK — cheaper and more fundamental than any `_GATES` entry, so it runs BEFORE
    # the gate pipeline itself, not as a gate inside it. Without this, `_gate_consent` sent a real
    # outbound consent request and recorded a real consent decision for a toggled-off tenant, on
    # nothing more than a stranger's first message — a customer-visible effect and a DB write
    # `core/licence.py::ToggleGatedLicence`'s own docstring says must never happen for OFF ("OFF
    # MUST READ EXACTLY LIKE UNSUBSCRIBED"). A DISALLOWED tenant skips `_GATES` ENTIRELY and falls
    # through to the engine below exactly as an allowed tenant would — `conversation.py`'s own door
    # gate (`handle_inbound_text`'s own `self._licence.allowed(tenant)` check) is what actually
    # answers it, with the SAME `_NOT_SUBSCRIBED_TEXT` reply an unsubscribed shop already gets
    # today; this is not a second, possibly-drifting refusal, only ONE LESS GATE standing in front
    # of that existing one. `record_if_new`/`mark_processed` above and below are plain per-message
    # bookkeeping, never customer-visible and never a consent decision — unaffected either way.
    licence = getattr(container, "licence", None)
    if licence is None or await licence.allowed(tenant):
        # THE PRE-AI GATE PIPELINE — see `_GATES`'s own module-level docstring for the
        # plug-and-play contract. Cheapest/most-fundamental first; each gate gets the exact same
        # context and either answers this message itself (returns a final result) or hands it,
        # untouched, to the next.
        gate_ctx = GateContext(
            container=container, logger=logger, settings=settings, auditor=auditor, tenant=tenant,
            branch_id=branch_id, wamid=wamid, from_number=from_number, kind=kind, text=text,
            reply_id=reply_id)
        for gate in _GATES:
            outcome = await gate(gate_ctx)
            if outcome is not None:
                return outcome

    try:
        subject_ref = await resolve_subject_ref(container, settings, tenant, from_number)

        # Stamps this message's row (already persisted by record_if_new) with the subject_ref it
        # belongs to — the join key app/core/retention.py and app/core/erasure.py need to find and
        # purge a subject's raw messages. Best-effort: a message this fails on ages out along with
        # its whole conversation regardless.
        await container.inbound_store.attach_subject_ref(tenant, wamid, subject_ref)

        # WHO, WHEN, NEVER WHAT — written to the audit chain BEFORE the message's own content can
        # ever age out under CHAT_RETENTION_DAYS. The chat text stays exactly where it already
        # lived (this service's own store, purged on schedule); this is a second, much smaller
        # fact recorded separately — tenant, this subject's pseudonym, and the wamid — so a shop
        # can still be told "a conversation happened, from this customer, at this time" for a
        # message whose actual content is long gone. Never critical: refusing every ordinary
        # inbound message because the audit log is briefly unreachable would take the whole
        # assistant down to protect a record, the same trade this file already makes for
        # consent_refused/proposal_rejected above and below.
        try:
            await auditor.record(
                "whatsapp_assistant.message_attributed", actor=subject_ref,
                resource=f"wamid:{wamid}", tenant=tenant)
        except Exception:                                            # noqa: BLE001
            pass

        # WHATSAPP DIRECT ORDERING — checked BEFORE every other kind, deliberately: a pending
        # order (core/conversation.py::handle_order) must intercept the very next message no
        # matter what kind it arrives as (the location itself, a cancel, a fresh cart, or
        # anything else that needs the "still waiting on your location" reminder) rather than
        # fall through to the AI/button/location dispatch below and silently lose track of it.
        # `None` means this conversation holds no pending order at all — the normal chain below
        # runs completely unchanged.
        plan = await container.engine.handle_order_followup(
            tenant=tenant, subject_ref=subject_ref, kind=kind, text=text,
            from_number=from_number, wamid=wamid, reply_id=reply_id)
        from_order_flow = plan is not None
        if plan is not None:
            pass
        elif kind == "order":
            # A catalog order arriving with no pending one already open -- see
            # core/conversation.py::handle_order for why this never touches the LLM at all.
            plan = await container.engine.handle_order(
                tenant=tenant, subject_ref=subject_ref, text=text, wamid=wamid)
            from_order_flow = True
        elif kind in ("button_reply", "list_reply"):
            if reply_id.startswith("points:"):
                # WhatsApp Direct Ordering's own points-reward button — "points:{use|skip}:
                # {order_id}" (core/conversation.py::handle_order_followup's own points offer).
                # Deterministic, same posture as every other order-flow id here.
                action = reply_id.split(":", 2)[1] if reply_id.count(":") >= 2 else ""
                plan = await container.engine.handle_points_choice(
                    tenant=tenant, subject_ref=subject_ref, action=action)
                from_order_flow = plan is not None
            elif reply_id.startswith("triage:"):
                # The mandatory first-message triage gate's own list-reply ids — resolved
                # separately from proposal button_reply/list_reply ids below, since a
                # "complaint"/"other" pick must skip the tool-allowlist path entirely (see
                # core/conversation.py::handle_triage_selection).
                plan = await container.engine.handle_triage_selection(
                    tenant=tenant, subject_ref=subject_ref, reply_id=reply_id)
            elif reply_id.startswith("branch:"):
                # The central-number branch-selection gate's own list-reply ids — see
                # core/conversation.py::handle_branch_selection.
                plan = await container.engine.handle_branch_selection(
                    tenant=tenant, subject_ref=subject_ref, reply_id=reply_id)
            else:
                plan = await container.engine.handle_button_reply(
                    tenant=tenant, subject_ref=subject_ref, reply_id=reply_id, auditor=auditor)
        elif kind == "location":
            # THE MOBILE-VISIT-REQUEST FLOW'S OTHER HALF (core/tools.py::MobileLocationRequest,
            # core/conversation.py::handle_location) — deterministic, never the LLM/batching path:
            # a location message can only ever mean something to a conversation the model itself
            # already put into `awaiting_mobile_location` (or nothing at all, answered plainly).
            plan = await container.engine.handle_location(
                tenant=tenant, subject_ref=subject_ref, from_number=from_number, text=text)
        else:
            # THE mandatory triage gate's entry point — never `on_inbound_text` directly. Free
            # text before a triage pick is answered with the same list and never reaches the
            # batching/LLM machinery at all (see core/conversation.py's module docstring).
            plan = await container.engine.handle_inbound_text(
                tenant=tenant, subject_ref=subject_ref, from_number=from_number, text=text,
                branch_id=branch_id)

        # COEXISTENCE: the owner may have just answered this same customer from their own phone
        # (app/core/coexistence_poll.py). The message is still ingested, still attributed, still
        # advances the conversation above — only the SEND is held back, for the bounded cooldown,
        # so the customer does not get a human answer immediately followed by a bot one.
        from app.core.owner_presence import is_owner_active
        owner_active = not from_order_flow and plan is not None and plan.kind in (
            "text", "list", "request_location", "interactive") and await is_owner_active(
            container, tenant=tenant, contact=from_number, now=int(time.time()))
        if owner_active:
            logger.info("whatsapp_owner_active_suppressed",
                       extra={"tenant": tenant, "wamid": wamid})
        elif (not from_order_flow and plan is not None and plan.kind in (
                "text", "list", "request_location", "interactive") and not await outbound_allowed(
                container, settings, tenant, subject_ref=subject_ref, branch_id=branch_id)):
            logger.warning("whatsapp_outbound_capped", extra={"tenant": tenant, "wamid": wamid})
            # A CAP TRIPPING IS AN EXPECTED, WORKING SAFETY MECHANISM, NOT A FAILURE — it is logged
            # at `warning`, which Fluent Bit's own shape.lua deliberately never ships to
            # error-collector (only error/fatal/critical, or an HTTP 500+, reach that screen; see
            # deploy/k3s/fluent-bit.yaml's own `is_failure` note). Without this, an operator has no
            # way to ever see or count how often either limiter actually trips. The audit trail is
            # the right home for it instead — same pattern as `consent_refused` just above: a real,
            # queryable, per-tenant record, best-effort so a down audit sink cannot block a message.
            try:
                await auditor.record(
                    "whatsapp_assistant.outbound_capped", actor="whatsapp-assistant",
                    resource=f"wamid:{wamid}", tenant=tenant,
                    metadata={"subject_ref": subject_ref, "branch_id": branch_id})
            except Exception:                                        # noqa: BLE001
                pass
        elif plan is not None and plan.kind == "text" and plan.text:
            await container.sender.send_template(
                tenant=tenant, to=from_number, template_name="wa_assistant_reply",
                variables=[plan.text], idempotency_key=f"{wamid}:reply")
        elif plan is not None and plan.kind == "list" and plan.list_rows:
            await container.sender.send_list(
                tenant=tenant, to=from_number, body=plan.text,
                button_text=plan.list_button_text, rows=plan.list_rows,
                idempotency_key=f"{wamid}:triage")
        elif plan is not None and plan.kind == "request_location" and plan.text:
            await container.sender.send_location_request(
                tenant=tenant, to=from_number, body=plan.text,
                idempotency_key=f"{wamid}:loc_request")
        elif plan is not None and plan.kind == "interactive" and plan.interactive_buttons:
            await container.sender.send_interactive(
                tenant=tenant, to=from_number, body=plan.text,
                buttons=plan.interactive_buttons, idempotency_key=f"{wamid}:interactive")
    except Exception as exc:                                        # noqa: BLE001
        logger.warning("whatsapp_message_handling_failed",
                       extra={"error": str(exc)[:200], "tenant": tenant, "wamid": wamid})
        return {"processed": False, "reason": "handler_error"}
    finally:
        await container.inbound_store.mark_processed(tenant, wamid)

    return {"processed": True, "reason": ""}
