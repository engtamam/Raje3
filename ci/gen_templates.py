#!/usr/bin/env python3
# =============================================================================
# gen_templates.py — validate the WhatsApp library against ITS OWN CURATED FIELDS.
#
# ONE FILE ON DISK (2026-09-13, deepened): `services/operations/data/templates.seed.json` is not
# only the file operations actually pushes into a tenant's registry when they connect — it is now
# also the only place the RULES below read from. There used to be a second source, a markdown
# specification (`docs/وصف-منصة-راجع.md`) that this module regex-parsed for the wording, the
# variable count, the «الفراغات» fills row and an 8.4.3 deferral table, and the curated seed
# carried its own copy of the same facts as structured fields. Two representations of one truth
# drift: the runtime library once held 23 types while the spec described 26 (three finished
# features — a weekly digest, a safety notice, a DSAR code — submitted for nobody, silently,
# because the send path correctly declines a template the account never had). The fix was not a
# sharper diff between the two — it was noticing there was only ever supposed to be ONE file, and
# the markdown was prose ABOUT the seed rather than a second copy of it.
#
# So every fact this module used to extract by regex — the body, the variable count, who fills
# each blank, the class, the header, the deferral policy — is read directly off the seed's own
# rows now. Nothing here decides the CONTENT of a template any more; it only decides whether the
# content already written is internally consistent, the same rules Meta would apply hours later
# against a name that is then burned.
#
# Run it after editing the seed:       python ci/gen_templates.py
# Print the parsed library as JSON:    python ci/gen_templates.py --emit
#
# THE CHECKS ARE THE POINT, not any file this produces. Each one is a rejection that would
# otherwise arrive from Meta hours later, against a template name that is then burned — a name
# cannot be reused with different content and cannot be changed after approval.
# =============================================================================
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "services" / "operations" / "data" / "templates.seed.json"

# Meta's category decides the PRICE and the odds of acceptance. Getting it wrong means they
# re-categorise and bill at the marketing rate. Kept here as the EXPECTED mapping so a curated row
# whose `category` disagrees with its own `class` is caught — the seed carries both fields
# separately, and nothing before this forced them to agree.
CATEGORY = {"service": "UTILITY", "personal": "UTILITY",
            "warning": "UTILITY", "marketing": "MARKETING"}
TONES = ("masculine", "feminine")

# WHO FILLS EACH BLANK, IN ORDER. Meta approves the WORDS, so the numbered blanks are the only
# thing a shop decides, and every one of them belongs to somebody: to us at send time («system»),
# to a tap on his own service list («catalogue»), to a typed value with a shape («amount», «code»,
# «date»), or to him («owner» — the one free blank, at most one per template).
FILLS = ("system", "catalogue", "owner", "amount", "date", "invite", "stop_link",
         # THE RATING APP'S OWN CLAUSE (rating-app-feature.md) — a whole sentence computed
         # server-side (points-participation line, or a neutral one when no points are configured),
         # never a template-level condition. Same discipline as «invite»: WhatsApp refuses an
         # empty variable, so this is always a full sentence, never blank.
         "rating_cta",
         # THE ONE OWNER-ONLY NAME SLOT (per_weekly_digest) — never the customer this vocabulary
         # otherwise assumes at slot 1. See services/reminders' rendering.py::campaign_slots.
         "establishment")
FREE = "owner"

# THE LAST BLANK OF EVERY TEMPLATE, AND IT IS NOT A STYLE RULE.
#
# Marketing is opt-IN: without a grant no promotional message may lawfully leave. And a grant needs
# somewhere to be given — a screen the customer can reach from a message he already trusts. So the
# address lives in the BODY, where we control it end to end:
#
#   invite      utility classes. Resolves to the grant screen for somebody who has not agreed,
#               and to a plain line with no link for somebody who has. Never both.
#   stop_link   marketing only, and mandatory (§8.3 of the retired spec): one tap to stop, in
#               every promotional message, with no exception any establishment can switch off.
#
# AND THE INVITE STAYS QUIET ON PURPOSE. A utility template whose text sells is re-categorised by
# Meta as MARKETING — a higher price per message and a service message that suddenly needs consent
# to send. That is what SELLING_WORDS below already guards for the warning class; the invitation
# obeys the same rule by carrying no price, no discount and no offer.
LAST_FILL = {"marketing": "stop_link"}
LAST_FILL_DEFAULT = "invite"

# A warning template carrying any of these is not a warning — it is marketing by its text, whatever
# it is labelled. Meta re-categorises it and bills accordingly, and the establishment is then
# sending promotion under a utility consent.
SELLING_WORDS = ("خصم", "عرض", "ريال", "مجاناً", "مجانا", "اشترِ", "اشتري", "احجز", "زُرنا",
                 "زرنا", "سعر", "تخفيض")

DEFERRALS = ("drop", "defer", "priority")

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def _rows() -> list[dict]:
    return json.loads(SEED.read_text(encoding="utf-8")).get("templates") or []


def parse() -> tuple[list[dict], list[str]]:
    """Every curated row, checked against itself, then grouped into one entry per template TYPE.

    THE GROUPING EXISTS FOR `build()`'S CONSUMERS, not for the checks below — those run against
    every row on its own, carousel variants and sleeping ones included, because Meta applies its
    rules to whatever is actually submitted, active or not. The grouped `types` list keeps the
    shape the manual seeder (`deploy/seed/seed-templates.sh --emit`) and `check_meta_rules.py`'s
    own re-expansion already expect: the FLAT (non-carousel) body per tone, since a carousel
    variant is a SHAPE a goal may take rather than a second wording to submit through this path.
    """
    rows = _rows()
    problems: list[str] = []

    # ── every row, checked against its own fields ───────────────────────────────────────────────
    for r in rows:
        name = r.get("name", "?")
        cls = r.get("class", "")
        body = r.get("body", "")
        variables = list(r.get("variables") or [])
        fills = list(r.get("fills") or [])

        # ── the gaps Meta rejects, found here instead of hours later ───────────────────────────
        if variables and variables != list(range(1, len(variables) + 1)):
            problems.append(f"{name}: variables {variables} have a gap — Meta numbers them and "
                            f"rejects the submission, hours later, against a burned name")

        # ── the category that has to be true rather than declared ──────────────────────────────
        expected_category = CATEGORY.get(cls)
        if expected_category and r.get("category") != expected_category:
            problems.append(f"{name}: class {cls!r} implies category {expected_category!r}, the "
                            f"row says {r.get('category')!r} — Meta bills and reviews by the "
                            f"category actually submitted, not by the class we call it")

        # A warning template's header is a bold word above the message that earns its purpose —
        # that he reads it — without spending a line of the body. Nothing else gets one.
        expected_header = "تنبيه" if cls == "warning" else ""
        if r.get("header", "") != expected_header:
            problems.append(f"{name}: header is {r.get('header')!r}, expected {expected_header!r} "
                            f"for a {cls!r} template")

        if cls == "warning":
            hit = [w for w in SELLING_WORDS if w in body]
            if hit:
                problems.append(f"{name}: contains {hit} — a warning template with a price or an "
                                f"invitation is MARKETING by its text, and Meta will re-categorise "
                                f"and bill it as such")

        # ── who fills each of those blanks ──────────────────────────────────────────────────────
        if variables and not fills:
            problems.append(f"{name}: no fills declared for {len(variables)} blank(s) — every one "
                            f"defaults to «system» then, so anything the shop types reaches no "
                            f"slot and the preview draws «…»")
        elif len(fills) != len(variables):
            problems.append(f"{name}: {len(variables)} blanks in the body, {len(fills)} fills "
                            f"declared — the list is read BY POSITION, so one missing entry shifts "
                            f"every blank after it onto the wrong source")
        else:
            unknown = [f for f in fills if f not in FILLS]
            if unknown:
                problems.append(f"{name}: unknown filler {unknown} — the readers branch on these "
                                f"by name and treat anything else as «system». Use one of {FILLS}")
            # AN OWNER-ONLY TEMPLATE OWES NO CUSTOMER-FACING ADDRESS. `establishment` fills slot 1
            # of `per_weekly_digest` alone (reasons.py: "تقريرك أنت، لا رسالة لعميلك" — your own
            # report, never a message to your customer) — there is no customer on the other end to
            # invite into marketing consent, so the invite/stop_link rule below does not apply to
            # it. Named by the fill that marks an owner-only template, not by the template's own
            # name, so a future owner-only text is exempt for the same reason without a second edit
            # here.
            elif fills and "establishment" not in fills:
                # ── the address every message has to carry, and exactly one of them ────────────
                wanted = LAST_FILL.get(cls, LAST_FILL_DEFAULT)
                if fills[-1] != wanted:
                    problems.append(
                        f"{name}: last blank is «{fills[-1]}», must be «{wanted}» — a {cls} "
                        f"template ends with the one address it owes its reader. Marketing owes a "
                        f"one-tap stop; everything else owes the invitation that is the only way "
                        f"consent can ever be given. Without it the message is a dead end and the "
                        f"campaigns engine can never lawfully send.")
                stray = [f for f in fills[:-1] if f in ("invite", "stop_link")]
                if stray:
                    problems.append(
                        f"{name}: {stray} appears before the last blank — an address mid-sentence "
                        f"reads as a broken line on a phone, and two of them in one message is two "
                        f"calls to action competing for the same tap")
            if fills.count(FREE) > 1:
                problems.append(f"{name}: asks the owner to write {fills.count(FREE)} free blanks. "
                                f"One at most — two is a form he abandons halfway, and the customer "
                                f"never hears")

        # NO TEMPLATE WITHOUT A POLICY. When the day's WhatsApp ceiling is exhausted the engine has
        # to decide whether this message is worth sending tomorrow, and there is no safe default:
        # deferring a visit confirmation sends something strange, dropping a follow-up loses a
        # message that cost nothing to delay. So whoever curated the row answers the question — as
        # a field ON the row now, not a lookup into a separate table that could omit one silently.
        deferral = r.get("deferral")
        if deferral not in DEFERRALS:
            problems.append(f"{name}: deferral is {deferral!r}, must be one of {DEFERRALS} — when "
                            f"the ceiling runs out, is this message still worth sending tomorrow? "
                            f"There is no default that is right for both a visit confirmation and "
                            f"an offer")

    # ── the tones of one template must agree on their blanks (ط-4/ح-1's own rule) ─────────────
    # Grouped by (type, is-a-carousel-variant): a carousel row is a different SHAPE of the same
    # goal, not a second tone of the same message, so it is compared only against ITS OWN
    # carousel siblings — exactly the distinction check_template_fills.py already draws.
    siblings: dict[tuple[str, bool], list[dict]] = {}
    for r in rows:
        siblings.setdefault((r.get("type", ""), bool(r.get("carousel"))), []).append(r)
    for (type_name, is_carousel), group in siblings.items():
        var_sets = {tuple(g.get("variables") or []) for g in group}
        if len(var_sets) > 1:
            problems.append(f"{type_name}{' (carousel)' if is_carousel else ''}: the tones "
                            f"disagree on variables {var_sets} — the tone is a live switch, so "
                            f"changing it would leave a variable unfilled and Meta refuses an "
                            f"empty variable")
        fill_sets = {tuple(g.get("fills") or []) for g in group}
        if len(fill_sets) > 1:
            problems.append(f"{type_name}{' (carousel)' if is_carousel else ''}: the tones "
                            f"disagree on who fills each blank {fill_sets} — the tone is a switch "
                            f"the owner flips, not a different message")

    # ── one entry per type, for build()'s consumers ─────────────────────────────────────────────
    types: list[dict] = []
    seen: set[str] = set()
    for r in rows:
        type_name = r.get("type", "")
        if type_name in seen:
            continue
        seen.add(type_name)
        flat = [x for x in rows if x.get("type") == type_name and not x.get("carousel")]
        source = flat or [x for x in rows if x.get("type") == type_name]
        first = source[0]
        types.append({
            "name": type_name,
            "deferral": first.get("deferral"),
            "title": first.get("label", ""),
            "cls": first.get("class", ""),
            "category": first.get("category", ""),
            "header": first.get("header", ""),
            "tones": {x.get("tone", ""): x.get("body", "") for x in source},
            "fills": list(first.get("fills") or []),
        })

    return types, problems


def check_variables(lib_vars: dict) -> list[str]:
    """A NAME IS NOT AN EXAMPLE, and Meta's review is where that is discovered otherwise.

    We shipped the example values in the names field for a day — correct against a port with one
    list, wrong the moment it became two. Nothing failed loudly: the API accepted it, and the
    rejection would have arrived from a human reviewer hours later, against 72 names that cannot
    then be reused or renamed.
    """
    problems: list[str] = []
    names = [v["name"] for v in lib_vars.values()]
    if len(set(names)) != len(names):
        problems.append(f"variables: two parameters share a name {names} — a send substitutes by "
                        f"name, so the second would overwrite the first")
    for num, v in lib_vars.items():
        if v["name"] == v["example"]:
            problems.append(f"variable {num}: the example IS the name ({v['name']!r}) — Meta's "
                            f"review rejects placeholder-looking examples")
        if not v["example"].strip():
            problems.append(f"variable {num}: no example — Meta refuses a template whose text "
                            f"carries a placeholder with no example value")
        if re.fullmatch(r"[a-z_]+", v["name"]) is None:
            problems.append(f"variable {num}: name {v['name']!r} is not a plain identifier")

    return problems


def build(types: list[dict]) -> dict:
    return {
        "_comment": [
            "GENERATED by ci/gen_templates.py FROM services/operations/data/templates.seed.json.",
            "Do not hand-edit: this is a read-only view of the curated file, and a copy retyped",
            "by hand drifts from the seed that operations actually submits.",
            "",
            "AUTHORED ONCE, APPROVED PER ESTABLISHMENT (spec §6.6.1, retired). A template at Meta",
            "belongs to one WhatsApp Business Account and every shop has its own — which is the",
            "whole basis of the promise that messages arrive under the shop's name and not ours.",
            "So this file is submitted in full to every account that connects.",
            "",
            "ALL OF THEM, not the half of one tone. The tone is in the NAME and a name",
            "cannot change after approval, so submitting a single tone makes a later change a",
            "second review the owner waits through. Submitting all makes it a switch.",
        ],
        # THREE THINGS PER NUMBER, AND THE LAST TWO ARE NOT THE SAME THING.
        #
        # `name` is the parameter's NAME — the key a send substitutes by, whose ORDER maps it to a
        # position, because Meta fills by position and does not name anything.
        #
        # `example` is an example VALUE, and Meta REQUIRES one for every parameter at creation: a
        # component whose text contains a placeholder is refused without it.
        #
        # AND A NAME IS NOT A VALID EXAMPLE. Meta's review rejects placeholder-looking examples, so
        # sending "customer_name" where "محمد" belongs fails review rather than the API — hours
        # later, against a name that cannot then be reused or renamed.
        #
        # `means` is for us. It never leaves this file. This table is our own convention for the
        # POSITIONAL blanks (the ones no address slot claims), not a curated field — every row's
        # own `variable_examples` still overrides these for its actual submission.
        "variables": {
            "1": {"name": "customer_name", "example": "محمد",
                  "means": "the customer's name or its substitute — never empty; Meta rejects an "
                           "empty variable"},
            "2": {"name": "establishment", "example": "مغسلة النخيل",
                  "means": "the establishment's name — its identity, never ours"},
            "3": {"name": "service", "example": "قص شعر",
                  "means": "the service or the content"},
            "4": {"name": "detail", "example": "1234",
                  "means": "a second detail: a date, an amount, a transaction reference"},
            "5": {"name": "balance", "example": "40",
                  "means": "what is LEFT after the act — today the points balance that remains"},
        },
        "tones": list(TONES),
        "types": types,
    }


def main() -> int:
    if not SEED.exists():
        print(f"{C_R}  ✗ {SEED} is missing{C_N}")
        return 1
    types, problems = parse()
    problems += check_variables(build([])["variables"])

    for p in problems:
        print(f"{C_R}  ✗ {p}{C_N}")
    if problems:
        print(f"\n{C_R}  ✗ {len(problems)} problem(s) in the library{C_N}")
        return 1

    if "--emit" in sys.argv:
        # A caller that needs the library as JSON (the manual `seed-templates.sh`) asks for it
        # fresh on every run instead of reading a file that could be one edit behind the seed.
        payload = build(types)
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0

    # `--check` is still accepted (CI's own invocation) — this same validation pass, run for its
    # exit code.
    counts = Counter(t["cls"] for t in types)
    print(f"{C_G}  ✔ {len(types)} texts x {len(TONES)} tones = {len(types) * len(TONES)} "
          f"templates{C_N}")
    print(f"    {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
