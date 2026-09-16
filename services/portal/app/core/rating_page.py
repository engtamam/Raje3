"""The hosted rating page's own form — [[task-service-procedure-checklists]] phase 2.

WHY THIS EXISTS, SEPARATE FROM `onescreen.py`. That file's `render_one_screen` is exactly what its
own docstring says: one sentence and one button. This screen asks for a star rating, an optional
checklist of what went wrong, and an optional comment — a real form, not a single tap — so it gets
its own small renderer rather than stretching `render_one_screen` into something it was never
built to be.

NO JAVASCRIPT, SAME RULE AS THE REST OF THIS SERVICE. Every control here is a native HTML input;
the one rule the customer cannot break by hand (5 stars + a flagged problem is a contradiction —
see the owner's own instruction, 2026-09-16) is enforced SERVER-SIDE, on submit, not client-side —
this page must still work with scripting off, on a preview pane, on a slow connection with one bar
of signal in a workshop.

NEGATIVE SELECTION (the checklist). Nothing checked means nothing was wrong — the ordinary case,
never something the customer has to affirm. See `ProcedureStep`'s own docstring
(services/operations/app/core/models.py) for the full design this page is the front end of.
"""
from __future__ import annotations

from app.core.render import FONT_STACK, _e
from app.core.theme import Theme

STARS = (5, 4, 3, 2, 1)


def _css(theme: Theme) -> str:
    return (
        f":root{{{theme.css_variables()}}}"
        f"*{{box-sizing:border-box}}"
        f"body{{margin:0;font-family:{FONT_STACK};background:var(--surface);"
        f"color:var(--text);min-height:100vh;padding:24px 16px}}"
        ".card{max-width:480px;width:100%;margin:0 auto}"
        ".logo{width:56px;height:56px;border-radius:14px;object-fit:cover;margin:0 auto 12px;"
        "display:block}"
        "h1{font-size:19px;margin:0 0 4px;font-weight:700;text-align:center}"
        "p.sub{font-size:14px;color:var(--text-muted);text-align:center;margin:0 0 20px}"
        ".err{background:var(--accent-soft);color:var(--accent-soft-ink);border-radius:12px;"
        "padding:12px 14px;font-size:14px;line-height:1.7;margin:0 0 16px}"
        "fieldset{border:1px solid var(--border);border-radius:14px;padding:14px;margin:0 0 16px}"
        "legend{font-size:14px;font-weight:700;padding:0 6px}"
        # STARS AS A ROW OF BIG, EQUAL TAP TARGETS — a radio group styled as buttons, no JS: the
        # checked state alone is what `:checked + label` reads to show which one is selected.
        ".stars{display:flex;flex-direction:row-reverse;gap:8px;justify-content:center}"
        ".stars input{position:absolute;opacity:0;width:1px;height:1px}"
        ".stars label{flex:1;text-align:center;padding:12px 0;border-radius:10px;"
        "border:1px solid var(--border);font-size:20px;cursor:pointer;user-select:none}"
        ".stars input:checked + label{background:var(--accent);border-color:var(--accent);"
        "color:var(--accent-ink)}"
        ".step{display:flex;align-items:flex-start;gap:10px;padding:10px 2px;font-size:15px;"
        "line-height:1.6;border-bottom:1px solid var(--border)}"
        ".step:last-child{border-bottom:0}"
        ".step input{width:20px;height:20px;flex-shrink:0;margin-top:2px}"
        "textarea{width:100%;border:1px solid var(--border);border-radius:12px;padding:12px;"
        f"font-size:15px;font-family:{FONT_STACK};color:var(--text);background:var(--surface-2);"
        "resize:vertical;min-height:80px}"
        "button{width:100%;padding:16px;font-size:17px;font-weight:700;border:0;"
        "border-radius:14px;background:var(--accent);color:var(--accent-ink);cursor:pointer;"
        f"font-family:{FONT_STACK};margin-top:4px}}"
    )


def render_rating_form(*, shop_name: str, theme: Theme, action: str, logo_url: str = "",
                       service_names: list[str] | None = None,
                       steps: list[dict] | None = None,
                       error: str = "", selected_stars: int = 0,
                       selected_step_ids: list[str] | None = None,
                       comment: str = "") -> str:
    """The form itself. `selected_stars`/`selected_step_ids`/`comment` carry the customer's OWN
    answers back when re-rendering after a validation error — losing his selections on a refused
    submit is its own small cruelty on top of the refusal."""
    shop = shop_name or "المتجر"
    selected_step_ids = selected_step_ids or []
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
        parts.append(f"<img class='logo' src='{_e(logo_url)}' alt='' width='56' height='56'>")
    parts.append(f"<h1>كيف كانت زيارتك في {_e(shop)}؟</h1>")
    if service_names:
        parts.append(f"<p class='sub'>{_e('، '.join(service_names))}</p>")
    if error:
        parts.append(f"<p class='err'>{_e(error)}</p>")

    parts.append(f"<form method='post' action='{_e(action)}'>")
    parts.append("<fieldset><legend>تقييمك</legend><div class='stars'>")
    for n in STARS:
        checked = " checked" if selected_stars == n else ""
        parts.append(f"<input type='radio' name='stars' id='star{n}' value='{n}'{checked} "
                    f"required>"
                    f"<label for='star{n}'>{'⭐' * n}</label>")
    parts.append("</div></fieldset>")

    if steps:
        parts.append("<fieldset><legend>هل واجهت أي مشكلة؟ (اختياري)</legend>")
        for s in steps:
            sid = str(s.get("id") or "")
            text = str(s.get("text") or "")
            checked = " checked" if sid in selected_step_ids else ""
            parts.append(f"<label class='step'><input type='checkbox' name='issue' "
                        f"value='{_e(sid)}'{checked}>{_e(text)}</label>")
        parts.append("</fieldset>")

    parts.append("<fieldset><legend>ملاحظاتك (اختياري)</legend>"
                f"<textarea name='comment' maxlength='2000'>{_e(comment)}</textarea></fieldset>")
    parts.append("<button type='submit'>إرسال</button></form>")
    parts.append("</div></body></html>")
    return "".join(parts)
