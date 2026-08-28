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

from app.ports.consent_gate import DENIED, UNKNOWN


async def ingest_inbound_message(
    *, container: Any, logger: Any, settings: Any, auditor: Any,
    tenant: str, wamid: str, from_number: str, kind: str, text: str, reply_id: str,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    if not tenant or not wamid or not from_number:
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

        if kind in ("button_reply", "list_reply"):
            if reply_id.startswith("triage:"):
                # The mandatory first-message triage gate's own list-reply ids — resolved
                # separately from proposal button_reply/list_reply ids below, since a
                # "complaint"/"other" pick must skip the tool-allowlist path entirely (see
                # core/conversation.py::handle_triage_selection).
                plan = await container.engine.handle_triage_selection(
                    tenant=tenant, subject_ref=subject_ref, reply_id=reply_id)
            else:
                plan = await container.engine.handle_button_reply(
                    tenant=tenant, subject_ref=subject_ref, reply_id=reply_id,
                    redeemer=container.points_summary, auditor=auditor)
        else:
            # THE mandatory triage gate's entry point — never `on_inbound_text` directly. Free
            # text before a triage pick is answered with the same list and never reaches the
            # batching/LLM machinery at all (see core/conversation.py's module docstring).
            plan = await container.engine.handle_inbound_text(
                tenant=tenant, subject_ref=subject_ref, from_number=from_number, text=text)

        if plan is not None and plan.kind == "text" and plan.text:
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
