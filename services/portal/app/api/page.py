"""The routes a customer ever reaches, and one that survives unlinked.

PUBLIC, ALL OF THEM. No token, no capability, no session — the link arrives in a chat and the
person opening it has no account and never will. Everything that makes that safe lives in
core/reference.py; this file's job is to never undo it.

THE FULL CUSTOMER PAGE (points, visits, preferences, the `PUBLIC_PAGE_ENABLED` closed placeholder)
IS GONE, BY PRODUCT DECISION — not unfinished, deleted. It was never shipped open in production and
this service now serves only what §8.3/§8.5 actually require: a minimal marketing consent screen.

  GET  /p/{ref}/allow    ask, in one screen (§8.5)
  POST /p/{ref}/allow    record the grant
  GET  /p/{ref}/stop     withdraw, in one tap (§8.3)

`POST /p/{ref}/data` (the DSAR request) is kept exactly as it was, on purpose, though there is no
longer any page that links to it — see its own docstring below.

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
from app.core.onescreen import render_one_screen, statement_for
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


def _page_open(request: Request) -> bool:
    """Is the full page served? ALWAYS FALSE — the full page was deleted, not merely closed.

    Kept as a function, not inlined to `False` at each call site, because `ask_about_data` and
    `stop` are untouched on purpose (see their docstrings): a single place to read still means one
    thing changes if a future page ever comes back, rather than call sites disagreeing.
    """
    return False


async def _shop(c, tenant: str) -> tuple[str, str, str]:
    """Name, accent and logo for a one-screen page — ONE peer call, and never a failure.

    The full page composes five reads under a deadline. These screens need only the shop's
    identity, and asking operations for visits in order to draw a consent button would make a
    legal obligation depend on an unrelated service being up.
    """
    try:
        shop = await c.identity.get(tenant)
    except Exception:                                                         # noqa: BLE001
        return "", "", ""
    if shop is None:
        return "", "", ""
    branding = getattr(shop, "branding", {}) or {}
    return (getattr(shop, "name", "") or "",
            str(branding.get("accent") or ""),
            str(branding.get("logo_url") or ""))


async def _logo(c, tenant: str) -> str:
    """The shop's mark, and NEVER the reason the page fails.

    THE 500 THIS CLOSES. `compose.py` swallows a tenant-service outage on purpose — the page still
    has his points, his visits and his switches, and half a page beats none. Then this read was
    added after it, bare, and threw the exception straight out: an outage at tenant-service turned
    the customer's page into an English error screen.

    He arrived from a WhatsApp message sent by a shop he knows. A page that answers with a stack
    trace does not read as «a service is down» to him — it reads as «that message was a scam», and
    that is not a conclusion we get to correct later.
    """
    read = getattr(c.identity, "logo_url", None)
    if read is None:
        return ""
    try:
        return await read(tenant) or ""
    except Exception:                                                         # noqa: BLE001
        return ""


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
    # CLOSED WITH THE PAGE, AND THIS ONE COSTS SOMETHING TO CLOSE. A privacy request is his right
    # under the PDPL and the page is where he exercises it. But a route that records a request no
    # screen can show him the outcome of is worse than one that is honestly shut: he would be told
    # to wait thirty days by a page we then took away. The rights notice in the message and the
    # shop's own channel remain, and the page returns with them.
    if not _page_open(request):
        name, accent, logo = await _shop(c, r.tenant) if r.valid else ("", "", "")
        return HTMLResponse(render_one_screen(
            shop_name=name, theme=build_theme(accent or None), logo_url=logo,
            headline="صفحتك قيد التجهيز",
            body="لطلب نسخة من بياناتك أو حذفها، تواصل مع المتجر مباشرة."), headers=NO_STORE)
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
    # THE ANSWER, NOT OUR OPTIMISM — the same rule the form path a hundred lines up already
    # follows, and it explains itself there: «a customer who is told their choice was saved and
    # keeps receiving messages does not try again, they block the number».
    #
    # THIS IS THE PATH THAT MATTERS MOST. It is the one-tap link inside every marketing message,
    # made frictionless on purpose because somebody who wants out is already annoyed. It rendered
    # «تم حفظ تفضيلاتك» unconditionally: the save could fail, the offers keep coming, and he does
    # not retry — he was told it worked. The shop then loses him and its sender reputation
    # together, for a save that never happened.
    saved = False
    if r.valid:
        saved = bool(await c.reminders.set_prefs(
            r.tenant, r.subject_ref, stopped=["marketing"], merge=True))

    # WHATEVER ELSE IS CLOSED, THIS ANSWERS (spec §8.3). With the page shut it renders the outcome
    # on one screen rather than composing five sections he cannot see anyway — and it still reports
    # the PEER's answer, because the whole point of this route is that he is told the truth about
    # whether the offers stopped.
    if not _page_open(request):
        name, accent, logo = await _shop(c, r.tenant) if r.valid else ("", "", "")
        return HTMLResponse(render_one_screen(
            shop_name=name, theme=build_theme(accent or None), logo_url=logo,
            headline="أُوقفت العروض" if saved else "تعذّر الإيقاف الآن",
            body=("لن تصلك رسائل عروض بعد الآن. رسائل الخدمة — تأكيد زيارتك وموعد صيانتك — "
                  "تستمر كما هي." if saved else
                  "لم يتغيّر شيء. افتح الرابط مرة أخرى بعد قليل، أو أخبر المتجر مباشرة.")),
            headers=NO_STORE)

    built = (await c.composer.build(r.tenant, r.subject_ref)) if r.valid else None
    if built is None:
        from app.core.compose import Page
        built = Page(reference=ref, tenant="")
    theme = build_theme(built.brand_colour)
    return HTMLResponse(render_page(built, theme, saved=saved), headers=NO_STORE)


@router.get("/{ref}/allow", response_class=HTMLResponse, dependencies=[Depends(rate_limit)])
async def allow(request: Request, ref: str) -> Response:
    """Ask for marketing consent, in one screen (spec §8.5).

    THE SCREEN EXISTS BECAUSE THE LINK ALONE CANNOT BE CONSENT. A grant on GET would be one fewer
    tap and would not be a positive act: WhatsApp's own preview fetcher opens links, messages are
    forwarded, and scanners crawl. `/stop` gets to be a GET precisely because its worst accident is
    fewer messages; the worst accident here is a consent record for somebody who never agreed —
    which is the one document we would be asked to produce.

    SERVED EVEN WHEN THE PAGE IS CLOSED, and that is the whole reason this route is separate from
    it. Marketing is opt-in, so with no way to grant there is no lawful marketing at all, and the
    campaigns engine — complete, and sold as an app — sends nothing forever.
    """
    r = parse(ref)
    c = request.app.state.container
    name, accent, logo = await _shop(c, r.tenant) if r.valid else ("", "", "")
    theme = build_theme(accent or None)
    return HTMLResponse(render_one_screen(
        shop_name=name, theme=theme, logo_url=logo,
        # THE PERSUASION IS ABOVE THE LINE, THE DISCLOSURE IS ON IT. What makes somebody tap is
        # knowing they get the discount before everyone else; what makes the grant lawful is the
        # sentence below, which names the sender, the volume and the exit. Selling inside the
        # statement itself would corrupt the record — the two are deliberately different registers.
        headline=f"خصومات {name}" if name else "خصوماتنا",
        body="عروض وتخفيضات تصل عملاءنا المسجّلين أولاً — قبل أن تُعلن. بلا إزعاج، وتوقفها متى شئت.",
        say=statement_for(name),
        action=f"/p/{ref}/allow", action_label="أرسلوا لي العروض"), headers=NO_STORE)


@router.post("/{ref}/allow", response_class=HTMLResponse, dependencies=[Depends(rate_limit)])
async def grant(request: Request, ref: str) -> Response:
    """Record the grant, and say what actually happened.

    THE PEER'S ANSWER, NEVER OUR OPTIMISM — the rule every write on this service already follows.
    A customer told he is subscribed who then receives nothing does not press again; he concludes
    the shop is disorganised, and the shop never learns why its consent count is short.
    """
    r = parse(ref)
    c = request.app.state.container
    saved = False
    if r.valid:
        saved = bool(await c.reminders.grant_marketing(r.tenant, r.subject_ref))

    name, accent, logo = await _shop(c, r.tenant) if r.valid else ("", "", "")
    return HTMLResponse(render_one_screen(
        shop_name=name, theme=build_theme(accent or None), logo_url=logo,
        headline="تمّ — صرت من الأوائل" if saved else "تعذّر التسجيل الآن",
        body=("أول ما ينزل عرض أو خصم، يوصلك. ولإيقافه، ضغطة واحدة من أسفل أي رسالة عروض."
              if saved else
              "لم يُسجَّل شيء. افتح الرابط مرة أخرى بعد قليل.")), headers=NO_STORE)
