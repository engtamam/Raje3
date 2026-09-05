"""One screen, one sentence, one button — the only thing this service serves.

WHY THIS FILE EXISTS. The full customer page (points, visits, preferences, DSAR buttons) has been
deleted outright — a product of its own, and not one worth carrying forward half-built. Deleting it
would take the marketing consent path down with it if these two screens were part of it, and
consent is not decoration: without a grant NO marketing message may leave, so no page means the
campaigns engine — which is built, complete and paid for — sends nothing at all, forever.

So two screens survive the page's deletion, and they are the two that carry a legal obligation:

    GET  /p/{ref}/allow    ask, in one screen
    POST /p/{ref}/allow    record the grant
    GET  /p/{ref}/stop     withdraw, in one tap (spec §8.3)

WHY NOT A LINK THAT GRANTS ON TAP. It would be one fewer tap and it would not be consent. A tap on
a link in a message is evidence that a link was tapped — by the person, by their phone's preview
fetcher, or by whoever the message was forwarded to. PDPL asks for a prior, informed, positive act,
and Meta's own policy asks the same. A screen with the sentence and a button is the smallest thing
that is actually an act, and it is still under two seconds.

AND THE SENTENCE SHOWN IS THE SENTENCE RECORDED. reminders stores the exact text with its version
at the moment of granting (core/consent.py `statement_for`), so if this screen showed a different
wording the record would attest to words the customer never read. That is the failure this file is
most able to cause and least able to notice, so STATEMENT below is byte-identical to theirs and a
gate compares them: ci/check_the_consent_sentence_shown_is_the_sentence_recorded.py.

NO TRACE OF US, same as the full page (spec §8.6.1). The shop's name, the shop's colour, and no
mention of the product anywhere.
"""
from __future__ import annotations

from app.core.render import FONT_STACK, _e
from app.core.theme import Theme

# BYTE-IDENTICAL TO reminders' `core/consent.py`. Not imported: these are two services with two
# images and no shared package, and a copy that drifts is caught by a gate rather than trusted.
STATEMENT = (
    "أوافق على استقبال عروض {shop} على واتساب. "
    "أربع رسائل شهرياً على الأكثر، ويمكنني الإيقاف بضغطة في أي وقت."
)


def statement_for(shop: str) -> str:
    """The sentence, with the shop named. Same fallback as theirs, for the same reason: consent
    given to nobody in particular is the ambiguity that makes a bought list look lawful."""
    return STATEMENT.format(shop=shop or "المنشأة")


def _css(theme: Theme) -> str:
    """Small enough to read in one screen, and inlined for the same reason the full page inlines
    its own: this is opened from WhatsApp on one bar of signal, and a second request is a round
    trip before anything appears."""
    return (
        f":root{{{theme.css_variables()}}}"
        f"*{{box-sizing:border-box}}"
        f"body{{margin:0;font-family:{FONT_STACK};background:var(--surface);"
        f"color:var(--text);min-height:100vh;display:flex;align-items:center;"
        f"justify-content:center;padding:24px}}"
        ".card{max-width:420px;width:100%;text-align:center}"
        ".logo{width:64px;height:64px;border-radius:16px;object-fit:cover;margin:0 auto 16px}"
        "h1{font-size:20px;margin:0 0 8px;font-weight:700}"
        "p{font-size:16px;line-height:1.7;margin:0 0 20px;color:var(--text-muted)}"
        ".say{color:var(--text);background:var(--surface-2);border:1px solid var(--border);"
        "border-radius:12px;padding:14px;font-size:15px;line-height:1.8}"
        # THE BUTTON IS THUMB-SIZED AND FULL WIDTH. This is opened one-handed, standing up, and a
        # target somebody has to aim at is a target somebody misses and gives up on.
        "button{width:100%;padding:16px;font-size:17px;font-weight:700;border:0;"
        "border-radius:14px;background:var(--accent);color:var(--accent-ink);cursor:pointer;"
        f"font-family:{FONT_STACK}}}"
        ".ok{color:var(--accent);font-weight:700}"
    )


def render_one_screen(*, shop_name: str, theme: Theme, headline: str, body: str,
                      logo_url: str = "", say: str = "", action: str = "",
                      action_label: str = "") -> str:
    """The whole document. No JavaScript at all — the button is a form submit, so it works on a
    browser with scripting off and on a preview pane that renders no scripts."""
    shop = shop_name or "متجرك"
    parts: list[str] = [
        "<!doctype html><html lang='ar' dir='rtl'><head>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>",
        f"<meta name='theme-color' content='{_e(theme.accent)}'>",
        "<meta name='robots' content='noindex,nofollow,noarchive'>",
        "<meta name='referrer' content='no-referrer'>",
        f"<title>{_e(shop)}</title>",
        f"<style>{_css(theme)}</style>",
        "</head><body><div class='card'>",
    ]
    if logo_url:
        parts.append(f"<img class='logo' src='{_e(logo_url)}' alt='' width='64' height='64'>")
    parts.append(f"<h1>{_e(headline)}</h1>")
    if body:
        parts.append(f"<p>{_e(body)}</p>")
    if say:
        parts.append(f"<p class='say'>{_e(say)}</p>")
    if action and action_label:
        # POST, because this one changes state and is not the annoyed customer's exit. The rule
        # that lets `/stop` be a GET — a prefetcher firing it only ever sends FEWER messages —
        # inverts here: a prefetched grant would be a consent nobody gave.
        parts.append(f"<form method='post' action='{_e(action)}'>"
                     f"<button type='submit'>{_e(action_label)}</button></form>")
    parts.append("</div></body></html>")
    return "".join(parts)
