"""Tool validation gate — the model PROPOSES, this VALIDATES, only then a button is rendered.

This is the core safety property of the whole service (design point 5 / point 9's priority list).
The sequence for every allowlisted tool is always:

    1. GeminiLlm returns a ToolCall — a NAME and ARGS the model chose. Untrusted.
    2. `validate_and_render()` here re-checks it against REAL current state (real availability,
       real points balance) — never trusts anything the model claimed about that state.
    3. Only if validation passes is an interactive WhatsApp message built and a PendingProposal
       persisted, keyed by an id that is embedded in the button/list reply ids.
    4. The state-changing action (a booking write, a points redemption) fires ONLY when a
       button_reply/list_reply comes back matching that PendingProposal id — see
       core/conversation.py::handle_button_reply. Free text can never trigger it, and the model is
       never consulted again for that decision.

`confirm_booking` DOES NOT EXIST as a tool anywhere in this file, the LLM schema (adapters/llm/
gemini.py), or the allowlist (config.py::LLM_TOOL_ALLOWLIST). Confirmation is button-only by
construction, not by convention.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.models import PENDING_PROPOSALS, PendingProposal, as_row


@dataclass(frozen=True)
class RenderedProposal:
    """What core/conversation.py hands to the WhatsAppSender — body text plus button ids that map
    back to a PendingProposal.id 1:1."""
    proposal_id: str
    body: str
    buttons: list[dict[str, str]]


class ToolValidationError(Exception):
    """The model proposed something reality does not support — a slot that is gone, a service that
    does not exist. Never rendered as a button; the caller falls back to plain text."""


async def validate_and_render(*, tenant: str, subject_ref: str, conversation_id: str,
                              tool: str, args: dict[str, Any], allowed_tools: frozenset[str],
                              store: Any, booking_provider: Any, points_summary: Any,
                              proposal_ttl_seconds: int, now: int | None = None,
                              related_services: Any = None, service_catalog: Any = None
                              ) -> RenderedProposal | str:
    """Returns a RenderedProposal (interactive message + pending proposal persisted) for a
    state-changing tool, or a plain str for a read-only one. Raises ToolValidationError if the
    model's proposal does not hold up against real state.
    """
    now = now if now is not None else int(time.time())

    if tool not in allowed_tools:
        # DEFENCE IN DEPTH: gemini.py already filters this before it ever reaches here, but a tool
        # name reaching this function outside the allowlist must never be trusted to mean "someone
        # forgot to filter" — it is refused again, unconditionally, at the one place execution
        # could actually happen.
        raise ToolValidationError(f"tool {tool!r} is not allowlisted")

    if tool == "check_availability":
        service_id = str(args.get("service_id") or "")
        if not service_id:
            raise ToolValidationError("check_availability requires service_id")
        earliest = _parse_date(args.get("earliest_date")) or now
        slots = await booking_provider.availability(
            tenant=tenant, service_id=service_id, earliest=earliest, horizon_days=0)
        if not slots:
            return "لا توجد مواعيد متاحة قريبًا لهذه الخدمة."
        listed = ", ".join(_fmt_slot(s.starts_at) for s in slots[:5])
        return f"المواعيد المتاحة: {listed}"

    if tool == "propose_booking":
        service_id = str(args.get("service_id") or "")
        starts_at = _parse_iso(args.get("starts_at_iso"))
        if not service_id or starts_at is None:
            raise ToolValidationError("propose_booking requires service_id and starts_at_iso")
        # RE-VALIDATED, not trusted: is this slot STILL real, right now, independent of whatever
        # the model believed when it proposed it.
        slots = await booking_provider.availability(
            tenant=tenant, service_id=service_id, earliest=starts_at, horizon_days=0)
        if not any(s.starts_at == starts_at for s in slots):
            raise ToolValidationError(
                f"proposed slot {starts_at} for {service_id!r} is not actually available")

        proposal_id = f"prp_{uuid.uuid4().hex[:24]}"
        proposal = PendingProposal(
            id=proposal_id, tenant=tenant, subject_ref=subject_ref,
            conversation_id=conversation_id, tool="propose_booking",
            args={"service_id": service_id, "starts_at": starts_at},
            validated_snapshot={"validated_at": now},
            created_at=now, expires_at=now + proposal_ttl_seconds)
        await store.put(PENDING_PROPOSALS, proposal_id, as_row(proposal))
        return RenderedProposal(
            proposal_id=proposal_id,
            body=f"هل تؤكد الموعد الساعة {_fmt_slot(starts_at)}؟",
            buttons=[{"id": f"{proposal_id}:confirm", "title": "تأكيد"},
                    {"id": f"{proposal_id}:cancel", "title": "إلغاء"}])

    if tool == "get_customer_points_summary":
        summary = await points_summary.summary(tenant=tenant, subject_ref=subject_ref)
        return summary.get("text", "")

    if tool == "suggest_redeemable_offer":
        offer = await points_summary.redeemable_offer(tenant=tenant, subject_ref=subject_ref)
        if not offer:
            return "لا توجد مكافأة متاحة برصيدك الحالي بعد."
        proposal_id = f"prp_{uuid.uuid4().hex[:24]}"
        proposal = PendingProposal(
            id=proposal_id, tenant=tenant, subject_ref=subject_ref,
            conversation_id=conversation_id, tool="suggest_redeemable_offer",
            args={"reward_id": offer["reward_id"]},
            validated_snapshot={"validated_at": now, "points": offer.get("points")},
            created_at=now, expires_at=now + proposal_ttl_seconds)
        await store.put(PENDING_PROPOSALS, proposal_id, as_row(proposal))
        return RenderedProposal(
            proposal_id=proposal_id,
            body=f"يمكنك استبدال «{offer['reward_name']}» بنقاطك الحالية. هل ترغب بذلك؟",
            buttons=[{"id": f"{proposal_id}:confirm", "title": "استبدال"},
                    {"id": f"{proposal_id}:cancel", "title": "لا شكرًا"}])

    if tool == "suggest_related_service":
        service_id = str(args.get("service_id") or "")
        if not service_id:
            raise ToolValidationError("suggest_related_service requires service_id")
        # READ-ONLY, like check_availability/get_customer_points_summary — this NEVER adds the
        # related service to a booking itself; a customer who wants it still goes through
        # propose_booking/button-confirm like any other service. No proposal, no button, no
        # PendingProposal row.
        related_ids = (await related_services.related_to(tenant, service_id)
                      if related_services is not None else [])
        if not related_ids:
            return "لا توجد خدمة أخرى تُطلب عادةً مع هذه الخدمة."
        names_by_id: dict[str, str] = {}
        if service_catalog is not None:
            for s in await service_catalog.list_active(tenant):
                names_by_id[str(s.get("id"))] = str(s.get("name") or s.get("id"))
        names = [names_by_id.get(rid, rid) for rid in related_ids]
        # NO DISCOUNT FIELD EXISTS ANYWHERE IN THIS RESULT — the associations engine
        # (services/insights/app/core/associations.py) returns only a verdict and an id, never a
        # price or a discount. There is nothing here for the model to embellish from; any discount
        # claim in its reply is therefore always fabricated and is caught by
        # core/conversation.py's `_sanitize_reply` regardless of what this tool returns.
        listed = "، ".join(names[:3])
        return f"عادةً ما يُطلب مع هذه الخدمة أيضًا: {listed}. هل تحب إضافتها؟"

    raise ToolValidationError(f"tool {tool!r} has no handler")


async def execute_confirmed_proposal(*, tenant: str, proposal_id: str, store: Any,
                                     booking_provider: Any, redeemer: Any, auditor: Any,
                                     idempotency_key: str, now: int | None = None) -> dict[str, Any]:
    """The ONLY path that turns a proposal into a real write — reached exclusively from a matching
    button_reply id (core/conversation.py::handle_button_reply). Re-validates AGAIN: a proposal
    confirmed minutes after it was rendered must still hold against current state, not the state
    at proposal time.
    """
    now = now if now is not None else int(time.time())
    row = await store.get(PENDING_PROPOSALS, proposal_id)
    if row is None or row.get("tenant") != tenant:
        raise ToolValidationError("no such pending proposal for this tenant")
    if row.get("consumed"):
        raise ToolValidationError("proposal already consumed")
    if int(row.get("expires_at") or 0) < now:
        raise ToolValidationError("proposal expired")

    tool = row.get("tool")
    args = row.get("args") or {}
    subject_ref = row.get("subject_ref", "")

    if tool == "propose_booking":
        try:
            booking = await booking_provider.hold_and_confirm(
                tenant=tenant, subject_ref=subject_ref, service_id=args["service_id"],
                starts_at=int(args["starts_at"]), idempotency_key=idempotency_key)
        except Exception as exc:
            raise ToolValidationError(f"booking confirm failed: {exc}") from exc
        # CRITICAL: a booking confirmed by this assistant on a customer's behalf must be
        # witnessed. Fail-closed per app/core/audit.py — see auditable_actions.py.
        await auditor.record("whatsapp_assistant.booking_confirmed", actor="whatsapp-assistant",
                             resource=f"booking:{booking.get('id', '')}", tenant=tenant,
                             metadata={"subject_ref": subject_ref, "service_id": args["service_id"]})
        row["consumed"] = True
        await store.put(PENDING_PROPOSALS, proposal_id, row)
        return {"kind": "booking", "booking": booking}

    if tool == "suggest_redeemable_offer":
        try:
            result = await redeemer.redeem(tenant=tenant, subject_ref=subject_ref,
                                           reward_id=args["reward_id"],
                                           idempotency_key=idempotency_key)
        except Exception as exc:
            raise ToolValidationError(f"redemption failed: {exc}") from exc
        # CRITICAL: spends something the customer owns, on their behalf, with nobody standing at
        # a till watching it happen — the exact case app/core/audit.py's docstring names as
        # needing a fail-closed record.
        await auditor.record("whatsapp_assistant.points_redeemed", actor="whatsapp-assistant",
                             resource=f"reward:{args['reward_id']}", tenant=tenant,
                             metadata={"subject_ref": subject_ref})
        row["consumed"] = True
        await store.put(PENDING_PROPOSALS, proposal_id, row)
        return {"kind": "redemption", "result": result}

    raise ToolValidationError(f"proposal tool {tool!r} has no confirm handler")


def _parse_date(value: Any) -> int | None:
    if not value:
        return None
    import datetime as _dt
    try:
        d = _dt.datetime.strptime(str(value), "%Y-%m-%d")
        return int(d.replace(tzinfo=_dt.timezone.utc).timestamp())
    except ValueError:
        return None


def _parse_iso(value: Any) -> int | None:
    if not value:
        return None
    import datetime as _dt
    try:
        return int(_dt.datetime.fromisoformat(str(value)).timestamp())
    except ValueError:
        return None


def _fmt_slot(epoch: int) -> str:
    import datetime as _dt
    d = _dt.datetime.fromtimestamp(epoch, _dt.timezone(_dt.timedelta(hours=3)))
    return d.strftime("%Y-%m-%d %H:%M")
