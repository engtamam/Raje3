"""The three routes a customer ever reaches.

PUBLIC, ALL OF THEM. No token, no capability, no session — the link arrives in a chat and the
person opening it has no account and never will. Everything that makes that safe lives in
core/reference.py; this file's job is to never undo it.

FOUR RULES THIS FILE MUST NOT BREAK:

  1. Never distinguish "unknown" from "malformed" in a response. Either answer, twice, is an
     oracle for whether a shop has a customer with that reference.
  2. Never put anything identifying in a header, a redirect, or an error.
  3. Never let a proxy or a shared phone cache the page. It is one person's page; a
     Cache-Control that permits storage is the previous customer's page shown to the next.
  4. Rate limit hard. It is the only unauthenticated write on the product.

AND THE UNSUBSCRIBE IS ONE TAP (spec §8.3). `/stop` stops the marketing and THEN shows what it
did — it does not open a panel asking somebody to find a setting. A customer who wants out is
already annoyed, and making them navigate is how a stop becomes a block.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse

from app.api.ratelimit import rate_limit
from app.core.reference import parse
from app.core.render import render_page
from app.core.theme import build_theme

router = APIRouter(prefix="/p", tags=["page"])

# NO STORAGE ANYWHERE. `private` alone is not enough: it permits a browser to keep the page, and a
# phone shared between a father and his son shows the second one the first one's visits after a
# back button. `no-store` is the only header that means what we need.
NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate, private",
            "Pragma": "no-cache",
            # Belt and braces against a proxy that ignores Cache-Control on a 200.
            "Vary": "Cookie"}


def _render(request: Request, ref: str, *, saved: bool = False) -> Response:
    return HTMLResponse("", headers=NO_STORE)


@router.get("/{ref}", response_class=HTMLResponse, dependencies=[Depends(rate_limit)])
async def page(request: Request, ref: str) -> Response:
    """The page.

    ALWAYS 200, EVEN FOR A REFERENCE THAT MEANS NOTHING. A 404 here answers "does this shop have a
    customer with this reference?" to anyone holding a forwarded link — and the caller's behaviour
    is identical either way, because there is nothing they can do about it. So an unknown reference
    renders the same shell as a known one, with empty sections.
    """
    r = parse(ref)
    c = request.app.state.container
    if not r.valid:
        # The shell, with no peer calls at all. Not an error, and not a lookup: asking three
        # services about a reference we know is malformed would also make this route a way to make
        # us do work.
        from app.core.compose import Page
        blank = Page(reference=ref, tenant="")
        return HTMLResponse(render_page(blank, build_theme(None)), headers=NO_STORE)

    built = await c.composer.build(r.tenant, r.subject_ref)
    theme = build_theme(built.brand_colour)
    logo = await c.identity.logo_url(r.tenant) if hasattr(c.identity, "logo_url") else ""
    return HTMLResponse(render_page(built, theme, saved=False, logo_url=logo), headers=NO_STORE)


@router.post("/{ref}/prefs", response_class=HTMLResponse, dependencies=[Depends(rate_limit)])
async def save_prefs(request: Request, ref: str) -> Response:
    """Save the five switches.

    THE BODY IS PARSED BY HAND, and that is a dependency decision rather than a style one.
    FastAPI's `Form(...)` requires `python-multipart` the moment it appears — even for a form that
    sends nothing multipart. Ours is five checkboxes with no file input, so the browser sends
    `application/x-www-form-urlencoded`, which the standard library already reads. Adding a
    package to parse a format we do not use would be a third-party dependency in the only
    internet-facing service on the product, for nothing.

    Found by deploying: the import succeeded, the tests passed, and the pod crash-looped on
    startup because FastAPI checks for the library when it builds the route, not when it is called.

    THE FORM SENDS WHAT IS ON, so what is off is everything else. That is how an HTML checkbox
    works — an unchecked box submits nothing — and it is why this takes the enabled list rather
    than a stopped one: reading the absent values is the browser's contract, not a convention we
    invented.

    RENDERS THE RESULT RATHER THAN REDIRECTING. A redirect would put the reference through a
    Location header and a second request, which is two more places it can be logged. And the page
    it would redirect to is the page we already have.
    """
    r = parse(ref)
    c = request.app.state.container
    if not r.valid:
        from app.core.compose import Page
        return HTMLResponse(render_page(Page(reference=ref, tenant=""), build_theme(None)),
                            headers=NO_STORE)

    import urllib.parse

    from app.core.compose import CLASS_ORDER
    # Bounded read: this is the only unauthenticated write on the product, and an unbounded body
    # read is a way to make us hold memory for anyone with the URL.
    raw = (await request.body())[:4096].decode("utf-8", "ignore")
    on = set(urllib.parse.parse_qs(raw).get("on", []))
    stopped = [cls for cls in CLASS_ORDER if cls not in on]
    saved = await c.reminders.set_prefs(r.tenant, r.subject_ref, stopped=stopped)

    built = await c.composer.build(r.tenant, r.subject_ref)
    theme = build_theme(built.brand_colour)
    logo = await c.identity.logo_url(r.tenant) if hasattr(c.identity, "logo_url") else ""
    # `saved` is the PEER's answer, not our optimism. A save that failed must not show a
    # confirmation — a customer who is told their choice was saved and keeps receiving messages
    # does not try again, they block the number.
    return HTMLResponse(render_page(built, theme, saved=saved, logo_url=logo), headers=NO_STORE)


@router.post("/{ref}/data", response_class=HTMLResponse, dependencies=[Depends(rate_limit)])
async def ask_about_data(request: Request, ref: str) -> Response:
    """«اطلب نسخة من بياناتي» / «اطلب حذف بياناتي» — his right, exercised against his shop.

    RECORDED, NOT EXECUTED, and the establishment answers. It is the controller under the PDPL and
    we are its processor; a page that erased his history on a tap would also be a delete button for
    anyone who ever saw the link. See operations' privacy-request route.

    THE ANSWER IS THE PEER'S, NOT OUR OPTIMISM — the same rule the preferences save learned. A
    customer told his request was received, when nothing recorded it, does not ask again: he
    assumes the shop ignored him, which is the one outcome this page exists to prevent.
    """
    r = parse(ref)
    c = request.app.state.container
    if not r.valid:
        from app.core.compose import Page
        return HTMLResponse(render_page(Page(reference=ref, tenant=""), build_theme(None)),
                            headers=NO_STORE)

    import urllib.parse

    raw = (await request.body())[:4096].decode("utf-8", "ignore")
    kind = (urllib.parse.parse_qs(raw).get("ask") or [""])[0]
    ok = False
    if kind in ("export", "erase"):
        # THE PEER'S FAILURE IS AN ANSWER, NOT A CRASH — and this call had nothing around it.
        #
        # `HttpOperations.privacy_request` lets a urllib error propagate, so a restarting or slow
        # operations pod reached the app-wide handler, which answers `{"error":"INTERNAL_ERROR"}`
        # with a 500 — a JSON blob rendered into a CUSTOMER's browser, on the page he opened from a
        # WhatsApp message, on the one action that is his legal right. He cannot tell whether his
        # request was recorded, and the thirty-day clock never starts.
        #
        # The honest sentence was already written four lines below and simply could not be reached:
        # «تعذّر تسجيل طلبك الآن … ولم يتغيّر شيء في بياناتك» — which is true, and is what he needs
        # to know in order to try again.
        try:
            ok = await c.operations.privacy_request(r.tenant, r.subject_ref, kind)
        except Exception:                                                   # noqa: BLE001
            ok = False

    built = await c.composer.build(r.tenant, r.subject_ref)
    theme = build_theme(built.brand_colour)
    logo = await c.identity.logo_url(r.tenant) if hasattr(c.identity, "logo_url") else ""
    # WHAT HAPPENS NEXT, IN HIS WORDS AND WITH A DEADLINE. «تم» tells him nothing about whether to
    # wait or to follow up; the regulation gives the shop thirty days and he is entitled to know it.
    said = ("وصل طلبك إلى المتجر. يرد عليك خلال ثلاثين يوماً — وقد يتواصل معك للتأكد من هويتك قبل "
            "التنفيذ." if ok else
            "تعذّر تسجيل طلبك الآن. حاول بعد قليل — ولم يتغيّر شيء في بياناتك.")
    return HTMLResponse(render_page(built, theme, logo_url=logo, asked=said), headers=NO_STORE)


@router.get("/{ref}/stop", response_class=HTMLResponse, dependencies=[Depends(rate_limit)])
async def stop(request: Request, ref: str) -> Response:
    """One tap: stop the marketing, then say so (spec §8.3).

    A GET THAT CHANGES STATE, DELIBERATELY. Every rule says not to — and every rule assumes the
    actor has a session, a form, and a reason to be careful. Here the actor is a person tapping a
    link at the bottom of a message they did not want, and the alternative is a page with a button
    they have to find and press. A customer who wants out is already annoyed, and making them
    navigate is how a stop becomes a block on the shop's number.

    The risk a GET normally carries is a prefetcher or a scanner firing it. Its worst outcome here
    is that somebody's marketing stops — the same worst case the whole link design already accepts,
    and the failure direction is fewer messages.

    IT STOPS MARKETING ONLY. Not the service messages: someone unsubscribing from offers still
    wants to know their car is ready, and taking that away is not what they asked for.
    """
    r = parse(ref)
    c = request.app.state.container
    if r.valid:
        await c.reminders.set_prefs(r.tenant, r.subject_ref, stopped=["marketing"], merge=True)

    built = (await c.composer.build(r.tenant, r.subject_ref)) if r.valid else None
    if built is None:
        from app.core.compose import Page
        built = Page(reference=ref, tenant="")
    theme = build_theme(built.brand_colour)
    return HTMLResponse(render_page(built, theme, saved=True), headers=NO_STORE)
