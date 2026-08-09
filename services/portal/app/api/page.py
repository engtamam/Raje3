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

from fastapi import APIRouter, Depends, Form, Request, Response
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
async def save_prefs(request: Request, ref: str, on: list[str] = Form(default=[])) -> Response:
    """Save the five switches.

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

    from app.core.compose import CLASS_ORDER
    stopped = [cls for cls in CLASS_ORDER if cls not in set(on)]
    saved = await c.reminders.set_prefs(r.tenant, r.subject_ref, stopped=stopped)

    built = await c.composer.build(r.tenant, r.subject_ref)
    theme = build_theme(built.brand_colour)
    logo = await c.identity.logo_url(r.tenant) if hasattr(c.identity, "logo_url") else ""
    # `saved` is the PEER's answer, not our optimism. A save that failed must not show a
    # confirmation — a customer who is told their choice was saved and keeps receiving messages
    # does not try again, they block the number.
    return HTMLResponse(render_page(built, theme, saved=saved, logo_url=logo), headers=NO_STORE)


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
