"""The page: one document, rendered on the server, sent complete.

THE CONSTRAINT THAT DECIDES EVERYTHING HERE. This page is opened from a WhatsApp message by
someone standing in a shop with one bar of signal. A JavaScript bundle costs the first paint, a web
font costs a round trip before any text appears, and a spinner is a page that was never read. So:
one HTML document, CSS inlined in the head, no framework, no external request of any kind.

The few lines of JavaScript at the end are for the switches only, and the form works without them —
a customer whose script fails still gets a page they can submit.

NOT A TRACE OF US (spec §8.6.1). The shop's name, the shop's colour, and no mention of the product
anywhere: not in the title, not in a footer, not in a comment. The customer is having a
relationship with a workshop, not with a platform, and every pixel that says otherwise makes the
shop look like a reseller of something.

ARABIC FIRST AND RTL BY CONSTRUCTION, not by an override. `dir="rtl"` on the document and a font
stack that names the faces a Saudi phone actually has — no download, no swap, no layout shift while
a webfont arrives.

AND EVERY VALUE IS ESCAPED. A shop's name is typed by a person into a form, and this page renders
it into HTML. A name containing a quote is a broken page; a name containing a tag is worse.
"""
from __future__ import annotations

import html
from typing import Any

from app.core.compose import Page
from app.core.theme import Theme

# Faces a Saudi phone already has, newest first. No webfont: a download before first paint is the
# single most expensive thing this page could do, and the system Arabic on iOS and Android is
# excellent.
FONT_STACK = ('-apple-system, "SF Arabic", "Segoe UI", Roboto, '
              '"Noto Sans Arabic", "Helvetica Neue", Arial, sans-serif')


def _e(value: Any) -> str:
    """Escape for HTML text and attributes both. `quote=True` matters: this goes inside
    attributes, and a shop name with a double quote would otherwise end one early."""
    return html.escape(str(value or ""), quote=True)


def _css(theme: Theme) -> str:
    """The whole stylesheet. Inlined because a second request is a second round trip, and on the
    connection this page is opened over that is the difference between reading it and closing it.

    Deliberately small. Every rule here earns its place: there is no grid system, no utility
    classes, and no state this page does not have.
    """
    return (
        ":root{" + theme.css_variables() + "}"
        "*{box-sizing:border-box;margin:0;padding:0}"
        f"body{{font-family:{FONT_STACK};background:var(--surface-2);color:var(--text);"
        "line-height:1.65;-webkit-font-smoothing:antialiased;"
        # 17px, not 16: Arabic at 16 on a phone reads cramped, and this page is read once by
        # someone who is not trying very hard.
        "font-size:17px}"
        ".wrap{max-width:34rem;margin:0 auto;padding:0 1.15rem 3rem}"
        # ── the header: the shop's, entirely ──────────────────────────────────────────────
        ".hd{background:var(--accent);color:var(--accent-ink);padding:2.6rem 1.15rem 2.2rem;"
        "text-align:center}"
        ".hd h1{font-size:1.5rem;font-weight:650;letter-spacing:-.01em}"
        ".hd p{opacity:.82;font-size:.95rem;margin-top:.35rem}"
        ".logo{width:64px;height:64px;border-radius:18px;object-fit:cover;margin:0 auto .9rem;"
        "display:block;background:var(--accent-soft)}"
        # ── cards ─────────────────────────────────────────────────────────────────────────
        ".card{background:var(--surface);border:1px solid var(--border);border-radius:16px;"
        "padding:1.15rem 1.25rem;margin-top:1.15rem}"
        ".card h2{font-size:1.05rem;font-weight:640;margin-bottom:.2rem}"
        ".card .sub{color:var(--text-muted);font-size:.9rem;margin-bottom:.9rem}"
        # ── the switches ──────────────────────────────────────────────────────────────────
        ".row{display:flex;align-items:flex-start;gap:.9rem;padding:.85rem 0;"
        "border-top:1px solid var(--border)}"
        ".row:first-of-type{border-top:0}"
        ".row .t{flex:1;min-width:0}"
        ".row .t b{display:block;font-weight:600;font-size:1rem}"
        ".row .t span{color:var(--text-muted);font-size:.86rem}"
        # A real checkbox, restyled. Not a div pretending: a checkbox is focusable, announced by a
        # screen reader, and submits with the form when the script does not run.
        ".sw{position:relative;flex:0 0 auto;width:52px;height:31px;margin-top:.15rem}"
        ".sw input{position:absolute;inset:0;opacity:0;width:100%;height:100%;margin:0;"
        "cursor:pointer;z-index:2}"
        ".sw i{position:absolute;inset:0;background:#D1D5DB;border-radius:99px;"
        "transition:background .18s ease}"
        ".sw i::after{content:'';position:absolute;top:3px;right:3px;width:25px;height:25px;"
        "background:#fff;border-radius:50%;transition:transform .18s ease;"
        "box-shadow:0 1px 3px rgba(0,0,0,.28)}"
        ".sw input:checked + i{background:var(--accent)}"
        # RTL: the knob travels LEFT when on, because the track is read right to left.
        ".sw input:checked + i::after{transform:translateX(-21px)}"
        ".sw input:focus-visible + i{outline:2px solid var(--accent);outline-offset:2px}"
        # ── visits ────────────────────────────────────────────────────────────────────────
        ".v{display:flex;justify-content:space-between;gap:1rem;padding:.7rem 0;"
        "border-top:1px solid var(--border)}"
        ".v:first-of-type{border-top:0}"
        ".v .d{color:var(--text-muted);font-size:.88rem;white-space:nowrap}"
        ".muted{color:var(--text-muted);font-size:.92rem}"
        ".btn{display:block;width:100%;padding:.95rem;border:0;border-radius:12px;"
        "background:var(--accent);color:var(--accent-ink);font:inherit;font-weight:620;"
        "cursor:pointer;margin-top:1.15rem}"
        ".btn:disabled{opacity:.55}"
        ".ok{background:var(--accent-soft);color:var(--accent-soft-ink);border-radius:12px;"
        "padding:.8rem 1rem;margin-top:1rem;font-size:.93rem}"
        "@media(prefers-color-scheme:dark){"
        "body{background:#0B0F14;color:#E5E7EB}"
        ".card{background:#141A21;border-color:#232C36}"
        ".row,.v{border-color:#232C36}}"
    )


def render_page(page: Page, theme: Theme, *, saved: bool = False,
                logo_url: str = "") -> str:
    """The whole document.

    Returns a string rather than writing to a template engine: there is one page on this service,
    it is small, and a template file would be a second place to look for the same markup.
    """
    shop = page.shop_name or "متجرك"
    parts: list[str] = [
        "<!doctype html><html lang='ar' dir='rtl'><head>",
        "<meta charset='utf-8'>",
        # `viewport-fit=cover` so the header colour reaches the notch rather than leaving a white
        # band above the shop's brand.
        "<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>",
        f"<meta name='theme-color' content='{_e(theme.accent)}'>",
        # NOT INDEXED. This page is one customer's relationship with one shop; a search engine
        # holding it is a disclosure with no upside to anybody.
        "<meta name='robots' content='noindex,nofollow,noarchive'>",
        # NO REFERRER. The reference is in the URL, and a link out would hand it to whoever is on
        # the other side.
        "<meta name='referrer' content='no-referrer'>",
        # THE TITLE IS THE SHOP'S NAME AND NOTHING ELSE. It is what shows in a screenshot and in a
        # browser's history — a customer's name here would be the leak this whole design avoids.
        f"<title>{_e(shop)}</title>",
        f"<style>{_css(theme)}</style>",
        "</head><body>",
    ]

    # ── the shop's header ─────────────────────────────────────────────────────────────────
    parts.append("<header class='hd'>")
    if logo_url:
        parts.append(f"<img class='logo' src='{_e(logo_url)}' alt='' loading='lazy' "
                     "width='64' height='64'>")
    parts.append(f"<h1>{_e(shop)}</h1>")
    parts.append("<p>صفحتك لدى المتجر</p></header>")
    parts.append("<div class='wrap'>")

    if saved:
        parts.append("<div class='ok'>تم حفظ تفضيلاتك.</div>")

    # ── the switches ──────────────────────────────────────────────────────────────────────
    parts.append("<section class='card'><h2>الرسائل التي تصلك</h2>"
                 "<p class='sub'>أوقف ما لا يناسبك. القرار قرارك في أي وقت.</p>")
    if page.prefs.available:
        parts.append(f"<form method='post' action='/p/{_e(page.reference)}/prefs'>")
        for s in page.prefs.data:
            checked = " checked" if s["enabled"] else ""
            parts.append(
                "<label class='row'>"
                f"<span class='t'><b>{_e(s['label'])}</b><span>{_e(s['hint'])}</span></span>"
                f"<span class='sw'><input type='checkbox' name='on' "
                f"value='{_e(s['class'])}'{checked}><i></i></span>"
                "</label>")
        parts.append("<button class='btn' type='submit'>حفظ</button></form>")
    else:
        # HONEST, AND READ-ONLY. Rendering togglable switches whose save will fail is worse than
        # saying the setting cannot be reached right now.
        parts.append("<p class='muted'>تعذّر تحميل تفضيلاتك الآن. حاول بعد قليل — "
                     "لم يتغيّر شيء.</p>")
    parts.append("</section>")

    # ── the visits ────────────────────────────────────────────────────────────────────────
    parts.append("<section class='card'><h2>زياراتك</h2>")
    if not page.visits.available:
        parts.append("<p class='muted'>تعذّر تحميل سجلّ زياراتك الآن.</p>")
    elif not page.visits.data:
        parts.append("<p class='muted'>لا زيارات مسجّلة بعد.</p>")
    else:
        for v in page.visits.data[:10]:
            parts.append(f"<div class='v'><span>{_e(v.get('services') or 'زيارة')}</span>"
                         f"<span class='d'>{_e(v.get('date') or '')}</span></div>")
    parts.append("</section>")

    parts.append("</div>")

    # THE ONLY SCRIPT, AND THE PAGE WORKS WITHOUT IT. It submits the form when a switch changes so
    # a customer does not have to find the button — but the button is there, and a failed script
    # leaves a form that still submits.
    parts.append(
        "<script>document.querySelectorAll('.sw input').forEach(function(i){"
        "i.addEventListener('change',function(){var f=i.closest('form');"
        "if(f){f.querySelector('.btn').disabled=true;f.submit();}})});</script>")

    parts.append("</body></html>")
    return "".join(parts)
