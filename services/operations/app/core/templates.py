"""The message-template library — platform content, edited at runtime.

CONTENT, NOT CODE, AND FOR A REASON. The first version of the library lived in a
document: changing a word meant editing the spec, rebuilding an image, and rolling a service. That
is not a library, it is a constant. Templates are content our own people revise — a wording that
reads badly, a cycle that changed, a Meta rejection that needs different phrasing — and content
that needs a deploy is content that does not get revised.

So the templates live in the datastore, edited through the platform console
(/api/v1/platform/templates, capability `platform.operations`), and the JSON file is applied ONCE
when the table is empty. Re-applying it on every boot would silently undo an operator's edits.

PLATFORM-SCOPED. One library for the whole product, under the reserved `_platform` tenant. An
establishment does not get to rewrite "خدمة أخرى" for everybody else — and more importantly, the
text being OURS is the entire reason the four-class taxonomy is honest (spec §8.4.1). If a shop
could write its own template under a low-friction class, the first one to notice would reclassify
its advertising as something else, and we would have built the loophole ourselves.

WHAT THIS IS NOT. It is not the per-tenant WhatsApp registry — notification-service owns that,
including submission to Meta and the approval sweep. This is the CURATED SET we push into a
tenant's registry when they connect, and the place we edit it before we do.
"""
# arabic-indic-digits: intentional — named in a refusal message, as the shape we do NOT accept.
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

TEMPLATES = "templates"
PLATFORM = "_platform"

# The four regulatory classes (spec §8.4.1). The class decides the rules, so it is validated
# rather than accepted: a template in the wrong class carries the wrong constraints, and an
# account notice filed as "service" looks stoppable and countable when it is neither.
CLASSES = ("service", "personal", "warning", "marketing")
TONES = ("masculine", "feminine")
# Meta's categories. Ours map onto these, and getting it wrong means Meta re-categorises and
# bills at the marketing rate.
CATEGORIES = ("UTILITY", "MARKETING", "AUTHENTICATION")
# Where a variable's value comes from. Only `owner` is a blank page — see upsert().
#
# AND TWO OF THEM ARE TYPED, DELIBERATELY. `amount` and `date` were `owner` free text until an
# offer template made the cost visible: an owner writing «خصم كبير» promises nothing a customer can
# hold us to, «٢٠٪» arrives in digits half our own screens refuse, and a discount with no end is a
# discount for ever. A typed slot is validated at send (reminders/rendering.py) and phrased by us,
# so the sentence reads the same in every shop. `code` USED TO BE A THIRD — `per_dsar_code`'s own
# verification-code slot, deleted with the template itself (2026-09-13): opening that request
# required a Raje3-internal admin screen, which meant a customer had to contact Raje3 directly, a
# line this product does not cross. Nothing fills `code` any more.
# `invite` and `stop_link` carry an ADDRESS rather than a word, and each is the last blank of
# its class: `stop_link` on marketing (the one-tap stop §8.3 makes mandatory), `invite` on
# everything else (the only door marketing consent can come through). See ci/gen_templates.py.
# `establishment` USED TO BE A THIRD — `per_weekly_digest`'s own owner-name slot, deleted with the
# template itself (2026-09-13, the weekly report feature removed entirely). Nothing fills
# `establishment` any more.
FILLS = ("system", "catalogue", "owner", "amount", "date", "invite", "stop_link",
        "rating_cta")
# WHICH REMINDER MODEL A TEMPLATE SERVES (spec 16.6.5). Not a second taxonomy competing with the
# five classes: the class says what a message IS to the regulator, the model says which kind of
# business it is FOR. A cafe customer returns in days and there is no such thing as "time for your
# coffee"; a workshop customer returns in months and the cycle is the entire product.
MODELS = ("cycle", "loyalty", "both")

# WHICH META COMPONENT SHAPE ONE ROW REGISTERS AS (2026-09-13). "plain" is every template that
# predates this field and every one that never needs a photo; "photo_button" is the single-item
# quick-reply-button variant (core/shape.py's own BUTTON_TYPES) — a media HEADER plus a flat
# BUTTON, registered under its own name because Meta fixes a template's components at approval.
SHAPES = ("plain", "photo_button")


class TemplateError(Exception):
    """A refusal a console user can act on."""


class TemplateLibrary:
    def __init__(self, store) -> None:
        self._s = store

    # ── reads ─────────────────────────────────────────────────────────────────────────────────
    async def list(self, *, cls: str = "", tone: str = "",
                    active_only: bool = True) -> list[dict[str, Any]]:
        """The platform library.

        DEFAULTS TO ACTIVE, DELIBERATELY — the same convention as `ServiceStore.list`. A retired
        template is still in this table (see `deactivate`: we never delete, because an
        establishment's registry and Meta's approval both still name it), so the naive `list()`
        used to hand a caller who never thought about the question every retired row along with the
        live ones. Two publish paths did exactly that: they pushed 66 rows at Meta's 100/hour cap
        when 40 were dead text nobody chose, and the human reviewer saw wording we had pulled.
        Filtering had to be the accident-proof direction — a caller that genuinely wants the
        inactive rows (the platform console, managing the library) asks for them explicitly with
        `active_only=False`.
        """
        where: dict[str, Any] = {"tenant": PLATFORM}
        if cls:
            where["class"] = cls
        if tone:
            where["tone"] = tone
        rows, _ = await self._s.find(TEMPLATES, where, limit=500, sort=("name", "asc"))
        if active_only:
            rows = [r for r in rows if r.get("active", True)]
        return rows

    async def get(self, name: str) -> dict[str, Any] | None:
        return await self._s.get(TEMPLATES, f"{PLATFORM}|{name}")

    async def for_model(self, model: str, *, active_only: bool = True) -> list[dict[str, Any]]:
        """The set an establishment of this kind should have switched on at signup.

        `both` is always included: a confirmation and a receipt are the same message in any
        business. The rest is the shop's own half — and the other half is NOT hidden from the
        console, only left off with its reason attached, because a shop that is genuinely both a
        workshop and a cafe exists and must be able to say so.
        """
        if model not in MODELS:
            raise TemplateError(f"unknown model {model!r} — one of {list(MODELS)}")
        rows = await self.list(active_only=active_only)
        return [t for t in rows if t.get("model", "both") in (model, "both")]

    async def for_tone(self, tone: str) -> list[dict[str, Any]]:
        """The set an establishment gets when it picks a tone.

        One choice, twenty-one templates. The owner is not asked forty-two times — that is a
        form, not a feature (spec §10.8).
        """
        if tone not in TONES:
            raise TemplateError(f"unknown tone {tone!r} — one of {list(TONES)}")
        return await self.list(tone=tone)

    # ── writes: the platform console ──────────────────────────────────────────────────────────
    async def upsert(self, t: dict[str, Any]) -> dict[str, Any]:
        name = (t.get("name") or "").strip()
        if not name:
            raise TemplateError("a template needs a name — it is what Meta keys on")
        cls = t.get("class", "")
        if cls not in CLASSES:
            raise TemplateError(f"class must be one of {list(CLASSES)}, got {cls!r}")
        cat = (t.get("category") or "").upper()
        if cat not in CATEGORIES:
            raise TemplateError(f"category must be one of {list(CATEGORIES)}, got {cat!r}")
        body = (t.get("body") or "").strip()
        if not body:
            raise TemplateError("a template with no body cannot be submitted")

        variables = _variables(body)
        # META REFUSES A GAP in the numbering, and the rejection arrives days later blaming the
        # wording. Two templates in our own library opened at {{2}} and would have been rejected
        # at submission — caught by counting, not by reading. So it is checked here, at the point
        # anybody can introduce it.
        if variables and variables != list(range(1, len(variables) + 1)):
            raise TemplateError(
                f"variables must be numbered from 1 with no gap — {name} uses {variables}. "
                f"Meta refuses this at submission and blames the wording.")

        # THE LINE THAT MAKES THE CLASS HONEST (spec §8.4.1). A warning template carrying a
        # price, a discount or an invitation to visit is an advertisement by its text whatever we
        # label it — and we can guarantee it because we author it, not because we police it.
        # Policing fails at volume; authoring does not.
        if cls == "warning" and cat != "UTILITY":
            raise TemplateError(f"{cls} must be UTILITY — if it needs MARKETING it is not {cls}")
        if cls == "warning" and _looks_promotional(body):
            raise TemplateError(
                f"this {cls} template reads as promotional (a price, a discount, or an invitation "
                f"to visit). That makes it advertising by its text, not by its label — file it as "
                f"marketing or remove the offer.")

        # WHO FILLS EACH VARIABLE — and the one-blank-page rule.
        #
        # The count of variables was never the problem. Who TYPES them is. `system` comes from the
        # record we already hold (the name, the establishment, a date, an amount, a points
        # balance); `catalogue` is a tap on a list the owner already maintains; `owner` is a blank
        # page, and it is the only one that costs them anything.
        #
        # AT MOST ONE OWNER FIELD PER TEMPLATE. A template with two is a form, and a form is what
        # makes an owner stop sending — they abandon it halfway and the customer never comes back.
        # It is checked here rather than written in a document, because a rule nobody enforces is
        # re-broken by the next person who adds a template in a hurry.
        fills = list(t.get("fills") or [])
        if fills:
            unknown = [f for f in fills if f not in FILLS]
            if unknown:
                raise TemplateError(f"unknown fill source {unknown[0]!r} — one of {list(FILLS)}")
            if len(fills) != len(variables):
                raise TemplateError(
                    f"{name} declares {len(fills)} fill sources for {len(variables)} variables; "
                    f"a mismatch means the console asks for the wrong field")
            if fills.count("owner") > 1:
                raise TemplateError(
                    f"{name} asks the owner to write {fills.count('owner')} fields. One at most — "
                    f"anything more is a form, and an owner who abandons a form sends nothing.")

        model = t.get("model", "both")
        if model not in MODELS:
            raise TemplateError(f"model must be one of {list(MODELS)}, got {model!r}")

        shape = t.get("shape", "plain")
        if shape not in SHAPES:
            raise TemplateError(f"shape must be one of {list(SHAPES)}, got {shape!r}")
        if shape == "photo_button" and not t.get("media_header"):
            raise TemplateError(
                f"{name}: shape 'photo_button' needs a media_header — Meta refuses a HEADER "
                f"component with no example to review")

        row = {
            "id": name, "tenant": PLATFORM, "name": name,
            "model": model, "model_why": t.get("model_why", ""),
            "type": t.get("type", name.rsplit("_", 1)[0]),
            "tone": t.get("tone", ""), "label": t.get("label", ""),
            "class": cls, "category": cat, "language": t.get("language", "ar"),
            "body": body, "header": t.get("header", ""), "button": t.get("button"),
            # A FIXED LINE UNDER THE BODY, NO VARIABLES (2026-09-13) — Meta's own FOOTER
            # component (60 chars, plain text). Added for the five campaign-sent marketing
            # templates so a customer who wants a real date/time or scope not spelled out in the
            # body has somewhere to ask, without the body claiming a precision (a start date, a
            # send window) that not every campaign actually has.
            "footer": t.get("footer", ""),
            # FORWARDED VERBATIM TO REGISTRATION (library.py::register reads these exact keys) —
            # BUG FIXED HERE (2026-09-13, found while wiring the photo+button variant): this row
            # dict never carried `flow_button`/`carousel` at all, so every template the seed
            # declares one for (the booking Flow's own button, the carousel cards) registered with
            # Meta MISSING that component — `register()` skips a falsy `{}` silently, so nothing
            # ever raised. `media_header`/`flat_button`/`shape` are the new flat photo+button
            # variant's own fields, same "absent means none" posture.
            "flow_button": dict(t.get("flow_button") or {}),
            "carousel": dict(t.get("carousel") or {}),
            "shape": t.get("shape", "plain"),
            "media_header": dict(t.get("media_header") or {}),
            "flat_button": dict(t.get("flat_button") or {}),
            "variables": variables, "fills": fills,
            # WHAT TO DO WHEN IT CANNOT GO OUT NOW — quiet hours, or the day's ceiling.
            #
            # `reminders` has read this field since task 137 («a late confirmation is not late but
            # strange») and NOTHING ever wrote it: not the spec, not the seed, not this row. So
            # `str(t.get("deferral") or "defer")` resolved to «defer» for all 66, and a thank-you
            # for today's visit arrived the next morning — which is the one outcome that task was
            # written to prevent. A field a rule reads and nobody writes is not a conservative
            # default; it is the rule never running.
            #
            # `drop` belongs to the messages whose value expires with the moment they describe: a
            # visit confirmation, a redemption confirmation, a receipt. Everything else defers,
            # because a reminder or an offer is just as good an hour later.
            "deferral": t.get("deferral", "defer"),
            "active": bool(t.get("active", True)),
            "updated": int(time.time()),
        }
        await self._s.put(TEMPLATES, f"{PLATFORM}|{name}", row)
        return row

    async def deactivate(self, name: str) -> bool:
        """Deactivate, never delete — the same rule as coupons.

        Establishments already carry this template in their registry, and Meta holds an approved
        copy under this exact name. Deleting our row would leave both pointing at nothing we can
        explain.
        """
        row = await self.get(name)
        if row is None:
            return False
        row["active"] = False
        row["updated"] = int(time.time())
        await self._s.put(TEMPLATES, f"{PLATFORM}|{name}", row)
        return True

    # ── the one-time seed ─────────────────────────────────────────────────────────────────────
    async def seed_from_file(self, path: str) -> int:
        """Bring the library to what the file says — on EVERY boot, not once.

        THE DEFECT THIS REPLACES, AND IT KILLED THE WHOLE PRODUCT SILENTLY. This used to return
        early whenever the table was non-empty: `if await self.list(): return 0`. So the library
        written on the first boot was the library for ever, and no deploy could correct it.

        On the cluster that meant 78 rows written in one second on 2026-08-12 — an older file, from
        an older image — EVERY ONE OF THEM `active: False`. Every preview in «رسائلي» answered
        «تعذّر عرض نصّ هذه الرسالة», because a text that is not active is not offered; and the send
        path had nothing to pick either. Nothing failed anywhere. A shop with an inactive library is
        a shop that cannot send a single message, and eleven redeploys could not have fixed it.

        SO IT RECONCILES. Every template in the file is upserted — that repairs a wrong `active`, a
        reworded body, a changed category — and any PLATFORM row the file no longer names is
        deactivated rather than deleted (see `deactivate` for why: establishments carry the name and
        Meta holds an approved copy under it).

        IT TOUCHES ONLY OUR OWN ROWS. A shop's custom templates live under its own tenant and are
        never in this file; `list()` here is the platform library alone.
        """
        if not path:
            return 0
        p = Path(path)
        if not p.is_file():
            raise TemplateError(f"TEMPLATES_SEED_FILE points at {path!r}, which does not exist — "
                                f"the library would be empty and no establishment could send")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TemplateError(f"the template seed is not valid JSON: {exc}") from exc
        wanted = {str(row.get("name") or ""): row for row in data.get("templates", [])
                  if row.get("name")}
        n = 0
        for row in wanted.values():
            await self.upsert(row)
            n += 1

        # RETIRED, NOT DELETED. A template we stopped shipping is one an establishment may still
        # have registered with Meta under that exact name — deleting our row leaves both pointing
        # at something we cannot explain.
        for existing in await self.list():
            name = str(existing.get("name") or "")
            if name and name not in wanted and existing.get("active", True):
                await self.deactivate(name)
        return n


def _variables(body: str) -> list[int]:
    import re
    return sorted({int(x) for x in re.findall(r"\{\{(\d)\}\}", body)})


# Words that turn advice into advertising. Deliberately a small, blunt list rather than a clever
# one: it is a second pair of eyes on text WE write, not a filter on text a stranger submits. Its
# job is to catch the moment somebody edits a warning template in the console and slips an
# offer into it — the exact way this taxonomy would rot.
_PROMO_MARKERS = ("خصم", "عرض", "مجان", "ريال", "%", "احجز", "اطلب", "وفّر", "وفر")


def _looks_promotional(body: str) -> bool:
    return any(w in body for w in _PROMO_MARKERS)
