# =============================================================================
# whatsapp-assistant — Internal tier (service-to-service, X-Internal-Token)
# -----------------------------------------------------------------------------
# NOT user-facing. Guarded by a shared token compared in CONSTANT TIME
# (CWE-208), exactly as every sibling service's internal.py does it.
# =============================================================================
from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.manifest import build_manifest

router = APIRouter(prefix="/internal", tags=["internal"])

_HEADER = "X-Internal-Token"


async def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias=_HEADER),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = settings.INTERNAL_SERVICE_TOKEN
    provided = x_internal_token or ""
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")


@router.get("/health", dependencies=[Depends(require_internal_token)])
async def internal_health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "service": settings.SERVICE_NAME}


@router.get("/manifest", dependencies=[Depends(require_internal_token)])
async def manifest(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    container = request.app.state.container
    return build_manifest(settings, ports=container.describe())


@router.post("/whatsapp_assistant/tick", dependencies=[Depends(require_internal_token)])
async def tick(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    """The scheduled sweep: compose debounced replies whose window elapsed, close sessions past
    their silence timeout. Imitates services/reminders' /internal split between the event
    fast-path (subscribed in main.py's lifespan) and this cron-driven tick — the fast path can
    silently miss an event; this cannot silently miss a due conversation, because it scans this
    service's OWN datastore rather than depending on the bus a second time.

    Per-tenant, bounded (CONVERSATION_TICK_BATCH_SIZE) — the same reasoning as reminders'
    TICK_BATCH_SIZE: an unbounded sweep is how one busy tenant starves every other one.
    """
    import time as _time

    c = request.app.state.container
    tenant = ""
    body: dict = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    tenant = str(body.get("tenant") or "")
    if not tenant:
        return {"error": "tenant is required"}

    now = int(_time.time())
    batch = settings.CONVERSATION_TICK_BATCH_SIZE
    replied = 0
    closed = 0

    due = await c.engine.sweep_due(tenant, now=now, batch=batch)
    for subject_ref in due:
        plan = await c.engine.compose_reply(tenant, subject_ref, now=now)
        if plan.kind == "none":
            continue
        conv = await c.datastore.get("wa_conversations", f"{tenant}|{subject_ref}")
        to = (conv or {}).get("from_number", "")
        if not to:
            continue
        if plan.kind == "text" and plan.text:
            await c.sender.send_template(
                tenant=tenant, to=to, template_name="wa_assistant_reply",
                variables=[plan.text], idempotency_key=f"tick_{tenant}_{subject_ref}_{now}")
            replied += 1
        elif plan.kind == "interactive" and plan.proposal is not None:
            await c.sender.send_interactive(
                tenant=tenant, to=to, body=plan.proposal.body, buttons=plan.proposal.buttons,
                idempotency_key=f"tick_{plan.proposal.proposal_id}")
            replied += 1

    timed_out = await c.engine.sweep_timed_out(tenant, now=now, batch=batch)
    closed = len(timed_out)

    return {"tenant": tenant, "replied": replied, "closed": closed, "scanned": len(due)}
