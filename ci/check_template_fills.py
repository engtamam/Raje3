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

FILLS = ("system", "catalogue", "owner", "amount", "code", "date")

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
# mentioned" but "is there a trigger that fires it", and that now has an answer: the registry.
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


def trigger_types() -> set[str]:
    """Every template type the trigger registry can fire.

    THE REGISTRY, NOT A GREP — it is the one place that answers "what makes a message go out",
    and it is the same answer the engine acts on.
    """
    src = (SERVICES / "reminders" / "app" / "core" / "triggers.py").read_text(encoding="utf-8")
    return set(re.findall(r'template_type="([a-z_]+)"', src))


def campaign_types() -> set[str]:
    """And the goals, which fire without a trigger row of their own."""
    src = (SERVICES / "campaigns" / "app" / "core" / "models.py").read_text(encoding="utf-8")
    return set(re.findall(r'\("([a-z_]+)",\s*"(?:marketing|awareness|service|personal)"\)', src))


def main() -> int:
    rows = json.loads(CURATED.read_text(encoding="utf-8"))["templates"]
    fired = trigger_types() | campaign_types()
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
        problems.append(f"{type_name}: no trigger and no goal fires it, and no reason is written "
                        f"down. It is submitted to Meta for every establishment and can reach "
                        f"nobody — wire it, delete it, or say here why it sleeps")

    for type_name in sorted(SLEEPING):
        if type_name not in by_type:
            problems.append(f"{type_name}: listed as sleeping and no longer in the library — "
                            f"delete the line, or the next reader trusts a note about nothing")

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
