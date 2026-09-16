"""GET/POST /r/{ref} — the hosted rating page, [[task-service-procedure-checklists]] phase 2.

REPLACES A NATIVE WHATSAPP FLOW, not an addition beside it. The rating message's own template
button now opens this page instead of a Flow screen — see reminders' `tick.py`
(`url_button_param`) and services/operations' `ProcedureStep`/`Visit.rating_issue_step_ids` for
the rest of this feature. Same public, unauthenticated, rate-limited posture every route in this
file already follows (see `page.py`'s own module docstring for the four rules this must not
break — no oracle, no PII in headers/errors, no caching, hard rate limits).

`ref` IS THE SAME STRING reminders' own `RatingRequestStore` keys on — this file never invents,
parses, or validates its shape; it is opaque here exactly as `parse()`'s `subject_ref` is opaque
to `page.py`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse

from app.api.page import NO_STORE, _shop
from app.api.ratelimit import rate_limit
from app.core.onescreen import render_one_screen
from app.core.rating_page import render_rating_form
from app.core.theme import build_theme

router = APIRouter(prefix="/r", tags=["rating"])

# ONE STAR SHORT OF FIVE IS THE HIGHEST RATING THAT CAN STILL CARRY A FLAGGED PROBLEM — 5 means
# "nothing wrong", by definition, the same reading `Visit.rating_issue_step_ids`'s own docstring
# gives the empty list. A contradiction is refused here, server-side, before it ever reaches
# reminders/operations — see this module's own docstring on why there is no client-side check.
_PERFECT = 5


def _refused_screen(theme, shop_name: str, logo_url: str) -> Response:
    return HTMLResponse(render_one_screen(
        shop_name=shop_name, theme=theme, logo_url=logo_url,
        headline="تعذّر فتح الرابط", body="هذا الرابط لم يعد صالحاً — ربما استُخدم من قبل."),
        headers=NO_STORE)


@router.get("/{ref}", response_class=HTMLResponse, dependencies=[Depends(rate_limit)])
async def rating_form(request: Request, ref: str) -> Response:
    """The form — or a plain explanation when there is nothing left to answer."""
    c = request.app.state.container
    anchor = await c.reminders.rating_anchor(ref)
    if not anchor.get("found"):
        return _refused_screen(build_theme(None), "", "")

    tenant = str(anchor.get("tenant") or "")
    name, accent, logo = await _shop(c, tenant)
    theme = build_theme(accent or None)

    ctx = await c.operations.rating_context(tenant, str(anchor.get("visit_id") or ""))
    if not ctx.get("found"):
        return _refused_screen(theme, name, logo)
    if ctx.get("already_rated"):
        return HTMLResponse(render_one_screen(
            shop_name=name, theme=theme, logo_url=logo,
            headline="شكراً لك", body="تقييمك وصلنا بالفعل — لا حاجة لخطوة أخرى."),
            headers=NO_STORE)

    return HTMLResponse(render_rating_form(
        shop_name=name, theme=theme, logo_url=logo, action=f"/r/{ref}",
        service_names=list(ctx.get("service_names") or []),
        steps=list(ctx.get("steps") or [])), headers=NO_STORE)


@router.post("/{ref}", response_class=HTMLResponse, dependencies=[Depends(rate_limit)])
async def rating_submit(request: Request, ref: str) -> Response:
    """Validate, then either re-ask (a real error) or submit (reminders' own idempotent write)."""
    c = request.app.state.container
    anchor = await c.reminders.rating_anchor(ref)
    if not anchor.get("found"):
        return _refused_screen(build_theme(None), "", "")

    tenant = str(anchor.get("tenant") or "")
    name, accent, logo = await _shop(c, tenant)
    theme = build_theme(accent or None)

    form = await request.form()
    try:
        stars = int(str(form.get("stars") or ""))
    except ValueError:
        stars = 0
    issue_ids = [str(v) for v in form.getlist("issue")]
    comment = str(form.get("comment") or "").strip()[:2000]

    ctx = await c.operations.rating_context(tenant, str(anchor.get("visit_id") or ""))
    steps = list(ctx.get("steps") or []) if ctx.get("found") else []

    error = ""
    if not 1 <= stars <= 5:
        error = "اختر تقييماً من نجمة واحدة إلى خمس قبل الإرسال."
    # THE OWNER'S OWN RULE (2026-09-16): 5 نجوم يعني كل شي تمام — لا يصح مع مشكلة معلّمة.
    elif stars == _PERFECT and issue_ids:
        error = "اخترت خمس نجوم مع تحديد مشكلة — هل تقصد تقييماً أقل من خمس؟ عدّل اختيارك وأرسل مجدداً."

    if error:
        return HTMLResponse(render_rating_form(
            shop_name=name, theme=theme, logo_url=logo, action=f"/r/{ref}",
            service_names=list(ctx.get("service_names") or []), steps=steps, error=error,
            selected_stars=stars, selected_step_ids=issue_ids, comment=comment), headers=NO_STORE)

    result = await c.reminders.rating_submit(
        ref, rating=stars, feedback_text=comment, rating_issue_step_ids=issue_ids)
    if not result.get("recorded"):
        return HTMLResponse(render_one_screen(
            shop_name=name, theme=theme, logo_url=logo,
            headline="تعذّر إرسال تقييمك", body="حاول فتح الرابط مرة أخرى بعد قليل."),
            headers=NO_STORE)

    return HTMLResponse(render_one_screen(
        shop_name=name, theme=theme, logo_url=logo,
        headline="وصل تقييمك، شكراً لك", body="نقدّر وقتك — رأيك يصل مباشرة إلى المتجر."),
        headers=NO_STORE)
