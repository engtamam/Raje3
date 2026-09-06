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

from typing import Any

from app.core.sending_identity import split as split_sending_identity
from app.ports.consent_gate import DENIED, UNKNOWN


async def outbound_allowed(container: Any, settings: Any, tenant: str) -> bool:
    """One tenant's outbound AI replies are capped per rolling hour — belt beside
    notification-service's own ceiling (OUTBOUND_MAX_PER_TENANT_PER_HOUR's own config.py note), so
    a runaway conversation loop or a bug that keeps re-proposing the same reply cannot spend a
    shop's whole WhatsApp allowance by itself. Shared by both send paths — this fast-path ingest
    and app/api/internal.py's tick — so the budget is the same no matter which one is sending."""
    verdict = await container.rate_limiter.check(
        f"wa_outbound:{tenant}", limit=settings.OUTBOUND_MAX_PER_TENANT_PER_HOUR, window_s=3600)
    return verdict.allowed


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

    # THE CONSENT CHECK, WITH THE RAW NUMBER, BEFORE IT IS EVER FOLDED INTO A PSEUDONYM. The port
    # (app/ports/consent_gate.py) is explicit that a service holding only a subject_ref cannot use
    # it without defeating the pseudonymisation — so this is the one honest place left to ask: the
    # raw `from_number` is already in hand for this one call (same transient use customer_lookup
    # makes a few lines down), never persisted, and gone the moment this function returns.
    #
    # DENIED IS NEVER OVERRIDABLE BY POLICY — an on-record withdrawal holds regardless of
    # CONSENT_POLICY_ON_UNKNOWN, which only ever governs what happens when compliance-service could
    # not be reached at all. See config.py's own note on why UNKNOWN defaults to fail_open here.
    verdict = await container.consent_gate.check(
        tenant=tenant, subject=from_number, purpose=settings.CONSENT_PURPOSE)
    if verdict.status == DENIED or (
            verdict.status == UNKNOWN and settings.CONSENT_POLICY_ON_UNKNOWN == "fail_closed"):
        await container.inbound_store.mark_processed(tenant, wamid)
        logger.info("whatsapp_consent_refused", extra={
            "tenant": tenant, "wamid": wamid, "status": verdict.status, "reason": verdict.reason})
        # NOT CRITICAL (see auditable_actions.py's own note on this action) — best-effort, never
        # blocks the refusal itself: the safe outcome (nothing processed) already happened.
        try:
            await auditor.record("whatsapp_assistant.consent_refused", actor="whatsapp-assistant",
                                 resource=f"wamid:{wamid}", tenant=tenant,
                                 metadata={"status": verdict.status, "reason": verdict.reason,
                                          "purpose": settings.CONSENT_PURPOSE})
        except Exception:                                            # noqa: BLE001
            pass
        return {"processed": False, "reason": f"consent_{verdict.status}"}

    try:
        lookup = await container.customer_lookup.resolve(tenant, from_number)
        subject_ref = str(lookup.get("subject_ref") or "")
        if not subject_ref:
            # UNKNOWN CUSTOMER. Rather than invent a pseudonym (which would collide with a real
            # one the day this number does become a customer), the conversation is keyed on a
            # per-number-per-tenant hash derived the same way core/pii.py derives subject_ref, so
            # an unrecognised sender can still hold a session.
            from app.core.pii import subject_ref as derive_ref
            subject_ref = derive_ref(settings.PII_SALT or "dev-salt", tenant, from_number)

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

        if kind in ("button_reply", "list_reply"):
            if reply_id.startswith("triage:"):
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
        else:
            # THE mandatory triage gate's entry point — never `on_inbound_text` directly. Free
            # text before a triage pick is answered with the same list and never reaches the
            # batching/LLM machinery at all (see core/conversation.py's module docstring).
            plan = await container.engine.handle_inbound_text(
                tenant=tenant, subject_ref=subject_ref, from_number=from_number, text=text,
                branch_id=branch_id)

        if plan is not None and plan.kind in ("text", "list") and not await outbound_allowed(
                container, settings, tenant):
            logger.warning("whatsapp_outbound_capped", extra={"tenant": tenant, "wamid": wamid})
        elif plan is not None and plan.kind == "text" and plan.text:
            await container.sender.send_template(
                tenant=tenant, to=from_number, template_name="wa_assistant_reply",
                variables=[plan.text], idempotency_key=f"{wamid}:reply")
        elif plan is not None and plan.kind == "list" and plan.list_rows:
            await container.sender.send_list(
                tenant=tenant, to=from_number, body=plan.text,
                button_text=plan.list_button_text, rows=plan.list_rows,
                idempotency_key=f"{wamid}:triage")
    except Exception as exc:                                        # noqa: BLE001
        logger.warning("whatsapp_message_handling_failed",
                       extra={"error": str(exc)[:200], "tenant": tenant, "wamid": wamid})
        return {"processed": False, "reason": "handler_error"}
    finally:
        await container.inbound_store.mark_processed(tenant, wamid)

    return {"processed": True, "reason": ""}
