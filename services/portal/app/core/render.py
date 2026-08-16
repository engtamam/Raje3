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


def _when(epoch: int) -> str:
    """A date a person reads, in Riyadh's hours and in WESTERN DIGITS.

    Not the browser's locale: the shop is in Saudi Arabia and so is the offer's deadline, and a
    customer whose phone is set to another timezone must not be told his offer ends a day later
    than the shop believes. The countdown beside it works from the absolute moment and agrees.
    """
    import datetime as _dt

    riyadh = _dt.timezone(_dt.timedelta(hours=3))
    t = _dt.datetime.fromtimestamp(int(epoch), riyadh)
    return t.strftime("%Y-%m-%d · %H:%M")


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
        # A SECOND, QUIETER BUTTON. These two ask for something rather than saving a
        # preference, and giving them the same weight as «حفظ» would make the page look
        # like it is urging him to leave.
        ".btn.ghost{background:transparent;color:var(--text);border:1px solid var(--border);margin-inline-end:.5rem;margin-top:.4rem}"
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
        # ── his offers: the reason most people open this link ─────────────────────────────
        #
        # THE ONE CARD THAT IS ALLOWED TO LOOK EXPENSIVE. Everything else on this page is a
        # setting or a record; this is the thing he was sent here for, and a shop that discounts
        # something and then shows it in the same grey box as a checkbox has undersold itself.
        #
        # THE SHOP'S OWN COLOUR CARRIES IT — a tint, a hairline and a soft glow, all derived from
        # `--accent`. No second palette, so a workshop in green and a salon in rose each get a card
        # that looks made for them rather than one we painted.
        # The offers heading sits OUTSIDE a card — the cards below it are the offers themselves,
        # and wrapping a card in a card is how a page starts looking like a form.
        ".ttl{font-size:1.05rem;font-weight:640;margin:1.5rem 0 .2rem}"
        ".offer{position:relative;overflow:hidden;background:var(--surface);"
        "border:1px solid var(--accent);border-radius:18px;padding:1.2rem 1.25rem 1.1rem;"
        "margin-top:.85rem;box-shadow:0 10px 30px -18px var(--accent)}"
        # The tint sits behind the text rather than on it, so the words keep full contrast.
        ".offer::before{content:'';position:absolute;inset:0;background:var(--accent);"
        "opacity:.07;pointer-events:none}"
        ".offer > *{position:relative}"
        ".offer .txt{font-size:1.18rem;font-weight:640;line-height:1.5}"
        ".offer .code{margin-top:.5rem;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;"
        "font-size:1.05rem;letter-spacing:.16em;color:var(--accent-on-soft);"
        "background:var(--accent-soft);border-radius:.5rem;padding:.35rem .6rem;"
        "display:inline-block}"
        ".offer .scope{color:var(--text-muted);font-size:.88rem;margin-top:.35rem}"
        # ── the countdown ─────────────────────────────────────────────────────────────────
        # Four cells, largest first in reading order. `tabular-nums` so the width does not shiver
        # every second — a number that jitters reads as broken rather than as live.
        ".cd{display:flex;gap:.5rem;margin-top:.95rem;direction:ltr;justify-content:flex-end}"
        ".cd div{flex:0 0 3.4rem;text-align:center;background:var(--accent-soft);"
        "color:var(--accent-soft-ink);border-radius:11px;padding:.45rem .2rem}"
        ".cd b{display:block;font-size:1.22rem;font-weight:680;font-variant-numeric:tabular-nums;"
        "line-height:1.15}"
        ".cd span{font-size:.7rem;opacity:.75}"
        # The plain date, for a phone whose script did not run. Hidden only once the countdown
        # has actually rendered — never before, or a failed script leaves no end date at all.
        ".cd-fallback{color:var(--text-muted);font-size:.88rem;margin-top:.7rem}"
        ".offer.live .cd-fallback{display:none}"
        # ── visits ────────────────────────────────────────────────────────────────────────
        ".v{display:flex;justify-content:space-between;gap:1rem;padding:.7rem 0;"
        "border-top:1px solid var(--border)}"
        ".v:first-of-type{border-top:0}"
        ".v .d{color:var(--text-muted);font-size:.88rem;white-space:nowrap}"
        ".v .b{color:var(--text-muted);font-size:.88rem}"
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
                logo_url: str = "", asked: str = "") -> str:
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

    # ── his offers, FIRST ─────────────────────────────────────────────────────────────────
    #
    # ABOVE THE SWITCHES AND ABOVE THE VISITS, because it is why he opened the link. He arrived
    # from a message that offered him something; a page that puts a notification setting where the
    # offer should be makes him scroll to find what he was promised, and some of them do not.
    #
    # AND THE SECTION IS ABSENT WHEN HE HAS NOTHING — no empty card, no "you have no offers".
    # Telling somebody he has been given nothing is a worse page than not raising it at all.
    # ── «AN UNAVAILABLE OFFERS SECTION SAYS SO» — and it never did ────────────────────────────
    #
    # `compose.py` promises exactly that, in writing, next to the field: the section «does not
    # pretend he has none». This file then had one branch — available AND non-empty — so an offers
    # read that FAILED rendered the same page as a customer who was sent nothing.
    #
    # He opened the link from a message that offered him something. A page with no offer on it
    # tells him the offer was not real, and he does not come back to check whether a service was
    # briefly down.
    if page.offers.failed:
        parts.append("<section><h2 class='ttl'>عروضك الحصرية</h2>"
                     "<p class='sub'>تعذّر عرض عروضك الآن — والخلل عندنا لا عندك. "
                     "افتح الرابط بعد قليل، وعروضك كما هي.</p></section>")
    if page.offers.available and page.offers.data:
        parts.append("<section><h2 class='ttl'>عروضك الحصرية</h2>"
                     "<p class='sub'>وصلتك أنت. اذكرها عند الزيارة.</p>")
        for o in page.offers.data:
            parts.append(f"<article class='offer' data-until='{int(o['expires_at'])}'>")
            parts.append(f"<p class='txt'>{_e(o['text'])}</p>")
            # WHAT IT COVERS, in words. "The whole shop" is a real answer and a good one; leaving
            # it blank would make the most generous offer look like the least specified.
            if o["services"]:
                names = "، ".join(_e(s) for s in o["services"][:4])
                parts.append(f"<p class='scope'>على: {names}</p>")
            elif o.get("scoped"):
                # NAMED AS LIMITED WITHOUT NAMING THE SERVICES. Saying «كل الخدمات» here would
                # promise him the whole shop over a missing word, and he would find that out at
                # the counter, in front of somebody who has to refuse him.
                parts.append("<p class='scope'>على خدمات محدّدة — اسأل عند الزيارة</p>")
            else:
                parts.append("<p class='scope'>على كل الخدمات</p>")
            # THE CODE, BIG ENOUGH TO READ FROM A PHONE HELD AT ARM'S LENGTH across a counter.
            # `dir=ltr` because it is Latin and digits: without it the dash and the letters swap
            # sides, and he reads it back across the counter in the wrong order.
            if o.get("code"):
                parts.append(f"<p class='code' dir='ltr'>{_e(o['code'])}</p>")
            # The countdown's cells, and beneath them the plain date for a device with no script.
            #
            # THE WORD "device" RATHER THAN THE OBVIOUS ONE IS NOT AN ACCIDENT. A trap in this
            # service reads this function's SOURCE and refuses any mention of an identifying
            # field — it caught this comment, which is exactly the bluntness that makes it work.
            # Weakening the trap to allow a word in prose would be trading a real guard for a
            # sentence.
            parts.append(
                "<div class='cd'>"
                "<div><b>--</b><span>ثانية</span></div>"
                "<div><b>--</b><span>دقيقة</span></div>"
                "<div><b>--</b><span>ساعة</span></div>"
                "<div><b>--</b><span>يوم</span></div>"
                "</div>")
            parts.append(f"<p class='cd-fallback'>ينتهي: {_e(_when(o['expires_at']))}</p>")
            parts.append("</article>")
        parts.append("</section>")

    # ── his points, AFTER the offers and BEFORE the switches ──────────────────────────────
    #
    # AFTER, because an offer is a thing he already has and points are a thing he is working
    # towards — the first is why he opened the link, the second is why he comes back. BEFORE the
    # switches for the same reason the offers are: a notification setting is not what anybody
    # opened this page to read.
    #
    # ABSENT ENTIRELY FOR A SHOP WITH NO PROGRAMME. A points card reading zero on a page belonging
    # to a shop that runs no loyalty is a promise nobody made, and the customer would ask about it
    # at the counter.
    if page.points.available and page.points.data:
        pts = page.points.data
        parts.append("<section class='card'><h2>نقاطك</h2>")
        parts.append(f"<p class='big'>{int(pts.get('points') or 0)} <span>نقطة</span></p>")

        rewards = list(pts.get("rewards") or [])
        if rewards:
            # ONLY WHAT HE CAN AFFORD — the service filtered before answering. Listing what he
            # cannot reach turns his own page into a display of things withheld from him.
            parts.append("<p class='sub'>تقدر تستبدلها الآن — اطلبها عند زيارتك:</p><ul class='rw'>")
            for r in rewards[:6]:
                parts.append(f"<li>{_e(str(r.get('name') or ''))}"
                             f" <b>{int(r.get('cost') or 0)} نقطة</b></li>")
            parts.append("</ul>")
        elif int(pts.get("to_next_reward") or 0) > 0:
            # ENCOURAGEMENT ONLY WHEN IT IS TRUE. Zero means he can afford everything, or the shop
            # has no rewards at all — and «تبقى لك 0» is a sentence that means nothing.
            parts.append(f"<p class='sub'>باقي لك {int(pts['to_next_reward'])} نقطة"
                         f" لأقرب مكافأة.</p>")
        parts.append("</section>")

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
            # THE BRANCH BESIDE THE SERVICE, and ONLY when the row carries one. A shop with a
            # single branch records none, and «الفرع الرئيسي» on all ten rows of a one-branch shop
            # is a label that says nothing ten times — which is how a reader learns to skip the
            # line the useful half also lives on.
            branch = _e(v.get('branch') or '')
            where = f" <span class='b'>· {branch}</span>" if branch else ""
            parts.append(f"<div class='v'><span>{_e(v.get('services') or 'زيارة')}{where}</span>"
                         f"<span class='d'>{_e(v.get('date') or '')}</span></div>")
    parts.append("</section>")

    # ── his data, and what he can ask for ─────────────────────────────────────────────────
    #
    # THE RIGHT EXISTS WHETHER OR NOT THE PAGE OFFERS IT, and a right nobody is told about is not
    # one. The PDPL gives him access to his data and its erasure, and it gives them AGAINST THE
    # SHOP — not against us — so the page asks the shop, plainly, in the same place the rest of his
    # relationship with it lives.
    #
    # LAST ON THE PAGE. He came for his offer and his points; this is the paragraph he reads once
    # in his life, on the day he wants it, and it must be findable rather than prominent.
    #
    # NO CONFIRMATION DIALOG, AND NOTHING IS DESTROYED BY THE TAP. It records a request his shop
    # answers — see operations — so the cost of a mistaken tap is a message to the workshop, not a
    # deleted history. A confirm step here would be theatre.
    parts.append("<section class='card'><h2>بياناتك</h2>"
                 "<p class='sub'>بياناتك لدى هذا المتجر ملكك. تقدر تطلب نسخة منها، أو تطلب "
                 "حذفها — والمتجر هو من ينفّذ الطلب، ويصلك رده.</p>")
    if asked:
        parts.append(f"<p class='ok'>{_e(asked)}</p>")
    parts.append(f"<form method='post' action='/p/{_e(page.reference)}/data'>"
                 "<button class='btn ghost' type='submit' name='ask' value='export'>"
                 "اطلب نسخة من بياناتي</button>"
                 "<button class='btn ghost' type='submit' name='ask' value='erase'>"
                 "اطلب حذف بياناتي</button></form>")
    parts.append("<p class='muted'>الحذف نهائي: تختفي زياراتك ونقاطك ورسائلك لدى هذا المتجر. "
                 "وتبقى الفواتير التي يلزم النظام بحفظها.</p>")
    parts.append("</section>")

    parts.append("</div>")

    # THE ONLY SCRIPT, AND THE PAGE WORKS WITHOUT IT. It submits the form when a switch changes so
    # a customer does not have to find the button — but the button is there, and a failed script
    # leaves a form that still submits.
    parts.append(
        "<script>document.querySelectorAll('.sw input').forEach(function(i){"
        "i.addEventListener('change',function(){var f=i.closest('form');"
        "if(f){f.querySelector('.btn').disabled=true;f.submit();}})});</script>")

    # ── the countdown ─────────────────────────────────────────────────────────────────────
    #
    # THE DEADLINE CAME FROM THE SERVER AS A MOMENT, and this only renders the distance to it. A
    # duration computed on the server would be wrong the second the page was read, and one the
    # customer could extend by changing his device's clock would be worse — the arithmetic is
    # local, the truth is not.
    #
    # AND AN OFFER THAT RUNS OUT WHILE HE LOOKS AT IT SAYS SO. Leaving 00:00:00 on the screen is a
    # page arguing with the man behind the counter he is standing in front of.
    parts.append(
        "<script>(function(){var c=document.querySelectorAll('.offer[data-until]');"
        "if(!c.length)return;function pad(n){return n<10?'0'+n:''+n}"
        "function tick(){c.forEach(function(o){"
        "var left=(+o.dataset.until)-Math.floor(Date.now()/1000);"
        "var b=o.querySelectorAll('.cd b');if(b.length<4)return;"
        "if(left<=0){o.querySelector('.cd').remove();"
        "var p=o.querySelector('.cd-fallback');if(p)p.textContent='انتهى هذا العرض';"
        "o.classList.remove('live');return}"
        "var d=Math.floor(left/86400),h=Math.floor(left%86400/3600),"
        "m=Math.floor(left%3600/60),s=left%60;"
        "b[0].textContent=pad(s);b[1].textContent=pad(m);b[2].textContent=pad(h);"
        "b[3].textContent=d;o.classList.add('live')})}"
        "tick();setInterval(tick,1000)})();</script>")

    parts.append("</body></html>")
    return "".join(parts)
