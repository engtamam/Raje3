#!/usr/bin/env python3
# =============================================================================
# check_template_fills.py — WHO fills each blank, and does anything send this template at all.
#
# The sister check (check_template_libraries.py) compares the two libraries WORD for word. It
# cannot see any of the following, because all of them live in fields the spec has no opinion
# about — and every one of them was found by hand, late:
#
#   · a template nobody sends. Eleven of twenty-six types could be fired by nothing: a finished
#     text, submitted to Meta for every establishment, that no code path can reach. It costs a
#     review slot and reads, from the library screen, exactly like a working feature.
#   · a blank whose source is a lie. `fills` says `catalogue` and the caller passes free text;
#     nothing fails, and the customer receives whatever the owner typed inside a template Meta
#     approved on the strength of a service name.
#   · a promise with no end. A discount template with no `date` blank is a discount for ever, and
#     the shop honours it at the till months after it meant to stop.
#   · `active: false` across the whole file. `choose()` filters on it, so the library looks
#     complete and NOTHING sends — the failure is a Arabic sentence in a log, once per message.
#
#   · a class that two files disagree about. The send carries the CALLER'S word for what class a
#     message is — and that word decides consent, the quiet window and the monthly cap. A goal
#     filing a marketing text as `awareness` sends advertising under an exemption, and nothing
#     downstream can tell.
#
# Run:  python ci/check_template_fills.py
# =============================================================================
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURATED = ROOT / "services" / "operations" / "data" / "templates.seed.json"
SERVICES = ROOT / "services"

# `invite` and `stop_link` carry an ADDRESS rather than a word, and each is the last blank of
# its class: `stop_link` on marketing (the one-tap stop §8.3 makes mandatory), `invite` on
# everything else (the only door marketing consent can come through). See ci/gen_templates.py.
FILLS = ("system", "catalogue", "owner", "amount", "code", "date", "invite", "stop_link")

# A blank of this kind may only appear in a template of these classes. `amount` and `code` are an
# offer by their nature: a utility template carrying a discount is marketing by its text whatever
# it is labelled (§8.4.1), and Meta re-categorises it and bills accordingly.
CLASS_OF_FILL = {"amount": {"marketing"}, "code": {"marketing"}}

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


# ── the types that sleep on purpose, each with the reason and what would wake it ──────────────
#
# GREPPING THE SOURCE WAS NOT ENOUGH, and it was quietly wrong. A type named anywhere counted as
# reachable — so `svc_booking_confirmation`, which appeared only in a list of window exemptions,
# passed this check while nothing in the fleet could send it. The question is not "is this string
# mentioned" but "is there a reason that fires it", and that now has an answer: the registry.
#
# A LINE HERE IS A DECISION, not a silencer. Anything not fired and not listed is a text we pay
# Meta to review for every establishment and that no customer can ever receive.
SLEEPING = {
    "wrn_safety_notice":
        "بقرار (§8.4.1): تحذير السلامة لا يُطلَق ذاتياً — يُراجَع لكل حالة، والقالب معتمَد ونائم",
    "mkt_cross_sell": "ينتظر هدفاً: «خدمة مكمّلة» — المحرك يعرف الاقترانات ولا بطاقة تطلقها",
    "mkt_package": "ينتظر هدفاً: «باقة» — ولم نقرّر بعد كيف تُسعَّر الباقة داخل الحملة",
    "mkt_referral": "ينتظر هدفاً: «ترشيح صديق» — ويحتاج أثراً يربط الصديق بمن رشّحه",
    "mkt_seasonal": "ينتظر مُطلِقاً تقويمياً ومباعدةً بين المنشآت (§10.9): يومٌ وطني ترسل فيه كلها",
    "mkt_coupon": "جاهز وينتظر خيار «قسيمة» في شاشة الحملة — الرمز والمولّد مبنيان",
    "awr_seasonal_care": "ينتظر المُطلِق التقويمي نفسه الذي ينتظره mkt_seasonal",
    # The receipt needs a total and a transaction reference. A VISIT DOES NOT CARRY EITHER: the
    # price lives on the service in the catalogue, and nothing records what was actually charged
    # — a visit is «من جاء وماذا أخذ», not an invoice. Wiring it would mean recording money at the
    # counter, which is a decision about what this product is, not a missing call.
    "svc_receipt": "ينتظر مبلغاً: الزيارة تسجّل مَن جاء وماذا أخذ، ولا تسجّل ما دُفع",
}


def reason_types() -> set[str]:
    """Every template type the reason registry can fire.

    THE REGISTRY, NOT A GREP — it is the one place that answers "what makes a message go out",
    and it is the same answer the engine acts on.
    """
    src = (SERVICES / "reminders" / "app" / "core" / "reasons.py").read_text(encoding="utf-8")
    return set(re.findall(r'template_type="([a-z_]+)"', src))


def campaign_types() -> dict[str, str]:
    """And the goals, which fire without a reason row of their own — type → the class they claim.

    THE CLASS TRAVELS WITH THE SEND, and it decides consent, the quiet window and the monthly cap.
    A goal that files a marketing template as `awareness` would send advertising under an
    exemption; the library is the authority, and this is the only place the two are compared.
    """
    src = (SERVICES / "campaigns" / "app" / "core" / "models.py").read_text(encoding="utf-8")
    return dict(re.findall(r'\("([a-z_]+)",\s*"(marketing|awareness|service|personal)"\)', src))


def goal_template_types() -> dict[str, str]:
    """Each campaign goal and the template type it sends — the other half of `campaign_types()`."""
    src = (SERVICES / "campaigns" / "app" / "core" / "models.py").read_text(encoding="utf-8")
    block = re.search(r"GOAL_TEMPLATE = \{(.*?)\n\}", src, re.S)
    if not block:
        return {}
    return dict(re.findall(r'"([a-z_]+)":\s*\("([a-z_]+)"', block.group(1)))


def offer_goals() -> set[str]:
    """The goals whose card must show the value and end-date fields (`Launch.tsx`) — ح-7."""
    src = (SERVICES / "campaigns" / "app" / "core" / "models.py").read_text(encoding="utf-8")
    m = re.search(r"OFFER_GOALS = \(([^)]*)\)", src)
    if not m:
        return set()
    return set(re.findall(r'"([a-z_]+)"', m.group(1)))


def reason_classes() -> dict[str, str]:
    """Each reason's template type and the class IT claims — same comparison, other service."""
    src = (SERVICES / "reminders" / "app" / "core" / "reasons.py").read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for cls, template in re.findall(r'cls="([a-z]+)",\s*template_type="([a-z_]+)"', src):
        out[template] = cls
    return out


def digest_class() -> dict[str, str]:
    """The weekly digest's own claim, made a THIRD time in a THIRD service.

    `reasons.py` already says `per_weekly_digest` is `personal` (ح-4) — but the message is actually
    built and sent from `insights/core/digest.py`, which used to hardcode `"cls": "service"` right
    next to it and disagreed. Neither this check nor `check_template_libraries.py` looked at
    insights at all, so the disagreement shipped and every digest quietly spent the SERVICE
    class's daily cap and quiet-hours exemption on a report that is not one.
    """
    path = SERVICES / "insights" / "app" / "core" / "digest.py"
    src = path.read_text(encoding="utf-8")
    template = re.search(r'TEMPLATE = "([a-z_]+)"', src)
    cls = re.search(r'"cls":\s*"([a-z]+)"', src)
    if not template or not cls:
        return {}
    return {template.group(1): cls.group(1)}


def main() -> int:
    rows = json.loads(CURATED.read_text(encoding="utf-8"))["templates"]
    goals = campaign_types()
    claims = {**goals, **reason_classes(), **digest_class()}
    fired = reason_types() | set(goals)
    problems: list[str] = []
    warnings: list[str] = []

    by_type: dict[str, list[dict]] = {}
    for r in rows:
        by_type.setdefault(r["type"], []).append(r)

    for r in rows:
        name, fills = r["name"], list(r.get("fills") or [])
        numbers = sorted({int(n) for n in re.findall(r"\{\{(\d+)\}\}", r["body"])})

        unknown = [f for f in fills if f not in FILLS]
        if unknown:
            problems.append(f"{name}: unknown fill {unknown[0]!r} — one of {list(FILLS)}")
        if len(fills) != len(numbers):
            problems.append(f"{name}: {len(fills)} fill sources for {len(numbers)} blanks — the "
                            f"console then asks for the wrong field, or for one that is ignored")
        if fills.count("owner") > 1:
            problems.append(f"{name}: {fills.count('owner')} free-text blanks. One at most — more "
                            f"is a form, and an owner who abandons a form sends nothing")
        if not r.get("active", False):
            problems.append(f"{name}: active is false — choose() filters on it, so this template "
                            f"exists everywhere and sends nowhere")

        for fill, classes in CLASS_OF_FILL.items():
            if fill in fills and r["class"] not in classes:
                problems.append(f"{name}: a {fill!r} blank in a {r['class']!r} template — a "
                                f"discount makes it MARKETING by its text (§8.4.1), and Meta "
                                f"re-categorises and bills it as such")

        # A DISCOUNT NEEDS AN END. Not a style rule: the shop honours what the message says, and a
        # message that names no last day is honoured for ever.
        if "amount" in fills and "date" not in fills:
            problems.append(f"{name}: promises a discount and names no end date")

        # THE TONES OF ONE TYPE MUST AGREE ON THEIR BLANKS. The tone is a live switch: a shop that
        # changes it mid-campaign would otherwise leave a blank unfilled, which Meta refuses.
        if fills != list(by_type[r["type"]][0].get("fills") or []):
            problems.append(f"{name}: its blanks differ from the other tones of {r['type']} — the "
                            f"tone is a switch the owner flips, not a different message")

    for type_name in sorted(by_type):
        if type_name in fired:
            continue
        reason = SLEEPING.get(type_name)
        if reason:
            warnings.append(f"{type_name}: asleep on purpose — {reason}")
            continue
        problems.append(f"{type_name}: no reason and no goal fires it, and no reason is written "
                        f"down. It is submitted to Meta for every establishment and can reach "
                        f"nobody — wire it, delete it, or say here why it sleeps")

    # ── the class a caller CLAIMS must be the class the text IS ──────────────────────────────
    # It decides consent, the quiet window and the monthly cap. A goal filing a marketing text as
    # `awareness` would send advertising under an exemption, and nothing downstream would notice:
    # the send carries the caller's word for it. The library is the authority, and this is the
    # only place the two are ever compared.
    for type_name, claimed in sorted(claims.items()):
        rows_for = by_type.get(type_name)
        if not rows_for:
            problems.append(f"{type_name}: named by a reason or a goal and absent from the "
                            f"library — the send picks no template and refuses, once, per shop")
            continue
        actual = rows_for[0]["class"]
        if actual != claimed:
            problems.append(f"{type_name}: sent as {claimed!r} and written as {actual!r}. The "
                            f"class decides consent, the quiet window and the monthly cap — the "
                            f"two answers cannot differ by which file you read")

    for type_name in sorted(SLEEPING):
        if type_name not in by_type:
            problems.append(f"{type_name}: listed as sleeping and no longer in the library — "
                            f"delete the line, or the next reader trusts a note about nothing")

    # ── A GOAL'S CARD MUST ASK FOR WHAT ITS TEMPLATE NEEDS (ح-7) ──────────────────────────────
    # `Launch.tsx` draws the value and end-date fields only when the goal's card says
    # `offers=True` (derived from `OFFER_GOALS`) — and `preview.build` refuses a send whose
    # template declares `amount`/`date` fills with nothing in them. A goal left out of
    # `OFFER_GOALS` while its own template needs those fills is a goal the owner can select, fill
    # in as instructed, and watch refuse every single time, with no field on the screen to fix.
    offering = offer_goals()
    for goal, template_type in sorted(goal_template_types().items()):
        rows_for = by_type.get(template_type)
        if not rows_for:
            continue
        needs_offer_fields = any(f in ("amount", "date") for f in (rows_for[0].get("fills") or []))
        if needs_offer_fields and goal not in offering:
            problems.append(f"{goal}: its template {template_type!r} needs amount/date but "
                            f"OFFER_GOALS does not include {goal!r} — Launch.tsx never draws the "
                            f"fields and every send refuses")

    for w in warnings:
        print(f"{C_Y}  ! {w}{C_N}")
    for p in problems:
        print(f"{C_R}  ✗ {p}{C_N}")
    if problems:
        print(f"\n{C_R}  ✗ {len(problems)} problem(s) in the template library{C_N}")
        return 1
    print(f"{C_G}  ✔ {len(rows)} templates: every blank has a source, and every discount an end"
          f"{C_N}")
    if warnings:
        print(f"{C_Y}    {len(warnings)} type(s) nothing sends — see above{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
